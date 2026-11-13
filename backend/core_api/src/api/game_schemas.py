from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from src.simulation.models import (
    DeploymentComparison,
    Diagram,
    Difficulty,
    GameSettings,
    HistoryPoint,
    Metrics,
    Model,
    Name,
    Snapshot,
    Speed,
    Topology,
)

ScenarioId = Literal["messenger", "social", "multiplayer", "education"]
FeatureId = Literal["text", "groups", "images", "voice", "search", "files", "calls"]
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


class SettingsAction(Action):
    settings: GameSettings


class FeatureAction(Action):
    action: Literal["develop", "release"]


class TutorialAction(Action):
    interaction: Literal["inspect", "monitor"]


class DraftReviewRequest(Model):
    revision: int = Field(ge=0)
    topology: Topology | None = None


class Range(Model):
    low: float
    high: float


class Forecast(Model):
    rps: Range
    latency: Range
    availability: Range
    audience: Range
    confidence: Literal["low", "medium", "high"]


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
    audience: int
    balance: float
    saved_at: datetime


class BusinessPoint(Model):
    tick: int
    audience: int
    balance: float


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


class FeatureView(Model):
    id: str
    state: Literal["locked", "available", "developing", "ready", "released"]
    remaining: int = 0
    requirements: list[str] = Field(default_factory=list)
    demand_change: float = 0


class CampaignView(Model):
    id: str
    remaining: int = 0
    progress: float = 0


class IncidentView(Model):
    id: str
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
    campaigns: list[CampaignView]
    incidents: list[IncidentView]
    deployments: list[DeploymentView]
    settings: GameSettings
    tutorial: int
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
    daily: float
    fields: dict[str, CatalogField]
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


class Catalog(Model):
    components: dict[str, ComponentDefinition]
    scenarios: dict[str, ScenarioDefinition]
    difficulties: dict[Difficulty, DifficultyDefinition]
    features: dict[str, FeatureDefinition]
    campaigns: dict[str, CampaignDefinition]
    operations: dict[str, str]
    connections: dict[str, list[str]]
    connection_types: dict[str, dict[str, str]]
    minutes_per_tick: int
