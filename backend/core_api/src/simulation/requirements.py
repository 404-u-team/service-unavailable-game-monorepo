from collections.abc import Callable
from dataclasses import dataclass

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
        "Connect each API that receives traffic directly to a primary database for writes.",
        ("database",),
    ),
    "media_storage": Requirement(
        "Connect each API that receives traffic to a primary database with at least 8 GB free for media.",
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


def requirement_met(rule: Requirement, graph: Graph, game: Game) -> bool:
    apis = [
        node
        for node in graph.nodes.values()
        if node.kind == "api" and node.id in graph.reachable
    ]
    for api in apis:
        candidates = {api.id}
        for kind in rule.path:
            candidates = {
                target
                for source in candidates
                for target in (
                    graph.primaries(source)[:1]
                    if kind == "database" and graph.nodes[source].kind == "api"
                    else graph.targets[source]
                )
                if graph.nodes[target].kind == kind
            }
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
