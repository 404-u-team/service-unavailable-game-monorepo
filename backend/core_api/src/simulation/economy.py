from math import exp

from src.simulation.catalog import (
    ADVERTISING,
    BUSINESS,
    DAYS_PER_MONTH,
    REGIONS,
    TICKS_PER_DAY,
)
from src.simulation.demand import (
    SECONDS_PER_DAY,
    daily_active_users,
    premium_media_gain,
    product_settings,
    regional_audience,
)
from src.simulation.engine import Evaluation
from src.simulation.engineering import effective_topology
from src.simulation.models import (
    FinanceSample,
    Game,
    OperatingCosts,
    RevenueSources,
    SubscriptionTerm,
)
from src.simulation.topology import topology_cost

TERM_TICKS = DAYS_PER_MONTH * TICKS_PER_DAY
STEP_SECONDS = SECONDS_PER_DAY / TICKS_PER_DAY


def update_subscriptions(game: Game, quality: float, active_users: float) -> float:
    memory = BUSINESS["premium_reliability_memory_days"] * TICKS_PER_DAY
    game.premium_quality += (quality - game.premium_quality) / memory
    if game.tick % TICKS_PER_DAY:
        return 0
    expiring = [term for term in game.subscriptions if term.expires <= game.tick]
    game.subscriptions = [
        term for term in game.subscriptions if term.expires > game.tick
    ]
    if "premium" not in game.enabled_features:
        return 0

    product = product_settings(game)
    ad_free_value = (
        ADVERTISING[product.ad_intensity]["friction"]
        if "advertising" in game.enabled_features
        else 0
    )
    price_delta = product.premium_price - BUSINESS["premium_default_price"]
    price_factor = adoption_factor = population_weight = 0.0
    for region_id, population in regional_audience(game, game.audience):
        region = REGIONS[region_id]
        weight = daily_active_users(game, population, region)
        sensitivity = (
            BUSINESS["premium_price_sensitivity"] * region["price_sensitivity"]
        )
        price_response = exp(-sensitivity * price_delta)
        population_weight += weight
        price_factor += weight * price_response
        adoption_factor += weight * price_response * region["premium_adoption"]
    price_factor /= max(1, population_weight)
    adoption_factor /= max(1, population_weight)
    reliability = max(
        0,
        1
        - BUSINESS["premium_reliability_sensitivity"]
        * max(0, BUSINESS["premium_quality_floor"] - game.premium_quality),
    )
    benefits = (
        1 if product.premium_fast_sync else BUSINESS["premium_standard_adoption_factor"]
    )
    media_benefit = (
        BUSINESS["premium_media_adoption_multiplier"]
        if product.premium_high_quality_media and premium_media_gain(game, product)
        else 1
    )
    renewals = (
        sum(term.subscribers for term in expiring)
        * BUSINESS["premium_renewal"]
        * reliability
        * benefits
        * min(1, price_factor ** BUSINESS["premium_renewal_price_sensitivity"])
    )
    new_subscribers = (
        max(0, active_users - game.subscribers - renewals)
        * min(
            BUSINESS["premium_max_daily_adoption"],
            BUSINESS["premium_daily_adoption"]
            * adoption_factor
            * benefits
            * media_benefit
            * (1 + BUSINESS["premium_ad_free_adoption"] * ad_free_value),
        )
        * reliability
        * game.satisfaction
    )
    subscribers = renewals + new_subscribers
    if subscribers > 0:
        game.subscriptions.append(
            SubscriptionTerm(
                expires=game.tick + TERM_TICKS,
                subscribers=subscribers,
                price=product.premium_price,
                fast_sync=product.premium_fast_sync,
                high_quality_media=product.premium_high_quality_media,
            )
        )
    return subscribers * product.premium_price


def book_tick(
    game: Game, result: Evaluation, subscription_cash: float
) -> FinanceSample:
    impressions = result.ad_impressions_per_second * STEP_SECONDS
    revenue = RevenueSources(
        advertising=impressions * result.ad_value_per_impression,
        subscriptions=sum(term.subscribers * term.price for term in game.subscriptions)
        / TERM_TICKS,
    )
    expenses = OperatingCosts(
        infrastructure=topology_cost(effective_topology(game)) / TICKS_PER_DAY,
        traffic=result.snapshot.metrics.throughput
        * BUSINESS["traffic_cost_per_rps_day"]
        / TICKS_PER_DAY,
        payments=subscription_cash * BUSINESS["payments_fee"],
    )
    received = revenue.advertising + subscription_cash
    game.advertising_revenue += revenue.advertising
    game.subscription_revenue += revenue.subscriptions
    game.subscription_cash += subscription_cash
    game.infrastructure_spend += expenses.infrastructure
    game.traffic_spend += expenses.traffic
    game.payment_spend += expenses.payments
    game.revenue += revenue.total
    game.operating += expenses.total
    game.balance += received - expenses.total
    return FinanceSample(
        revenue=revenue,
        expenses=expenses,
        cash_received=received,
        daily_active_users=result.daily_active_users,
        ad_impressions=impressions,
        regional_ads={
            key: rate * STEP_SECONDS for key, rate in result.regional_ad_rates.items()
        },
    )
