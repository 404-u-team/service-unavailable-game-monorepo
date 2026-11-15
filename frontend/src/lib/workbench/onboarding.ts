import type { Section } from '../labels';
import type { Game, Topology } from '../types';

export const chapters = [
  'Interface', 'Components', 'Monitoring', 'Infrastructure changes', 'Economy'
] as const;

export const target = {
  research: 'engineering.research',
  clock: 'header.clock', balance: 'header.balance',
  canvas: 'topology.canvas', canvasTools: 'topology.canvas-tools', list: 'topology.component-list',
  api: 'topology.api', openInspector: 'topology.open-inspector',
  configuration: 'inspector.configuration-tab', metrics: 'inspector.metrics-tab',
  capacity: 'inspector.capacity', missingMetrics: 'inspector.missing-metrics',
  cpu: 'inspector.cpu-metric', throughput: 'inspector.throughput', edit: 'inspector.edit-configuration',
  add: 'topology.component-catalog', catalogSearch: 'catalog.search', collector: 'catalog.monitoring',
  connect: 'topology.connect', source: 'connection.source', destination: 'connection.target',
  saveLink: 'connection.confirm', createDraft: 'topology.create-draft', returnDraft: 'topology.return-draft', viewProduction: 'topology.view-production',
  instance: 'configuration.instance-size', save: 'configuration.save',
  review: 'deployment.review-button', forecast: 'deployment.costs', capacityForecast: 'deployment.forecast', deploy: 'deployment.confirm',
  compare: 'deployment.comparison', done: 'deployment.done', eventComparison: 'events.latest-comparison',
  coverage: 'monitoring.coverage', finance: 'finance.revenue', expenses: 'finance.expenses',
  monetization: 'product.monetization', premium: 'product.premium', growth: 'growth.readiness', close: 'dialog.close'
} as const;

export type Target = typeof target[keyof typeof target] | `navigation.${Section}`;
export const nav = (section: Section): Target => `navigation.${section}`;

type Step = { id: string; chapter: number; title: string; text: string; mode?: 'action' | 'server'; section?: Section; target?: Target };

export const onboarding = [
  { id: 'clock', chapter: 0, title: 'Game time', text: 'Pause or change the simulation speed here. Demand changes over the game day.', target: target.clock },
  { id: 'balance', chapter: 0, title: 'Cash and daily profit', text: 'The top figure is cash on hand. The figure below is your net profit or loss per game day.', target: target.balance },
  { id: 'topology', chapter: 0, title: 'Navigate the topology', text: 'Drag to pan and use the canvas controls to zoom or fit the diagram. You can also switch to a component list.', section: 'build', target: target.canvas },
  { id: 'components', chapter: 1, title: 'From traffic to storage', text: 'Nodes are infrastructure components. The arrows show how requests reach the API through the balancer and how the API reads and writes to the database.', section: 'build', target: target.canvas },
  { id: 'select-api', chapter: 1, title: 'Select the API', text: 'Select the highlighted API server. Its inspector opens beside the canvas or below it on a small screen.', mode: 'action', section: 'build', target: target.api },
  { id: 'configuration', chapter: 1, title: 'Open Configuration', text: 'Choose Configuration in the component inspector to see the resources assigned to the API.', mode: 'action', section: 'build', target: target.configuration },
  { id: 'capacity', chapter: 1, title: 'Read the capacity settings', text: 'vCPU determines compute capacity. RAM holds active data and connections. Replicas share traffic, and concurrency limits how many requests each instance can handle at once.', section: 'build', target: target.capacity },
  { id: 'metrics', chapter: 1, title: 'Switch to Metrics', text: 'Choose Metrics to see throughput, latency and resource utilization when this component is covered by Monitoring.', mode: 'action', section: 'build', target: target.metrics },
  { id: 'metrics-coverage', chapter: 1, title: 'Check for component metrics', text: 'Incoming shows requests arriving per second. Processed shows what the component handled. If these readings are missing, deploy a linked Monitoring collector to see them.', section: 'build' },
  { id: 'return-configuration', chapter: 1, title: 'Return to Configuration', text: 'Choose Configuration in the inspector to go back to the component settings.', mode: 'action', section: 'build', target: target.configuration },
  { id: 'monitoring', chapter: 2, title: 'Set up monitoring coverage', text: 'Monitoring collects metrics through links from components. Each link uses one collection slot. Service history reserves two additional slots.', section: 'build', target: target.add },
  { id: 'add-collector', chapter: 2, title: 'Add a Monitoring collector', text: 'Choose Monitoring in the component library. The collector is added to a draft for review before it costs anything.', mode: 'server', section: 'build', target: target.collector },
  { id: 'link-coverage', chapter: 2, title: 'Link the API and database', text: 'Create a metrics collection link from each highlighted source to Monitoring.', mode: 'server', section: 'build', target: target.connect },
  { id: 'monitor-review', chapter: 2, title: 'Review monitoring changes', text: 'Open Deployment review to check the links and see how much the collector will cost.', mode: 'action', section: 'build', target: target.review },
  { id: 'monitor-costs', chapter: 2, title: 'Check the monitoring costs', text: 'Review the new daily infrastructure cost and the one-time installation charge before deploying.', section: 'build', target: target.forecast },
  { id: 'monitor-deploy', chapter: 2, title: 'Deploy monitoring coverage', text: 'Check the one-time and daily costs, then choose Deploy changes to start collecting metrics. You can skip if you want to keep the draft.', mode: 'server', section: 'build', target: target.deploy },
  { id: 'open-telemetry', chapter: 2, title: 'Open Telemetry', text: 'Use the highlighted navigation link to see what Monitoring collects across your service.', mode: 'action', target: nav('monitor') },
  { id: 'telemetry', chapter: 2, title: 'Check who is reporting', text: 'Monitoring coverage lists the connected components and available slots. Node health and Diagnostics below show the resource load and possible bottlenecks.', section: 'monitor', target: target.coverage },
  { id: 'api-utilization', chapter: 2, title: 'Read live API utilization', text: 'CPU utilization compares current demand with available compute. Around 100% means little spare capacity.', section: 'build', target: target.cpu },
  { id: 'api-throughput', chapter: 2, title: 'Compare incoming and processed requests', text: 'The Metrics tab shows how many requests arrive and how many the API processes each second. A sustained gap can indicate a capacity limit or a struggling dependency.', section: 'build', target: target.throughput },
  { id: 'infrastructure', chapter: 3, title: 'Plan an infrastructure change', text: 'A draft lets you change components while production keeps running. You can stop here and resume from Settings or the Guide.', section: 'build', target: target.canvasTools },
  { id: 'create-draft', chapter: 3, title: 'Create a draft', text: 'Create a draft to start editing a copy of production. If you already have one, the tutorial will use it.', mode: 'server', section: 'build', target: target.createDraft },
  { id: 'edit-api', chapter: 3, title: 'Open the API settings', text: 'Open Edit configuration from the API inspector.', mode: 'action', section: 'build', target: target.edit },
  { id: 'save-capacity', chapter: 3, title: 'Change capacity in the draft', text: 'Choose a different instance size or adjust a resource such as vCPU or replica count. Save the change to the draft.', mode: 'server', section: 'build', target: target.instance },
  { id: 'capacity-review', chapter: 3, title: 'Open Deployment review', text: 'Review the draft to compare projected daily costs and performance before committing your changes.', mode: 'action', section: 'build', target: target.review },
  { id: 'capacity-forecast', chapter: 3, title: 'Read the deployment forecast', text: 'Check the projected range of request load, availability and latency for the draft. After deployment you can compare before and after.', section: 'build', target: target.capacityForecast },
  { id: 'capacity-costs', chapter: 3, title: 'Check the deployment costs', text: 'Compare current and projected daily infrastructure costs. The installation charge is paid once, when you deploy.', section: 'build', target: target.forecast },
  { id: 'capacity-deploy', chapter: 3, title: 'Confirm the deployment', text: 'Review all pending edits and check the one-time charge and daily cost. Deploy when you are ready, or skip to keep the draft.', mode: 'server', section: 'build', target: target.deploy },
  { id: 'compare', chapter: 3, title: 'Compare before and after', text: 'Compare throughput, latency and daily costs at deployment time. The comparison is also kept in Events.', target: target.compare },
  { id: 'economy', chapter: 4, title: 'Follow the money', text: 'Use Finance to see what the service earns and what it spends. Product and Growth help you decide where to invest.', target: target.balance },
  { id: 'open-finance', chapter: 4, title: 'Open Finance', text: 'Open Finance to inspect your revenue and expenses.', mode: 'action', target: target.balance },
  { id: 'finance', chapter: 4, title: 'Read the revenue breakdown', text: 'Revenue comes from served ads and premium subscriptions. Finance shows revenue per game day and to date.', section: 'finance', target: target.finance },
  { id: 'expenses', chapter: 4, title: 'Read the expense breakdown', text: 'Operating costs include infrastructure, traffic and payment fees. Deployments and development appear separately as one-time purchases.', section: 'finance', target: target.expenses },
  { id: 'open-product', chapter: 4, title: 'Open Product', text: 'Open Product to see how to develop and release features, including monetization.', mode: 'action', target: nav('product') },
  { id: 'product', chapter: 4, title: 'Explore advertising', text: 'Advertising earns revenue from served ads after release. Check the additional request load and the effect of ad intensity on players.', section: 'product', target: target.monetization },
  { id: 'premium', chapter: 4, title: 'Explore premium subscriptions', text: 'Premium earns recurring revenue after release. Its faster synchronization can increase request load. Review the requirements before starting development.', section: 'product', target: target.premium },
  { id: 'open-growth', chapter: 4, title: 'Open Growth', text: 'Open Growth to see how a campaign could change demand.', mode: 'action', target: nav('growth') },
  { id: 'growth', chapter: 4, title: 'Check capacity before growing', text: 'Campaigns can bring more users and more requests. Compare projected load with current capacity and budget for any infrastructure you need to add.', section: 'growth', target: target.growth }
] as const satisfies readonly Step[];

export type StepId = typeof onboarding[number]['id'] | 'complete';
export type TutorialEvent = 'component-selected' | 'configuration-opened' | 'metrics-opened';
export type TutorialAction = 'back' | 'next' | 'skip-step' | 'skip' | 'resume' | 'restart' | 'observed';
export type TutorialProgress = { step: number; furthest: number; skipped: boolean; step_id?: StepId | null; furthest_id?: StepId | null };

const legacySteps: StepId[] = ['clock', 'topology', 'select-api', 'monitoring', 'open-telemetry', 'telemetry', 'infrastructure', 'capacity-review', 'open-finance', 'complete'];
export const stepId = (progress: TutorialProgress) => progress.step_id ?? legacySteps[progress.step] ?? 'complete';

export function tutorialApi(topology: Topology) {
  return topology.nodes.find((node) => node.id === 'api' && node.kind === 'api') ?? topology.nodes.find((node) => node.kind === 'api');
}

export function coverageNodes(topology: Topology) {
  const api = tutorialApi(topology);
  if (!api) return [];
  const database = topology.nodes.find((node) => node.kind === 'database' &&
    topology.edges.some((edge) => edge.source === api.id && edge.target === node.id));
  return [api, ...(database ? [database] : [])];
}

export function monitored(game: Game) {
  const required = coverageNodes(game.production);
  return required.length > 0 && required.every((node) => game.snapshot.components[node.id]);
}

export function draftCoverage(game: Game, fallbackSlots: number) {
  const topology = game.draft ?? game.production;
  const collectors = topology.nodes.filter((node) => node.kind === 'monitor');
  const linked = new Set(collectors.flatMap((collector) => {
    const slots = Number(collector.config.slots ?? fallbackSlots);
    const capacity = slots - (slots >= 3 && collector.config.detail === 'Service history' ? 2 : 0);
    return topology.edges.filter((edge) => edge.target === collector.id).map((edge) => edge.source).sort().slice(0, capacity);
  }));
  const missing = coverageNodes(game.production).filter((node) => !linked.has(node.id));
  return { collectors, missing };
}

export function apiConfigChanged(before: Topology, after: Topology, defaults: Record<string, unknown>) {
  const api = tutorialApi(before);
  if (!api) return false;
  const updated = after.nodes.find((node) => node.id === api.id && node.kind === 'api');
  return Boolean(updated && [...new Set([...Object.keys(api.config), ...Object.keys(updated.config), ...Object.keys(defaults)])]
    .some((key) => (api.config[key] ?? defaults[key]) !== (updated.config[key] ?? defaults[key])));
}

export type TutorialArchitecture = {
  api?: string; missingDraftApi: boolean; selected: string; inspector: boolean; tab: 'configuration' | 'metrics';
  dialog?: string; layout: 'canvas' | 'list'; viewingDraft: boolean; connectSource: string; connectTarget: string;
  changedConfig: boolean; reviewReady: boolean; reviewPending: boolean; reviewValid: boolean; comparison: boolean; hasForecast: boolean; collectorVisible: boolean;
};

type View = { target?: Target; instruction?: string; args?: string[]; open?: Section; observed?: boolean; allowed?: boolean };
type Context = {
  game: Game; section: Section; ui?: TutorialArchitecture; event?: { step: StepId; name: TutorialEvent };
  apiDefaults: Record<string, unknown>; monitorSlots: number; compact: boolean;
};

export function tutorialView(step: Step, context: Context): View {
  const { game, section, ui, event, apiDefaults, monitorSlots, compact } = context;
  const id = step.id;
  const did = (name: TutorialEvent) => event?.step === id && event.name === name;
  const coverage = () => draftCoverage(game, monitorSlots);
  const close = { target: target.close, instruction: 'Close this dialog to continue the tutorial.' };
  const go = (destination: Section, control = nav(destination)): View => section === destination
    ? { observed: true }
    : { target: control, open: destination, allowed: true };

  if (id === 'open-telemetry') {
    if (ui?.dialog === 'deployed') return { target: target.done, instruction: 'Choose Done, then open Telemetry.' };
    return go('monitor');
  }
  if (id === 'open-finance') return go('finance', section === 'more' ? nav('finance') : target.balance);
  if (id === 'open-product') {
    if (compact && section !== 'more' && section !== 'product') {
      return { target: nav('more'), instruction: 'Open More to find Product.' };
    }
    return go('product');
  }
  if (id === 'open-growth') return go('growth');
  if (id === 'compare') {
    if (ui?.comparison) return { target: target.compare, allowed: true };
    if (game.deployments[0]?.comparison) return section === 'events'
      ? { target: target.eventComparison, instruction: 'Open the saved comparison to see the before and after metrics.', allowed: true }
      : { open: 'events', instruction: 'Open Events to see the saved deployment comparison.' };
    return { instruction: 'A comparison will be available in Events after a deployment.', allowed: true };
  }

  if (step.section && step.section !== section) return { open: step.section };
  if (step.section === 'build' && !ui) return {};

  const inspectApi = ['select-api', 'configuration', 'capacity', 'metrics', 'metrics-coverage',
    'return-configuration', 'api-utilization', 'api-throughput', 'edit-api', 'save-capacity'].includes(id);
  if (inspectApi && ui?.missingDraftApi && (id !== 'edit-api' && id !== 'save-capacity')) return ui.dialog ? close : {
    target: target.viewProduction, instruction: 'The API is missing from this draft. View production to inspect the live component.'
  };
  if (id === 'select-api') return ui?.dialog ? close : ui?.api
    ? { target: target.api, observed: ui.selected === ui.api && did('component-selected') }
    : { instruction: 'There is no API server in the current topology. You can skip this step.' };

  if (inspectApi) {
    if (id === 'save-capacity' && game.draft && apiConfigChanged(game.production, game.draft, apiDefaults) && ui?.dialog !== 'configuration') {
      return { observed: true };
    }
    if (!ui?.api) return { instruction: 'There is no API server in the current topology. You can skip this step.' };
    if ((id === 'edit-api' || id === 'save-capacity') && game.draft && !ui.viewingDraft) return ui.dialog ? close : {
      target: target.returnDraft, instruction: 'Return to the draft to edit the API.'
    };
    if (ui.dialog === 'configuration' && ui.selected === ui.api) {
      if (id === 'edit-api') return { observed: true };
      if (id === 'save-capacity') return ui.changedConfig
        ? { target: target.save, instruction: 'Save the configuration to the draft.' }
        : { target: target.instance };
      return close;
    }
    if (ui.dialog && ui.dialog !== 'inspector') return close;
    if (ui.selected !== ui.api) return ui.dialog === 'inspector' ? close
      : { target: target.api, instruction: 'Select the highlighted API server to continue.' };
    if (!ui.inspector) return { target: target.openInspector, instruction: 'Choose Open component to show the full inspector.' };

    if (id === 'configuration' || id === 'return-configuration') {
      return { target: target.configuration, observed: ui.tab === 'configuration' && did('configuration-opened') };
    }
    if (id === 'metrics') return { target: target.metrics, observed: ui.tab === 'metrics' && did('metrics-opened') };
    if (id === 'metrics-coverage' || id === 'api-utilization' || id === 'api-throughput') {
      if (ui.tab !== 'metrics') return { target: target.metrics, instruction: 'Choose Metrics in the inspector to continue.' };
      const metric = game.snapshot.components[ui.api];
      if (id !== 'metrics-coverage' && !metric) return {
        target: target.missingMetrics, instruction: 'This API has no live readings. Check its coverage in Telemetry, or skip this step.'
      };
      return { target: metric ? (id === 'api-utilization' && 'CPU' in metric.utilization ? target.cpu : target.throughput) : target.missingMetrics, allowed: true };
    }
    if (ui.tab !== 'configuration') return { target: target.configuration, instruction: 'Choose Configuration in the inspector to continue.' };
    if (id === 'capacity') return { target: target.capacity, allowed: true };
    return { target: target.edit, instruction: id === 'save-capacity' ? 'Reopen Edit configuration to change the API settings.' : undefined };
  }

  if (id === 'add-collector') {
    if (coverage().collectors.length || monitored(game)) return { observed: true };
    if (ui?.dialog === 'catalog') return {
      target: ui.collectorVisible ? target.collector : target.catalogSearch,
      instruction: ui.collectorVisible ? undefined : 'Clear the search to find Monitoring.'
    };
    if (ui?.dialog) return close;
    return { target: target.add, instruction: 'Choose Add node to open the component library.' };
  }
  if (id === 'link-coverage') {
    if (monitored(game) || (game.draft && coverageNodes(game.production).length && !coverage().missing.length)) return { observed: true };
    const { collectors, missing } = coverage();
    if (ui?.dialog && ui.dialog !== 'connect') return close;
    const next = missing[0];
    if (!next) return { instruction: 'There is no API server in the current topology. You can skip this step.' };
    if (!collectors.length) return { instruction: 'Add a Monitoring collector first, or go Back to the previous step.' };

    if (ui?.dialog !== 'connect' && game.draft && collectors.every((collector) =>
      game.draft!.edges.some((edge) => edge.source === next.id && edge.target === collector.id))) {
      return { instruction: 'There is no free collection slot for this component. Edit the collector to add capacity, or skip this step.' };
    }
    if (!ui?.viewingDraft) return {
      target: game.draft ? target.returnDraft : target.createDraft,
      instruction: 'Open the draft so you can add monitoring links.'
    };
    const args = [next.name];
    if (ui.dialog !== 'connect') return { target: target.connect, instruction: 'Choose Connect to create a collection link for {0}.', args };
    if (ui.connectSource !== next.id) return { target: target.source, instruction: 'Choose {0} as the source component.', args };
    if (!collectors.some((node) => node.id === ui.connectTarget)) return {
      target: target.destination, instruction: 'Choose Monitoring as the target component. A collection slot is needed for each link.'
    };
    return { target: target.saveLink, instruction: 'Confirm the metrics collection link.' };
  }
  if (id === 'create-draft') {
    if (game.draft) return { observed: true };
    return ui?.dialog ? close : { target: target.createDraft };
  }
  if (['monitor-review', 'monitor-costs', 'monitor-deploy', 'capacity-review', 'capacity-forecast', 'capacity-costs', 'capacity-deploy'].includes(id)) {
    const monitoring = id.startsWith('monitor');
    const information = id === 'monitor-costs' || id === 'capacity-costs' || id === 'capacity-forecast';
    if (monitoring && monitored(game)) {
      return information ? { allowed: true, instruction: 'This coverage is already deployed. Continue to the next step.' } : { observed: true };
    }
    if (!game.draft) return { instruction: 'There is no open draft to review. Go Back to recreate it, or skip this step.' };
    if (ui?.dialog === 'review') {
      if (!ui.reviewReady) return ui.reviewPending
        ? { instruction: 'Checking the draft before deployment.' }
        : { target: target.close, instruction: 'Close the dialog and reopen Deployment review to retry.' };
      if (id.endsWith('review')) return { target: target.forecast, observed: ui.reviewValid };
      if (!ui.reviewValid) return { target: target.close, instruction: 'Review the errors in the dialog. Close it to fix the draft, or skip this step.' };
      if (information) {
        if (id === 'capacity-forecast' && !ui.hasForecast) return {
          target: target.forecast, allowed: true,
          instruction: 'A performance forecast is unavailable. You can still review the costs.'
        };
        return { target: id === 'capacity-forecast' ? target.capacityForecast : target.forecast, allowed: true };
      }
      return { target: target.deploy };
    }
    if (ui?.dialog) return close;
    if (!ui?.viewingDraft) return { target: target.returnDraft, instruction: 'Return to the draft before reviewing it.' };
    return { target: target.review, instruction: id.endsWith('review') ? undefined : 'Open Deployment review to see the costs and deploy.' };
  }
  if (ui?.dialog) return close;
  return { target: id === 'topology' || id === 'components' ? (ui?.layout === 'list' ? target.canvasTools : target.canvas) : step.target, allowed: true };
}
