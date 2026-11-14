from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from math import pi, sin
from zoneinfo import ZoneInfo

from src.simulation.catalog import (
    ADVERTISING,
    BUSINESS,
    CAMPAIGNS,
    FEATURES,
    MINUTES_PER_TICK,
    OPERATIONS,
    REGIONS,
    SCENARIOS,
    SYNC_FREQUENCY,
    TICKS_PER_DAY,
)
from src.simulation.models import (
    AdIntensity,
    DemandOverview,
    Game,
    ProductSettings,
    RegionDemand,
)

MINUTES_PER_DAY = 24 * 60
SECONDS_PER_DAY = MINUTES_PER_DAY * 60


def product_settings(game: Game) -> ProductSettings:
    return game.product or ProductSettings(
        premium_price=BUSINESS["premium_default_price"]
    )


def active_incidents(game: Game):
    return (
        event
        for event in game.incidents
        if event.start <= game.tick < event.end and event.resolution is None
    )


def campaign_weight(progress: float) -> float:
    return 4 * progress * (1 - progress) if 0 < progress < 1 else 0


def game_minute(game: Game) -> int:
    return game.start_minute + game.tick * MINUTES_PER_TICK


def active_markets(game: Game) -> set[str]:
    active = {"europe"} | game.launched_markets
    if product_settings(game).north_america:
        active.add("north_america")
    return active


def language_ready(game: Game, language: str) -> bool:
    return (
        language == "English"
        or game.language_projects.get(language, game.tick + 1) <= game.tick
    )


def adoption(game: Game, region: str) -> float:
    return (
        1.18
        if language_ready(game, REGIONS[region]["language"])
        and REGIONS[region]["language"] != "English"
        else 1.0
    )


def regional_audience(game: Game, audience: float) -> list[tuple[str, float]]:
    populations = {**game.market_audience, "north_america": game.north_america_audience}
    markets = active_markets(game)
    regional_total = sum(populations.values())
    denominator = max(1, game.audience, regional_total)
    return [
        (
            key,
            audience
            * (
                max(0, 1 - regional_total / denominator)
                if key == "europe"
                else populations.get(key, 0) / denominator
            ),
        )
        for key in REGIONS
        if key in markets or populations.get(key, 0) > 0
    ]


def acquire(game: Game, region: str, users: float) -> None:
    game.audience += users
    if region == "north_america":
        game.north_america_audience += users
    elif region != "europe":
        game.market_audience[region] = game.market_audience.get(region, 0) + users


GAME_EPOCH = datetime(2025, 1, 6, tzinfo=UTC)


@lru_cache(maxsize=4096)
def local_time(zone: str, utc_minute: int) -> tuple[int, int, int]:
    local = (GAME_EPOCH + timedelta(minutes=utc_minute)).astimezone(ZoneInfo(zone))
    offset = local.utcoffset()
    return (
        local.weekday(),
        local.hour * 60 + local.minute,
        int(offset.total_seconds() / 60) if offset else 0,
    )


def activity(region: dict, utc_minute: int) -> float:
    day, minute, _ = local_time(region["timezone"], utc_minute)
    index, fraction = divmod(minute / 180, 1)
    anchors = region["profile"]
    left, right = anchors[int(index)], anchors[(int(index) + 1) % len(anchors)]
    weight = fraction * fraction * (3 - 2 * fraction)
    # Fade the weekend adjustment in and out over local nighttime.
    weekend = day % 7 in (5, 6)
    start = day % 7 == 5 and minute < 360
    end = day % 7 == 6 and minute >= 1080
    weekend_weight = (
        minute / 360 if start else (1440 - minute) / 360 if end else int(weekend)
    )
    return (left + (right - left) * weight) * (
        1 + (region["weekend"] - 1) * weekend_weight
    )


def daily_active_users(game: Game, population: float, region: dict) -> float:
    return population * min(
        1,
        BUSINESS["active_share"]
        * region["engagement"]
        * (0.60 + 0.40 * game.satisfaction),
    )


@dataclass
class AdForecast:
    requests_per_day: float
    value_per_day: float
    friction: float
    additional_churn: float


def free_share(game: Game) -> float:
    return max(0, 1 - game.subscribers / max(1, game.audience))


def filled_impressions(active: float, params: dict) -> float:
    return (
        active
        * BUSINESS["sessions_per_dau"]
        * (1 - params["friction"])
        * params["slots"]
        * params["fill"]
    )


def ad_forecast(game: Game, intensity: AdIntensity) -> AdForecast:
    eligible_share = free_share(game)
    params = ADVERTISING[intensity]
    impressions = value = 0.0
    for region_id, population in regional_audience(game, game.audience):
        region = REGIONS[region_id]
        active = daily_active_users(game, population, region) * eligible_share
        filled = filled_impressions(active, params)
        impressions += filled
        value += filled * params["cpm"] * region["ad_value"] / 1000
    return AdForecast(
        impressions,
        value,
        params["friction"] * eligible_share,
        params["churn"] * eligible_share,
    )


@dataclass
class Demand:
    operations: dict[str, float]
    active_users: float
    ad_value_per_impression: float
    overview: DemandOverview | None
    regional_ad_rates: dict[str, float]


def workload(
    game: Game,
    audience: float | None = None,
    boost: float = 0,
    *,
    overview: bool = False,
) -> Demand:
    scenario = SCENARIOS[game.scenario]
    users = game.audience if audience is None else audience
    product = product_settings(game)
    enabled = game.enabled_features
    ad_params = ADVERTISING[product.ad_intensity] if "advertising" in enabled else None
    eligible_share = free_share(game) if ad_params else 0
    base_rates = {
        key: OPERATIONS[key]["rate"]
        for key in dict.fromkeys(
            [
                *scenario["operations"],
                *(
                    FEATURES[key]["operation"]
                    for key in sorted(enabled)
                    if FEATURES[key]["operation"] and key != "advertising"
                ),
            ]
        )
    }
    fast_subscribers = sum(
        term.subscribers for term in game.subscriptions if term.fast_sync
    )
    premium_share = min(1, fast_subscribers / max(1, game.audience))
    sync = SYNC_FREQUENCY[product.sync_frequency]["load"] * (
        1 + premium_share * (BUSINESS["premium_sync_multiplier"] - 1)
    )
    for key in ("history", "conversations", "connection"):
        if key in base_rates:
            base_rates[key] *= sync
    # Ad-heavy sessions generate fewer application requests.
    friction = ad_params["friction"] * eligible_share if ad_params else 0
    engagement = (0.82 + 0.18 * game.satisfaction) * (1 - friction * 0.55)
    legacy_campaign = sum(
        CAMPAIGNS[key]["spike"]
        * campaign_weight((game.tick - start) / CAMPAIGNS[key]["duration"])
        for key, start in game.campaigns.items()
    )
    event = sum(
        incident.factor - 1
        for incident in active_incidents(game)
        if incident.kind == "spike"
    )
    # Smooth seeded variation gives days different shapes without per-tick jitter.
    noise = 1 + 0.025 * sin(game.seed + game.tick * 2 * pi / (TICKS_PER_DAY * 2.7))
    utc_minute = game_minute(game)
    regions = regional_audience(game, users)
    population_activity = active = ad_rate = ad_value = campaign_requests = (
        baseline_requests
    ) = 0.0
    regional_details = []
    regional_ad_rates: dict[str, float] = {}
    expected = [0.0] * 25 if overview else []
    base_rps = sum(base_rates.values()) * engagement * scenario["activity"]
    weekday_start = utc_minute - utc_minute % MINUTES_PER_DAY
    for region_id, population in regions:
        region = REGIONS[region_id]
        profile = activity(region, utc_minute)
        targeted = sum(
            plan.spike * campaign_weight((game.tick - plan.start) / plan.duration)
            for plan in game.regional_campaigns.values()
            if plan.region == region_id
        )
        regional_lift = 1 + targeted + legacy_campaign + event + boost
        audience_activity = population * profile * regional_lift
        active_users = daily_active_users(game, population, region)
        population_activity += audience_activity
        active += active_users
        region_ads = daily_ad_revenue = 0.0
        if ad_params:
            mean_profile = sum(region["profile"]) / len(region["profile"])
            price = ad_params["cpm"] * region["ad_value"] / 1000
            daily_impressions = filled_impressions(
                active_users * eligible_share, ad_params
            )
            region_ads = daily_impressions / SECONDS_PER_DAY / mean_profile
            requested_ads = region_ads * profile * regional_lift
            regional_ad_rates[region_id] = requested_ads * price * noise
            daily_ad_revenue = daily_impressions * price
            ad_rate += requested_ads
            ad_value += requested_ads * price
        baseline = profile * (base_rps * population + region_ads)
        baseline_requests += baseline
        campaign_requests += baseline * targeted
        if overview:
            _, local_minute, offset = local_time(region["timezone"], utc_minute)
            regional_details.append(
                RegionDemand(
                    id=region_id,
                    name=region["name"],
                    utc_offset=offset,
                    local_minute=local_minute,
                    audience=round(population),
                    daily_active_users=active_users,
                    requests=baseline * noise * regional_lift,
                    daily_ad_revenue=daily_ad_revenue,
                )
            )
            for hour in range(len(expected)):
                expected[hour] += (base_rps * population + region_ads) * activity(
                    region, weekday_start + hour * 60
                )

    operations = {
        key: rate * population_activity * engagement * scenario["activity"] * noise
        for key, rate in base_rates.items()
    }
    if ad_params:
        operations["ad"] = ad_rate * noise
    return Demand(
        operations,
        active,
        ad_value / ad_rate if ad_rate else 0,
        DemandOverview(
            day=utc_minute // MINUTES_PER_DAY + 1,
            utc_minute=utc_minute % MINUTES_PER_DAY,
            regions=regional_details,
            expected=expected,
            campaign_lift=legacy_campaign
            + (campaign_requests / baseline_requests if baseline_requests else 0),
            event_lift=event,
        )
        if overview
        else None,
        regional_ad_rates,
    )
