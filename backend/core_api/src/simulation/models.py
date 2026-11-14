from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from src.simulation.onboarding import TUTORIAL_STEPS, TutorialStep

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
Speed = Literal[0, 1, 3, 5]
Difficulty = Literal["beginner", "standard", "expert"]
NodeId = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,48}$")]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]
Setting = str | float
AdIntensity = Literal["low", "moderate", "high"]
SyncFrequency = Literal["relaxed", "standard", "frequent"]
MediaQuality = Literal["compressed", "standard", "high"]


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


class DiagramViewport(Model):
    x: float
    y: float
    zoom: float = Field(ge=0.15, le=2.5)


class Diagram(Model):
    positions: dict[NodeId, Position] = Field(default_factory=dict, max_length=240)
    routes: dict[RouteId, Waypoints] = Field(default_factory=dict, max_length=480)
    groups: list[DiagramGroup] = Field(default_factory=list, max_length=80)

    viewports: dict[Literal["compact", "wide"], DiagramViewport] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def unique_groups(self) -> Self:
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
    p95_latency: float | None = None
    errors: float = 0
    rejected: float = 0


class DatabaseDiagnostic(Model):
    level: Literal["write_exceeded", "write_pressure", "resource_pressure"]
    resources: list[str]
    upgrades: list[
        Literal[
            "cpu", "memory", "connections", "storage", "nvme", "nvme_array", "legacy"
        ]
    ]
    limiting: list[str] = Field(default_factory=list)
    read_options: bool = False


class DatabaseTelemetry(Model):
    read_demand: float
    disk_read_iops: float | None = None
    disk_write_iops: float | None = None
    disk_capacity_iops: float | None = None
    write_demand: float
    write_capacity: float | None
    replication_demand: float = 0
    replication_throughput: float = 0
    replication_backlog: float = 0
    diagnostic: DatabaseDiagnostic | None = None


class ComponentMetrics(Model):
    status: Literal["healthy", "warning", "overloaded", "failed", "idle"]
    rps: float
    throughput: float
    latency: float
    utilization: dict[str, float]
    cache_hit: float | None = None
    backlog: float | None = None
    queue_wait_minutes: float | None = None
    jobs_dropped: float | None = None
    jobs_expired: float | None = None
    active_instances: float | None = None
    storage_used: float | None = None
    replication_lag: float | None = None
    database: DatabaseTelemetry | None = None


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


class RegionDemand(Model):
    id: str
    name: str
    utc_offset: int
    local_minute: int
    audience: int
    daily_active_users: float
    requests: float
    daily_ad_revenue: float = 0
    earned_ad_revenue: float = 0


class DemandOverview(Model):
    day: int
    utc_minute: int
    regions: list[RegionDemand]
    expected: list[float]
    campaign_lift: float
    event_lift: float


class Snapshot(Model):
    metrics: Metrics
    components: dict[str, ComponentMetrics] = Field(default_factory=dict)
    traffic: list[Traffic] = Field(default_factory=list)
    demand: dict[str, float] = Field(default_factory=dict)
    demand_overview: DemandOverview | None = None
    monitored: bool = False
    monitors: dict[NodeId, MonitorCoverage] = Field(default_factory=dict)


class RevenueSources(Model):
    advertising: float = 0
    subscriptions: float = 0
    legacy: float = 0

    @property
    def total(self) -> float:
        return self.advertising + self.subscriptions + self.legacy


class OperatingCosts(Model):
    infrastructure: float = 0
    traffic: float = 0
    payments: float = 0
    legacy: float = 0

    @property
    def total(self) -> float:
        return self.infrastructure + self.traffic + self.payments + self.legacy


class OneTimeCosts(Model):
    development: float = 0
    marketing: float = 0
    deployment: float = 0

    @property
    def total(self) -> float:
        return self.development + self.marketing + self.deployment


class FinanceSample(Model):
    revenue: RevenueSources
    expenses: OperatingCosts
    cash_received: float
    daily_active_users: float
    ad_impressions: float
    regional_ads: dict[str, float] = Field(
        default_factory=dict, exclude_if=lambda value: not value
    )


class HistoryPoint(Model):
    tick: int
    audience: int
    balance: float
    metrics: Metrics
    finance: FinanceSample | None = None
    audience_churn: float = 0
    peak_utilization: dict[NodeId, float] = Field(default_factory=dict)
    resource_utilization: dict[NodeId, dict[str, float]] = Field(default_factory=dict)


class Incident(Model):
    id: str
    kind: str
    cause: str | None = None
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


class ResourcePressure(Model):
    component: Name
    resource: str
    utilization: float


class DeploymentComparison(Model):
    before: Metrics
    after: Metrics
    daily_before: float
    daily_after: float
    capacity_before: float | None = None
    capacity_after: float | None = None
    pressure_before: ResourcePressure | None = None
    pressure_after: ResourcePressure | None = None


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


class ProductSettings(Model):
    ad_intensity: AdIntensity = "moderate"
    # Existing terms are held by the paid cohort. This price applies at checkout.
    premium_price: float
    premium_fast_sync: bool = True
    sync_frequency: SyncFrequency = "standard"
    media_quality: MediaQuality = "standard"
    north_america: bool = False


class SubscriptionTerm(Model):
    expires: int
    subscribers: float
    price: float
    fast_sync: bool = True


class Onboarding(Model):
    step: int = Field(default=0, ge=0, le=9)
    furthest: int = Field(default=0, ge=0, le=9)
    skipped: bool = False
    step_id: TutorialStep | None = None
    furthest_id: TutorialStep | None = None

    @model_validator(mode="after")
    def validate_tutorial_ids(self) -> Self:
        if (self.step_id is None) != (self.furthest_id is None) or (
            self.step_id is not None
            and self.furthest_id is not None
            and TUTORIAL_STEPS.index(self.step_id)
            > TUTORIAL_STEPS.index(self.furthest_id)
        ):
            raise ValueError("Invalid tutorial progress")
        return self


class CampaignAllocation(Model):
    budget: float = Field(gt=0, le=100_000)
    audience: float = Field(ge=0)


class RegionalCampaign(Model):
    region: str
    start: int
    duration: int
    budget: float
    audience: float
    spike: float
    allocations: dict[str, CampaignAllocation] = Field(default_factory=dict)

    @property
    def regions(self) -> list[str]:
        return list(self.allocations) or [self.region]


class Game(Model):
    id: UUID
    name: Name
    seed: int
    scenario: str = "messenger"
    difficulty: Difficulty = "beginner"
    tick: int = 0
    speed: Speed = 0
    start_minute: int = 0
    clock_fraction: float = Field(default=0, ge=0, lt=1)
    audience: float = 8_400
    balance: float = 10_000
    satisfaction: float = 0.96
    strain: float = 0
    revenue: float = 0
    operating: float = 0
    advertising_revenue: float = 0
    subscription_revenue: float = 0
    subscription_cash: float = 0
    infrastructure_spend: float = 0
    traffic_spend: float = 0
    payment_spend: float = 0
    development_spend: float = 0
    marketing_spend: float = 0
    deployment_spend: float = 0
    recent_purchases: dict[int, OneTimeCosts] = Field(default_factory=dict)
    production: Topology
    draft: Topology | None = None
    diagram: Diagram = Field(default_factory=Diagram)
    revision: int = 0
    released: list[str] = Field(default_factory=lambda: ["text"])
    infrastructure_releases: list[str] = Field(default_factory=list)
    disabled_features: set[str] = Field(default_factory=set)
    product: ProductSettings | None = None
    north_america_audience: float = 0
    market_audience: dict[str, float] = Field(default_factory=dict)
    market_projects: dict[str, int] = Field(default_factory=dict)
    launched_markets: set[str] = Field(default_factory=set)
    language_projects: dict[str, int] = Field(default_factory=dict)
    regional_campaigns: dict[str, RegionalCampaign] = Field(default_factory=dict)
    premium_quality: float = 0.98
    subscriptions: list[SubscriptionTerm] = Field(default_factory=list)
    development: dict[str, int] = Field(default_factory=dict)
    campaigns: dict[str, int] = Field(default_factory=dict)
    event_sequence: int = 0
    incidents: list[Incident] = Field(default_factory=list)
    deployments: list[Deployment] = Field(default_factory=list)
    history: list[HistoryPoint] = Field(default_factory=list)
    queues: dict[str, float] = Field(default_factory=dict)
    storage: dict[str, float] = Field(default_factory=lambda: {"db": 2.0})
    replication: dict[NodeId, float] = Field(default_factory=dict)
    settings: GameSettings = Field(default_factory=GameSettings)
    tutorial: int = 0
    onboarding: Onboarding | None = None

    @property
    def enabled_features(self) -> set[str]:
        return set(self.released) - self.disabled_features

    @property
    def subscribers(self) -> float:
        return sum(term.subscribers for term in self.subscriptions)
