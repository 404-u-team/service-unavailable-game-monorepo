from collections import defaultdict, deque
from dataclasses import dataclass

from src.simulation.catalog import (
    COMPONENTS,
    CONNECTIONS,
    DATABASE_DISKS,
    DAYS_PER_MONTH,
    LEGACY_DATABASE_LIMITS,
    defaults,
)
from src.simulation.models import Edge, Kind, Node, Position, Topology


class RuleError(ValueError):
    """A gameplay rule rejected an action."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "rule_violation",
        values: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.values = values


@dataclass
class Graph:
    nodes: dict[str, Node]
    targets: dict[str, list[str]]
    order: list[str]
    reachable: set[str]
    relationships: dict[tuple[str, str], str]

    def primaries(self, node_id: str) -> list[str]:
        return sorted(self.primary_routes(node_id))

    def primary_routes(self, node_id: str) -> dict[str, str]:
        routes = {
            target: target for target in self.targets[node_id]
            if self.nodes[target].kind == "database"
        }
        if self.nodes[node_id].kind == "api":
            for router in self.targets[node_id]:
                if self.nodes[router].kind != "shard_router":
                    continue
                domain = config(self.nodes[router])["domain"]
                for primary in self.targets[router]:
                    node = self.nodes[primary]
                    if node.kind == "database" and config(node)["domain"] == domain:
                        routes[primary] = router
        return routes


def inspect_graph(topology: Topology) -> Graph:
    nodes = {node.id: node for node in topology.nodes}
    if len(nodes) != len(topology.nodes):
        raise RuleError("Component IDs must be unique.")
    sources = [node.id for node in nodes.values() if node.kind == "source"]
    if len(sources) != 1 or sources[0] != "traffic":
        raise RuleError("Keep the original traffic source.")
    for node in nodes.values():
        fields = COMPONENTS[node.kind]["fields"]
        for key, value in node.config.items():
            field = fields.get(key)
            if field is None and (
                node.kind == "database" or (node.kind == "replica" and key == "reads")
            ):
                field = LEGACY_DATABASE_LIMITS.get(key)
            if field is None:
                raise RuleError(f"{node.name} has an unknown setting: {key}.")
            if "options" in field:
                valid = value in field["options"]
            else:
                valid = (
                    isinstance(value, (float, int))
                    and field["min"] <= value <= field["max"]
                )
                if key in {"instances", "slots", "min_instances", "max_instances"}:
                    valid = valid and int(value) == value
            if not valid:
                raise RuleError(
                    f"{node.name}: invalid value for {field['label']}.",
                    code="invalid_setting",
                    values=(node.name, field["label"]),
                )

    targets: dict[str, list[str]] = defaultdict(list)
    incoming = dict.fromkeys(nodes, 0)
    relationships = {}
    for edge in topology.edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise RuleError("Connections must link existing components.")
        source, target = nodes[edge.source], nodes[edge.target]
        relationship = CONNECTIONS[source.kind].get(target.kind)
        if relationship is None:
            raise RuleError(
                f"{source.name} cannot connect to {target.name}.",
                code="incompatible_connection",
                values=(source.name, target.name),
            )
        if relationship == "identity" and (
            config(source)["role"] in {"Universal", "Accounts"}
            or config(target)["role"] != "Accounts"
        ):
            raise RuleError(
                "Identity dependencies must connect a specialized service to an Accounts API."
            )
        if edge.target in targets[edge.source]:
            raise RuleError(
                "A connection already exists between these components.",
                code="duplicate_connection",
            )
        targets[edge.source].append(edge.target)
        relationships[edge.source, edge.target] = relationship
        if relationship not in {"telemetry", "replication"}:
            incoming[edge.target] += 1

    for children in targets.values():
        children.sort()
    order = []
    ready = deque(sorted(node for node, count in incoming.items() if not count))
    while ready:
        node = ready.popleft()
        order.append(node)
        for target in targets[node]:
            if relationships[node, target] in {"telemetry", "replication"}:
                continue
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    if len(order) != len(nodes):
        raise RuleError("Connections cannot form a cycle.", code="connection_cycle")
    for node in nodes.values():
        if (
            node.kind == "replica"
            and sum(nodes[t].kind == "database" for t in targets[node.id]) > 1
        ):
            raise RuleError(
                f"{node.name} can replicate from one primary database.",
                code="multiple_primaries",
                values=(node.name,),
            )
    reachable = {sources[0]}
    for node in order:
        if node in reachable:
            reachable.update(
                target
                for target in targets[node]
                if relationships[node, target] not in {"telemetry", "replication"}
            )
    return Graph(nodes, targets, order, reachable, relationships)


def messenger_datasets(graph: Graph) -> dict[str, tuple[str, ...]]:
    return {
        node_id: tuple(sorted(graph.primaries(node_id)))
        for node_id in graph.reachable
        if graph.nodes[node_id].kind == "api"
    }


def has_split_dataset(datasets: dict[str, tuple[str, ...]]) -> bool:
    return len({primary for links in datasets.values() for primary in links}) > 1


def deployment_warnings(graph: Graph) -> list[str]:
    writes = set()
    for node_id in reversed(graph.order):
        kind = graph.nodes[node_id].kind
        if kind == "database" or (
            kind in {"api", "source", "limiter", "balancer", "shard_router"}
            and any(target in writes for target in graph.targets[node_id])
        ):
            writes.add(node_id)
    if "traffic" not in writes:
        raise RuleError(
            "Connect traffic to an API server, then connect it to a primary database or a shard router.",
            code="missing_write_path",
        )
    warnings = []
    for node in graph.nodes.values():
        if node.kind == "monitor":
            links = sum(
                target == node.id and kind == "telemetry"
                for (_, target), kind in graph.relationships.items()
            )
            if not links:
                warnings.append(f"{node.name} has no monitoring links.")
            elif links > config(node)["slots"] - (
                2
                if config(node)["detail"] == "Service history"
                and config(node)["slots"] >= 3
                else 0
            ):
                warnings.append(
                    f"{node.name} has more monitoring links than available slots."
                )
        elif node.id not in graph.reachable:
            warnings.append(
                f"{node.name} is disconnected and will still incur operating costs."
            )
        elif node.kind in {"api", "limiter", "balancer"} and node.id not in writes:
            warnings.append(
                f"{node.name} has no write path. Route traffic to an API connected to a primary database or a shard router."
            )
        elif (
            node.kind == "api"
            and len(graph.primaries(node.id)) > 1
            and all(
                config(graph.nodes[p])["domain"] == "Shared"
                for p in graph.primaries(node.id)
            )
        ):
            warnings.append(
                f"{node.name} has multiple primary links. Only the first by component ID serves its dataset."
            )
        elif node.kind == "replica" and not any(
            graph.nodes[t].kind == "database" for t in graph.targets[node.id]
        ):
            warnings.append(f"{node.name} needs a connection to a primary database.")
        elif node.kind == "cache" and not any(
            graph.nodes[t].kind in {"database", "replica"} for t in graph.targets[node.id]
        ):
            warnings.append(
                f"{node.name} cannot serve cache misses without a data connection."
            )
        elif node.kind == "queue" and not any(
            graph.nodes[t].kind == "worker" for t in graph.targets[node.id]
        ):
            warnings.append(f"{node.name} has no worker. Its backlog will build up.")
    return warnings


def config(node: Node) -> dict:
    return defaults(node.kind) | node.config


def daily_cost(node: Node) -> float:
    cfg = config(node)
    base = COMPONENTS[node.kind]["monthly"] / DAYS_PER_MONTH
    if not cfg:
        return base
    extras = sum(
        max(0, float(cfg[key]) / max(1, field["default"]) - 1) * 0.18
        for key, field in COMPONENTS[node.kind]["fields"].items()
        if "min" in field
        and key
        not in {
            "instances",
            "ttl",
            "limit",
            "window",
            "burst",
            "retention",
            "min_instances",
            "max_instances",
            "target_utilization",
        }
        and (key != "connections" or node.kind == "balancer")
    )
    disk = DATABASE_DISKS[cfg["disk"]][1] if "disk" in cfg else 0
    history = 0.20 if cfg.get("detail") == "Service history" else 0
    recovery = 0.30 if cfg.get("recovery") == "Managed replacement" else 0
    return round(
        base * cfg.get("instances", 1) * (1 + extras + disk + history + recovery), 2
    )


def topology_cost(topology: Topology) -> float:
    return round(sum(daily_cost(node) for node in topology.nodes), 2)


def diff(before: Topology, after: Topology) -> dict[str, list[str]]:
    old = {n.id: n for n in before.nodes}
    new = {n.id: n for n in after.nodes}
    old_edges = {(e.source, e.target) for e in before.edges}
    new_edges = {(e.source, e.target) for e in after.edges}

    def connections(pairs: set, nodes: dict) -> list[str]:
        return [
            f"{nodes[source].name} → {nodes[target].name}"
            for source, target in sorted(pairs)
        ]

    return {
        "added": [n.name for n in after.nodes if n.id not in old],
        "removed": [n.name for n in before.nodes if n.id not in new],
        "modified": [
            n.name
            for n in after.nodes
            if n.id in old
            and (
                n.kind != old[n.id].kind
                or n.name != old[n.id].name
                or config(n) != config(old[n.id])
            )
        ],
        "moved": [
            n.name
            for n in after.nodes
            if n.id in old and n.position != old[n.id].position
        ],
        "connected": connections(new_edges - old_edges, new),
        "disconnected": connections(old_edges - new_edges, old),
    }


def install_cost(before: Topology, after: Topology) -> float:
    old = {n.id: n for n in before.nodes}
    cost = 0.0
    for node in after.nodes:
        previous = old.get(node.id)
        cost += max(0, daily_cost(node) - (daily_cost(previous) if previous else 0)) * 4
    return round(cost, 2)


def starter_topology() -> Topology:
    def node(node_id: str, kind: Kind, name: str, x: int, y: int) -> Node:
        return Node(id=node_id, kind=kind, name=name, position=Position(x=x, y=y))

    return Topology(
        nodes=[
            node("traffic", "source", "Incoming traffic", 45, 185),
            node("edge", "balancer", "Edge balancer", 275, 185),
            node("api", "api", "Messenger API", 505, 185),
            node("db", "database", "Primary database", 735, 185),
        ],
        edges=[
            Edge(source="traffic", target="edge"),
            Edge(source="edge", target="api"),
            Edge(source="api", target="db"),
        ],
    )
