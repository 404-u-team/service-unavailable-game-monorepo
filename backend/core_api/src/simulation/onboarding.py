"""Stable save identifiers for the workbench walkthrough."""

from enum import StrEnum


class TutorialStep(StrEnum):
    CLOCK = "clock"
    BALANCE = "balance"
    TOPOLOGY = "topology"
    COMPONENTS = "components"
    SELECT_API = "select-api"
    CONFIGURATION = "configuration"
    CAPACITY = "capacity"
    METRICS = "metrics"
    METRICS_COVERAGE = "metrics-coverage"
    RETURN_CONFIGURATION = "return-configuration"
    MONITORING = "monitoring"
    ADD_COLLECTOR = "add-collector"
    LINK_COVERAGE = "link-coverage"
    MONITOR_REVIEW = "monitor-review"
    MONITOR_COSTS = "monitor-costs"
    MONITOR_DEPLOY = "monitor-deploy"
    OPEN_TELEMETRY = "open-telemetry"
    TELEMETRY = "telemetry"
    API_UTILIZATION = "api-utilization"
    API_THROUGHPUT = "api-throughput"
    INFRASTRUCTURE = "infrastructure"
    CREATE_DRAFT = "create-draft"
    EDIT_API = "edit-api"
    SAVE_CAPACITY = "save-capacity"
    CAPACITY_REVIEW = "capacity-review"
    CAPACITY_FORECAST = "capacity-forecast"
    CAPACITY_COSTS = "capacity-costs"
    CAPACITY_DEPLOY = "capacity-deploy"
    COMPARE = "compare"
    ECONOMY = "economy"
    OPEN_FINANCE = "open-finance"
    FINANCE = "finance"
    EXPENSES = "expenses"
    OPEN_PRODUCT = "open-product"
    PRODUCT = "product"
    PREMIUM = "premium"
    OPEN_GROWTH = "open-growth"
    GROWTH = "growth"
    COMPLETE = "complete"


TUTORIAL_STEPS = tuple(TutorialStep)
LEGACY_TUTORIAL_STEPS = (
    TutorialStep.CLOCK,
    TutorialStep.TOPOLOGY,
    TutorialStep.SELECT_API,
    TutorialStep.MONITORING,
    TutorialStep.OPEN_TELEMETRY,
    TutorialStep.TELEMETRY,
    TutorialStep.INFRASTRUCTURE,
    TutorialStep.CAPACITY_REVIEW,
    TutorialStep.OPEN_FINANCE,
    TutorialStep.COMPLETE,
)
