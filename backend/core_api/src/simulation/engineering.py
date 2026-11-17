"""Architectural capabilities and topology changes.

Domains partition existing operations, never multiply external traffic. Conversation
partitions use 128 stable virtual keys with a 12% hot conversation cohort.
"""

from collections import defaultdict
from functools import lru_cache
from hashlib import sha256
from math import ceil

from src.simulation.models import Edge, Game, Node, Topology
from src.simulation.topology import Graph, RuleError, config, daily_cost, inspect_graph

RESEARCH = {
    "object_storage": {
        "name": "Object Storage",
        "cost": 1600,
        "duration": 36,
        "prereq": [],
        "description": "Store media bytes separately from attachment metadata.",
        "unlocks": "Object Storage for Universal and Media APIs.",
        "advantages": "Large attachments use object capacity and leave space in the database.",
        "tradeoffs": "The API still transfers files. Copying old attachments consumes database resources.",
        "guide": "object_storage",
    },
    "decomposition": {
        "name": "Service Decomposition",
        "cost": 1800,
        "duration": 36,
        "prereq": [],
        "description": "Unlock independently configured Messaging, Accounts, Media and Search APIs.",
        "unlocks": "API service roles and explicit identity service dependencies.",
        "advantages": "Scale and isolate the operations that need capacity.",
        "tradeoffs": "Specialized APIs add 6% compute and network work, identity calls and extra infrastructure.",
        "guide": "service-decomposition",
    },
    "domains": {
        "name": "Domain Data Separation",
        "cost": 2600,
        "duration": 48,
        "prereq": ["decomposition"],
        "description": "Assign independent primaries to Messages, Accounts, Media and Search data.",
        "unlocks": "Database data domains and planned data migration.",
        "advantages": "Move each operation's actual data demand to its owning database.",
        "tradeoffs": "Each domain needs consistent ownership. Moving data takes time, money and spare storage.",
        "guide": "data-domains",
    },
    "queries": {
        "name": "Database Query Optimization",
        "cost": 2100,
        "duration": 42,
        "prereq": [],
        "description": "Use covering indexes for history and conversation-list reads.",
        "unlocks": "Optional History indexes on each primary and its replicas.",
        "advantages": "History read work falls 35%; conversation-list read work falls 20%.",
        "tradeoffs": "Message and group writes add 10% index-maintenance work. Other operations are unchanged.",
        "guide": "query-optimization",
    },
    "sharding": {
        "name": "Database Sharding",
        "cost": 6200,
        "duration": 96,
        "prereq": ["domains"],
        "description": "Partition one logical data domain across finite independent primaries.",
        "unlocks": "Shard routers and partition membership on primary databases.",
        "advantages": "Spread reads and writes beyond one primary's resource ceiling.",
        "tradeoffs": "Routing adds compute and latency. Hot conversations, partial failures and paid rebalancing remain.",
        "guide": "database-sharding",
    },
    "autoscaling": {
        "name": "API Autoscaling",
        "cost": 3200,
        "duration": 54,
        "prereq": ["decomposition"],
        "description": "Adjust API instances within configured bounds using observed utilization.",
        "unlocks": "Minimum, maximum and utilization target per API service group.",
        "advantages": "Add capacity during demand peaks and release it after cooldown.",
        "tradeoffs": "Requires monitoring, reacts after two ticks, waits three ticks between changes, and charges every active instance.",
        "guide": "api-autoscaling",
    },
}

DOMAINS = {
    "send": "Messages",
    "history": "Messages",
    "conversations": "Messages",
    "connection": "Messages",
    "groups": "Messages",
    "calls": "Messages",
    "ad": "Messages",
    "auth": "Accounts",
    "identity": "Accounts",
    "upload": "Media",
    "voice": "Media",
    "files": "Media",
    "download": "Media",
    "search": "Search",
}
ROLES = {
    "Universal": set(DOMAINS),
    **{
        role: {op for op, domain in DOMAINS.items() if domain == role}
        for role in ("Messages", "Accounts", "Media", "Search")
    },
}


def researched(game: Game, key: str) -> bool:
    return key in game.engineering and game.engineering[key] <= game.tick


def supports(node, operation: str) -> bool:
    return operation in ROLES[config(node).get("role", "Universal")]


def data_targets(graph: Graph, api: str, operation: str) -> list[str]:
    primaries = graph.primaries(api)
    explicit = [
        p
        for p in primaries
        if config(graph.nodes[p])["domain"] == DOMAINS.get(operation)
    ]
    candidates = explicit or [
        p for p in primaries if config(graph.nodes[p])["domain"] == "Shared"
    ]
    if not candidates:
        return []
    # Legacy shared links keep their original first-primary behavior.
    if all(config(graph.nodes[p])["partition"] == "Independent" for p in candidates):
        return candidates[:1]
    return candidates


SHARD_KEYS = 128
MIGRATION_PACES = {"gentle": 0.5, "normal": 1.0, "fast": 2.0, "paused": 0.0}


@lru_cache(maxsize=8)
def key_hashes(domain: str) -> tuple[int, ...]:
    return tuple(
        int.from_bytes(sha256(f"{domain}:{key}".encode()).digest()[:4], "big")
        for key in range(SHARD_KEYS)
    )


def key_weight(key: int) -> float:
    return 0.12 if key == 0 else 0.88 / (SHARD_KEYS - 1)


def key_owners(
    domain: str, targets: list[str], overrides: dict[int, str] | None = None
) -> list[str]:
    if not targets:
        return []
    overrides = overrides or {}
    return [
        overrides.get(key, targets[digest % len(targets)])
        for key, digest in enumerate(key_hashes(domain))
    ]


def partition_weights(
    domain: str, targets: list[str], overrides: dict[int, str] | None = None
) -> list[float]:
    weights = dict.fromkeys(targets, 0.0)
    for key, owner in enumerate(key_owners(domain, targets, overrides)):
        weights[owner] += key_weight(key)
    return [weights[p] for p in targets]


def shard_assignments(topology: Topology) -> dict[str, list[str]]:
    graph = inspect_graph(topology)
    return {
        node.id: key_owners(
            config(node)["domain"],
            graph.primaries(node.id),
            graph.shard_owners.get(node.id),
        )
        for node in topology.nodes
        if node.kind == "shard_router"
    }


def domain_overrides(graph: Graph, domain: str) -> dict[int, str]:
    apis = request_apis(graph)
    return next(
        (
            graph.shard_owners.get(n.id, {})
            for n in graph.nodes.values()
            if n.kind == "shard_router"
            and config(n)["domain"] == domain
            and any(n.id in graph.targets[api] for api in apis)
        ),
        {},
    )


def object_target(graph: Graph, api: str) -> str | None:
    return next(
        (t for t in graph.targets[api] if graph.nodes[t].kind == "object_storage"), None
    )


def object_destination(graph: Graph) -> str | None:
    return next(
        (
            target
            for api in sorted(request_apis(graph))
            if (target := object_target(graph, api))
        ),
        None,
    )


def physical_media(game: Game, graph: Graph | None = None) -> dict[str, float]:
    if game.media_by_node is not None:
        return dict(game.media_by_node)
    graph = graph or inspect_graph(game.production)
    growth = data_growth_by_domain(game)
    fraction = growth.get("Media", 0) / max(sum(growth.values()), 1e-20)
    return {
        node.id: volume
        for node in graph.nodes.values()
        if node.kind in {"database", "object_storage"}
        and (
            volume := game.storage.get(node.id, 0)
            * (
                1
                if node.kind == "object_storage"
                else {"Shared": fraction, "Media": 1}.get(config(node)["domain"], 0)
            )
        )
        > 0
    }


def media_moves(game: Game, candidate: Topology) -> tuple[str | None, dict[str, float]]:
    target = object_destination(inspect_graph(candidate))
    sources = {
        n: gb for n, gb in physical_media(game).items() if n != target and gb > 0
    }
    if not target:
        old = inspect_graph(game.production)
        if any(
            old.nodes.get(n) and old.nodes[n].kind == "object_storage" for n in sources
        ):
            raise RuleError(
                "Connect an Object Storage destination for the stored attachments."
            )
        return None, {}
    return target, sources


def migration_object(game: Game) -> Node:
    pending = game.migration
    target = next(
        node for node in pending.topology.nodes if node.id == pending.media_target
    )
    live = next((node for node in game.production.nodes if node.id == target.id), None)
    if live is None:
        return target
    settings = config(target)
    return target.model_copy(
        update={
            "config": {
                field: max(config(live)[field], capacity)
                for field, capacity in settings.items()
            }
        }
    )


def migration_topology(game: Game) -> Topology:
    pending = game.migration
    if pending is None or pending.media_target is None:
        return game.production
    node = migration_object(game)
    nodes = [n if n.id != node.id else node for n in game.production.nodes]
    if all(n.id != node.id for n in nodes):
        nodes.append(node)
    graph = inspect_graph(game.production)
    edges = list(game.production.edges)
    edges.extend(
        Edge(source=api, target=node.id)
        for api in sorted(request_apis(graph))
        if config(graph.nodes[api])["role"] in {"Universal", "Media"}
        and node.id not in graph.targets[api]
    )
    return game.production.model_copy(update={"nodes": nodes, "edges": edges})


def request_apis(graph: Graph) -> set[str]:
    reachable = {"traffic"}
    for node_id in graph.order:
        if node_id in reachable:
            reachable.update(
                t
                for t in graph.targets[node_id]
                if graph.relationships[node_id, t] == "request"
            )
    return {n for n in reachable if graph.nodes[n].kind == "api"}


def specialization_errors(graph: Graph) -> list[str]:
    domains = {
        config(n)["domain"] for n in graph.nodes.values() if n.kind == "database"
    }
    roles = {config(n)["role"] for n in graph.nodes.values() if n.kind == "api"}
    errors = []
    if "Shared" in domains and len(domains) > 1:
        errors.append(
            "Use either shared databases or domain databases throughout the topology."
        )
    if "Universal" in roles and len(roles) > 1:
        errors.append(
            "Use either Universal APIs or specialized APIs throughout the topology."
        )
    return errors


def architecture_errors(
    game: Game, graph: Graph, *, partial: bool = False
) -> list[str]:
    errors = []
    for node in graph.nodes.values():
        cfg = config(node)
        if node.kind == "object_storage" and not researched(game, "object_storage"):
            errors.append(
                "Complete Object Storage research before adding this component."
            )
        if node.kind == "shard_router" and not researched(game, "sharding"):
            errors.append(
                "Complete Database Sharding research before using a shard router."
            )
        for field, key, default in (
            ("role", "decomposition", "Universal"),
            ("domain", "domains", "Shared"),
            ("partition", "sharding", "Independent"),
            ("query_plan", "queries", "Standard"),
            ("autoscale", "autoscaling", "Disabled"),
        ):
            if cfg.get(field, default) != default and not researched(game, key):
                errors.append(
                    "Complete the required Engineering research before using this setting."
                )
        if cfg.get("partition") == "Partition" and cfg.get("domain") == "Shared":
            errors.append(
                "Assign a specific data domain before configuring partitions."
            )
        if (
            cfg.get("autoscale") == "Enabled"
            and cfg["min_instances"] > cfg["max_instances"]
        ):
            errors.append("Autoscaling minimum must not exceed its maximum.")
    if partial:
        return list(dict.fromkeys(errors))
    for node in graph.nodes.values():
        if node.kind == "shard_router":
            primaries = [graph.nodes[p] for p in graph.primaries(node.id)]
            if len(primaries) < 2 or any(
                config(primary)["partition"] != "Partition"
                or config(primary)["domain"] != config(node)["domain"]
                for primary in primaries
            ):
                errors.append(
                    "Connect each shard router to at least two primary partitions of its data domain."
                )
        elif node.kind == "api":
            router_domains = [
                config(graph.nodes[t])["domain"]
                for t in graph.targets[node.id]
                if graph.nodes[t].kind == "shard_router"
            ]
            if len(router_domains) != len(set(router_domains)) or any(
                graph.nodes[t].kind == "database"
                and config(graph.nodes[t])["domain"] in router_domains
                for t in graph.targets[node.id]
            ):
                errors.append(
                    "Connect each API to one shard router per domain and "
                    "remove its direct links to that domain's primaries."
                )
    media_apis = [
        api
        for api in sorted(request_apis(graph))
        if config(graph.nodes[api])["role"] in {"Universal", "Media"}
    ]
    if (
        any(
            sum(graph.nodes[t].kind == "object_storage" for t in graph.targets[api]) > 1
            for api in media_apis
        )
        or len({object_target(graph, api) for api in media_apis}) > 1
    ):
        errors.append("Media APIs must share the same storage destination.")
    from src.simulation.demand import workload

    operations = workload(game, enforce_media_quota=False).operations
    apis = [graph.nodes[n] for n in sorted(request_apis(graph))]
    owners = defaultdict(set)
    key_maps = defaultdict(set)
    for op, rate in operations.items():
        if not rate:
            continue
        capable = [n for n in apis if supports(n, op)]
        if not capable:
            errors.append(
                "A required operation has no connected API service. Connect an API that handles this operation."
            )
        for api in capable:
            primaries = data_targets(graph, api.id, op)
            if not primaries and DOMAINS.get(op):
                errors.append(
                    "An API is missing its operation's data domain. Connect the owning primary or all its partitions."
                )
            owners[DOMAINS[op]].add(tuple(primaries))
            if len(primaries) > 1 and any(
                config(graph.nodes[p])["partition"] != "Partition" for p in primaries
            ):
                errors.append(
                    "Multiple primaries for one domain must all be explicit partitions."
                )
            if config(api)["role"] not in {"Universal", "Accounts"} and not any(
                graph.nodes[t].kind == "api"
                and config(graph.nodes[t])["role"] == "Accounts"
                for t in graph.targets[api.id]
            ):
                errors.append(
                    "Connect each specialized service to an Accounts API for identity checks."
                )
    # Identity-only Accounts pools own the same account data as externally
    # routed authentication pools, even when a Universal API handles auth.
    for (source, target), relationship in graph.relationships.items():
        if relationship != "identity" or source not in graph.reachable:
            continue
        primaries = data_targets(graph, target, "identity")
        owners["Accounts"].add(tuple(primaries))
        if not primaries:
            errors.append(
                "An API is missing its operation's data domain. Connect the owning primary or all its partitions."
            )
    if any(len(sets) > 1 for sets in owners.values()):
        errors.append(
            "APIs handling the same domain must use the same primary or the same complete partition set."
        )
    for api in apis:
        routes = graph.primary_routes(api.id)
        for domain in sorted(set(DOMAINS.values())):
            operation = next(op for op, name in DOMAINS.items() if name == domain)
            if not supports(api, operation):
                continue
            primaries = data_targets(graph, api.id, operation)
            if len(primaries) > 1:
                key_maps[domain].add(
                    tuple(
                        key_owners(
                            domain,
                            primaries,
                            graph.shard_owners.get(routes[primaries[0]]),
                        )
                    )
                )
    if any(len(maps) > 1 for maps in key_maps.values()):
        errors.append(
            "APIs handling one data domain must share the same shard key map."
        )
    # Independent links cannot silently turn into synchronized copies.
    for api in apis:
        by_domain = defaultdict(list)
        for p in graph.primaries(api.id):
            by_domain[config(graph.nodes[p])["domain"]].append(p)
        if any(
            len(ps) > 1
            and any(config(graph.nodes[p])["partition"] != "Partition" for p in ps)
            for ps in by_domain.values()
        ):
            errors.append(
                "Multiple primaries for one domain must all be explicit partitions."
            )
    return list(dict.fromkeys(errors))


def ownership(topology: Topology) -> dict[str, tuple[str, ...]]:
    graph = inspect_graph(topology)
    return {
        domain: tuple(
            sorted(
                {
                    p
                    for n in graph.nodes.values()
                    if n.kind == "api" and n.id in graph.reachable
                    for op, d in DOMAINS.items()
                    if d == domain and supports(n, op)
                    for p in data_targets(graph, n.id, op)
                }
            )
        )
        for domain in sorted(set(DOMAINS.values()))
    }


def database_transfers(
    game: Game, topology: Topology, *, moving_media: bool = False
) -> tuple[dict[str, float], set[str]]:
    before, after = ownership(game.production), ownership(topology)
    old, new = inspect_graph(game.production), inspect_graph(topology)
    growth = data_growth_by_domain(game)
    physical = physical_media(game) if moving_media else {}
    sources: dict[str, float] = defaultdict(float)
    destinations = set()
    for domain, primaries in before.items():
        if not primaries:
            continue
        old_keys = key_owners(domain, list(primaries), domain_overrides(old, domain))
        new_keys = key_owners(
            domain, list(after[domain]), domain_overrides(new, domain)
        )
        if old_keys == new_keys:
            continue
        destinations.update(after[domain])
        for primary in primaries:
            stored = max(0, game.storage.get(primary, 0) - physical.get(primary, 0))
            owned_growth = sum(
                growth[d] for d, owners in before.items() if primary in owners
            )
            domain_share = growth[domain] / owned_growth if owned_growth else 1
            keys = [key for key, owner in enumerate(old_keys) if owner == primary]
            old_weight = sum(key_weight(key) for key in keys)
            moved = sum(
                key_weight(key)
                for key in keys
                if not new_keys or new_keys[key] != primary
            )
            sources[primary] += (
                stored * domain_share * (moved / old_weight if old_weight else 0)
            )
    return dict(sources), destinations


def migration_plan(
    game: Game, topology: Topology, sources: dict[str, float] | None = None
) -> tuple[int, float]:
    target, media = media_moves(game, topology)
    database, destinations = database_transfers(
        game, topology, moving_media=bool(target)
    )
    if sources is not None:
        sources.update(database)
    if not database and not media:
        return 0, 0
    nodes = {n.id: n for n in topology.nodes}
    speed = min([4.0, *(float(config(nodes[p])["cpu"]) for p in sorted(destinations))])
    stored = sum(database.values())
    media_volume = sum(media.values())
    media_speed = object_copy_speed(nodes[target]) if target and media else 1
    duration = max(3, ceil(stored / max(1, speed)), ceil(media_volume / media_speed))
    cost = round(
        120
        + (stored + media_volume) * 4
        + sum(daily_cost(nodes[p]) for p in sorted(destinations)) * duration / 144,
        2,
    )
    return duration, cost


def object_copy_speed(node: Node) -> float:
    from src.simulation.database import SECONDS_PER_STEP

    return min(4.0, 0.25 * config(node)["network"] * SECONDS_PER_STEP / 1000)


def data_growth_by_domain(game: Game) -> dict[str, float]:
    from src.simulation.catalog import FEATURES, OPERATIONS, SCENARIOS

    operations = set(SCENARIOS[game.scenario]["operations"]) | {
        FEATURES[f]["operation"] for f in game.released if FEATURES[f]["operation"]
    }
    growth = defaultdict(float)
    # Disabled features retain their data.
    for op in sorted(operations):
        operation = OPERATIONS[op]
        growth[DOMAINS[op]] += operation["rate"] * max(
            operation["storage"], operation["write"] * 0.00000001
        )
    return growth


def place_domain(
    domain: str,
    by_source: dict[str, float],
    targets: list[str],
    previous: list[str],
    before: Graph,
    after: Graph,
) -> dict[str, float]:
    old_keys = key_owners(domain, previous, domain_overrides(before, domain))
    new_keys = key_owners(domain, targets, domain_overrides(after, domain))
    volumes: dict[str, float] = defaultdict(float)
    for source, volume in sorted(by_source.items()):
        if not volume:
            continue
        if not targets:
            raise RuleError("A migration must retain a destination for stored data.")
        keys = [key for key, owner in enumerate(old_keys) if owner == source]
        if not keys:
            keys = list(range(SHARD_KEYS))
        total_weight = sum(key_weight(key) for key in keys)
        for key in keys:
            volumes[new_keys[key]] += volume * key_weight(key) / total_weight
    return dict(volumes)


def migrated_storage(
    game: Game,
    topology: Topology,
    *,
    validate: bool = True,
    media_result: dict[str, float] | None = None,
) -> dict[str, float]:
    """Conserve stored GB using modeled data growth to apportion legacy shared data."""
    before, after = ownership(game.production), ownership(topology)
    old_nodes = {n.id: n for n in game.production.nodes}
    new_nodes = {n.id: n for n in topology.nodes}
    old_graph, graph = inspect_graph(game.production), inspect_graph(topology)
    target = object_destination(graph)
    physical = physical_media(game) if target or game.media_by_node is not None else {}
    growth = data_growth_by_domain(game)
    unchanged = {
        d
        for d in after
        if before[d] == after[d]
        and key_owners(d, list(before[d]), domain_overrides(old_graph, d))
        == key_owners(d, list(after[d]), domain_overrides(graph, d))
    }
    repartition = len(unchanged) != len(after)
    volumes: dict[str, dict[str, float]] = defaultdict(dict)
    result = defaultdict(float)
    for primary, stored in sorted(game.storage.items()):
        stored = max(0, stored - physical.get(primary, 0))
        if not stored:
            continue
        if not repartition and primary in new_nodes:
            result[primary] += stored
            continue
        old = old_nodes.get(primary)
        explicit = config(old)["domain"] if old else "Shared"
        domains = (
            [explicit]
            if explicit != "Shared"
            else [d for d in sorted(before) if primary in before[d] and growth[d] > 0]
        )
        if not domains:
            if primary in new_nodes:
                result[primary] += stored
                continue
            if stored:
                raise RuleError(
                    "A migration must retain a destination for stored data."
                )
        denominator = sum(growth[d] for d in domains)
        for domain in domains:
            volume = stored * (
                growth[domain] / denominator if denominator else 1 / len(domains)
            )
            if domain in unchanged and primary in new_nodes:
                result[primary] += volume
            else:
                volumes[domain][primary] = volume
    for domain, by_source in sorted(volumes.items()):
        targets = list(after[domain]) or sorted(
            n.id
            for n in topology.nodes
            if n.kind == "database" and config(n)["domain"] == domain
        )
        for primary, stored in place_domain(
            domain, by_source, targets, list(before[domain]), old_graph, graph
        ).items():
            result[primary] += stored
    if target:
        placed_media = {target: sum(physical.values())}
    elif "Media" not in unchanged:
        placed_media = place_domain(
            "Media",
            physical,
            list(after["Media"]),
            list(before["Media"]),
            old_graph,
            graph,
        )
    else:
        placed_media = physical
    for node_id, volume in placed_media.items():
        if volume:
            result[node_id] += volume
    if media_result is not None:
        media_result.update(
            {node_id: volume for node_id, volume in placed_media.items() if volume}
        )
    # Preparation reserves headroom for writes arriving while the old topology runs.
    fill_limit = 0.85 if validate else 1
    for node in topology.nodes:
        if (
            node.kind in {"database", "object_storage"}
            and result.get(node.id, 0) > config(node)["storage"] * fill_limit
        ):
            raise RuleError(
                "Migration needs spare destination storage. Add storage before moving this dataset."
            )
    return dict(result)


def effective_topology(game: Game, topology: Topology | None = None) -> Topology:
    topology = (topology or migration_topology(game)).model_copy(deep=True)
    for node in topology.nodes:
        cfg = config(node)
        if cfg.get("autoscale") == "Enabled":
            state = game.autoscaling.get(node.id)
            node.config["instances"] = min(
                cfg["max_instances"],
                max(
                    cfg["min_instances"],
                    state.instances if state else cfg["min_instances"],
                ),
            )
    return topology
