"""Architectural capabilities; request rates remain owned by demand.workload.

Domains partition existing operations, never multiply external traffic. Conversation
partitions use 128 stable virtual keys with a 12% hot conversation cohort.
"""

from collections import defaultdict
from hashlib import sha256
from math import ceil

from src.simulation.models import Game, Topology
from src.simulation.topology import Graph, RuleError, config, daily_cost

RESEARCH = {
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
        "unlocks": "Partition membership on primary databases.",
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


def partition_weights(domain: str, targets: list[str]) -> list[float]:
    weights = dict.fromkeys(targets, 0.0)
    for key in range(128):
        digest = sha256(f"{domain}:{key}".encode()).digest()
        owner = targets[int.from_bytes(digest[:4], "big") % len(targets)]
        weights[owner] += 0.12 if key == 0 else 0.88 / 127
    return [weights[p] for p in targets]


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


def architecture_errors(
    game: Game, graph: Graph, *, partial: bool = False
) -> list[str]:
    errors = []
    for node in graph.nodes.values():
        cfg = config(node)
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
    from src.simulation.demand import workload

    operations = workload(game).operations
    apis = [graph.nodes[n] for n in sorted(request_apis(graph))]
    owners = defaultdict(set)
    for op, rate in operations.items():
        if not rate:
            continue
        capable = [n for n in apis if supports(n, op)]
        if not capable:
            errors.append(
                "A required operation has no connected API service. Add a capable API or a Universal API."
            )
        for api in capable:
            primaries = data_targets(graph, api.id, op)
            if not primaries and DOMAINS.get(op):
                errors.append(
                    "An API is missing its operation's data domain. Connect the owning primary or all its partitions."
                )
            owners[DOMAINS.get(op)].add(tuple(primaries))
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
    from src.simulation.topology import inspect_graph

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


def migration_plan(game: Game, topology: Topology) -> tuple[int, float]:
    before, after = ownership(game.production), ownership(topology)
    changed = {d for d in before if before[d] and before[d] != after[d]}
    if not changed:
        return 0, 0
    stored = sum(
        game.storage.get(p, 0) for p in sorted({p for d in changed for p in before[d]})
    )
    # Conservative aggregate copy: 4 GB per tick; bounded by slowest destination CPU.
    destinations = {p for d in changed for p in after[d]}
    nodes = {n.id: n for n in topology.nodes}
    speed = min([4.0, *(float(config(nodes[p])["cpu"]) for p in sorted(destinations))])
    duration = max(3, ceil(stored / max(1, speed)))
    cost = round(
        120
        + stored * 4
        + sum(daily_cost(nodes[p]) for p in sorted(destinations)) * duration / 144,
        2,
    )
    return duration, cost


def migrated_storage(
    game: Game, topology: Topology, *, validate: bool = True
) -> dict[str, float]:
    """Conserve stored GB using modeled data growth to apportion legacy shared data."""
    from src.simulation.catalog import FEATURES, OPERATIONS, SCENARIOS

    before, after = ownership(game.production), ownership(topology)
    old_nodes = {n.id: n for n in game.production.nodes}
    new_nodes = {n.id: n for n in topology.nodes}
    operations = set(SCENARIOS[game.scenario]["operations"]) | {
        FEATURES[f]["operation"] for f in game.released if FEATURES[f]["operation"]
    }
    growth = defaultdict(float)
    # Disabled features keep their data. Explicit domains retain their own GB;
    # only legacy Shared data needs an aggregate allocation assumption.
    for op in sorted(operations):
        operation = OPERATIONS[op]
        growth[DOMAINS[op]] += operation["rate"] * max(
            operation["storage"], operation["write"] * 0.00000001
        )
    volumes = defaultdict(float)
    result = defaultdict(float)
    for primary, stored in sorted(game.storage.items()):
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
            volumes[domain] += stored * (
                growth[domain] / denominator if denominator else 1 / len(domains)
            )
    for domain, stored in sorted(volumes.items()):
        targets = list(after[domain]) or sorted(
            n.id
            for n in topology.nodes
            if n.kind == "database" and config(n)["domain"] == domain
        )
        if not targets and stored:
            raise RuleError("A migration must retain a destination for stored data.")
        for primary, share in zip(
            targets, partition_weights(domain, targets) if targets else []
        ):
            result[primary] += stored * share
    for node in topology.nodes:
        if (
            validate
            and node.kind == "database"
            and result.get(node.id, 0) > config(node)["storage"] * 0.85
        ):
            raise RuleError(
                "Migration needs spare destination storage. Add storage before moving this dataset."
            )
    return dict(result)


def effective_topology(game: Game, topology: Topology | None = None) -> Topology:
    topology = (topology or game.production).model_copy(deep=True)
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
