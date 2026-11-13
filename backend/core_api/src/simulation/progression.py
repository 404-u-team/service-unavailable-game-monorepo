from random import Random
from uuid import UUID

from src.simulation.catalog import (
    CAMPAIGNS,
    DIFFICULTIES,
    FEATURES,
    HISTORY_LIMIT,
    MINUTES_PER_TICK,
    SCENARIOS,
    TICKS_PER_DAY,
)
from src.simulation.engine import evaluate
from src.simulation.models import Difficulty, Game, HistoryPoint, Incident, Metrics
from src.simulation.topology import RuleError, config, starter_topology, topology_cost

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
    )
    game.history = [history_point(game, evaluate(game).snapshot.metrics)]
    return game


def history_point(game: Game, metrics: Metrics) -> HistoryPoint:
    return HistoryPoint(
        tick=game.tick,
        audience=round(game.audience),
        balance=game.balance,
        metrics=metrics,
    )


def spend(game: Game, amount: float, ledger: str) -> None:
    if game.balance < amount:
        raise RuleError(
            f"This action costs ${amount:,.2f}. Available balance is ${game.balance:,.2f}."
        )
    game.balance -= amount
    setattr(game, ledger, getattr(game, ledger) + amount)


def add_event(
    game: Game,
    kind: str,
    title: str,
    symptom: str,
    severity: str,
    duration: int,
    target: str | None = None,
    factor: float = 1,
) -> None:
    game.event_sequence += 1
    game.incidents.append(
        Incident(
            id=f"{kind}-{game.tick}-{game.event_sequence}",
            kind=kind,
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
        event.id.startswith("failure-") and event.title == "Instance failure drill"
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
    )


def advance(game: Game, steps: int) -> None:
    for _ in range(steps):
        game.tick += 1
        for event in game.incidents:
            if event.resolution is None and game.tick >= event.end:
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
                game.audience += (
                    campaign["audience"]
                    * 6
                    * phase
                    * (1 - phase)
                    / campaign["duration"]
                )
        game.campaigns = {
            key: start
            for key, start in game.campaigns.items()
            if game.tick < start + CAMPAIGNS[key]["duration"]
        }

        roll_event(game)
        result = evaluate(game)
        game.queues = result.queues
        game.storage = result.storage
        metrics = result.snapshot.metrics
        for event in game.incidents:
            if event.resolution is None:
                event.failed_requests += metrics.errors * SECONDS_PER_STEP

        scenario = SCENARIOS[game.scenario]
        latency_penalty = min(0.48, max(0, metrics.latency - 90) / 480)
        quality = max(0.05, metrics.availability - latency_penalty)
        game.satisfaction += (quality - game.satisfaction) * 0.09
        game.strain = min(1, max(0, game.strain + (0.82 - quality) * 0.075))
        appeal = sum(FEATURES[key]["appeal"] for key in game.released)
        growth = scenario["organic"] * (1 + appeal) * game.satisfaction
        churn = (0.002 + (1 - game.satisfaction) * 0.055) / (
            1 + appeal * 0.4
        ) + game.strain * 0.13
        game.audience = max(50, game.audience * (1 + (growth - churn) / TICKS_PER_DAY))
        daily_revenue, daily_expense = operating_rates(game, metrics, appeal)
        revenue = daily_revenue / TICKS_PER_DAY
        expense = daily_expense / TICKS_PER_DAY
        game.revenue += revenue
        game.operating += expense
        game.balance += revenue - expense
        game.history.append(history_point(game, metrics))
        game.history = game.history[-HISTORY_LIMIT:]
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
                )


def operating_rates(game: Game, metrics: Metrics, appeal: float) -> tuple[float, float]:
    revenue = (
        game.audience
        * SCENARIOS[game.scenario]["daily_revenue"]
        * (1 + appeal * 0.6)
        * (0.3 + 0.7 * game.satisfaction)
    )
    expenses = topology_cost(game.production) + metrics.throughput * 0.002
    return revenue, expenses


def roll_event(game: Game) -> None:
    if (
        game.tick < 30
        or game.tick % 8
        or any(event.resolution is None for event in game.incidents)
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
        )
        return
    component = {"failure": "api", "degradation": "database", "network": "balancer"}[
        kind
    ]
    targets = sorted(
        node.id for node in game.production.nodes if node.kind == component
    )
    if targets:
        add_event(
            game,
            "failure" if kind == "failure" else "degradation",
            "Service degradation",
            "Requests are slower or failing more often.",
            "warning",
            duration,
            rng.choice(targets),
            0.52,
        )
