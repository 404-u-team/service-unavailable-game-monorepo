"""Portable game snapshots. Each supported version has its own loader."""

import json
import re
from datetime import UTC, datetime
from math import isclose, isfinite
from unicodedata import normalize

from pydantic import AwareDatetime, ValidationError

from src.api.game_schemas import SavePreview
from src.simulation.catalog import (
    BUSINESS,
    CAMPAIGNS,
    FEATURES,
    LANGUAGES,
    REGIONS,
    SCENARIOS,
)
from src.simulation.demand import MINUTES_PER_DAY, game_minute
from src.simulation.engineering import RESEARCH, architecture_errors, researched
from src.simulation.models import (
    DeploymentComparison,
    FinanceSample,
    Game,
    HistoryPoint,
    Incident,
    Metrics,
    Model,
    Onboarding,
    ProductSettings,
    RegionalCampaign,
    SubscriptionTerm,
)
from src.simulation.topology import RuleError, deployment_warnings, inspect_graph

FORMAT = "service-unavailable-save"
VERSION = 1
MAX_SAVE_BYTES = 8 * 1024 * 1024
INVALID = "This save file is incomplete or contains invalid game data."


class SaveFileV1(Model):
    format: str
    version: int
    exported_at: AwareDatetime | None
    game: Game

    def preview(self) -> SavePreview:
        game = self.game
        return SavePreview(
            name=game.name,
            scenario=game.scenario,
            day=game_minute(game) // MINUTES_PER_DAY + 1,
            audience=round(game.audience),
            balance=game.balance,
            version=self.version,
            exported_at=self.exported_at,
        )


def export_file(game: Game) -> tuple[str, SaveFileV1]:
    exported_at = datetime.now(UTC)
    ascii_name = normalize("NFKD", game.name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or game.scenario
    filename = f"service-unavailable-{slug}-{exported_at.date()}.json"
    return filename, SaveFileV1(
        format=FORMAT, version=VERSION, exported_at=exported_at, game=game
    )


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return result


def validate_scalars(value: object, depth: int = 0) -> None:
    if depth > 20:
        raise ValueError("Save is too deeply nested")
    if isinstance(value, dict):
        for key, item in value.items():
            validate_scalars(key, depth + 1)
            validate_scalars(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            validate_scalars(item, depth + 1)
    elif isinstance(value, str):
        # PostgreSQL JSONB rejects NUL and unpaired UTF-16 surrogates.
        if "\0" in value:
            raise ValueError("Invalid character")
        value.encode("utf-8")
    elif type(value) is float and (not isfinite(value) or abs(value) > 1e100):
        raise ValueError("Invalid number")
    elif type(value) is int and abs(value) > 2**63 - 1:
        raise ValueError("Integer outside supported range")


def require_complete(value: object) -> None:
    if isinstance(value, Model):
        allowed_omissions = set()
        if isinstance(value, Game):
            allowed_omissions = {
                "engineering",
                "autoscaling",
                "migration",
                "engineering_lesson",
            }
        elif isinstance(value, FinanceSample):
            allowed_omissions = {"regional_ads"}
        elif isinstance(value, Onboarding):
            allowed_omissions = {"step_id", "furthest_id"}
        elif isinstance(value, ProductSettings):
            allowed_omissions = {"premium_high_quality_media"}
        elif isinstance(value, SubscriptionTerm):
            allowed_omissions = {"high_quality_media"}
        elif isinstance(value, HistoryPoint):
            allowed_omissions = {"resource_utilization"}
        elif isinstance(value, Incident):
            allowed_omissions = {"cause"}
        elif isinstance(value, Metrics):
            allowed_omissions = {"p95_latency"}
        elif isinstance(value, DeploymentComparison):
            allowed_omissions = {"capacity_before", "capacity_after"}
        elif isinstance(value, RegionalCampaign):
            allowed_omissions = {"allocations"}
        if type(value).model_fields.keys() - value.model_fields_set - allowed_omissions:
            raise ValueError("Missing state fields")
        for _, item in value:
            require_complete(item)
    elif isinstance(value, list):
        for item in value:
            require_complete(item)
    elif isinstance(value, dict):
        for item in value.values():
            require_complete(item)


def validate_game(game: Game) -> None:
    # Bound the simulation date well inside datetime's range and keep SQL summary casts safe.
    if not (
        0 <= game.seed < 2**32
        and 0 <= game.tick <= 400_000_000
        and 0 <= game.start_minute < MINUTES_PER_DAY
        and game.revision >= 0
        and 0 <= game.tutorial <= 4
        and 0 <= game.satisfaction <= 1
        and 0 <= game.premium_quality <= 1
        and game.scenario in SCENARIOS
        and SCENARIOS[game.scenario]["available"]
    ):
        raise ValueError("Invalid simulation state")

    if not game.engineering.keys() <= RESEARCH.keys() or any(
        t < 0 for t in game.engineering.values()
    ):
        raise ValueError("Unknown engineering state")
    for key in game.engineering:
        if any(not researched(game, p) for p in RESEARCH[key]["prereq"]):
            raise ValueError("Invalid engineering prerequisites")
    graph = inspect_graph(game.production)
    if architecture_errors(game, graph, partial=True):
        raise ValueError("Unsupported architecture settings")
    if game.migration:
        if (
            game.migration.ready_at <= game.tick
            or game.migration.topology != game.draft
            or any(d.id == game.migration.request_id for d in game.deployments)
        ):
            raise ValueError("Invalid pending migration")
        if architecture_errors(game, inspect_graph(game.migration.topology)):
            raise ValueError("Invalid migration topology")
    if any(
        n.config.get("role", "Universal") != "Universal"
        or n.config.get("domain", "Shared") != "Shared"
        or n.config.get("partition", "Independent") != "Independent"
        for n in game.production.nodes
    ) and architecture_errors(game, graph):
        raise ValueError("Inconsistent data ownership")
    for node_id, state in game.autoscaling.items():
        if (
            node_id not in graph.nodes
            or graph.nodes[node_id].kind != "api"
            or state.changed_at > game.tick
        ):
            raise ValueError("Invalid autoscaling state")
    deployment_warnings(graph)
    if game.draft is not None:
        draft = inspect_graph(game.draft)
        if architecture_errors(game, draft, partial=True):
            raise ValueError("Unsupported draft settings")
        if any(
            node_id in graph.nodes and node.kind != graph.nodes[node_id].kind
            for node_id, node in draft.nodes.items()
        ):
            raise ValueError("Draft changes a component type")
    for deployment in game.deployments:
        deployment_warnings(inspect_graph(deployment.topology))

    # Diagram entries survive removals and drafts so that undo and rollback can reuse them.
    # Diagram itself validates IDs, positions, waypoints and nested group integrity.
    for values, kind in (
        (game.queues, "queue"),
        (game.storage, "database"),
        (game.replication, "replica"),
    ):
        if any(value < 0 for value in values.values()):
            raise ValueError("Negative component state")
        if any(
            node_id in graph.nodes and graph.nodes[node_id].kind != kind
            for node_id in values
        ):
            raise ValueError("Component state has the wrong type")

    if not (
        {"text"} <= set(game.released) <= FEATURES.keys()
        and set(game.infrastructure_releases) <= set(game.released)
        and game.disabled_features <= set(game.released) - {"text"}
        and game.development.keys() <= FEATURES.keys() - set(game.released)
        and game.campaigns.keys() <= CAMPAIGNS.keys()
        and game.regional_campaigns.keys() <= CAMPAIGNS.keys() - game.campaigns.keys()
        and game.launched_markets <= REGIONS.keys()
        and game.market_projects.keys() <= REGIONS.keys()
        and game.market_audience.keys() <= REGIONS.keys()
        and game.language_projects.keys() <= LANGUAGES.keys()
    ):
        raise ValueError("Unknown product or market state")
    if (
        game.product
        and not BUSINESS["premium_min_price"]
        <= game.product.premium_price
        <= BUSINESS["premium_max_price"]
    ):
        raise ValueError("Invalid product price")
    if (
        min(game.audience, game.north_america_audience, *game.market_audience.values())
        < 0
    ):
        raise ValueError("Negative audience")
    if any(
        term.expires < 0
        or term.subscribers < 0
        or not BUSINESS["premium_min_price"]
        <= term.price
        <= BUSINESS["premium_max_price"]
        for term in game.subscriptions
    ):
        raise ValueError("Invalid subscription")
    if any(
        plan.region not in REGIONS
        or not set(plan.allocations) <= REGIONS.keys()
        or (
            plan.allocations
            and (
                plan.region not in plan.allocations
                or not isclose(
                    plan.budget, sum(part.budget for part in plan.allocations.values())
                )
                or not isclose(
                    plan.audience,
                    sum(part.audience for part in plan.allocations.values()),
                )
            )
        )
        or not 1 <= plan.duration <= 288
        or not 0 <= plan.start <= game.tick
        or min(plan.budget, plan.audience, plan.spike) < 0
        for plan in game.regional_campaigns.values()
    ):
        raise ValueError("Invalid regional campaign")
    if any(not 0 <= start <= game.tick for start in game.campaigns.values()):
        raise ValueError("Invalid campaign start")
    for items, key in (
        (game.incidents, "start"),
        (game.history, "tick"),
        (game.deployments, "tick"),
    ):
        ticks = [getattr(item, key) for item in items]
        if ticks != sorted(ticks) or any(not 0 <= tick <= game.tick for tick in ticks):
            raise ValueError("Invalid history order")
    if (
        game.event_sequence < len(game.incidents)
        or len({item.id for item in game.incidents}) != len(game.incidents)
        or len({item.id for item in game.deployments}) != len(game.deployments)
        or any(
            item.end < item.start or not 0 < item.factor <= 10
            for item in game.incidents
        )
        or any(not 0 <= tick <= game.tick for tick in game.recent_purchases)
        or any(
            tick < 0
            for projects in (
                game.development,
                game.market_projects,
                game.language_projects,
            )
            for tick in projects.values()
        )
        or (game.onboarding and game.onboarding.step > game.onboarding.furthest)
    ):
        raise ValueError("Invalid event or project state")


def load_v1(data: dict) -> SaveFileV1:
    # Strict JSON keeps UUIDs, dates and sets in their portable representations.
    save = SaveFileV1.model_validate_json(json.dumps(data), strict=True)
    require_complete(save)
    validate_game(save.game)
    return save


LOADERS = {1: load_v1}


def parse_save_file(raw: bytes | bytearray) -> SaveFileV1:
    if len(raw) > MAX_SAVE_BYTES:
        raise RuleError(
            "The save file is larger than 8 MB.", code="save_file_too_large"
        )
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
        validate_scalars(data)
    except (ValueError, RecursionError) as error:
        raise RuleError(
            "The selected file is not a valid JSON save.", code="save_file_json"
        ) from error
    if (
        not isinstance(data, dict)
        or data.get("format") != FORMAT
        or type(data.get("version")) is not int
    ):
        raise RuleError(INVALID, code="save_file_invalid")
    loader = LOADERS.get(data["version"])
    if loader is None:
        raise RuleError(
            "This save file version is unsupported.", code="save_file_version"
        )
    try:
        return loader(data)
    except (ValidationError, ValueError) as error:
        raise RuleError(INVALID, code="save_file_invalid") from error
