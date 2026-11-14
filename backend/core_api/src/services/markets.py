from decimal import Decimal
from math import isfinite

from src.api.game_schemas import CampaignPlan, LanguageView, MarketView
from src.simulation.catalog import (
    CAMPAIGNS,
    LANGUAGES,
    REGION_LANGUAGE_WEIGHTS,
    REGION_LOCALIZATION_BONUS,
    REGIONS,
)
from src.simulation.demand import (
    active_markets,
    adoption,
    arrival_weight,
    language_ready,
    regional_audience,
)
from src.simulation.models import CampaignAllocation, Game, RegionalCampaign
from src.simulation.progression import add_event, spend
from src.simulation.topology import RuleError


def markets(game: Game) -> list[MarketView]:
    active = active_markets(game)
    return [
        MarketView(
            id=key,
            name=profile["name"],
            population=profile["population"],
            potential=profile["potential"],
            language=profile["language"],
            language_weights=REGION_LANGUAGE_WEIGHTS[key],
            language_benefits={
                name: weight * REGION_LOCALIZATION_BONUS
                for name, weight in REGION_LANGUAGE_WEIGHTS[key].items()
                if name != "English"
            },
            cost=profile["cost"],
            duration=profile["duration"],
            remaining=max(0, game.market_projects.get(key, 0) - game.tick),
            stage=(
                "active"
                if key in active
                else "planned"
                if key not in game.market_projects
                else "developing"
                if game.market_projects[key] > game.tick
                else "ready"
            ),
        )
        for key, profile in REGIONS.items()
    ]


def languages(game: Game) -> list[LanguageView]:
    return [
        LanguageView(
            name=name,
            cost=cost,
            duration=duration,
            ready=language_ready(game, name),
            remaining=max(0, game.language_projects.get(name, 0) - game.tick),
        )
        for name, (cost, duration) in {"English": (0, 0), **LANGUAGES}.items()
    ]


def market_action(game: Game, key: str, action: str) -> None:
    if key not in REGIONS or key in active_markets(game):
        raise RuleError("This market is unavailable for expansion.")
    profile = REGIONS[key]
    if action == "develop" and key not in game.market_projects:
        spend(game, profile["cost"], "development")
        game.market_projects[key] = game.tick + profile["duration"]
    elif (
        action == "launch" and game.market_projects.get(key, game.tick + 1) <= game.tick
    ):
        if game.satisfaction < 0.65:
            raise RuleError("Restore service satisfaction to 65% before launching.")
        game.launched_markets.add(key)
    else:
        raise RuleError("This market is not ready for that action.")


def develop_language(game: Game, name: str) -> None:
    if name not in LANGUAGES or name in game.language_projects:
        raise RuleError("This language is unavailable for development.")
    cost, duration = LANGUAGES[name]
    spend(game, cost, "development")
    game.language_projects[name] = game.tick + duration


def campaign_plan(
    game: Game,
    key: str,
    region: str | list[str],
    budget: float | None,
    duration: int | None,
) -> CampaignPlan:
    regions = [region] if isinstance(region, str) else region
    if not regions or len(set(regions)) != len(regions):
        raise RuleError("Select distinct target markets.")
    if not set(regions) <= active_markets(game):
        raise RuleError("Launch the target market before starting a campaign.")
    template = CAMPAIGNS[key]
    budget = template["cost"] if budget is None else budget
    duration = template["duration"] if duration is None else duration
    if not isfinite(budget) or not 10 <= budget <= 100_000 or not 1 <= duration <= 288:
        raise RuleError("Enter a valid budget and duration to see the forecast.")
    cents = round(Decimal(str(budget)) * 100)
    share, remainder = divmod(cents, len(regions))
    populations = dict(regional_audience(game, game.audience))
    allocations = {}
    for index, target in enumerate(sorted(regions)):
        allocation = (share + int(index < remainder)) / 100
        profile = REGIONS[target]
        capacity = max(0.0, profile["potential"] - populations.get(target, 0))
        acquired = min(
            capacity,
            allocation
            * template["audience"]
            / template["cost"]
            * REGIONS["europe"]["acquisition_cost"]
            / profile["acquisition_cost"]
            * adoption(game, target),
        )
        if not acquired:
            raise RuleError("A selected market has reached its audience potential.")
        allocations[target] = CampaignAllocation(budget=allocation, audience=acquired)
    acquired = sum(part.audience for part in allocations.values())
    budget = cents / 100
    return CampaignPlan(
        region=regions[0],
        allocations=allocations,
        arrivals=[
            acquired * arrival_weight(step, duration) for step in range(1, duration + 1)
        ],
        budget=budget,
        duration=duration,
        acquired=acquired,
        cost_per_user=budget / acquired,
    )


def campaign_state(game: Game, key: str, plan: CampaignPlan) -> RegionalCampaign:
    return RegionalCampaign(
        region=plan.region,
        allocations=plan.allocations,
        start=game.tick,
        duration=plan.duration,
        budget=plan.budget,
        audience=plan.acquired,
        spike=CAMPAIGNS[key]["spike"],
    )


def targeted_campaign(game: Game, key: str, plan: CampaignPlan) -> None:
    if key in game.campaigns or key in game.regional_campaigns:
        raise RuleError("That campaign is already running.")
    spend(game, plan.budget, "marketing")
    game.regional_campaigns[key] = campaign_state(game, key, plan)
    add_event(
        game,
        "campaign",
        f"{CAMPAIGNS[key]['name']} campaign started",
        "Acquisition will increase request volume.",
        "info",
        0,
    )
