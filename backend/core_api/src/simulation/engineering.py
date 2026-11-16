"""Architectural capabilities and topology changes.

Domains partition existing operations, never multiply external traffic. Conversation
partitions use 128 stable virtual keys with a 12% hot conversation cohort.
"""

from collections import defaultdict
from hashlib import sha256
from math import ceil
from uuid import uuid4

from pydantic import ValidationError

from src.simulation.models import Edge, Game, Kind, Node, Position, Setting, Topology
from src.simulation.topology import Graph, RuleError, config, daily_cost, inspect_graph

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
        if node.kind == "shard_router" and not researched(game, "sharding"):
            errors.append("Complete Database Sharding research before using a shard router.")
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
    from src.simulation.demand import workload

    operations = workload(game, enforce_media_quota=False).operations
    apis = [graph.nodes[n] for n in sorted(request_apis(graph))]
    owners = defaultdict(set)
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


def sharding_topology(game: Game, topology: Topology, primary_id: str) -> Topology:
    if not researched(game, "sharding"):
        raise RuleError(
            "Complete Database Sharding research before using a shard router."
        )
    graph = inspect_graph(topology)
    primary = graph.nodes.get(primary_id)
    if (
        primary is None
        or primary.kind != "database"
        or config(primary)["partition"] != "Independent"
    ):
        raise RuleError(
            "Select an independent primary database to prepare sharding."
        )
    current_domain = config(primary)["domain"]
    relevant = set(data_growth_by_domain(game))
    owners = {
        node.id: {
            domain: data_targets(graph, node.id, op)
            for op, domain in DOMAINS.items()
            if domain in relevant and supports(node, op)
        }
        for node in graph.nodes.values()
        if node.kind == "api"
    }
    apis = {
        api: (
            {domain for domain, links in routes.items() if primary_id in links}
            if current_domain == "Shared"
            else {current_domain}
        )
        for api, routes in owners.items()
        if primary_id in graph.targets[api]
    }
    domains = set().union(*apis.values())
    if not domains:
        raise RuleError(
            "Connect an API that uses this database before preparing sharding."
        )
    domain = min(domains, key=lambda name: (name != "Messages", name))
    nodes = [node.model_copy(deep=True) for node in topology.nodes]
    original = next(node for node in nodes if node.id == primary_id)
    original.config.update(domain=domain, partition="Partition")
    if current_domain == "Shared" and "Search" in domains - {domain}:
        original.config["search_index"] = "Disabled"
    # Legacy mixed topologies can already use a Shared primary for just one domain.
    for node in nodes:
        if node.kind != "database" or config(node)["domain"] != "Shared":
            continue
        assigned = {
            name
            for routes in owners.values()
            for name, targets in routes.items()
            if node.id in targets
        }
        if len(assigned) == 1:
            node.config["domain"] = assigned.pop()

    anchor = game.diagram.positions.get(primary_id, primary.position)
    occupied = [game.diagram.positions.get(node.id, node.position) for node in nodes]

    def add(kind: Kind, name: str, settings: dict[str, Setting]) -> Node:
        # Seed positions only for new nodes. Existing diagram edits stay independent.
        direction = 1 if anchor.x < 99_000 else -1
        vertical = 1 if anchor.y < 85_000 else -1
        x = anchor.x + 235 * direction
        y = anchor.y + 140 * vertical
        while any(
            abs(point.x - x) < 175 and abs(point.y - y) < 115 for point in occupied
        ):
            y += 140 * vertical
        position = Position(x=x, y=y)
        node = Node(
            id=str(uuid4()), kind=kind, name=name, position=position, config=settings
        )
        nodes.append(node)
        occupied.append(position)
        return node

    router = add("shard_router", "Shard router", {"domain": domain})
    second = add("database", "Second shard", original.config.copy())
    extra = {
        name: add(
            "database",
            f"{name} database",
            {**primary.config, "domain": name, "partition": "Independent"},
        )
        for name in sorted(domains - {domain})
    }
    edges = [
        edge
        for edge in topology.edges
        if not (edge.source in apis and edge.target == primary_id)
    ]
    edges.extend(
        Edge(source=router.id, target=target) for target in (primary_id, second.id)
    )
    for api, assigned in apis.items():
        for name in sorted(assigned):
            target = router if name == domain else extra[name]
            edges.append(Edge(source=api, target=target.id))
    for node in topology.nodes:
        if node.kind == "cache" and primary_id in graph.targets[node.id]:
            edges.extend(
                Edge(source=node.id, target=target.id)
                for target in (second, *extra.values())
            )
    try:
        return Topology(nodes=nodes, edges=edges)
    except ValidationError as error:
        raise RuleError(
            "The draft has no room for the additional sharding components or connections."
        ) from error


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


def migrated_storage(
    game: Game, topology: Topology, *, validate: bool = True
) -> dict[str, float]:
    """Conserve stored GB using modeled data growth to apportion legacy shared data."""
    before, after = ownership(game.production), ownership(topology)
    old_nodes = {n.id: n for n in game.production.nodes}
    new_nodes = {n.id: n for n in topology.nodes}
    growth = data_growth_by_domain(game)
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
