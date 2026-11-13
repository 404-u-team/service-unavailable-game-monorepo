from datetime import UTC, datetime, timedelta
from json import dumps
from typing import Annotated, Literal
from uuid import UUID, uuid4

import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.api.game_schemas import (
    Action,
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
    SaveSummary,
    SettingsAction,
    TutorialAction,
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
    deploy,
    discard_draft,
    edit_draft,
    forecast,
    open_draft,
    review,
    start_campaign,
    view,
)
from src.simulation.catalog import (
    ALLOWED,
    CAMPAIGNS,
    COMPONENTS,
    CONNECTIONS,
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
    except (jwt.InvalidTokenError, ValueError):
        return None


def owner(request: Request, response: Response) -> str:
    account = token_subject(request.cookies.get("access_token"), "access")
    if account:
        return f"account:{account}"
    guest = token_subject(request.cookies.get(COOKIE), "game_guest")
    if guest:
        return f"guest:{guest}"
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
        return HTTPException(404, "Save not found.")
    if isinstance(error, RevisionConflict):
        return HTTPException(409, str(error))
    if isinstance(error, RuleError):
        return HTTPException(
            422,
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
        "components": COMPONENTS,
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


@router.get("/{game_id}", response_model=GameView)
async def get_game(game_id: UUID, owner_id: Owner, service: Service):
    try:
        return await service.read(owner_id, game_id, view)
    except SaveNotFound as error:
        raise game_errors(error) from error


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
            owner_id, game_id, lambda game, _: evaluate(game).snapshot
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
        lambda game: setattr(game, "diagram", body.diagram),
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


@router.get("/{game_id}/campaigns/{campaign_id}/forecast", response_model=Forecast)
async def campaign_forecast(
    game_id: UUID, campaign_id: CampaignId, owner_id: Owner, service: Service
):
    try:
        return await service.read(
            owner_id,
            game_id,
            lambda game, _: forecast(game, game.production, campaign_id),
        )
    except SaveNotFound as error:
        raise game_errors(error) from error


@router.post("/{game_id}/campaigns/{campaign_id}", response_model=GameView)
async def campaign(
    game_id: UUID,
    campaign_id: CampaignId,
    body: Action,
    owner_id: Owner,
    service: Service,
):
    return await mutate(
        service,
        owner_id,
        game_id,
        body,
        f"campaign:{campaign_id}",
        lambda game: start_campaign(game, campaign_id),
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
