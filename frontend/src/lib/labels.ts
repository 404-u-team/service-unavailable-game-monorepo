import { Activity, ArrowUpRight, BookOpen, Boxes, Cable, Database, Diamond, Gauge,
  GitFork, HardDrive, House, Layers, List, Network, Radio, Server, Settings2, Wallet, Workflow } from '@lucide/svelte';
import type { Kind } from './types';

export const sections = {
  home: { name: 'Overview', mobile: 'Home', icon: House, description: 'Service health and activity' },
  build: { name: 'Topology', mobile: 'Build', icon: Diamond, description: 'Infrastructure architecture' },
  monitor: { name: 'Telemetry', mobile: 'Monitor', icon: Activity, description: 'Performance and observability' },
  growth: { name: 'Growth', mobile: 'Growth', icon: ArrowUpRight, description: 'Campaigns and audience' },
  finance: { name: 'Finance', mobile: 'Finance', icon: Wallet, description: 'Balance, income and expenses' },
  events: { name: 'Events', mobile: 'Events', icon: List, description: 'Warnings and incident history' },
  product: { name: 'Product', mobile: 'Product', icon: Boxes, description: 'Features and releases' },
  guide: { name: 'Guide', mobile: 'Guide', icon: BookOpen, description: 'Tutorial and component reference' },
  saves: { name: 'Saved games', mobile: 'Saved games', icon: HardDrive, description: 'Open another save' },
  settings: { name: 'Settings', mobile: 'Settings', icon: Settings2, description: 'Game preferences' },
  more: { name: 'More', mobile: 'More', icon: List, description: 'Service management' }
};

export type Section = keyof typeof sections;
export const desktop: Section[] = ['build', 'monitor', 'growth', 'finance', 'events', 'product', 'guide', 'settings'];
export const mobile: Section[] = ['home', 'build', 'monitor', 'growth', 'more'];
export const more: Section[] = ['product', 'finance', 'events', 'guide', 'saves', 'settings'];

export const componentIcon = {
  source: Radio, balancer: GitFork, api: Server, database: Database, replica: Database,
  cache: Layers, limiter: Gauge, queue: Cable, worker: Workflow, monitor: Network
} satisfies Record<Kind, typeof Server>;

export const tutorial = [
  { title: 'Inspect an API server', text: 'Open Topology and select the Messenger API to see its instance settings.', section: 'build' },
  { title: 'Change the API configuration', text: 'Edit the API server, then save a CPU, RAM or instance change to the draft.', section: 'build' },
  { title: 'Deploy the draft', text: 'Open Deployment review. Check the forecast and confirm the change.', section: 'build' },
  { title: 'Review telemetry', text: 'Open Telemetry to see how the deployment changed service metrics.', section: 'monitor' }
] as const;

export const statusLabel = {
  healthy: 'Healthy', warning: 'Warning', overloaded: 'Overloaded', failed: 'Failed', idle: 'Idle'
};
