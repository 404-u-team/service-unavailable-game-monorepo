"""Replay 35 game days per strategy. Run from backend/core_api with python -m scripts.balance."""

from argparse import ArgumentParser
from statistics import mean
from uuid import UUID, uuid4

from src.services.games import (
    change_feature,
    change_product,
    deploy,
    edit_draft,
    open_draft,
)
from src.simulation.catalog import ADVERTISING, DIFFICULTIES, TICKS_PER_DAY
from src.simulation.demand import product_settings
from src.simulation.models import Difficulty, Edge
from src.simulation.progression import add_event, advance, new_game

SEEDS = (7, 19, 73)
STRATEGIES = (
    "minimal",
    "stable",
    "low ads",
    "moderate ads",
    "high ads",
    "premium",
    "expensive premium",
    "mixed",
    "overprovisioned",
    "manual scaling",
    "frequent failures",
)


def simulate(
    strategy: str, seed: int, difficulty: Difficulty, days: int
) -> dict[str, float]:
    game = new_game(UUID(int=seed), "Balance run", seed, "messenger", difficulty)

    def configure(*, instances: int, cpu: int, disk: str) -> None:
        open_draft(game, game.revision)
        draft = game.draft.model_copy(deep=True)
        api = next(node for node in draft.nodes if node.id == "api")
        db = next(node for node in draft.nodes if node.id == "db")
        api.config = {"instances": instances, "cpu": cpu}
        db.config = {"cpu": 4 if cpu > 2 else 2, "disk": disk}
        if strategy == "minimal":
            draft.nodes = [node for node in draft.nodes if node.id != "edge"]
            draft.edges = [
                Edge(source="traffic", target="api"),
                Edge(source="api", target="db"),
            ]
        edit_draft(game, game.revision, draft)
        deploy(game, game.revision, uuid4())

    if strategy == "minimal":
        configure(instances=1, cpu=2, disk="SSD")
    elif strategy == "overprovisioned":
        configure(instances=8, cpu=8, disk="NVMe")
    else:
        configure(instances=2, cpu=2, disk="SSD")

    monetization = []
    if strategy in {
        "mixed",
        "overprovisioned",
        "manual scaling",
        "frequent failures",
    } or strategy.endswith(" ads"):
        monetization.append("advertising")
    if strategy in {"premium", "expensive premium", "mixed", "frequent failures"}:
        monetization.append("premium")
    for key in monetization:
        change_feature(game, key, "develop")
    advance(game, 18)
    for key in monetization:
        change_feature(game, key, "release")
    product = product_settings(game)
    intensity = strategy.removesuffix(" ads")
    if intensity in ADVERTISING:
        product = product.model_copy(update={"ad_intensity": intensity})
    if strategy == "expensive premium":
        product = product.model_copy(update={"premium_price": 12})
    change_product(game, product)

    start_audience = DIFFICULTIES[difficulty]["audience"]
    satisfaction = 0.0
    availability = sum(point.metrics.availability for point in game.history[1:])
    churn = sum(point.audience_churn for point in game.history[1:])
    steps = days * TICKS_PER_DAY
    while game.tick < steps:
        if strategy == "frequent failures" and game.tick % 24 == 0:
            add_event(
                game,
                "failure",
                "Balance drill",
                "An API instance failed.",
                "warning",
                12,
                "api",
            )
        if strategy == "manual scaling" and game.tick == 7 * TICKS_PER_DAY + 90:
            change_product(
                game,
                product_settings(game).model_copy(update={"sync_frequency": "relaxed"}),
            )
            configure(instances=1, cpu=3, disk="SSD")
        advance(game, 1)
        availability += game.history[-1].metrics.availability
        satisfaction += game.satisfaction
        churn += game.history[-1].audience_churn

    return {
        "revenue": game.revenue,
        "operating": game.operating,
        "profit": game.revenue - game.operating,
        "net": game.revenue
        - game.operating
        - game.development_spend
        - game.deployment_spend,
        "growth": 100 * (game.audience / start_audience - 1),
        "satisfaction": 100 * satisfaction / (steps - 18),
        "churn": churn,
        "availability": 100 * availability / steps,
        "subscribers": game.subscribers,
        "final_day": sum(
            point.finance.revenue.total - point.finance.expenses.total
            for point in game.history
            if point.finance
        ),
    }


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=35)
    parser.add_argument("--difficulty", choices=DIFFICULTIES, default="standard")
    args = parser.parse_args()
    if args.days < 30:
        parser.error("Run at least 30 game days.")
    columns = (
        "revenue",
        "operating",
        "profit",
        "net",
        "growth",
        "satisfaction",
        "churn",
        "availability",
        "subscribers",
        "final_day",
    )
    print(f"{args.difficulty.title()}, {args.days} days, mean of seeds {SEEDS}")
    print(f"{'Strategy':<19}" + "".join(f"{column:>14}" for column in columns))
    for strategy in STRATEGIES:
        results = [
            simulate(strategy, seed, args.difficulty, args.days) for seed in SEEDS
        ]
        print(
            f"{strategy:<19}"
            + "".join(
                f"{mean(row[column] for row in results):>14.1f}" for column in columns
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
