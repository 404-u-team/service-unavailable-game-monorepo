from src.api.game_schemas import CampaignPlan, LanguageView, MarketView
from src.simulation.catalog import CAMPAIGNS, LANGUAGES, REGIONS
from src.simulation.demand import (
    active_markets,
    adoption,
    language_ready,
    regional_audience,
)
from src.simulation.models import Game, RegionalCampaign
from src.simulation.progression import spend
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
    game: Game, key: str, region: str, budget: float | None, duration: int | None
) -> CampaignPlan:
    if region not in active_markets(game):
        raise RuleError("Launch the target market before starting a campaign.")
    template = CAMPAIGNS[key]
    profile = REGIONS[region]
    budget = template["cost"] if budget is None else budget
    duration = template["duration"] if duration is None else duration
    population = dict(regional_audience(game, game.audience)).get(region, 0)
    capacity = max(0.0, profile["potential"] - population)
    acquired = min(
        capacity,
        budget
        * template["audience"]
        / template["cost"]
        * REGIONS["europe"]["acquisition_cost"]
        / profile["acquisition_cost"]
        * adoption(game, region),
    )
    return CampaignPlan(
        region=region,
        budget=budget,
        duration=duration,
        acquired=acquired,
        cost_per_user=budget / acquired if acquired else None,
    )


def targeted_campaign(game: Game, key: str, plan: CampaignPlan) -> None:
    if key in game.campaigns or key in game.regional_campaigns:
        raise RuleError("That campaign is already running.")
    if not plan.acquired:
        raise RuleError("This market has reached its audience potential.")
    spend(game, plan.budget, "marketing")
    game.regional_campaigns[key] = RegionalCampaign(
        region=plan.region,
        start=game.tick,
        duration=plan.duration,
        budget=plan.budget,
        audience=plan.acquired,
        spike=CAMPAIGNS[key]["spike"],
    )
