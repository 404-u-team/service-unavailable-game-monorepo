from random import Random
from typing import Literal
from uuid import UUID

from src.simulation.catalog import (
    ADVERTISING,
    BUSINESS,
    CAMPAIGNS,
    DIFFICULTIES,
    FEATURES,
    HISTORY_LIMIT,
    MEDIA_QUALITY,
    MINUTES_PER_TICK,
    REGIONS,
    SCENARIOS,
    START_MINUTE_UTC,
    SYNC_FREQUENCY,
    TICKS_PER_DAY,
)
from src.simulation.demand import (
    acquire,
    active_markets,
    adoption,
    arrival_weight,
    free_share,
    product_settings,
    regional_audience,
)
from src.simulation.economy import book_tick, update_subscriptions
from src.simulation.engine import evaluate
from src.simulation.models import (
    Difficulty,
    FinanceSample,
    Game,
    HistoryPoint,
    Incident,
    Onboarding,
    OneTimeCosts,
    Snapshot,
)
from src.simulation.topology import RuleError, config, starter_topology

SECONDS_PER_STEP = MINUTES_PER_TICK * 60
EVENT_LIMIT = 100


def new_game(
    game_id: UUID,
    name: str,
    seed: int,
    scenario: str,
    difficulty: Difficulty = "beginner",
) -> Game:
    profile = DIFFICULTIES[difficulty]
    game = Game(
        id=game_id,
        name=name,
        seed=seed,
        scenario=scenario,
        production=starter_topology(),
        audience=profile["audience"],
        balance=profile["balance"],
        difficulty=difficulty,
        start_minute=START_MINUTE_UTC,
        onboarding=Onboarding(),
    )
    game.history = [history_point(game, evaluate(game).snapshot)]
    return game


def history_point(
    game: Game,
    snapshot: Snapshot,
    finance: FinanceSample | None = None,
    churn: float = 0,
) -> HistoryPoint:
    recorded = {
        node_id
        for monitor in snapshot.monitors.values()
        if monitor.history
        for node_id in monitor.covered
    }
    return HistoryPoint(
        tick=game.tick,
        audience=round(game.audience),
        balance=game.balance,
        metrics=snapshot.metrics,
        finance=finance,
        audience_churn=churn,
        resource_utilization={
            node_id: metric.utilization
            for node_id, metric in snapshot.components.items()
            if node_id in recorded and metric.utilization
        },
        peak_utilization={
            node_id: max(metric.utilization.values())
            for node_id, metric in snapshot.components.items()
            if node_id in recorded and metric.utilization
        },
    )


def spend(
    game: Game, amount: float, ledger: Literal["development", "marketing", "deployment"]
) -> None:
    if amount < 0:
        raise ValueError("Purchase amounts must be nonnegative")
    if amount > 0 and game.balance < amount:
        raise RuleError(
            f"This action costs ${amount:,.2f}. Available balance is ${game.balance:,.2f}."
        )
    game.balance -= amount
    field = f"{ledger}_spend"
    setattr(game, field, getattr(game, field) + amount)
    if amount:
        purchase = game.recent_purchases.setdefault(game.tick, OneTimeCosts())
        setattr(purchase, ledger, getattr(purchase, ledger) + amount)


def add_event(
    game: Game,
    kind: str,
    title: str,
    symptom: str,
    severity: str,
    duration: int,
    target: str | None = None,
    factor: float = 1,
    *,
    cause: str | None = None,
) -> None:
    game.event_sequence += 1
    prefix = "incident" if target else kind
    game.incidents.append(
        Incident(
            id=f"{prefix}-{game.tick}-{game.event_sequence}",
            kind=kind,
            cause=cause,
            title=title,
            symptom=symptom,
            severity=severity,
            start=game.tick,
            end=game.tick + duration,
            target=target,
            factor=factor,
            resolution="Recorded" if duration == 0 else None,
        )
    )
    game.incidents = game.incidents[-EVENT_LIMIT:]


def drill(game: Game) -> None:
    if any(
        event.kind == "failure" and event.title == "Instance failure drill"
        for event in game.incidents
    ):
        raise RuleError(
            "The instance failure drill is already in this save’s event history."
        )
    target = next(
        (node.id for node in game.production.nodes if node.kind == "api"), None
    )
    if target is None:
        raise RuleError("Deploy an API server to run the failure drill.")
    add_event(
        game,
        "failure",
        "Instance failure drill",
        "A planned drill is reducing service capacity.",
        "warning",
        12,
        target,
        cause="Planned failure drill",
    )


def advance(game: Game, steps: int) -> None:
    product = product_settings(game)
    for _ in range(steps):
        game.tick += 1
        for event in game.incidents:
            if (
                event.kind != "capacity"
                and event.resolution is None
                and game.tick >= event.end
            ):
                event.resolution = (
                    "Capacity restored"
                    if event.target
                    else "Activity returned to baseline"
                )

        # Integrating the acquisition curve gives the campaign's advertised total.
        for key, start in game.campaigns.items():
            campaign = CAMPAIGNS[key]
            elapsed = game.tick - start
            if 0 < elapsed <= campaign["duration"]:
                phase = (elapsed - 0.5) / campaign["duration"]
                acquired = (
                    campaign["audience"]
                    * 6
                    * phase
                    * (1 - phase)
                    / campaign["duration"]
                )
                game.audience += acquired
                if product.north_america:
                    game.north_america_audience += (
                        acquired * BUSINESS["expansion_acquisition_share"]
                    )
            if elapsed == campaign["duration"]:
                add_event(
                    game,
                    "campaign-complete",
                    f"{campaign['name']} campaign has ended",
                    "The campaign has finished acquiring users.",
                    "info",
                    0,
                )
        game.campaigns = {
            key: start
            for key, start in game.campaigns.items()
            if game.tick < start + CAMPAIGNS[key]["duration"]
        }

        finished = []
        for key, plan in game.regional_campaigns.items():
            elapsed = game.tick - plan.start
            weight = arrival_weight(elapsed, plan.duration)
            if weight:
                for region in plan.regions:
                    audience = (
                        plan.allocations[region].audience
                        if plan.allocations
                        else plan.audience
                    )
                    acquire(game, region, audience * weight)
            if elapsed >= plan.duration:
                finished.append(key)
                add_event(
                    game,
                    "campaign-complete",
                    f"{CAMPAIGNS[key]['name']} campaign has ended",
                    "The campaign has finished acquiring users.",
                    "info",
                    0,
                )

        roll_event(game)
        result = evaluate(game)
        for key in finished:
            del game.regional_campaigns[key]
        game.queues = result.queues
        game.storage = result.storage
        game.replication = result.replication
        metrics = result.snapshot.metrics
        record_capacity_event(game, result.snapshot)
        for event in game.incidents:
            if event.resolution is None:
                event.failed_requests += metrics.errors * SECONDS_PER_STEP

        scenario = SCENARIOS[game.scenario]
        latency_penalty = min(0.48, max(0, metrics.latency - 90) / 480)
        quality = max(0.05, metrics.availability - latency_penalty)
        enabled = game.enabled_features
        ads = ADVERTISING[product.ad_intensity] if "advertising" in enabled else None
        eligible_share = free_share(game) if ads else 0
        experience = quality + SYNC_FREQUENCY[product.sync_frequency]["satisfaction"]
        if enabled & {"images", "voice", "files"}:
            experience += MEDIA_QUALITY[product.media_quality]["satisfaction"]
        if ads:
            experience -= ads["friction"] * eligible_share
            experience += (
                BUSINESS["premium_ad_free_satisfaction"]
                * game.subscribers
                / max(1, game.audience)
            )
        game.satisfaction += (max(0.05, min(1, experience)) - game.satisfaction) * 0.09
        game.strain = min(1, max(0, game.strain + (0.82 - quality) * 0.075))
        appeal = sum(FEATURES[key]["appeal"] for key in sorted(enabled))
        growth = scenario["organic"] * (1 + appeal) * game.satisfaction
        churn = (
            (0.002 + (1 - game.satisfaction) * 0.055) / (1 + appeal * 0.4)
            + game.strain * 0.13
            + (ads["churn"] * eligible_share if ads else 0)
        )
        base_population = game.audience - sum(game.market_audience.values())
        if "north_america" in game.launched_markets and not product.north_america:
            base_population -= game.north_america_audience
        organic_acquisition = (
            max(0, base_population) * growth * adoption(game, "europe") / TICKS_PER_DAY
        )
        churned = game.audience * churn / TICKS_PER_DAY
        retained = 1 - churn / TICKS_PER_DAY
        game.audience = max(
            50, game.subscribers, game.audience - churned + organic_acquisition
        )
        game.north_america_audience *= retained
        game.market_audience = {
            key: users * retained for key, users in game.market_audience.items()
        }
        if product.north_america:
            game.north_america_audience += (
                organic_acquisition * BUSINESS["expansion_acquisition_share"]
            )
        for region, population in regional_audience(game, game.audience):
            if (
                region not in active_markets(game)
                or region == "europe"
                or (region == "north_america" and product.north_america)
            ):
                continue
            profile = REGIONS[region]
            room = max(0.0, 1 - population / profile["potential"])
            acquire(
                game,
                region,
                (population + 300)
                * growth
                * profile["organic"]
                * adoption(game, region)
                * room
                / TICKS_PER_DAY,
            )
        premium_latency = max(
            0, metrics.latency - BUSINESS["premium_latency_threshold"]
        )
        premium_quality = max(
            0.05,
            metrics.availability - premium_latency / BUSINESS["premium_latency_scale"],
        )
        cash = update_subscriptions(game, premium_quality, result.daily_active_users)
        finance = book_tick(game, result, cash)
        game.history.append(history_point(game, result.snapshot, finance, churned))
        game.history = game.history[-HISTORY_LIMIT:]
        game.recent_purchases.pop(game.tick - TICKS_PER_DAY, None)
        for node in game.production.nodes:
            if node.kind != "database":
                continue
            if game.storage.get(node.id, 0) >= config(node)[
                "storage"
            ] * 0.85 and not any(
                event.kind == "storage" and event.target == node.id
                for event in game.incidents
            ):
                add_event(
                    game,
                    "storage",
                    "Storage alert",
                    "Persistent storage is approaching its limit.",
                    "warning",
                    0,
                    node.id,
                    cause="Storage pressure",
                )


def record_capacity_event(game: Game, snapshot: Snapshot) -> None:
    overloaded = {
        key: max(metric.utilization.values(), default=0)
        for key, metric in snapshot.components.items()
        if metric.status == "overloaded" and snapshot.metrics.errors > 1e-6
    }
    previous = next(
        (
            event
            for event in reversed(game.incidents)
            if event.kind == "capacity" and event.resolution is None
        ),
        None,
    )
    if previous and previous.target in overloaded:
        previous.end = game.tick + 1
        return
    if previous:
        previous.end = game.tick
        previous.resolution = (
            "Monitored capacity recovered"
            if previous.target in snapshot.components
            else "Monitoring coverage lost"
        )
    if overloaded:
        add_event(
            game,
            "capacity",
            "Capacity pressure",
            "Requests are being rejected or failing during high load.",
            "warning",
            1,
            max(overloaded, key=overloaded.get),
            cause="Resource saturation",
        )


def roll_event(game: Game) -> None:
    if (
        game.tick < 30
        or game.tick % 8
        or any(
            event.resolution is None and event.kind != "capacity"
            for event in game.incidents
        )
    ):
        return
    rng = Random(game.seed ^ (game.tick * 49157))
    if rng.random() > DIFFICULTIES[game.difficulty]["incident_chance"]:
        return
    kind = rng.choice(["spike", "failure", "degradation", "network"])
    duration = rng.randint(6, 15)
    if kind == "spike":
        add_event(
            game,
            "spike",
            "Activity spike",
            "Traffic is above its normal range.",
            "info",
            duration,
            factor=1.27,
            cause="Traffic spike",
        )
        return
    component = {"failure": "api", "degradation": "database", "network": "balancer"}[
        kind
    ]
    targets = sorted(
        node.id for node in game.production.nodes if node.kind == component
    )
    if targets:
        target = rng.choice(targets)
        if (
            kind == "failure"
            and config(
                next(node for node in game.production.nodes if node.id == target)
            ).get("recovery")
            == "Managed replacement"
        ):
            duration = max(1, (duration + 1) // 2)
        add_event(
            game,
            "failure" if kind == "failure" else "degradation",
            "Instance unavailable" if kind == "failure" else "Service degradation",
            "An instance stopped serving requests."
            if kind == "failure"
            else "Requests are slower or failing more often.",
            "warning",
            duration,
            target,
            0.52,
            cause={
                "failure": "Simulated hardware failure",
                "degradation": "Database slowdown",
                "network": "Network degradation",
            }[kind],
        )
