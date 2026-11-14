from asyncio import timeout, to_thread
from datetime import UTC, datetime, timedelta
from json import dumps
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import jwt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)

from src.api.game_schemas import (
    Action,
    CampaignAction,
    CampaignId,
    Catalog,
    ClockAction,
    CreateGame,
    DraftReview,
    DraftReviewRequest,
    Economy,
    FeatureAction,
    FeatureId,
    Forecast,
    GameView,
    IncidentView,
    MarketAction,
    OnboardingAction,
    PatchDiagram,
    ProductAction,
    SavePreview,
    SaveSummary,
    SettingsAction,
    TutorialAction,
    TutorialProgressAction,
    UpdateDiagram,
    UpdateDraft,
    VersionedAction,
)
from src.api.routers.dependencies import get_connection_pool
from src.config import settings
from src.repositories.games import GameRepository, SaveNotFound
from src.services.games import (
    GameService,
    Mutation,
    RevisionConflict,
    acknowledge_incident,
    change_feature,
    change_onboarding,
    change_product,
    deploy,
    discard_draft,
    edit_draft,
    forecast,
    open_draft,
    patch_diagram,
    review,
    start_campaign,
    view,
)
from src.services.live import live_frame
from src.services.markets import (
    campaign_plan,
    develop_language,
    market_action,
    targeted_campaign,
)
from src.services.save_files import (
    MAX_SAVE_BYTES,
    SaveFileV1,
    export_file,
    parse_save_file,
)
from src.simulation.catalog import (
    ALLOWED,
    BUSINESS,
    CAMPAIGNS,
    COMPONENTS,
    CONNECTIONS,
    DAYS_PER_MONTH,
    DIFFICULTIES,
    FEATURES,
    MINUTES_PER_TICK,
    OPERATIONS,
    SCENARIOS,
)
from src.simulation.engine import evaluate
from src.simulation.models import Game, Snapshot, Topology
from src.simulation.progression import drill
from src.simulation.topology import RuleError

router = APIRouter(prefix="/games", tags=["games"])
COOKIE = "su_workbench"


def token_subject(token: str | None, kind: str) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
        return str(UUID(payload["sub"])) if payload["type"] == kind else None
    except jwt.InvalidTokenError, ValueError:
        return None


def existing_owner(request: Request | WebSocket) -> str | None:
    account = token_subject(request.cookies.get("access_token"), "access")
    if account:
        return f"account:{account}"
    guest = token_subject(request.cookies.get(COOKIE), "game_guest")
    if guest:
        return f"guest:{guest}"
    return None


def owner(request: Request, response: Response) -> str:
    identity = existing_owner(request)
    if identity:
        return identity
    guest = str(uuid4())
    lifetime = timedelta(days=365)
    token = jwt.encode(
        {"sub": guest, "type": "game_guest", "exp": datetime.now(UTC) + lifetime},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.game_cookie_secure,
        samesite="strict",
    )
    return f"guest:{guest}"


def get_service(
    pool: Annotated[asyncpg.Pool, Depends(get_connection_pool)],
) -> GameService:
    return GameService(GameRepository(pool))


Owner = Annotated[str, Depends(owner)]
Service = Annotated[GameService, Depends(get_service)]


def game_errors(error: Exception) -> HTTPException:
    if isinstance(error, SaveNotFound):
        return HTTPException(
            404, "Save not found.", headers={"X-Game-Error-Code": "save_not_found"}
        )
    if isinstance(error, RuleError):
        return HTTPException(
            409 if isinstance(error, RevisionConflict) else 422,
            str(error),
            headers={
                "X-Game-Error-Code": error.code,
                "X-Game-Error-Values": dumps(error.values),
            },
        )
    raise error


@router.get("/catalog", response_model=Catalog)
def catalog():
    return {
        "components": {
            kind: {**definition, "daily": definition["monthly"] / DAYS_PER_MONTH}
            for kind, definition in COMPONENTS.items()
        },
        "difficulties": DIFFICULTIES,
        "features": FEATURES,
        "campaigns": CAMPAIGNS,
        "scenarios": {
            key: {field: item[field] for field in ("name", "available", "description")}
            for key, item in SCENARIOS.items()
        },
        "connections": {key: sorted(targets) for key, targets in ALLOWED.items()},
        "connection_types": CONNECTIONS,
        "operations": {key: op["label"] for key, op in OPERATIONS.items()},
        "minutes_per_tick": MINUTES_PER_TICK,
        "days_per_month": DAYS_PER_MONTH,
        "premium_price_min": BUSINESS["premium_min_price"],
        "premium_price_max": BUSINESS["premium_max_price"],
    }


@router.get("", response_model=list[SaveSummary])
async def list_games(owner_id: Owner, service: Service):
    return await service.list(owner_id)


@router.post("", response_model=GameView, status_code=201)
async def create_game(body: CreateGame, owner_id: Owner, service: Service):
    try:
        return await service.create(owner_id, body)
    except RuleError as error:
        raise game_errors(error) from error


async def read_save_upload(request: Request) -> SaveFileV1:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_SAVE_BYTES:
            raise HTTPException(
                413,
                "The save file is larger than 8 MB.",
                headers={"X-Game-Error-Code": "save_file_too_large"},
            )
        body.extend(chunk)
    try:
        return await to_thread(parse_save_file, body)
    except RuleError as error:
        raise game_errors(error) from error


@router.post("/import/preview", response_model=SavePreview)
async def preview_import(request: Request):
    return (await read_save_upload(request)).preview()


@router.post("/import", response_model=SaveSummary, status_code=201)
async def import_save(request: Request, owner_id: Owner, service: Service):
    save = await read_save_upload(request)
    return await service.import_game(owner_id, save.game)


@router.get("/{game_id}/export")
async def export_save(game_id: UUID, owner_id: Owner, service: Service):
    try:
        filename, save = await service.read(
            owner_id, game_id, lambda game, _: export_file(game), capture_clock=True
        )
    except SaveNotFound as error:
        raise game_errors(error) from error
    return Response(
        save.model_dump_json(),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{game_id}", response_model=GameView)
async def get_game(game_id: UUID, owner_id: Owner, service: Service):
    try:
        return await service.read(owner_id, game_id, view)
    except SaveNotFound as error:
        raise game_errors(error) from error


@router.websocket("/{game_id}/live")
async def game_live(socket: WebSocket, game_id: UUID, service: Service):
    origin = urlsplit(socket.headers.get("origin", ""))
    host = socket.headers.get("host", "").lower()
    owner_id = existing_owner(socket)
    if (
        not owner_id
        or origin.scheme not in {"http", "https"}
        or origin.netloc.lower() != host
    ):
        await socket.close(code=1008)
        return
    await socket.accept()
    previous = None
    version = None
    sequence = 0
    idle = 0
    try:
        while True:
            state = await service.read(
                owner_id,
                game_id,
                lambda game, saved_at, previous_version=version: (
                    view(game, saved_at) if saved_at != previous_version else None
                ),
            )
            if state is not None:
                sequence += 1
                frame, previous = live_frame(state, previous, sequence)
                await socket.send_json(frame)
                version = state.saved_at
                idle = 0
            elif idle >= 30:
                await socket.send_json({"type": "heartbeat"})
                idle = 0
            try:
                async with timeout(0.5):
                    event = await socket.receive()
            except TimeoutError:
                idle += 1
                continue
            if event["type"] == "websocket.disconnect":
                return
            await socket.close(code=1008)
            return
    except SaveNotFound:
        await socket.close(code=1008)
    except WebSocketDisconnect:
        return


@router.get("/{game_id}/architecture", response_model=Topology)
async def architecture(
    game_id: UUID,
    owner_id: Owner,
    service: Service,
    version: Literal["production", "draft"] = "production",
):
    def select(game: Game, _: datetime) -> Topology:
        if version == "draft":
            if game.draft is None:
                raise SaveNotFound
            return game.draft
        return game.production

    try:
        return await service.read(owner_id, game_id, select)
    except SaveNotFound as error:
        raise game_errors(error) from error


@router.get("/{game_id}/monitoring", response_model=Snapshot)
async def monitoring(game_id: UUID, owner_id: Owner, service: Service):
    try:
        return await service.read(
            owner_id, game_id, lambda game, _: evaluate(game, overview=True).snapshot
        )
    except SaveNotFound as error:
        raise game_errors(error) from error


@router.get("/{game_id}/finance", response_model=Economy)
async def finance(game_id: UUID, owner_id: Owner, service: Service):
    try:
        return (await service.read(owner_id, game_id, view)).economy
    except SaveNotFound as error:
        raise game_errors(error) from error


@router.get("/{game_id}/incidents", response_model=list[IncidentView])
async def incident_history(game_id: UUID, owner_id: Owner, service: Service):
    try:
        return (await service.read(owner_id, game_id, view)).incidents
    except SaveNotFound as error:
        raise game_errors(error) from error


async def mutate(
    service: GameService,
    owner_id: str,
    game_id: UUID,
    body: Action,
    scope: str,
    change: Mutation,
):
    try:
        return await service.mutate(owner_id, game_id, body, scope, change)
    except (SaveNotFound, RuleError) as error:
        raise game_errors(error) from error


@router.post("/{game_id}/save", response_model=GameView)
async def save_game(game_id: UUID, body: Action, owner_id: Owner, service: Service):
    return await mutate(service, owner_id, game_id, body, "save", lambda game: None)


@router.put("/{game_id}/clock", response_model=GameView)
async def clock(game_id: UUID, body: ClockAction, owner_id: Owner, service: Service):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "clock",
        lambda game: setattr(game, "speed", body.speed),
    )


@router.post("/{game_id}/draft", response_model=GameView)
async def create_draft(
    game_id: UUID, body: VersionedAction, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "open draft",
        lambda game: open_draft(game, body.revision),
    )


@router.put("/{game_id}/diagram", response_model=GameView)
async def update_diagram(
    game_id: UUID, body: UpdateDiagram, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "diagram",
        lambda game: setattr(
            game,
            "diagram",
            body.diagram.model_copy(
                update={"viewports": body.diagram.viewports or game.diagram.viewports}
            ),
        ),
    )


@router.patch("/{game_id}/diagram", response_model=GameView)
async def update_diagram_fields(
    game_id: UUID, body: PatchDiagram, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "patch diagram",
        lambda game: patch_diagram(game, body),
    )


@router.put("/{game_id}/draft", response_model=GameView)
async def update_draft(
    game_id: UUID, body: UpdateDraft, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "edit draft",
        lambda game: edit_draft(game, body.revision, body.topology),
    )


@router.post("/{game_id}/draft/discard", response_model=GameView)
async def remove_draft(
    game_id: UUID, body: VersionedAction, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "discard draft",
        lambda game: discard_draft(game, body.revision),
    )


@router.post("/{game_id}/draft/review", response_model=DraftReview)
async def review_draft(
    game_id: UUID, body: DraftReviewRequest, owner_id: Owner, service: Service
):
    try:
        return await service.read(
            owner_id,
            game_id,
            lambda game, _: review(game, body.revision, body.topology),
        )
    except (SaveNotFound, RuleError) as error:
        raise game_errors(error) from error


@router.post("/{game_id}/deployments", response_model=GameView)
async def deploy_draft(
    game_id: UUID, body: VersionedAction, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "deploy",
        lambda game: deploy(game, body.revision, body.request_id),
    )


@router.post("/{game_id}/deployments/{deployment_id}/rollback", response_model=GameView)
async def rollback(
    game_id: UUID,
    deployment_id: UUID,
    body: VersionedAction,
    owner_id: Owner,
    service: Service,
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        f"rollback:{deployment_id}",
        lambda game: deploy(game, body.revision, body.request_id, deployment_id),
    )


@router.post("/{game_id}/features/{feature_id}", response_model=GameView)
async def feature(
    game_id: UUID,
    feature_id: FeatureId,
    body: FeatureAction,
    owner_id: Owner,
    service: Service,
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        f"feature:{feature_id}",
        lambda game: change_feature(game, feature_id, body.action),
    )


@router.put("/{game_id}/product", response_model=GameView)
async def product(
    game_id: UUID, body: ProductAction, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "product",
        lambda game: change_product(game, body.product),
    )


@router.get("/{game_id}/campaigns/{campaign_id}/forecast", response_model=Forecast)
async def campaign_forecast(
    game_id: UUID,
    campaign_id: CampaignId,
    owner_id: Owner,
    service: Service,
    region: str | None = None,
    budget: Annotated[float | None, Query(ge=10, le=100_000)] = None,
    duration: Annotated[int | None, Query(ge=1, le=288)] = None,
):
    try:
        return await service.read(
            owner_id,
            game_id,
            lambda game, _: forecast(
                game,
                game.production,
                campaign_id,
                campaign_plan(game, campaign_id, region, budget, duration)
                if region
                else None,
            ),
        )
    except (SaveNotFound, RuleError) as error:
        raise game_errors(error) from error


@router.post("/{game_id}/campaigns/{campaign_id}", response_model=GameView)
async def campaign(
    game_id: UUID,
    campaign_id: CampaignId,
    body: CampaignAction,
    owner_id: Owner,
    service: Service,
):
    def start(game: Game) -> None:
        if body.region is None:
            start_campaign(game, campaign_id)
        else:
            plan = campaign_plan(
                game, campaign_id, body.region, body.budget, body.duration
            )
            targeted_campaign(game, campaign_id, plan)

    return await mutate(
        service, owner_id, game_id, body, f"campaign:{campaign_id}", start
    )


@router.post("/{game_id}/markets/{market_id}", response_model=GameView)
async def update_market(
    game_id: UUID, market_id: str, body: MarketAction, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        f"market:{market_id}",
        lambda game: market_action(game, market_id, body.action),
    )


@router.post("/{game_id}/languages/{name}", response_model=GameView)
async def update_language(
    game_id: UUID, name: str, body: Action, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        f"language:{name}",
        lambda game: develop_language(game, name),
    )


@router.post("/{game_id}/incidents/drill", response_model=GameView)
async def incident_drill(
    game_id: UUID, body: Action, owner_id: Owner, service: Service
):
    return await mutate(service, owner_id, game_id, body, "incident drill", drill)


@router.post("/{game_id}/incidents/{event_id}/acknowledge", response_model=GameView)
async def acknowledge(
    game_id: UUID, event_id: str, body: Action, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        f"acknowledge:{event_id}",
        lambda game: acknowledge_incident(game, event_id),
    )


@router.put("/{game_id}/settings", response_model=GameView)
async def update_settings(
    game_id: UUID, body: SettingsAction, owner_id: Owner, service: Service
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "settings",
        lambda game: setattr(game, "settings", body.settings),
    )


@router.post("/{game_id}/tutorial", response_model=GameView)
async def tutorial(
    game_id: UUID, body: TutorialAction, owner_id: Owner, service: Service
):
    def record(game: Game) -> None:
        if (game.tutorial, body.interaction) in {(0, "inspect"), (3, "monitor")}:
            game.tutorial += 1

    return await mutate(service, owner_id, game_id, body, "tutorial", record)


@router.post("/{game_id}/onboarding", response_model=GameView)
async def onboarding(
    game_id: UUID,
    body: OnboardingAction | TutorialProgressAction,
    owner_id: Owner,
    service: Service,
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        "onboarding",
        lambda game: change_onboarding(game, body),
    )
