from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from math import floor
from random import SystemRandom
from uuid import UUID, uuid4

from pydantic import ValidationError

from src.api.game_schemas import (
    Action,
    AdvertisingEstimate,
    BusinessPoint,
    CampaignPlan,
    CampaignView,
    CreateGame,
    DatabaseForecast,
    DeploymentView,
    DraftReview,
    Economy,
    FeatureView,
    FinancePoint,
    Forecast,
    GameView,
    IncidentView,
    Modification,
    OnboardingAction,
    PatchDiagram,
    Range,
    RequirementView,
    ResearchView,
    SaveSummary,
    TutorialProgressAction,
)
from src.repositories.games import GameRepository
from src.services.markets import campaign_state, languages, markets
from src.simulation.catalog import (
    ADVERTISING,
    BUSINESS,
    CAMPAIGNS,
    COMPONENTS,
    FEATURES,
    LEGACY_DATABASE_LIMITS,
    MINUTES_PER_TICK,
    OPERATIONS,
    SCENARIOS,
    SECONDS_PER_TICK,
    TICKS_PER_DAY,
)
from src.simulation.demand import (
    MINUTES_PER_DAY,
    acquire,
    ad_forecast,
    arrival_weight,
    premium_media_gain,
    product_settings,
    workload,
)
from src.simulation.engine import evaluate
from src.simulation.engineering import (
    RESEARCH,
    architecture_errors,
    effective_topology,
    migrated_storage,
    migration_plan,
    researched,
)
from src.simulation.models import (
    ArchitectureMigration,
    Deployment,
    DeploymentComparison,
    Diagram,
    Game,
    Incident,
    Node,
    Onboarding,
    OneTimeCosts,
    OperatingCosts,
    ProductSettings,
    ResourcePressure,
    RevenueSources,
    Snapshot,
    Topology,
)
from src.simulation.onboarding import (
    LEGACY_TUTORIAL_STEPS,
    TUTORIAL_STEPS,
    TutorialStep,
)
from src.simulation.progression import (
    add_event,
    advance,
    new_game,
    spend,
)
from src.simulation.requirements import REQUIREMENTS, requirement_met
from src.simulation.topology import (
    Graph,
    RuleError,
    config,
    daily_cost,
    deployment_warnings,
    diff,
    inspect_graph,
    install_cost,
    messenger_datasets,
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
            SaveSummary(
                id=row["id"],
                name=row["name"],
                scenario=row["scenario"],
                tick=row["tick"],
                day=(row["start_minute"] + row["tick"] * MINUTES_PER_TICK)
                // MINUTES_PER_DAY
                + 1,
                audience=round(row["audience"]),
                balance=row["balance"],
                saved_at=row["saved_at"],
            )
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
        self,
        owner: str,
        game_id: UUID,
        project: Callable[[Game, datetime], T],
        *,
        capture_clock: bool = False,
    ) -> T:
        async with self.repository.lock(owner, game_id) as (connection, row):
            game = self.repository.restore(row)
            now = max(datetime.now(UTC), row["clock_at"])
            anchor, ticks = advance_clock(game, row["clock_at"], now)
            saved_at = row["saved_at"]
            if ticks:
                saved_at = now
                await self.repository.save(connection, owner, game, anchor, saved_at)
            if capture_clock and game.speed:
                game.clock_fraction = min(
                    (now - anchor).total_seconds() * game.speed / SECONDS_PER_TICK,
                    0.999999,
                )
            return project(game, saved_at)

    async def import_game(self, owner: str, snapshot: Game) -> SaveSummary:
        game = snapshot.model_copy(update={"id": uuid4()})
        elapsed = (
            timedelta(seconds=game.clock_fraction * SECONDS_PER_TICK / game.speed)
            if game.speed
            else timedelta()
        )
        if game.speed:
            game.clock_fraction = 0
        saved_at = await self.repository.create(owner, game, elapsed)
        if saved_at is None:
            raise RuntimeError("Generated save ID already exists")
        return SaveSummary(
            id=game.id,
            name=game.name,
            scenario=game.scenario,
            tick=game.tick,
            day=(game.start_minute + game.tick * MINUTES_PER_TICK) // MINUTES_PER_DAY
            + 1,
            audience=round(game.audience),
            balance=game.balance,
            saved_at=saved_at,
        )

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
                raise RevisionConflict(
                    str(error), code="request_id_conflict"
                ) from error
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


def patch_diagram(game: Game, patch: PatchDiagram) -> None:
    diagram = game.diagram
    if (
        patch.groups is not None
        and patch.groups != diagram.groups
        and patch.group_base != diagram.groups
    ):
        raise RevisionConflict(
            "Diagram groups changed in another session. Reload the latest layout and retry.",
            code="diagram_conflict",
        )
    positions = diagram.positions | patch.positions
    routes = diagram.routes | patch.routes
    try:
        game.diagram = Diagram(
            positions={
                key: point for key, point in positions.items() if point is not None
            },
            routes={
                key: points for key, points in routes.items() if points is not None
            },
            groups=diagram.groups if patch.groups is None else patch.groups,
            viewports=diagram.viewports | patch.viewports,
        )
    except ValidationError as error:
        raise RuleError(
            "Some submitted values are invalid.", code="invalid_values"
        ) from error


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
            "The architecture changed in another session. Reload the latest draft and retry.",
            code="revision_conflict",
        )


def open_draft(game: Game, revision: int) -> None:
    check_revision(game, revision)
    if game.migration is not None:
        raise RuleError("Wait for the planned architecture migration to complete.")
    if game.draft is not None:
        raise RuleError("A draft already exists.")
    game.draft = game.production.model_copy(deep=True)
    game.revision += 1


def discard_draft(game: Game, revision: int) -> None:
    check_revision(game, revision)
    if game.migration is not None:
        raise RuleError("Wait for the planned architecture migration to complete.")
    game.draft = None
    game.revision += 1


def edit_draft(game: Game, revision: int, topology: Topology) -> None:
    check_revision(game, revision)
    if game.migration is not None:
        raise RuleError("Wait for the planned architecture migration to complete.")
    if game.draft is None:
        raise RuleError("Create a draft first.")
    graph = inspect_graph(topology)
    validate_identity(game.production, graph.nodes)
    errors = architecture_errors(game, graph, partial=True)
    if errors:
        raise RuleError(errors[0])
    game.draft = topology
    game.revision += 1
    modified = (
        diff(game.production, topology)["modified"]
        if game.tutorial == 1 or onboarding_progress(game).step == 6
        else []
    )
    if game.tutorial == 1 and modified:
        game.tutorial = 2
    if "api" in modified:
        advance_onboarding(game, 6)


def validate_identity(production: Topology, nodes: dict[str, Node]) -> None:
    for node in production.nodes:
        if node.id in nodes and nodes[node.id].kind != node.kind:
            raise RuleError(
                f"Remove {node.name} and add a new component to change its type."
            )


def forecast(
    game: Game,
    topology: Topology,
    campaign_id: str | None = None,
    plan: CampaignPlan | None = None,
    *,
    compare_databases: bool = False,
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
    if campaign_id and plan:
        control = assumed.model_copy(deep=True)
        assumed.regional_campaigns[campaign_id] = campaign_state(
            game, campaign_id, plan
        )
        peak_populations = {}
        best = -1.0
        baseline = 0.0
        for step in range(1, plan.duration + 1):
            assumed.tick = control.tick = game.tick + step
            for region, part in plan.allocations.items():
                acquire(
                    assumed, region, part.audience * arrival_weight(step, plan.duration)
                )
            peak = sum(workload(assumed).operations.values())
            baseline = max(baseline, sum(workload(control).operations.values()))
            if peak > best:
                best = peak
                plan.peak_tick = assumed.tick
                peak_populations = {**assumed.market_audience}
                peak_north_america = assumed.north_america_audience
                audience = assumed.audience
        plan.peak_rps = best
        plan.baseline_peak_rps = baseline
        assumed.tick = plan.peak_tick
        assumed.audience = audience
        assumed.market_audience = peak_populations
        assumed.north_america_audience = peak_north_america
    elif campaign_id:
        campaign = CAMPAIGNS[campaign_id]
        audience += campaign["audience"] * 0.8
        boost = campaign["spike"] * 0.85
        assumed.tick += int(campaign["duration"] * 0.65)
    low_snapshot = evaluate(
        assumed, topology, audience=audience * (1 - uncertainty), boost=boost
    ).snapshot
    high_snapshot = evaluate(
        assumed, topology, audience=audience * (1 + uncertainty), boost=boost
    ).snapshot
    low, high = low_snapshot.metrics, high_snapshot.metrics

    def span(first: float, second: float) -> Range:
        return Range(low=min(first, second), high=max(first, second))

    databases = {}
    if compare_databases:
        for node_id, current in telemetry.components.items():
            if current.database is None:
                continue
            low_node = low_snapshot.components.get(node_id)
            high_node = high_snapshot.components.get(node_id)
            if (
                not low_node
                or not high_node
                or not low_node.database
                or not high_node.database
            ):
                continue
            low_data, high_data = low_node.database, high_node.database
            databases[node_id] = DatabaseForecast(
                current_utilization=current.utilization,
                projected_utilization={
                    resource: span(
                        low_node.utilization[resource], high_node.utilization[resource]
                    )
                    for resource in high_node.utilization
                    if resource in low_node.utilization
                },
                current_write_capacity=current.database.write_capacity,
                current_write_demand=(
                    current.database.write_demand
                    if current.database.write_capacity is not None
                    else None
                ),
                projected_write_capacity=(
                    span(low_data.write_capacity, high_data.write_capacity)
                    if low_data.write_capacity is not None
                    and high_data.write_capacity is not None
                    else None
                ),
                projected_write_demand=(
                    span(low_data.write_demand, high_data.write_demand)
                    if high_data.write_capacity is not None
                    else None
                ),
            )

    return Forecast(
        rps=span(low.rps, high.rps),
        latency=span(low.latency, high.latency),
        availability=span(low.availability, high.availability),
        audience=span(audience * (1 - uncertainty), audience * (1 + uncertainty)),
        confidence=confidence,
        plan=plan,
        databases=databases,
    )


def review(
    game: Game,
    revision: int,
    topology: Topology | None = None,
    *,
    prepared: bool = False,
) -> DraftReview:
    check_revision(game, revision)
    if game.migration is not None:
        raise RuleError("Wait for the planned architecture migration to complete.")
    candidate = topology if topology is not None else game.draft
    if candidate is None:
        raise RuleError("Create a draft first.")
    errors = []
    warnings = []
    changes = {}
    details = []
    estimate = None
    install = 0.0
    daily_after = topology_cost(effective_topology(game))
    migration_ticks, migration_cost = 0, 0.0
    try:
        graph = inspect_graph(candidate)
        validate_identity(game.production, graph.nodes)
        daily_after = topology_cost(effective_topology(game, candidate))
        changes = diff(game.production, candidate)
        details = modifications(game.production, candidate)
        install = install_cost(
            effective_topology(game), effective_topology(game, candidate)
        )
        warnings = deployment_warnings(graph)
        issues = architecture_errors(game, graph)
        # Preserve legacy games with pre-existing split primaries; never permit a new split.
        if messenger_datasets(graph) == messenger_datasets(
            inspect_graph(game.production)
        ) and all(
            config(n).get("role", "Universal") == "Universal"
            and config(n).get("domain", "Shared") == "Shared"
            and config(n).get("partition", "Independent") == "Independent"
            for n in candidate.nodes
        ):
            for legacy in (
                "APIs handling the same domain must use the same primary or the same complete partition set.",
                "Multiple primaries for one domain must all be explicit partitions.",
            ):
                if legacy in issues:
                    issues.remove(legacy)
                    warnings.append(legacy)
        if (
            not researched(game, "domains")
            and "APIs handling the same domain must use the same primary or the same complete partition set."
            in issues
        ):
            issues[
                issues.index(
                    "APIs handling the same domain must use the same primary or the same complete partition set."
                )
            ] = "Messenger API servers receiving live requests must share one primary database."
        errors.extend(issues)
        for feature_id in game.infrastructure_releases:
            if feature_id in game.enabled_features:
                feature = FEATURES[feature_id]
                if any(
                    not requirement_met(
                        REQUIREMENTS[key], graph, game, feature["operation"]
                    )
                    for key in feature["infrastructure"]
                ):
                    errors.append(
                        "The draft cannot support a released product feature. Check its infrastructure requirements in Product."
                    )
        migration_ticks, migration_cost = migration_plan(game, candidate)
        if migration_ticks:
            migrated_storage(game, candidate, validate=not prepared)
            install += migration_cost
            warnings.append(
                "Data migration keeps production serving until preparation completes. Copying reserves 10% database capacity."
            )
        if game.speed and changes["disconnected"]:
            warnings.append(
                "Live routing changes can cause a brief interruption while traffic shifts."
            )
        estimate = forecast(game, candidate, compare_databases=True)
        if estimate.availability.low < 0.95:
            warnings.append("Some projected load exceeds the draft's service capacity.")
        if install > 0 and install > game.balance:
            errors.append("The game balance cannot cover the deployment cost.")
    except RuleError as error:
        errors.append(str(error))
    return DraftReview(
        migration_ticks=migration_ticks,
        migration_cost=migration_cost,
        revision=revision,
        errors=errors,
        warnings=warnings,
        changes=changes,
        details=details,
        daily_before=topology_cost(effective_topology(game)),
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
        for key in dict.fromkeys((*old_config, *new_config)):
            prior, value = old_config.get(key), new_config.get(key)
            if prior != value:
                records.append(
                    Modification(
                        component=node.name,
                        field=(fields.get(key) or LEGACY_DATABASE_LIMITS[key])["label"],
                        before=prior if prior is not None else "Automatic",
                        after=value if value is not None else "Automatic",
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


def service_capacity(
    game: Game, topology: Topology, snapshot: Snapshot
) -> float | None:
    """Current traffic mix at 99% successful processing, with state held fixed."""
    if not snapshot.monitored or snapshot.metrics.rps <= 0:
        return None
    low, high = 0.0, 1.0

    def serves(scale: float) -> bool:
        return (
            evaluate(game, topology, load_scale=scale).snapshot.metrics.availability
            >= 0.99
        )

    while high < 1024 and serves(high):
        low, high = high, high * 2
    if high == 1024 and serves(high):
        return None
    for _ in range(16):
        midpoint = (low + high) / 2
        if serves(midpoint):
            low = midpoint
        else:
            high = midpoint
    return snapshot.metrics.rps * low


def highest_pressure(snapshot: Snapshot, topology: Topology) -> ResourcePressure | None:
    resources = (
        ResourcePressure(component=node.name, resource=resource, utilization=value)
        for node in topology.nodes
        if (metric := snapshot.components.get(node.id))
        for resource, value in metric.utilization.items()
    )
    return max(resources, key=lambda item: item.utilization, default=None)


def deploy(
    game: Game,
    revision: int,
    request_id: UUID,
    rollback: UUID | None = None,
    *,
    prepared: bool = False,
    prepaid_cost: float | None = None,
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
    result = review(game, revision, candidate, prepared=prepared)
    if prepared:
        result.errors = [
            issue
            for issue in result.errors
            if issue != "The game balance cannot cover the deployment cost."
        ]
    if result.errors:
        raise RuleError(result.errors[0])
    if not any(result.changes.values()):
        raise RuleError("There are no architecture changes to deploy.")
    if not prepared:
        spend(game, result.install, "deployment")
        if result.migration_ticks:
            game.migration = ArchitectureMigration(
                request_id=request_id,
                ready_at=game.tick + result.migration_ticks,
                topology=candidate.model_copy(deep=True),
                cost=result.install,
            )
            game.draft = candidate.model_copy(deep=True)
            game.revision += 1
            add_event(
                game,
                "migration",
                "Architecture migration",
                "Production continues serving while data is prepared.",
                "info",
                result.migration_ticks,
            )
            return
    if prepaid_cost is not None:
        result.install = prepaid_cost
    transferred = (
        migrated_storage(game, candidate, validate=False)
        if result.migration_ticks
        else None
    )
    count = sum(len(items) for key, items in result.changes.items() if key != "moved")
    summary = (
        "Rollback"
        if rollback
        else f"Deployed {count} infrastructure changes"
        if count
        else "Updated canvas layout"
    )
    before = evaluate(game).snapshot
    pressure_before = highest_pressure(before, game.production)
    capacity_before = service_capacity(game, game.production, before)
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
    previous_graph, next_graph = (
        inspect_graph(game.production),
        inspect_graph(candidate),
    )
    game.replication = {
        replica: backlog
        for replica, backlog in game.replication.items()
        if replica in next_graph.nodes
        and next_graph.nodes[replica].kind == "replica"
        and next_graph.primaries(replica)
        and next_graph.primaries(replica) == previous_graph.primaries(replica)
    }
    game.production = candidate
    game.draft = None
    game.revision += 1
    live = {node.id for node in game.production.nodes}
    game.queues = {key: value for key, value in game.queues.items() if key in live}
    game.storage = (
        transferred
        if transferred is not None
        else {key: value for key, value in game.storage.items() if key in live}
    )
    for event in game.incidents:
        if event.resolution is None and event.target and event.target not in live:
            event.resolution = "Affected component removed in deployment"
            event.end = game.tick
    after = evaluate(game).snapshot
    capacity_after = service_capacity(game, game.production, after)
    if result.changes.get("disconnected") and game.speed:
        add_event(
            game,
            "deploy",
            "Routing rollout",
            "Some requests may fail briefly while connections switch to the new topology.",
            "info",
            2,
            factor=0.96,
            cause="Routing rollout",
        )
    game.deployments[-1].comparison = DeploymentComparison(
        before=before.metrics,
        after=after.metrics,
        daily_before=result.daily_before,
        daily_after=result.daily_after,
        capacity_before=capacity_before,
        capacity_after=capacity_after,
        pressure_before=pressure_before,
        pressure_after=highest_pressure(after, game.production),
    )
    if game.tutorial == 2:
        game.tutorial = 3
    if not rollback:
        advance_onboarding(game, 7)
        if {"api", "db"}.issubset(after.components):
            advance_onboarding(game, 3)
        progress = onboarding_progress(game)
        if progress.step_id in {
            TutorialStep.MONITOR_DEPLOY,
            TutorialStep.CAPACITY_DEPLOY,
        }:
            change_tutorial_progress(
                game,
                TutorialProgressAction(
                    request_id=request_id,
                    step_id=progress.step_id,
                    interaction="observed",
                ),
            )


def research_state(game: Game, key: str) -> ResearchView:
    if key in game.engineering:
        remaining = max(0, game.engineering[key] - game.tick)
        return ResearchView(
            id=key,
            state="developing" if remaining else "completed",
            remaining=remaining,
        )
    ready = all(researched(game, p) for p in RESEARCH[key]["prereq"])
    return ResearchView(id=key, state="available" if ready else "unavailable")


def develop_research(game: Game, key: str) -> None:
    if research_state(game, key).state != "available":
        raise RuleError(
            "Complete the research prerequisites first, or wait for the current project."
        )
    spend(game, RESEARCH[key]["cost"], "development")
    game.engineering[key] = game.tick + RESEARCH[key]["duration"]


def feature_state(game: Game, key: str, graph: Graph | None = None) -> FeatureView:
    feature = FEATURES[key]
    graph = graph or inspect_graph(game.production)
    infrastructure = [
        RequirementView(
            id=rule_id,
            description=rule.description,
            met=requirement_met(rule, graph, game, feature["operation"]),
        )
        for rule_id in feature["infrastructure"]
        for rule in (REQUIREMENTS[rule_id],)
    ]
    if feature["operation"] and any(
        config(node).get("role", "Universal") != "Universal"
        or config(node).get("domain", "Shared") != "Shared"
        for node in graph.nodes.values()
    ):
        assumed = game.model_copy(
            update={
                "released": list(dict.fromkeys([*game.released, key])),
                "disabled_features": game.disabled_features - {key},
            }
        )
        issues = architecture_errors(assumed, graph)
        infrastructure.append(
            RequirementView(
                id="service_routing",
                description=issues[0] if issues else "Routing and dependencies",
                met=not issues,
            )
        )
    enabled = game.enabled_features
    prereqs = [
        FEATURES[item]["name"] for item in feature["prereq"] if item not in enabled
    ]
    if key in game.released:
        dependents = [
            item
            for item, definition in FEATURES.items()
            if item in enabled and key in definition["prereq"]
        ]
        return FeatureView(
            id=key,
            state="released",
            infrastructure=infrastructure,
            enabled=key in enabled,
            can_enable=not prereqs and all(rule.met for rule in infrastructure),
            can_disable=key != "text" and not dependents,
            dependents=dependents,
            requirements=prereqs,
        )
    operation = feature["operation"]
    base = SCENARIOS[game.scenario]["operations"]
    active = [
        FEATURES[item]["operation"]
        for item in sorted(enabled)
        if FEATURES[item]["operation"]
    ]
    workload = sum(OPERATIONS[item]["rate"] for item in dict.fromkeys([*base, *active]))
    demand_change = OPERATIONS[operation]["rate"] / workload if operation else 0
    if key in game.development:
        remaining = max(0, game.development[key] - game.tick)
        return FeatureView(
            id=key,
            state="developing" if remaining else "ready",
            remaining=remaining,
            requirements=[
                *prereqs,
                *(rule.description for rule in infrastructure if not rule.met),
            ],
            infrastructure=infrastructure,
            can_release=not remaining
            and not prereqs
            and all(rule.met for rule in infrastructure),
            demand_change=demand_change,
        )
    return FeatureView(
        id=key,
        state="locked" if prereqs else "available",
        requirements=prereqs,
        infrastructure=infrastructure,
        demand_change=demand_change,
    )


def change_feature(game: Game, key: str, action: str) -> None:
    if game.migration is not None and action in {"release", "enable"}:
        raise RuleError("Wait for the planned architecture migration to complete.")
    state = feature_state(game, key)
    feature = FEATURES[key]
    if action == "develop" and state.state == "available":
        spend(game, feature["cost"], "development")
        game.development[key] = game.tick + feature["duration"]
    elif action == "release" and state.state == "ready":
        if any(item not in game.enabled_features for item in feature["prereq"]):
            raise RuleError(
                "Enable the required product features first.",
                code="feature_dependency_missing",
            )
        if not state.can_release:
            raise RuleError(
                "Production infrastructure does not meet the release requirements.",
                code="feature_infrastructure_missing",
            )
        game.released.append(key)
        game.infrastructure_releases.append(key)
        del game.development[key]
        add_event(
            game,
            "release",
            f"{feature['name']} released",
            "A new feature is generating demand.",
            "info",
            0,
        )
    elif action == "disable" and state.enabled:
        if state.dependents:
            raise RuleError(
                "Disable dependent features first.",
                code="feature_has_dependents",
            )
        if not state.can_disable:
            raise RuleError(
                "Text messaging is required for Messenger.", code="feature_required"
            )
        game.disabled_features.add(key)
        add_event(
            game,
            "feature-disabled",
            f"{feature['name']} disabled",
            "Product settings changed.",
            "info",
            0,
        )
    elif action == "enable" and state.state == "released" and not state.enabled:
        if state.requirements:
            raise RuleError(
                "Enable the required product features first.",
                code="feature_dependency_missing",
            )
        if not state.can_enable:
            raise RuleError(
                "Production infrastructure does not meet the release requirements.",
                code="feature_infrastructure_missing",
            )
        game.disabled_features.remove(key)
        if key not in game.infrastructure_releases:
            game.infrastructure_releases.append(key)
        add_event(
            game,
            "feature-enabled",
            f"{feature['name']} enabled",
            "Product settings changed.",
            "info",
            0,
        )
    else:
        raise RuleError(
            "This feature is not ready for that action.", code="feature_not_ready"
        )


def change_product(game: Game, product: ProductSettings) -> None:
    previous = product_settings(game)
    if (
        not BUSINESS["premium_min_price"]
        <= product.premium_price
        <= BUSINESS["premium_max_price"]
    ):
        raise RuleError(
            "Subscription price is outside the allowed range.",
            code="premium_price_range",
        )
    for field, feature in (
        ("ad_intensity", "advertising"),
        ("premium_price", "premium"),
        ("premium_fast_sync", "premium"),
        ("premium_high_quality_media", "premium"),
    ):
        if (
            getattr(product, field) != getattr(previous, field)
            and feature not in game.released
        ):
            raise RuleError(
                "Release the feature before changing its settings.",
                code="product_release_required",
            )
    if product != previous:
        game.product = product
        add_event(
            game,
            "product-settings",
            "Product settings updated",
            "Product settings changed.",
            "info",
            0,
        )


def finance(game: Game, active_users: float) -> Economy:
    product = product_settings(game)
    sources = RevenueSources(
        advertising=game.advertising_revenue,
        subscriptions=game.subscription_revenue,
        legacy=max(
            0, game.revenue - (game.advertising_revenue + game.subscription_revenue)
        ),
    )
    costs = OperatingCosts(
        infrastructure=game.infrastructure_spend,
        traffic=game.traffic_spend,
        payments=game.payment_spend,
        legacy=max(
            0,
            game.operating
            - (game.infrastructure_spend + game.traffic_spend + game.payment_spend),
        ),
    )
    history = [
        FinancePoint(tick=point.tick, **point.finance.model_dump())
        for point in game.history
        if point.finance is not None
    ]
    sample_count = len(history)
    factor = TICKS_PER_DAY / max(1, sample_count)
    daily_sources = RevenueSources(
        advertising=sum(p.revenue.advertising for p in history) * factor,
        subscriptions=sum(p.revenue.subscriptions for p in history) * factor,
    )
    daily_costs = OperatingCosts(
        infrastructure=sum(p.expenses.infrastructure for p in history) * factor,
        traffic=sum(p.expenses.traffic for p in history) * factor,
        payments=sum(p.expenses.payments for p in history) * factor,
    )
    dau = (
        sum(p.daily_active_users for p in history) / sample_count
        if sample_count
        else active_users
    )
    recent = OneTimeCosts(
        development=sum(
            purchase.development for purchase in game.recent_purchases.values()
        ),
        marketing=sum(
            purchase.marketing for purchase in game.recent_purchases.values()
        ),
        deployment=sum(
            purchase.deployment for purchase in game.recent_purchases.values()
        ),
    )
    daily_profit = daily_sources.total - daily_costs.total
    # One-time charges are reported as incurred even when the rolling window is partial.
    daily_total_expenses = daily_costs.total + recent.total
    cash_received = game.advertising_revenue + game.subscription_cash + sources.legacy
    return Economy(
        balance=game.balance,
        revenue=game.revenue,
        operating=game.operating,
        development=game.development_spend,
        marketing=game.marketing_spend,
        deployment=game.deployment_spend,
        profit=game.revenue
        - game.operating
        - game.development_spend
        - game.marketing_spend
        - game.deployment_spend,
        daily_infrastructure=topology_cost(effective_topology(game)),
        daily_revenue=daily_sources.total,
        daily_operating=daily_costs.total,
        daily_profit=daily_profit,
        daily_total_expenses=daily_total_expenses,
        daily_net_profit=daily_sources.total - daily_total_expenses,
        recent_purchases=recent,
        purchases=sorted(game.recent_purchases.items(), reverse=True),
        revenue_sources=sources,
        daily_sources=daily_sources,
        operating_costs=costs,
        daily_costs=daily_costs,
        starting_capital=game.balance
        - cash_received
        + game.operating
        + game.development_spend
        + game.marketing_spend
        + game.deployment_spend,
        cash_received=cash_received,
        subscription_cash=game.subscription_cash,
        deferred_subscription_revenue=max(
            0, game.subscription_cash - game.subscription_revenue
        ),
        daily_active_users=dau,
        operating_margin=daily_profit / daily_sources.total
        if daily_sources.total
        else None,
        arpdau=daily_sources.total / dau if sample_count and dau else None,
        cost_per_dau=daily_costs.total / dau if sample_count and dau else None,
        subscribers=round(game.subscribers),
        conversion=game.subscribers / max(1, game.audience),
        premium_satisfaction=min(
            1,
            game.premium_quality
            + BUSINESS["premium_sync_satisfaction"]
            * (
                sum(term.subscribers for term in game.subscriptions if term.fast_sync)
                / game.subscribers
                if game.subscribers
                else int(product.premium_fast_sync)
            )
            + premium_media_gain(game, product)
            * (
                sum(
                    term.subscribers
                    for term in game.subscriptions
                    if term.high_quality_media
                )
                / game.subscribers
                if game.subscribers
                else int(product.premium_high_quality_media)
            )
            + (
                BUSINESS["premium_ad_free_satisfaction"]
                if "advertising" in game.enabled_features
                else 0
            ),
        ),
        daily_ad_impressions=sum(p.ad_impressions for p in history) * factor,
        recorded_ticks=sample_count,
        history=history,
    )


def start_campaign(game: Game, key: str) -> None:
    if key in game.campaigns or key in game.regional_campaigns:
        raise RuleError("That campaign is already running.")
    campaign = CAMPAIGNS[key]
    spend(game, campaign["cost"], "marketing")
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


def legacy_onboarding(game: Game) -> Onboarding:
    if game.onboarding is not None:
        return game.onboarding
    stage = {0: 0, 1: 3, 2: 7, 3: 4}.get(game.tutorial, 9)
    return Onboarding(step=stage, furthest=stage)


def onboarding_progress(game: Game) -> Onboarding:
    progress = legacy_onboarding(game)
    if progress.step_id is not None:
        return progress
    return progress.model_copy(
        update={
            "step_id": LEGACY_TUTORIAL_STEPS[progress.step],
            "furthest_id": LEGACY_TUTORIAL_STEPS[progress.furthest],
        }
    )


def advance_onboarding(game: Game, step: int) -> None:
    progress = legacy_onboarding(game)
    if (
        progress.step_id is None
        and game.settings.show_tutorial
        and not progress.skipped
        and progress.step == step
    ):
        progress.step += 1
        progress.furthest = max(progress.furthest, progress.step)
        game.onboarding = progress


def change_onboarding(
    game: Game, body: OnboardingAction | TutorialProgressAction
) -> None:
    if isinstance(body, TutorialProgressAction):
        change_tutorial_progress(game, body)
        return
    progress = legacy_onboarding(game)
    if progress.step_id is not None or body.step != progress.step:
        return
    interaction = body.interaction
    step = progress.step
    if interaction in {"skip", "resume"}:
        progress.skipped = interaction == "skip"
    elif interaction == "back":
        progress.step = max(0, step - 1)
    elif not progress.skipped:
        advance_step = interaction == "next" and (
            step in {0, 1, 5, 8} or step < progress.furthest
        )
        if interaction == "inspect" and step == 2:
            advance_step = True
        elif interaction == "coverage" and step == 3:
            coverage = evaluate(game).snapshot.components
            advance_step = {"api", "db"}.issubset(coverage)
        elif interaction == "monitor" and step == 4:
            advance_step = True
        if advance_step:
            progress.step = min(9, step + 1)
            progress.furthest = max(progress.step, progress.furthest)
    game.onboarding = progress


TUTORIAL_INFORMATION = {
    TutorialStep.CLOCK,
    TutorialStep.BALANCE,
    TutorialStep.TOPOLOGY,
    TutorialStep.COMPONENTS,
    TutorialStep.CONFIGURATION,
    TutorialStep.CAPACITY,
    TutorialStep.METRICS_COVERAGE,
    TutorialStep.MONITOR_COSTS,
    TutorialStep.TELEMETRY,
    TutorialStep.DASHBOARD_LAYOUT,
    TutorialStep.API_UTILIZATION,
    TutorialStep.API_THROUGHPUT,
    TutorialStep.INFRASTRUCTURE,
    TutorialStep.CAPACITY_FORECAST,
    TutorialStep.CAPACITY_COSTS,
    TutorialStep.COMPARE,
    TutorialStep.ECONOMY,
    TutorialStep.FINANCE,
    TutorialStep.EXPENSES,
    TutorialStep.PRODUCT,
    TutorialStep.PREMIUM,
    TutorialStep.GROWTH,
}


def tutorial_api(topology: Topology) -> Node | None:
    return next(
        (node for node in topology.nodes if node.id == "api" and node.kind == "api"),
        None,
    ) or next((node for node in topology.nodes if node.kind == "api"), None)


def tutorial_coverage_nodes(topology: Topology) -> set[str]:
    api = tutorial_api(topology)
    database = next(
        (
            node
            for node in topology.nodes
            if api
            and node.kind == "database"
            and any(
                edge.source == api.id and edge.target == node.id
                for edge in topology.edges
            )
        ),
        None,
    )
    return {node.id for node in (api, database) if node}


def tutorial_config_changed(before: Topology, after: Topology) -> bool:
    api = tutorial_api(before)
    updated = next((node for node in after.nodes if api and node.id == api.id), None)
    return bool(
        api and updated and updated.kind == "api" and config(api) != config(updated)
    )


def tutorial_milestone(game: Game, step: TutorialStep) -> bool:
    if step == TutorialStep.CREATE_DRAFT:
        return game.draft is not None
    if step == TutorialStep.SAVE_CAPACITY:
        return game.draft is not None and tutorial_config_changed(
            game.production, game.draft
        )
    if step == TutorialStep.CAPACITY_DEPLOY:
        return bool(
            game.draft is None
            and game.deployments
            and game.deployments[-1].comparison
            and tutorial_config_changed(game.deployments[-1].topology, game.production)
        )
    if step in {
        TutorialStep.ADD_COLLECTOR,
        TutorialStep.LINK_COVERAGE,
        TutorialStep.MONITOR_REVIEW,
        TutorialStep.MONITOR_DEPLOY,
    }:
        required = tutorial_coverage_nodes(game.production)
        if required and required.issubset(evaluate(game).snapshot.components):
            return True
        draft = game.draft
        if step == TutorialStep.ADD_COLLECTOR:
            return any(
                node.kind == "monitor" for node in (draft or game.production).nodes
            )
        if step == TutorialStep.LINK_COVERAGE and draft and required:
            return required.issubset(evaluate(game, topology=draft).snapshot.components)
        return step == TutorialStep.MONITOR_REVIEW
    return step not in TUTORIAL_INFORMATION and step != TutorialStep.COMPLETE


def change_tutorial_progress(game: Game, body: TutorialProgressAction) -> None:
    progress = onboarding_progress(game).model_copy()
    if body.step_id != progress.step_id:
        return
    step = TUTORIAL_STEPS.index(body.step_id)
    furthest = TUTORIAL_STEPS.index(progress.furthest_id or body.step_id)
    interaction = body.interaction
    if interaction == "restart":
        step = furthest = 0
        progress.skipped = False
        game.settings.show_tutorial = True
    elif interaction == "skip":
        progress.skipped = True
    elif interaction == "resume":
        progress.skipped = False
        game.settings.show_tutorial = True
    elif not progress.skipped and game.settings.show_tutorial:
        if interaction == "back":
            step = max(0, step - 1)
        elif step < len(TUTORIAL_STEPS) - 1 and (
            interaction == "skip-step"
            or (
                interaction == "next"
                and (body.step_id in TUTORIAL_INFORMATION or step < furthest)
            )
            or (
                interaction == "observed"
                and step == furthest
                and tutorial_milestone(game, body.step_id)
            )
        ):
            step += 1
            furthest = max(step, furthest)
    progress.step_id = TUTORIAL_STEPS[step]
    progress.furthest_id = TUTORIAL_STEPS[furthest]
    progress.step = (
        sum(TUTORIAL_STEPS.index(key) <= step for key in LEGACY_TUTORIAL_STEPS) - 1
    )
    progress.furthest = (
        sum(TUTORIAL_STEPS.index(key) <= furthest for key in LEGACY_TUTORIAL_STEPS) - 1
    )
    game.onboarding = progress


def incident_view(event: Incident, snapshot: Snapshot) -> IncidentView:
    covered = event.target in snapshot.components
    hidden = event.target is not None and not covered
    diagnostic = {
        "failure": "Service incident",
        "degradation": "Service incident",
        "storage": "Service incident",
        "capacity": "Service incident",
        "deploy": "Deployment event",
        "spike": "Traffic event",
    }
    redact = hidden and event.title != "Instance failure drill"
    return IncidentView(
        id=event.id,
        title="Service event" if redact else event.title,
        category=diagnostic.get(event.kind, "Player action"),
        symptom=(
            "Requests failed during this event."
            if event.failed_requests
            else "Monitoring coverage is required for more detail."
        )
        if redact
        else event.symptom,
        severity=event.severity,
        start=event.start,
        end=event.end,
        active=event.resolution is None,
        cause=(event.cause or event.kind)
        if not hidden and event.kind in diagnostic
        else None,
        target=event.target if covered else None,
        resolution=event.resolution,
        failed_requests=round(event.failed_requests),
        acknowledged=event.acknowledged,
    )


def view(game: Game, saved_at: datetime) -> GameView:
    result = evaluate(game, overview=True)
    snapshot = result.snapshot
    if snapshot.demand_overview:
        for region in snapshot.demand_overview.regions:
            region.earned_ad_revenue = sum(
                point.finance.regional_ads.get(region.id, 0)
                for point in game.history
                if point.finance
            )
    estimates = {}
    if "advertising" in game.released:
        for intensity in ADVERTISING:
            projection = ad_forecast(game, intensity)
            estimates[intensity] = AdvertisingEstimate(
                impressions=projection.requests_per_day * snapshot.metrics.availability,
                revenue=projection.value_per_day * snapshot.metrics.availability,
                satisfaction_impact=-projection.friction,
                churn_impact=projection.additional_churn,
            )
    history = game.history if snapshot.monitored else []
    graph = inspect_graph(game.production)
    return GameView(
        id=game.id,
        name=game.name,
        scenario=game.scenario,
        tick=game.tick,
        day=(game.start_minute + game.tick * MINUTES_PER_TICK) // MINUTES_PER_DAY + 1,
        audience=round(game.audience),
        balance=game.balance,
        saved_at=saved_at,
        speed=game.speed,
        start_minute=game.start_minute,
        difficulty=game.difficulty,
        satisfaction=game.satisfaction,
        production=game.production,
        draft=game.draft,
        diagram=game.diagram,
        revision=game.revision,
        snapshot=snapshot,
        history=history,
        business_history=[
            BusinessPoint(tick=p.tick, audience=p.audience, balance=p.balance)
            for p in game.history
        ],
        economy=finance(game, result.daily_active_users),
        product=product_settings(game),
        advertising_estimates=estimates,
        component_costs={
            node.id: daily_cost(node) for node in effective_topology(game).nodes
        },
        draft_costs={
            node.id: daily_cost(node)
            for node in effective_topology(game, game.draft).nodes
        }
        if game.draft
        else {},
        engineering=[research_state(game, key) for key in RESEARCH],
        migration=game.migration,
        engineering_lesson=game.engineering_lesson,
        features=[feature_state(game, key, graph) for key in FEATURES],
        campaigns=[
            CampaignView(
                id=key,
                remaining=start + CAMPAIGNS[key]["duration"] - game.tick,
                progress=(game.tick - start) / CAMPAIGNS[key]["duration"],
            )
            for key, start in game.campaigns.items()
        ]
        + [
            CampaignView(
                id=key,
                region=plan.region,
                regions=plan.regions,
                budget=plan.budget,
                acquired=plan.audience,
                remaining=plan.start + plan.duration - game.tick,
                progress=(game.tick - plan.start) / plan.duration,
            )
            for key, plan in game.regional_campaigns.items()
        ],
        markets=markets(game),
        languages=languages(game),
        incidents=[
            incident_view(event, snapshot) for event in reversed(game.incidents)
        ],
        deployments=[
            DeploymentView(
                id=e.id,
                tick=e.tick,
                summary=e.summary,
                cost=e.cost,
                comparison=e.comparison,
            )
            for e in reversed(game.deployments)
        ],
        settings=game.settings,
        tutorial=game.tutorial,
        onboarding=onboarding_progress(game),
        peak=max(
            (point.metrics for point in history),
            key=lambda metrics: metrics.rps,
            default=None,
        ),
    )
