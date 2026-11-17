from collections.abc import Callable
from dataclasses import dataclass

from src.simulation.catalog import topic_accepts
from src.simulation.engineering import data_targets, object_target, supports
from src.simulation.models import Game, Kind, Node
from src.simulation.topology import Graph, config

MEDIA_FREE_GB = 8


@dataclass(frozen=True)
class Requirement:
    description: str
    path: tuple[Kind, ...]
    qualifies: Callable[[Node, Game], bool] = lambda _node, _game: True
    instances: int = 1


REQUIREMENTS = {
    "primary": Requirement(
        "Connect each API that receives traffic to a primary database or a shard router for writes.",
        ("database",),
    ),
    "media_storage": Requirement(
        "Connect each media API to a database and provide at least 8 GB free for attachments in its database or Object Storage.",
        ("database",),
        lambda node, game: (
            config(node)["storage"] - game.storage.get(node.id, 0) >= MEDIA_FREE_GB
        ),
    ),
    "background_jobs": Requirement(
        "Connect each API that receives traffic to a queue with at least one worker to process background jobs.",
        ("queue", "worker"),
    ),
    "search_index": Requirement(
        "Connect each API that receives traffic to a primary database with Message search index enabled.",
        ("database",),
        lambda node, _game: config(node)["search_index"] == "Enabled",
    ),
    "signaling": Requirement(
        "Give each API that receives traffic at least 40 MB/s of network capacity and 1,500 connections across its instances for voice calls.",
        (),
        lambda node, _game: (
            (cfg := config(node))["network"] * cfg["instances"] >= 40
            and cfg["connections"] * cfg["instances"] >= 1500
        ),
    ),
}


def requirement_met(
    rule: Requirement, graph: Graph, game: Game, operation: str | None = None
) -> bool:
    apis = [
        node
        for node in graph.nodes.values()
        if node.kind == "api"
        and node.id in graph.reachable
        and (operation is None or supports(node, operation))
    ]
    for api in apis:
        if rule is REQUIREMENTS["media_storage"] and (
            target := object_target(graph, api.id)
        ):
            if rule.qualifies(graph.nodes[target], game) and data_targets(
                graph, api.id, operation or "upload"
            ):
                continue
            return False
        candidates = {api.id}
        for kind in rule.path:
            candidates = {
                target
                for source in candidates
                for target in (
                    (
                        data_targets(graph, source, operation)
                        if operation
                        else graph.primaries(source)[:1]
                    )
                    if kind == "database" and graph.nodes[source].kind == "api"
                    else graph.targets[source]
                )
                if graph.nodes[target].kind == kind
                and (
                    kind != "queue"
                    or operation is None
                    or topic_accepts(config(graph.nodes[target])["topic"], operation)
                )
            }
        if rule.path == ("database",) and (
            not candidates
            or any(not rule.qualifies(graph.nodes[p], game) for p in candidates)
        ):
            return False
        if (
            sum(
                config(node).get("instances", 1)
                for node_id in candidates
                if rule.qualifies(node := graph.nodes[node_id], game)
            )
            < rule.instances
        ):
            return False
    return bool(apis)
