import type { Section } from '../labels';

export const onboarding = [
  { title: 'Game time', text: 'Demand changes over the game day. Pause or change the speed from the header.', target: '[data-guide="clock"]' },
  { title: 'Infrastructure topology', text: 'Traffic flows through the edge balancer to the Messenger API. The API sends reads and writes to the primary database.', target: '[data-guide="canvas"]', section: 'build' },
  { title: 'Inspect the Messenger API', text: 'Select the Messenger API to see its configuration and connections.', target: '[data-id="api"].svelte-flow__node, [data-guide="api-list"]', section: 'build', action: true },
  { title: 'Deploy monitoring coverage', text: 'Add Monitoring. Connect the Messenger API and primary database to it with metrics collection links, then review and deploy the draft. Select Service history in the collector settings to record utilization over time.', target: '[data-guide="add"]', section: 'build', action: true },
  { title: 'Open Telemetry', text: 'Open Telemetry to see the metrics collected from the API and database.', target: '[data-guide-nav="monitor"]', action: true },
  { title: 'Identify a bottleneck', text: 'Check the highest resource load. Utilization close to or above 100% can limit throughput. A healthy service may have no bottleneck at current demand.', target: '[data-guide="diagnostics"]', section: 'monitor' },
  { title: 'Change capacity in Draft', text: 'Open the Messenger API configuration and adjust its instance size or replica count. Save the change to Draft.', target: '[data-guide="edit-api"]', section: 'build', action: true },
  { title: 'Review and deploy', text: 'Compare the predicted capacity and daily cost. Deploy the draft when you are ready.', target: '[data-guide="review"]', section: 'build', action: true },
  { title: 'Cash and operating costs', text: 'The header shows your cash balance and net profit per game day. Open Finance to see revenue, ongoing costs, and one-time purchases.', target: '[data-guide="balance"]' }
] satisfies { title: string; text: string; target: string; section?: Section; action?: boolean }[];
