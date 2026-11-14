from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from src.simulation.models import (
    AdIntensity,
    CampaignAllocation,
    DeploymentComparison,
    Diagram,
    DiagramGroup,
    DiagramViewport,
    Difficulty,
    FinanceSample,
    GameSettings,
    HistoryPoint,
    Metrics,
    Model,
    Name,
    NodeId,
    Onboarding,
    OneTimeCosts,
    OperatingCosts,
    Position,
    ProductSettings,
    RevenueSources,
    RouteId,
    Setting,
    Snapshot,
    Speed,
    Topology,
    Waypoints,
)
from src.simulation.onboarding import TutorialStep

ScenarioId = Literal["messenger", "social", "multiplayer", "education"]
FeatureId = Literal[
    "text",
    "groups",
    "images",
    "voice",
    "search",
    "files",
    "calls",
    "advertising",
    "premium",
]
CampaignId = Literal["community", "creator", "ads"]


class CreateGame(Model):
    id: UUID
    name: Name
    scenario: ScenarioId = "messenger"
    difficulty: Difficulty = "beginner"
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    settings: GameSettings = Field(default_factory=GameSettings)


class Action(Model):
    request_id: UUID


class ClockAction(Action):
    speed: Speed


class VersionedAction(Action):
    revision: int = Field(ge=0)


class UpdateDraft(VersionedAction):
    topology: Topology


class UpdateDiagram(Action):
    diagram: Diagram


class PatchDiagram(Action):
    positions: dict[NodeId, Position | None] = Field(
        default_factory=dict, max_length=240
    )
    routes: dict[RouteId, Waypoints | None] = Field(
        default_factory=dict, max_length=480
    )
    groups: list[DiagramGroup] | None = Field(default=None, max_length=80)
    group_base: list[DiagramGroup] | None = Field(default=None, max_length=80)
    viewports: dict[Literal["compact", "wide"], DiagramViewport] = Field(
        default_factory=dict
    )


class SettingsAction(Action):
    settings: GameSettings


class FeatureAction(Action):
    action: Literal["develop", "release", "enable", "disable"]


class ProductAction(Action):
    product: ProductSettings


class TutorialAction(Action):
    interaction: Literal["inspect", "monitor"]


class OnboardingAction(Action):
    step: int = Field(ge=0, le=9)
    interaction: Literal[
        "back",
        "next",
        "skip",
        "resume",
        "inspect",
        "monitor",
        "coverage",
    ]


class TutorialProgressAction(Action):
    step_id: TutorialStep
    interaction: Literal[
        "back", "next", "skip-step", "skip", "resume", "restart", "observed"
    ]


class DraftReviewRequest(Model):
    revision: int = Field(ge=0)
    topology: Topology | None = None


class MarketAction(Action):
    action: Literal["develop", "launch"]


class CampaignAction(Action):
    region: str | None = None
    regions: list[str] | None = Field(default=None, min_length=1, max_length=8)
    budget: float | None = Field(default=None, ge=10, le=100_000)
    duration: int | None = Field(default=None, ge=1, le=288)


class MarketView(Model):
    id: str
    name: str
    population: int
    potential: int
    language: str
    language_weights: dict[str, float]
    language_benefits: dict[str, float]
    cost: float
    duration: int
    remaining: int
    stage: Literal["planned", "developing", "ready", "active"]


class LanguageView(Model):
    name: str
    cost: float
    duration: int
    ready: bool
    remaining: int


class CampaignPlan(Model):
    region: str
    allocations: dict[str, CampaignAllocation]
    arrivals: list[float]
    peak_tick: int | None = None
    peak_rps: float | None = None
    baseline_peak_rps: float | None = None
    budget: float
    duration: int
    acquired: float
    cost_per_user: float | None


class Range(Model):
    low: float
    high: float


class DatabaseForecast(Model):
    current_utilization: dict[str, float]
    projected_utilization: dict[str, Range]
    current_write_capacity: float | None
    current_write_demand: float | None
    projected_write_capacity: Range | None
    projected_write_demand: Range | None


class Forecast(Model):
    rps: Range
    latency: Range
    availability: Range
    audience: Range
    confidence: Literal["low", "medium", "high"]
    plan: CampaignPlan | None = None
    databases: dict[NodeId, DatabaseForecast] = Field(default_factory=dict)


class Modification(Model):
    component: str
    field: str
    before: float | str
    after: float | str


class DraftReview(Model):
    revision: int
    errors: list[str]
    warnings: list[str]
    changes: dict[str, list[str]]
    details: list[Modification]
    daily_before: float
    daily_after: float
    install: float
    forecast: Forecast | None


class SaveSummary(Model):
    id: UUID
    name: str
    scenario: str
    tick: int
    day: int
    audience: int
    balance: float
    saved_at: datetime


class SavePreview(Model):
    name: str
    scenario: str
    day: int
    audience: int
    balance: float
    version: int
    exported_at: datetime | None


class BusinessPoint(Model):
    tick: int
    audience: int
    balance: float


class FinancePoint(FinanceSample):
    tick: int


class AdvertisingEstimate(Model):
    impressions: float
    revenue: float
    satisfaction_impact: float
    churn_impact: float


class Economy(Model):
    balance: float
    revenue: float
    operating: float
    development: float
    marketing: float
    deployment: float
    profit: float
    daily_infrastructure: float
    daily_revenue: float
    daily_operating: float
    daily_profit: float
    daily_total_expenses: float
    daily_net_profit: float
    purchases: list[tuple[int, OneTimeCosts]] = Field(default_factory=list)
    recent_purchases: OneTimeCosts
    revenue_sources: RevenueSources
    daily_sources: RevenueSources
    operating_costs: OperatingCosts
    daily_costs: OperatingCosts
    starting_capital: float
    cash_received: float
    subscription_cash: float
    deferred_subscription_revenue: float
    daily_active_users: float
    operating_margin: float | None
    arpdau: float | None
    cost_per_dau: float | None
    subscribers: int
    conversion: float
    premium_satisfaction: float
    daily_ad_impressions: float
    recorded_ticks: int
    history: list[FinancePoint]


class RequirementView(Model):
    id: str
    description: str
    met: bool


class FeatureView(Model):
    id: str
    state: Literal["locked", "available", "developing", "ready", "released"]
    remaining: int = 0
    requirements: list[str] = Field(default_factory=list)
    infrastructure: list[RequirementView] = Field(default_factory=list)
    can_release: bool = False
    enabled: bool = False
    can_enable: bool = False
    can_disable: bool = False
    dependents: list[str] = Field(default_factory=list)
    demand_change: float = 0


class CampaignView(Model):
    id: str
    regions: list[str] = Field(default_factory=list)
    remaining: int = 0
    progress: float = 0
    region: str | None = None
    budget: float | None = None
    acquired: float | None = None


class IncidentView(Model):
    id: str
    category: str
    title: str
    symptom: str
    severity: str
    start: int
    end: int
    active: bool
    cause: str | None
    target: str | None
    resolution: str | None
    failed_requests: int
    acknowledged: bool


class DeploymentView(Model):
    id: UUID
    tick: int
    summary: str
    cost: float
    comparison: DeploymentComparison | None = None


class GameView(SaveSummary):
    speed: Speed
    start_minute: int
    difficulty: Difficulty
    satisfaction: float
    production: Topology
    draft: Topology | None
    diagram: Diagram
    revision: int
    snapshot: Snapshot
    history: list[HistoryPoint]
    business_history: list[BusinessPoint]
    economy: Economy
    component_costs: dict[str, float]
    draft_costs: dict[str, float]
    features: list[FeatureView]
    product: ProductSettings
    advertising_estimates: dict[AdIntensity, AdvertisingEstimate]
    campaigns: list[CampaignView]
    markets: list[MarketView]
    languages: list[LanguageView]
    incidents: list[IncidentView]
    deployments: list[DeploymentView]
    settings: GameSettings
    tutorial: int
    onboarding: Onboarding
    peak: Metrics | None = None


class CatalogField(Model):
    label: str
    default: float | str
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None


class ComponentDefinition(Model):
    name: str
    category: str
    monthly: float
    daily: float
    fields: dict[str, CatalogField]
    presets: dict[str, dict[str, Setting]] = Field(default_factory=dict)
    description: str


class ScenarioDefinition(Model):
    name: str
    available: bool
    description: str


class FeatureDefinition(Model):
    name: str
    cost: float
    duration: int
    appeal: float
    operation: str | None
    prereq: list[str]
    requires: list[str]
    infrastructure: list[str]


class CampaignDefinition(Model):
    name: str
    cost: float
    duration: int
    audience: int
    spike: float
    description: str


class DifficultyDefinition(Model):
    name: str
    balance: float
    audience: int
    incident_chance: float


class StorageTier(Model):
    read_capacity: float
    write_capacity: float
    base_cost_surcharge: float


class Catalog(Model):
    diagram_layout: Literal[True] = True
    components: dict[str, ComponentDefinition]
    database_storage: dict[str, StorageTier]
    scenarios: dict[str, ScenarioDefinition]
    difficulties: dict[Difficulty, DifficultyDefinition]
    features: dict[str, FeatureDefinition]
    campaigns: dict[str, CampaignDefinition]
    operations: dict[str, str]
    connections: dict[str, list[str]]
    connection_types: dict[str, dict[str, str]]
    minutes_per_tick: int
    days_per_month: int
    premium_price_min: float
    premium_price_max: float
