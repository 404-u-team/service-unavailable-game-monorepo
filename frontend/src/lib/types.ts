export type Kind = 'source' | 'balancer' | 'api' | 'database' | 'replica' | 'cache' | 'limiter' | 'queue' | 'worker' | 'monitor';
export type Speed = 0 | 1 | 3;
export const difficulties = ['beginner', 'standard', 'expert'] as const;
export type Difficulty = typeof difficulties[number];
export type Point = { x: number; y: number };
export type Setting = string | number;
export type Component = { id: string; kind: Kind; name: string; position: Point; config: Record<string, Setting> };
export type Connection = { source: string; target: string };
export type Topology = { nodes: Component[]; edges: Connection[] };
export type Metrics = { rps: number; throughput: number; availability: number; latency: number; errors: number; rejected: number };
export type ComponentMetrics = {
  status: 'healthy' | 'warning' | 'overloaded' | 'failed' | 'idle';
  rps: number; throughput: number; latency: number; utilization: Record<string, number>;
  cache_hit: number | null; backlog: number | null; active_instances: number | null; storage_used: number | null;
};
export type Snapshot = {
  metrics: Metrics; components: Record<string, ComponentMetrics>;
  traffic: (Connection & { rps: number })[]; demand: Record<string, number>; monitored: boolean;
};
export type History = { tick: number; audience: number; balance: number; metrics: Metrics };
export type Incident = {
  id: string; title: string; symptom: string; severity: string; start: number; end: number; active: boolean;
  cause: string | null; target: string | null; resolution: string | null; failed_requests: number; acknowledged: boolean;
};
export type Settings = { reduced_motion: boolean; show_tutorial: boolean };
export type Save = { id: string; name: string; scenario: string; tick: number; audience: number; balance: number; saved_at: string };
export type Economy = { balance: number; revenue: number; operating: number; development: number; marketing: number; deployment: number; profit: number; daily_infrastructure: number; daily_revenue: number; daily_operating: number; daily_profit: number };
export type Feature = { id: string; state: 'locked' | 'available' | 'developing' | 'ready' | 'released'; remaining: number; requirements: string[]; demand_change: number };
export type Campaign = { id: string; remaining: number; progress: number };
export type Deployment = { id: string; tick: number; summary: string; cost: number };
export type Game = Save & {
  speed: Speed; difficulty: Difficulty; satisfaction: number; production: Topology; draft: Topology | null; revision: number;
  snapshot: Snapshot; history: History[]; business_history: Pick<History, 'tick' | 'audience' | 'balance'>[]; economy: Economy; component_costs: Record<string, number>; draft_costs: Record<string, number>; features: Feature[]; campaigns: Campaign[];
  incidents: Incident[]; deployments: Deployment[]; settings: Settings; tutorial: number; peak: Metrics | null;
};
export type Field = { label: string; default: Setting; min: number | null; max: number | null; step: number | null; options: string[] | null };
export type Definition = { name: string; category: string; daily: number; fields: Record<string, Field>; description: string };
export type Scenario = { name: string; available: boolean; description: string };
export type FeatureDefinition = { name: string; cost: number; duration: number; appeal: number; operation: string | null; prereq: string[]; requires: Kind[] };
export type CampaignDefinition = { name: string; cost: number; duration: number; audience: number; spike: number; description: string };
export type Catalog = {
  components: Record<Kind, Definition>; scenarios: Record<string, Scenario>;
  features: Record<string, FeatureDefinition>; campaigns: Record<string, CampaignDefinition>;
  difficulties: Record<Difficulty, { name: string; balance: number; audience: number; incident_chance: number }>;
  operations: Record<string, string>; connections: Record<Kind, Kind[]>; minutes_per_tick: number;
};
export type Interval = { low: number; high: number };
export type Forecast = { rps: Interval; latency: Interval; availability: Interval; audience: Interval; confidence: 'low' | 'medium' | 'high' };
export type Review = {
  revision: number; errors: string[]; warnings: string[]; changes: Record<string, string[]>;
  details: { component: string; field: string; before: Setting; after: Setting }[];
  daily_before: number; daily_after: number; install: number; forecast: Forecast | null;
};
