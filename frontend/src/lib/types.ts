import type { TutorialProgress } from './workbench/onboarding';

export type Kind = 'source' | 'balancer' | 'api' | 'database' | 'replica' | 'cache' | 'limiter' | 'queue' | 'worker' | 'monitor';
export type Speed = 0 | 1 | 3 | 5;
export const difficulties = ['beginner', 'standard', 'expert'] as const;
export type Difficulty = typeof difficulties[number];
export type Point = { x: number; y: number };
export type Setting = string | number;
export type Component = { id: string; kind: Kind; name: string; position: Point; config: Record<string, Setting> };
export type Connection = { source: string; target: string };
export type Topology = { nodes: Component[]; edges: Connection[] };
export type DiagramGroup = { id: string; name: string; members: string[]; collapsed: boolean };
export type DiagramViewport = Point & { zoom: number };
export type Diagram = { positions: Record<string, Point>; routes: Record<string, Point[]>; groups: DiagramGroup[]; viewports?: Partial<Record<'compact' | 'wide', DiagramViewport>> };
export type Metrics = { rps: number; throughput: number; availability: number; latency: number; p95_latency?: number | null; errors: number; rejected: number };
export type DatabaseUpgrade = 'cpu' | 'memory' | 'connections' | 'storage' | 'nvme' | 'nvme_array' | 'legacy';
export type DatabaseTelemetry = {
  read_demand: number; disk_read_iops?: number | null; disk_write_iops?: number | null; disk_capacity_iops?: number | null; write_demand: number; write_capacity: number | null;
  replication_demand: number; replication_throughput: number; replication_backlog: number;
  diagnostic: {
    level: 'write_exceeded' | 'write_pressure' | 'resource_pressure';
    resources: string[]; limiting?: string[]; upgrades: DatabaseUpgrade[]; read_options: boolean;
  } | null;
};
export type Research = { id: string; state: 'unavailable' | 'available' | 'developing' | 'completed'; remaining: number };
export type ResearchDefinition = { name: string; cost: number; duration: number; prereq: string[]; description: string; unlocks: string; advantages: string; tradeoffs: string; guide: string };
export type ComponentMetrics = {
  completed_operations?: Record<string, number>; service_errors?: number | null; service_latency?: number | null;
  operations?: Record<string, number>; service_role?: string | null; data_domain?: string | null; partition_share?: number | null; daily_cost?: number; autoscaling?: string | null;
  status: 'healthy' | 'warning' | 'overloaded' | 'failed' | 'idle';
  rps: number; throughput: number; latency: number; utilization: Record<string, number>;
  cache_hit: number | null; backlog: number | null; active_instances: number | null; storage_used: number | null; replication_lag: number | null;
  database?: DatabaseTelemetry | null;
  queue_wait_minutes: number | null; jobs_dropped: number | null; jobs_expired: number | null;
};
export type MonitorCoverage = { capacity: number; history: boolean; covered: string[]; dropped: string[]; failed: boolean };
export type DemandOverview = {
  day: number; utc_minute: number; expected: number[]; campaign_lift: number; event_lift: number;
  regions: { id: string; name: string; utc_offset: number; local_minute: number; audience: number; daily_active_users: number; requests: number; daily_ad_revenue: number; earned_ad_revenue: number }[];
};
export type Snapshot = {
  demand_overview: DemandOverview | null; metrics: Metrics; components: Record<string, ComponentMetrics>;
  traffic: (Connection & { rps: number; operations: Record<string, number> })[]; demand: Record<string, number>; monitored: boolean; monitors: Record<string, MonitorCoverage>;
};
export type History = { tick: number; audience: number; balance: number; metrics: Metrics; peak_utilization?: Record<string, number>; resource_utilization?: Record<string, Record<string, number>> };
export type Incident = {
  id: string; category?: string; title: string; symptom: string; severity: string; start: number; end: number; active: boolean;
  cause: string | null; target: string | null; resolution: string | null; failed_requests: number; acknowledged: boolean;
};
export type Settings = { reduced_motion: boolean; show_tutorial: boolean; show_objectives?: boolean };
export type Save = { id: string; name: string; scenario: string; tick: number; day: number; audience: number; balance: number; saved_at: string };
export type RevenueSources = { advertising: number; subscriptions: number; legacy: number };
export type OperatingCosts = { infrastructure: number; traffic: number; payments: number; legacy: number };
export type FinancePoint = { tick: number; revenue: RevenueSources; expenses: OperatingCosts; cash_received: number; daily_active_users: number; ad_impressions: number };
export type AdIntensity = 'low' | 'moderate' | 'high';
export type ProductSettings = {
  ad_intensity: AdIntensity; premium_price: number; premium_fast_sync: boolean;
  sync_frequency: 'relaxed' | 'standard' | 'frequent';
  media_quality: 'compressed' | 'standard' | 'high';
  north_america: boolean;
};
export type AdEstimate = { impressions: number; revenue: number; satisfaction_impact: number; churn_impact: number };
export type Economy = { balance: number; revenue: number; operating: number; development: number; marketing: number; deployment: number; profit: number; daily_infrastructure: number; daily_revenue: number; daily_operating: number; daily_profit: number;
  daily_total_expenses: number; daily_net_profit: number;
  recent_purchases: { development: number; marketing: number; deployment: number };
  purchases: [number, Economy['recent_purchases']][];
  revenue_sources: RevenueSources; daily_sources: RevenueSources; operating_costs: OperatingCosts; daily_costs: OperatingCosts;
  starting_capital: number; cash_received: number; subscription_cash: number; deferred_subscription_revenue: number; daily_active_users: number;
  operating_margin: number | null; arpdau: number | null; cost_per_dau: number | null; subscribers: number;
  conversion: number; premium_satisfaction: number; daily_ad_impressions: number; recorded_ticks: number; history: FinancePoint[];
};
export type Feature = {
  id: string; state: 'locked' | 'available' | 'developing' | 'ready' | 'released';
  enabled: boolean; can_enable: boolean; can_disable: boolean; dependents: string[];
  remaining: number; requirements: string[]; demand_change: number; can_release: boolean;
  infrastructure: { id: string; description: string; met: boolean }[];
};
export type Campaign = { id: string; regions?: string[]; remaining: number; progress: number; region: string | null; budget: number | null; acquired: number | null };
export type Market = { id: string; name: string; population: number; potential: number; language: string; language_weights: Record<string, number>; language_benefits: Record<string, number>; cost: number; duration: number; remaining: number; stage: 'planned' | 'developing' | 'ready' | 'active' };
export type ProductLanguage = { name: string; cost: number; duration: number; ready: boolean; remaining: number };
export type CampaignPlan = {
  region: string; budget: number; duration: number; acquired: number; cost_per_user: number | null;
  allocations: Record<string, { budget: number; audience: number }>; arrivals: number[];
  peak_tick: number | null; peak_rps: number | null; baseline_peak_rps: number | null;
};
export type ResourcePressure = { component: string; resource: string; utilization: number };
export type Deployment = { id: string; tick: number; summary: string; cost: number; comparison: {
  before: Metrics; after: Metrics; daily_before: number; daily_after: number;
  capacity_before?: number | null; capacity_after?: number | null;
  pressure_before?: ResourcePressure | null; pressure_after?: ResourcePressure | null;
} | null };
export type Game = Save & {
  engineering: Research[]; engineering_lesson: number;
  migration: { request_id: string; ready_at: number; topology: Topology; cost: number } | null;
  start_minute: number; speed: Speed; difficulty: Difficulty; satisfaction: number; production: Topology; draft: Topology | null; revision: number;
  diagram: Diagram;
  snapshot: Snapshot; history: History[]; business_history: Pick<History, 'tick' | 'audience' | 'balance'>[]; economy: Economy; component_costs: Record<string, number>; draft_costs: Record<string, number>; features: Feature[]; campaigns: Campaign[]; markets: Market[]; languages: ProductLanguage[];
  product: ProductSettings; advertising_estimates: Partial<Record<AdIntensity, AdEstimate>>;
  incidents: Incident[]; deployments: Deployment[]; settings: Settings; tutorial: number; onboarding: TutorialProgress; peak: Metrics | null;
};
export type Field = { label: string; default: Setting; min: number | null; max: number | null; step: number | null; options: string[] | null };
export type Definition = { name: string; category: string; monthly: number; daily: number; fields: Record<string, Field>; presets?: Record<string, Record<string, Setting>>; description: string };
export type Scenario = { name: string; available: boolean; description: string };
export type FeatureDefinition = { name: string; cost: number; duration: number; appeal: number; operation: string | null; prereq: string[]; requires: Kind[]; infrastructure: string[] };
export type CampaignDefinition = { name: string; cost: number; duration: number; audience: number; spike: number; description: string };
export type Catalog = {
  service_roles: Record<string, string[]>; operation_domains: Record<string, string>;
  engineering: Record<string, ResearchDefinition>;
  diagram_layout: true;
  database_storage: Record<string, { read_capacity: number; write_capacity: number; base_cost_surcharge: number }>;
  components: Record<Kind, Definition>; scenarios: Record<string, Scenario>;
  features: Record<string, FeatureDefinition>; campaigns: Record<string, CampaignDefinition>;
  difficulties: Record<Difficulty, { name: string; balance: number; audience: number; incident_chance: number }>;
  operations: Record<string, string>; connections: Record<Kind, Kind[]>;
  connection_types: Record<Kind, Partial<Record<Kind, keyof typeof import('./workbench/connections').connectionLabels>>>;
  minutes_per_tick: number; days_per_month: number; premium_price_min: number; premium_price_max: number;
};
export type Interval = { low: number; high: number };
export type DatabaseForecast = {
  current_utilization: Record<string, number>; projected_utilization: Record<string, Interval>;
  current_write_capacity: number | null; current_write_demand?: number | null; projected_write_capacity: Interval | null;
  projected_write_demand: Interval | null;
};
export type Forecast = { rps: Interval; latency: Interval; availability: Interval; audience: Interval; confidence: 'low' | 'medium' | 'high'; plan?: CampaignPlan | null; databases?: Record<string, DatabaseForecast> };
export type Review = {
  migration_ticks?: number; migration_cost?: number;
  revision: number; errors: string[]; warnings: string[]; changes: Record<string, string[]>;
  details: { component: string; field: string; before: Setting; after: Setting }[];
  daily_before: number; daily_after: number; install: number; forecast: Forecast | null;
};

export type SavePreview = Pick<Save, 'name' | 'scenario' | 'day' | 'audience' | 'balance'> & {
  version: number; exported_at: string | null;
};
