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
    SaveSummary,
)
from src.repositories.games import GameRepository
from src.services.markets import languages, markets
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
    product_settings,
)
from src.simulation.engine import evaluate
from src.simulation.models import (
    Deployment,
    DeploymentComparison,
    Diagram,
    Game,
    Node,
    Onboarding,
    OneTimeCosts,
    OperatingCosts,
    ProductSettings,
    RegionalCampaign,
    ResourcePressure,
    RevenueSources,
    Snapshot,
    Topology,
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
    previous = inspect_graph(game.draft)
    for node in topology.nodes:
        if node.kind != "api":
            continue
        primaries = graph.primaries(node.id)
        if len(primaries) > 1 and (
            node.id not in previous.nodes or primaries != previous.primaries(node.id)
        ):
            raise RuleError(
                "An API can use one primary database for its dataset.",
                code="one_write_primary",
            )
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
        acquire(assumed, plan.region, plan.acquired * 0.8)
        audience = assumed.audience
        assumed.regional_campaigns[campaign_id] = RegionalCampaign(
            region=plan.region,
            start=game.tick,
            duration=plan.duration,
            audience=plan.acquired,
            budget=plan.budget,
            spike=CAMPAIGNS[campaign_id]["spike"],
        )
        assumed.tick += int(plan.duration * 0.65)
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
        estimate = forecast(game, candidate, compare_databases=True)
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


def highest_pressure(snapshot: Snapshot, topology: Topology) -> ResourcePressure | None:
    resources = (
        ResourcePressure(component=node.name, resource=resource, utilization=value)
        for node in topology.nodes
        if (metric := snapshot.components.get(node.id))
        for resource, value in metric.utilization.items()
        if value >= 0.78
    )
    return max(resources, key=lambda item: item.utilization, default=None)


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
    spend(game, result.install, "deployment")
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
    after = evaluate(game).snapshot
    game.deployments[-1].comparison = DeploymentComparison(
        before=before.metrics,
        after=after.metrics,
        daily_before=result.daily_before,
        daily_after=result.daily_after,
        pressure_before=pressure_before,
        pressure_after=highest_pressure(after, game.production),
    )
    if game.tutorial == 2:
        game.tutorial = 3
    if not rollback:
        advance_onboarding(game, 7)
        if {"api", "db"}.issubset(after.components):
            advance_onboarding(game, 3)


def feature_state(game: Game, key: str, graph: Graph | None = None) -> FeatureView:
    feature = FEATURES[key]
    graph = graph or inspect_graph(game.production)
    infrastructure = [
        RequirementView(
            id=rule_id,
            description=rule.description,
            met=requirement_met(rule, graph, game),
        )
        for rule_id in feature["infrastructure"]
        for rule in (REQUIREMENTS[rule_id],)
    ]
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
        daily_infrastructure=topology_cost(game.production),
        daily_revenue=daily_sources.total,
        daily_operating=daily_costs.total,
        daily_profit=daily_profit,
        daily_total_expenses=daily_total_expenses,
        daily_net_profit=daily_sources.total - daily_total_expenses,
        recent_purchases=recent,
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
                else int(product_settings(game).premium_fast_sync)
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


def onboarding_progress(game: Game) -> Onboarding:
    if game.onboarding is not None:
        return game.onboarding
    stage = {0: 0, 1: 3, 2: 7, 3: 4}.get(game.tutorial, 9)
    return Onboarding(step=stage, furthest=stage)


def advance_onboarding(game: Game, step: int) -> None:
    progress = onboarding_progress(game)
    if game.settings.show_tutorial and not progress.skipped and progress.step == step:
        progress.step += 1
        progress.furthest = max(progress.furthest, progress.step)
        game.onboarding = progress


def change_onboarding(game: Game, body: OnboardingAction) -> None:
    progress = onboarding_progress(game)
    if body.step != progress.step:
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
        component_costs={node.id: daily_cost(node) for node in game.production.nodes},
        draft_costs={node.id: daily_cost(node) for node in game.draft.nodes}
        if game.draft
        else {},
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
