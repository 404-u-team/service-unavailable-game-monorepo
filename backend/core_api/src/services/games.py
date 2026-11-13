from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from math import floor
from random import SystemRandom
from uuid import UUID

from src.api.game_schemas import (
    Action,
    BusinessPoint,
    CampaignView,
    CreateGame,
    DeploymentView,
    DraftReview,
    Economy,
    FeatureView,
    Forecast,
    GameView,
    IncidentView,
    Modification,
    Range,
    SaveSummary,
)
from src.repositories.games import GameRepository
from src.simulation.catalog import (
    CAMPAIGNS,
    COMPONENTS,
    FEATURES,
    OPERATIONS,
    SCENARIOS,
    SECONDS_PER_TICK,
)
from src.simulation.engine import evaluate
from src.simulation.models import Deployment, Game, Node, Topology
from src.simulation.progression import (
    add_event,
    advance,
    new_game,
    operating_rates,
    spend,
)
from src.simulation.topology import (
    RuleError,
    config,
    daily_cost,
    deployment_warnings,
    diff,
    inspect_graph,
    install_cost,
    topology_cost,
)

MAX_OFFLINE_STEPS = 288
Mutation = Callable[[Game], None]


class RevisionConflict(RuleError):
    pass


class GameService:
    def __init__(self, repository: GameRepository) -> None:
        self.repository = repository

    async def list(self, owner: str) -> list[SaveSummary]:
        return [
            SaveSummary.model_validate(dict(row) | {"audience": round(row["audience"])})
            for row in await self.repository.list(owner)
        ]

    async def create(self, owner: str, request: CreateGame) -> GameView:
        if not SCENARIOS[request.scenario]["available"]:
            raise RuleError("This scenario is unavailable.")
        seed = (
            request.seed
            if request.seed is not None
            else SystemRandom().randrange(2**32)
        )
        game = new_game(
            request.id, request.name, seed, request.scenario, request.difficulty
        )
        game.settings = request.settings
        await self.repository.create(owner, game)
        return await self.read(owner, request.id, view)

    async def read[T](
        self, owner: str, game_id: UUID, project: Callable[[Game, datetime], T]
    ) -> T:
        async with self.repository.lock(owner, game_id) as (connection, row):
            game = self.repository.restore(row)
            now = max(datetime.now(UTC), row["clock_at"])
            anchor, ticks = advance_clock(game, row["clock_at"], now)
            saved_at = row["saved_at"]
            if ticks:
                saved_at = now
                await self.repository.save(connection, owner, game, anchor, saved_at)
            return project(game, saved_at)

    async def mutate(
        self, owner: str, game_id: UUID, request: Action, scope: str, change: Mutation
    ) -> GameView:
        async with self.repository.lock(owner, game_id) as (connection, row):
            game = self.repository.restore(row)
            now = max(datetime.now(UTC), row["clock_at"])
            speed = game.speed
            anchor, ticks = advance_clock(game, row["clock_at"], now)
            fingerprint = scope + request.model_dump_json(exclude={"request_id"})
            try:
                fresh = await self.repository.record_action(
                    connection, owner, game_id, request.request_id, fingerprint
                )
            except ValueError as error:
                raise RevisionConflict(str(error)) from error
            if fresh:
                change(game)
                if speed != game.speed:
                    remainder = (
                        (now - anchor).total_seconds() * speed / SECONDS_PER_TICK
                    )
                    if speed:
                        game.clock_fraction = min(remainder, 0.999999)
                    if game.speed:
                        anchor = now - timedelta(
                            seconds=game.clock_fraction * SECONDS_PER_TICK / game.speed
                        )
                        game.clock_fraction = 0
                    else:
                        anchor = now
            saved_at = now if fresh or ticks else row["saved_at"]
            if fresh or ticks:
                await self.repository.save(connection, owner, game, anchor, saved_at)
            return view(game, saved_at)


def advance_clock(game: Game, anchor: datetime, now: datetime) -> tuple[datetime, int]:
    if not game.speed:
        return now, 0
    period = SECONDS_PER_TICK / game.speed
    elapsed = (now - anchor).total_seconds()
    whole = floor(elapsed / period)
    steps = min(MAX_OFFLINE_STEPS, whole)
    if steps:
        advance(game, steps)
    return anchor + timedelta(seconds=whole * period), steps


def check_revision(game: Game, revision: int) -> None:
    if game.revision != revision:
        raise RevisionConflict(
            "The architecture changed in another session. Reload the latest draft and retry."
        )


def open_draft(game: Game, revision: int) -> None:
    check_revision(game, revision)
    if game.draft is not None:
        raise RuleError("A draft already exists.")
    game.draft = game.production.model_copy(deep=True)
    game.revision += 1


def discard_draft(game: Game, revision: int) -> None:
    check_revision(game, revision)
    game.draft = None
    game.revision += 1


def edit_draft(game: Game, revision: int, topology: Topology) -> None:
    check_revision(game, revision)
    if game.draft is None:
        raise RuleError("Create a draft first.")
    graph = inspect_graph(topology)
    validate_identity(game.production, graph.nodes)
    game.draft = topology
    game.revision += 1
    if game.tutorial == 1 and diff(game.production, topology)["modified"]:
        game.tutorial = 2


def validate_identity(production: Topology, nodes: dict[str, Node]) -> None:
    for node in production.nodes:
        if node.id in nodes and nodes[node.id].kind != node.kind:
            raise RuleError(
                f"Remove {node.name} and add a new component to change its type."
            )


def forecast(
    game: Game, topology: Topology, campaign_id: str | None = None
) -> Forecast:
    telemetry = evaluate(game).snapshot
    coverage = len(telemetry.components)
    uncertainty, confidence = (
        (0.08, "high")
        if telemetry.monitored and coverage >= 2
        else ((0.15, "medium") if coverage else (0.26, "low"))
    )
    assumed = game.model_copy(deep=True)
    assumed.incidents = []
    audience = game.audience
    boost = 0.0
    if campaign_id:
        campaign = CAMPAIGNS[campaign_id]
        audience += campaign["audience"] * 0.8
        boost = campaign["spike"] * 0.85
        assumed.tick += int(campaign["duration"] * 0.65)
    low = evaluate(
        assumed, topology, audience=audience * (1 - uncertainty), boost=boost
    ).snapshot.metrics
    high = evaluate(
        assumed, topology, audience=audience * (1 + uncertainty), boost=boost
    ).snapshot.metrics

    def span(first: float, second: float) -> Range:
        return Range(low=min(first, second), high=max(first, second))

    return Forecast(
        rps=span(low.rps, high.rps),
        latency=span(low.latency, high.latency),
        availability=span(low.availability, high.availability),
        audience=span(audience * (1 - uncertainty), audience * (1 + uncertainty)),
        confidence=confidence,
    )


def review(game: Game, revision: int, topology: Topology | None = None) -> DraftReview:
    check_revision(game, revision)
    candidate = topology if topology is not None else game.draft
    if candidate is None:
        raise RuleError("Create a draft first.")
    errors = []
    warnings = []
    changes = {}
    details = []
    estimate = None
    install = 0.0
    daily_after = topology_cost(game.production)
    try:
        graph = inspect_graph(candidate)
        validate_identity(game.production, graph.nodes)
        daily_after = topology_cost(candidate)
        changes = diff(game.production, candidate)
        details = modifications(game.production, candidate)
        install = install_cost(game.production, candidate)
        warnings = deployment_warnings(graph)
        if game.speed and changes["disconnected"]:
            warnings.append(
                "Live routing changes can cause a brief interruption while traffic shifts."
            )
        estimate = forecast(game, candidate)
        if estimate.availability.low < 0.95:
            warnings.append("Some projected load exceeds the draft's service capacity.")
        if install > game.balance:
            errors.append("The game balance cannot cover the deployment cost.")
    except RuleError as error:
        errors.append(str(error))
    return DraftReview(
        revision=revision,
        errors=errors,
        warnings=warnings,
        changes=changes,
        details=details,
        daily_before=topology_cost(game.production),
        daily_after=daily_after,
        install=install,
        forecast=estimate,
    )


def modifications(before: Topology, after: Topology) -> list[Modification]:
    old = {node.id: node for node in before.nodes}
    records = []
    for node in after.nodes:
        previous = old.get(node.id)
        if previous is None:
            continue
        old_config, new_config = config(previous), config(node)
        fields = COMPONENTS[node.kind]["fields"]
        for key, value in new_config.items():
            prior = old_config[key]
            if prior != value:
                records.append(
                    Modification(
                        component=node.name,
                        field=fields[key]["label"],
                        before=prior,
                        after=value,
                    )
                )
        if node.name != previous.name:
            records.append(
                Modification(
                    component=node.name,
                    field="Name",
                    before=previous.name,
                    after=node.name,
                )
            )
    return records


def deploy(
    game: Game, revision: int, request_id: UUID, rollback: UUID | None = None
) -> None:
    candidate = game.draft
    if rollback:
        if candidate is not None:
            raise RuleError("Discard the current draft before rolling back.")
        entry = next(
            (entry for entry in game.deployments if entry.id == rollback), None
        )
        if entry is None:
            raise RuleError("That deployment is outside the rollback history.")
        candidate = entry.topology
    result = review(game, revision, candidate)
    if result.errors:
        raise RuleError(result.errors[0])
    if not any(result.changes.values()):
        raise RuleError("There are no architecture changes to deploy.")
    spend(game, result.install, "deployment_spend")
    count = sum(len(items) for key, items in result.changes.items() if key != "moved")
    summary = (
        "Rollback"
        if rollback
        else f"Deployed {count} infrastructure changes"
        if count
        else "Updated canvas layout"
    )
    game.deployments.append(
        Deployment(
            id=request_id,
            tick=game.tick,
            topology=game.production,
            cost=result.install,
            summary=summary,
        )
    )
    game.deployments = game.deployments[-20:]
    game.production = candidate
    game.draft = None
    game.revision += 1
    live = {node.id for node in game.production.nodes}
    game.queues = {key: value for key, value in game.queues.items() if key in live}
    game.storage = {key: value for key, value in game.storage.items() if key in live}
    for event in game.incidents:
        if event.resolution is None and event.target and event.target not in live:
            event.resolution = "Affected component removed in deployment"
            event.end = game.tick
    if result.changes.get("disconnected") and game.speed:
        add_event(
            game,
            "deploy",
            "Routing rollout",
            "Some requests may fail briefly while connections switch to the new topology.",
            "info",
            2,
            factor=0.96,
        )
    if game.tutorial == 2:
        game.tutorial = 3


def feature_state(game: Game, key: str) -> FeatureView:
    feature = FEATURES[key]
    if key in game.released:
        return FeatureView(id=key, state="released")
    operation = feature["operation"]
    base = SCENARIOS[game.scenario]["operations"]
    released = [
        FEATURES[key]["operation"]
        for key in game.released
        if FEATURES[key]["operation"]
    ]
    workload = sum(OPERATIONS[key]["rate"] for key in dict.fromkeys([*base, *released]))
    demand_change = OPERATIONS[operation]["rate"] / workload if operation else 0
    if key in game.development:
        remaining = max(0, game.development[key] - game.tick)
        graph = inspect_graph(game.production)
        active = {graph.nodes[node].kind for node in graph.reachable}
        requirements = [
            COMPONENTS[kind]["name"]
            for kind in feature["requires"]
            if kind not in active
        ]
        return FeatureView(
            id=key,
            state="developing" if remaining else "ready",
            remaining=remaining,
            requirements=requirements,
            demand_change=demand_change,
        )
    prereqs = [
        FEATURES[item]["name"]
        for item in feature["prereq"]
        if item not in game.released
    ]
    return FeatureView(
        id=key,
        state="locked" if prereqs else "available",
        requirements=prereqs,
        demand_change=demand_change,
    )


def change_feature(game: Game, key: str, action: str) -> None:
    state = feature_state(game, key)
    feature = FEATURES[key]
    if action == "develop" and state.state == "available":
        spend(game, feature["cost"], "development_spend")
        game.development[key] = game.tick + feature["duration"]
    elif action == "release" and state.state == "ready":
        if state.requirements:
            raise RuleError(
                f"Connect the required infrastructure: {', '.join(state.requirements)}."
            )
        game.released.append(key)
        del game.development[key]
        add_event(
            game,
            "release",
            f"{feature['name']} released",
            "A new feature is generating demand.",
            "info",
            0,
        )
    else:
        raise RuleError("This feature is not ready for that action.")


def start_campaign(game: Game, key: str) -> None:
    if key in game.campaigns:
        raise RuleError("That campaign is already running.")
    campaign = CAMPAIGNS[key]
    spend(game, campaign["cost"], "marketing_spend")
    game.campaigns[key] = game.tick
    add_event(
        game,
        f"campaign-{key}",
        campaign["name"],
        "Acquisition will increase request volume.",
        "info",
        0,
    )


def acknowledge_incident(game: Game, event_id: str) -> None:
    event = next((event for event in game.incidents if event.id == event_id), None)
    if event is None:
        raise RuleError("That event is outside this save’s incident history.")
    event.acknowledged = True


def view(game: Game, saved_at: datetime) -> GameView:
    snapshot = evaluate(game).snapshot
    appeal = sum(FEATURES[key]["appeal"] for key in game.released)
    daily_revenue, daily_operating = operating_rates(game, snapshot.metrics, appeal)
    costs = (
        game.operating
        + game.development_spend
        + game.marketing_spend
        + game.deployment_spend
    )
    history = game.history if snapshot.monitored else []
    return GameView(
        id=game.id,
        name=game.name,
        scenario=game.scenario,
        tick=game.tick,
        audience=round(game.audience),
        balance=game.balance,
        saved_at=saved_at,
        speed=game.speed,
        difficulty=game.difficulty,
        satisfaction=game.satisfaction,
        production=game.production,
        draft=game.draft,
        revision=game.revision,
        snapshot=snapshot,
        history=history,
        business_history=[
            BusinessPoint(tick=p.tick, audience=p.audience, balance=p.balance)
            for p in game.history
        ],
        economy=Economy(
            balance=game.balance,
            revenue=game.revenue,
            operating=game.operating,
            development=game.development_spend,
            marketing=game.marketing_spend,
            deployment=game.deployment_spend,
            profit=game.revenue - costs,
            daily_infrastructure=topology_cost(game.production),
            daily_revenue=daily_revenue,
            daily_operating=daily_operating,
            daily_profit=daily_revenue - daily_operating,
        ),
        component_costs={node.id: daily_cost(node) for node in game.production.nodes},
        draft_costs={node.id: daily_cost(node) for node in game.draft.nodes}
        if game.draft
        else {},
        features=[feature_state(game, key) for key in FEATURES],
        campaigns=[
            CampaignView(
                id=key,
                remaining=start + CAMPAIGNS[key]["duration"] - game.tick,
                progress=(game.tick - start) / CAMPAIGNS[key]["duration"],
            )
            for key, start in game.campaigns.items()
        ],
        incidents=[
            IncidentView(
                id=event.id,
                title=event.title,
                symptom=event.symptom,
                severity=event.severity,
                start=event.start,
                end=event.end,
                active=event.resolution is None,
                cause=event.kind if event.target in snapshot.components else None,
                target=event.target if event.target in snapshot.components else None,
                resolution=event.resolution,
                failed_requests=round(event.failed_requests),
                acknowledged=event.acknowledged,
            )
            for event in reversed(game.incidents)
        ],
        deployments=[
            DeploymentView(id=e.id, tick=e.tick, summary=e.summary, cost=e.cost)
            for e in reversed(game.deployments)
        ],
        settings=game.settings,
        tutorial=game.tutorial,
        peak=max(
            (point.metrics for point in history),
            key=lambda metrics: metrics.rps,
            default=None,
        ),
    )
