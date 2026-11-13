from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Kind = Literal[
    "source",
    "balancer",
    "api",
    "database",
    "replica",
    "cache",
    "limiter",
    "queue",
    "worker",
    "monitor",
]
Speed = Literal[0, 1, 3]
Difficulty = Literal["beginner", "standard", "expert"]
NodeId = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,48}$")]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]
Setting = str | float


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Position(Model):
    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)


class Node(Model):
    id: NodeId
    kind: Kind
    name: Name
    position: Position
    config: dict[str, Setting] = Field(default_factory=dict, max_length=20)


class Edge(Model):
    source: NodeId
    target: NodeId


class Topology(Model):
    nodes: list[Node] = Field(max_length=80)
    edges: list[Edge] = Field(max_length=240)


class DiagramGroup(Model):
    id: NodeId
    name: Name
    members: list[NodeId] = Field(min_length=1, max_length=80)
    collapsed: bool = False


RouteId = Annotated[
    str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,48}:[a-zA-Z0-9_-]{1,48}$")
]
Waypoints = Annotated[list[Position], Field(max_length=24)]


class Diagram(Model):
    positions: dict[NodeId, Position] = Field(default_factory=dict, max_length=240)
    routes: dict[RouteId, Waypoints] = Field(default_factory=dict, max_length=480)
    groups: list[DiagramGroup] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def unique_groups(self) -> "Diagram":
        groups = {group.id: group for group in self.groups}
        parent = {}
        if len(groups) != len(self.groups):
            raise ValueError("Group IDs must be unique.")
        for group in self.groups:
            for member in group.members:
                if member in parent:
                    raise ValueError("Each diagram item can belong to one group.")
                parent[member] = group.id
        for group_id in groups:
            seen = {group_id}
            cursor = group_id
            while cursor in parent:
                cursor = parent[cursor]
                if cursor in seen:
                    raise ValueError("Diagram groups cannot contain cycles.")
                seen.add(cursor)
        return self


class Metrics(Model):
    rps: float = 0
    throughput: float = 0
    availability: float = 1
    latency: float = 0
    errors: float = 0
    rejected: float = 0


class ComponentMetrics(Model):
    status: Literal["healthy", "warning", "overloaded", "failed", "idle"]
    rps: float
    throughput: float
    latency: float
    utilization: dict[str, float]
    cache_hit: float | None = None
    backlog: float | None = None
    active_instances: float | None = None
    storage_used: float | None = None
    replication_lag: float | None = None


class Traffic(Model):
    source: NodeId
    target: NodeId
    rps: float
    operations: dict[str, float] = Field(default_factory=dict)


class MonitorCoverage(Model):
    capacity: int
    history: bool
    covered: list[NodeId]
    dropped: list[NodeId]
    failed: bool = False


class Snapshot(Model):
    metrics: Metrics
    components: dict[str, ComponentMetrics] = Field(default_factory=dict)
    traffic: list[Traffic] = Field(default_factory=list)
    demand: dict[str, float] = Field(default_factory=dict)
    monitored: bool = False
    monitors: dict[NodeId, MonitorCoverage] = Field(default_factory=dict)


class HistoryPoint(Model):
    tick: int
    audience: int
    balance: float
    metrics: Metrics


class Incident(Model):
    id: str
    kind: str
    title: str
    symptom: str
    severity: Literal["info", "warning", "critical"]
    start: int
    end: int
    target: NodeId | None = None
    factor: float = 1
    resolution: str | None = None
    failed_requests: float = 0
    acknowledged: bool = False


class DeploymentComparison(Model):
    before: Metrics
    after: Metrics
    daily_before: float
    daily_after: float


class Deployment(Model):
    id: UUID
    tick: int
    topology: Topology
    cost: float
    summary: str
    comparison: DeploymentComparison | None = None


class GameSettings(Model):
    reduced_motion: bool = False
    show_tutorial: bool = True
    show_objectives: bool = True


class Game(Model):
    id: UUID
    name: Name
    seed: int
    scenario: str = "messenger"
    difficulty: Difficulty = "beginner"
    tick: int = 0
    speed: Speed = 0
    clock_fraction: float = Field(default=0, ge=0, lt=1)
    audience: float = 8_400
    balance: float = 10_000
    satisfaction: float = 0.96
    strain: float = 0
    revenue: float = 0
    operating: float = 0
    development_spend: float = 0
    marketing_spend: float = 0
    deployment_spend: float = 0
    production: Topology
    draft: Topology | None = None
    diagram: Diagram = Field(default_factory=Diagram)
    revision: int = 0
    released: list[str] = Field(default_factory=lambda: ["text"])
    development: dict[str, int] = Field(default_factory=dict)
    campaigns: dict[str, int] = Field(default_factory=dict)
    event_sequence: int = 0
    incidents: list[Incident] = Field(default_factory=list)
    deployments: list[Deployment] = Field(default_factory=list)
    history: list[HistoryPoint] = Field(default_factory=list)
    queues: dict[str, float] = Field(default_factory=dict)
    storage: dict[str, float] = Field(default_factory=lambda: {"db": 2.0})
    settings: GameSettings = Field(default_factory=GameSettings)
    tutorial: int = 0
