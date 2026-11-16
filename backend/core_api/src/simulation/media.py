from dataclasses import dataclass

from src.simulation.catalog import (
    MEDIA_OPERATIONS,
    MEDIA_QUALITY,
    MINUTES_PER_TICK,
    OPERATIONS,
)
from src.simulation.engineering import data_growth_by_domain
from src.simulation.models import Game, PremiumMediaQuota, ProductSettings
from src.simulation.topology import config


def effective_quota(
    standard: float | None, premium: PremiumMediaQuota | None
) -> float | None:
    if standard is None or premium == "unlimited":
        return None
    return max(standard, premium) if premium is not None else standard


def media_populations(game: Game, audience: float) -> tuple[float, ...]:
    subscribers = game.subscribers
    subscriber_ratio = min(1, audience / subscribers) if subscribers else 1
    paid = tuple(term.subscribers * subscriber_ratio for term in game.subscriptions)
    return (max(0, audience - sum(paid)), *paid)


def stored_media(game: Game) -> tuple[float, ...]:
    if game.free_media_storage_gb is not None:
        return (
            game.free_media_storage_gb,
            *(term.media_storage_gb for term in game.subscriptions),
        )
    # Old saves store physical volume only. Apportion Shared data as in migration.
    growth = data_growth_by_domain(game)
    shared_fraction = growth.get("Media", 0) / max(sum(growth.values()), 1e-20)
    total = 0.0
    for node in game.production.nodes:
        if node.kind == "database":
            fraction = {"Shared": shared_fraction, "Media": 1}.get(
                config(node)["domain"], 0
            )
            total += game.storage.get(node.id, 0) * fraction
    if not game.audience:
        return (total, *(0.0 for _ in game.subscriptions))
    return tuple(
        total * users / game.audience for users in media_populations(game, game.audience)
    )


@dataclass
class MediaDemand:
    stored: tuple[float, ...]
    storage_shares: tuple[float, ...] = ()
    rate_factor: float = 1
    size_factor: float = 1
    cpu_factor: float = 1


def media_demand(
    game: Game,
    product: ProductSettings,
    operations: dict[str, float],
    audience: float,
    load_scale: float,
    *,
    enforce_quota: bool,
) -> MediaDemand:
    stored = stored_media(game)
    # Every cohort models users with the same mean usage. Admission conserves
    # the remaining bytes over the full tick, across all three media operations.
    upload_gb = (
        sum(
            operations.get(op, 0) * OPERATIONS[op]["storage"]
            for op in sorted(MEDIA_OPERATIONS)
        )
        * MINUTES_PER_TICK * 60 * load_scale
    )
    if not upload_gb or not audience:
        return MediaDemand(stored)

    standard = product.media_quota_gb
    quotas = (
        standard,
        *(effective_quota(standard, term.media_quota_gb) for term in game.subscriptions),
    )
    qualities = (
        product.media_quality,
        *(
            "high" if term.high_quality_media else product.media_quality
            for term in game.subscriptions
        ),
    )
    admitted = weighted_size = weighted_cpu = 0.0
    sizes = []
    for users, used, quota, quality in zip(
        media_populations(game, audience), stored, quotas, qualities
    ):
        factors = MEDIA_QUALITY[quality]
        demand = users / audience
        if enforce_quota and quota is not None:
            headroom = max(0, quota * users - used)
            demand = min(demand, headroom / (upload_gb * factors["size"]))
        admitted += demand
        size = demand * factors["size"]
        sizes.append(size)
        weighted_size += size
        weighted_cpu += demand * factors["cpu"]
    return MediaDemand(
        stored,
        tuple(size / weighted_size for size in sizes) if weighted_size else (),
        min(1, admitted),
        weighted_size / admitted if admitted else 1,
        weighted_cpu / admitted if admitted else 1,
    )
