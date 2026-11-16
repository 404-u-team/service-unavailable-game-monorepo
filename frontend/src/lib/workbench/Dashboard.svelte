<script lang="ts">
  import { ActionRow, Badge, Button, Disclosure, PageColumns, Pagination, SearchSelect, Stat, Switch, Tabs, type DashboardSettings, type DashboardWidgetState, type Toasts } from '@service-unavailable/ui';
  import GameDashboard from './GameDashboard.svelte';
  import DashboardLayouts from './DashboardLayouts.svelte';
  import ServiceTelemetry from './ServiceTelemetry.svelte';
  import Engineering from './Engineering.svelte';
  import { apiMessage, message, t } from '../i18n.svelte';
  import Language from '../Language.svelte';
  import DeploymentComparison from './DeploymentComparison.svelte';
  import { onDestroy } from 'svelte';
  import { ArrowRight, ArrowUpRight } from '@lucide/svelte';
  import Modal from '../Modal.svelte';
  import { page } from '$app/state';
  import Select from '../controls/Select.svelte';
  import NumberInput from '../controls/NumberInput.svelte';
  import Meter from '../Meter.svelte';
  import Guide from '../Guide.svelte';
  import TutorialControls from './TutorialControls.svelte';
  import { nav, target, type Target, type TutorialAction } from './onboarding';
  import { guideArticleHref } from '../guide';
  import Chart from './Chart.svelte';
  import Finance from './Finance.svelte';
  import ProductSettings from './ProductSettings.svelte';
  import MarketProjects from './MarketProjects.svelte';
  import RegionalDemand from './RegionalDemand.svelte';
  import ForecastCard from './Forecast.svelte';
  import { api } from '../api';
  import { more, sections, statusLabel, type Section } from '../labels';
  import { clock, duration, money, ms, num, pct, preciseMoney, rps, when } from '../format';
  import type { Catalog, Feature, Game, Forecast, Incident } from '../types';

  let { section, game, catalog, link, act, busy, error, tutorialAction, toasts }: {
    section: Section; game: Game; catalog: Catalog; link: (section: Section, focus?: string) => string;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    busy: boolean; error: string; tutorialAction: (action: TutorialAction) => void; toasts: Toasts;
  } = $props();
  let dialog = $state<'campaign' | 'feature' | 'incident' | 'rollback' | 'drill'>();
  let drawer = $state<{ dismiss: (after?: () => void) => void }>();
  let detail = $state('');
  let confirmDisable = $state(false);
  let productTab = $state('features');
  let eventPage = $state(1);
  let deploymentPage = $state(1);
  let linkedEvent = '';
  const pageSize = 10;
  const eventFilters = ['all', 'active', 'closed'] as const;
  const tutorialWidgets: Partial<Record<Target, string>> = {
    [target.coverage]: 'coverage',
    [target.finance]: 'revenue',
    [target.expenses]: 'expenses',
    [target.growth]: 'readiness'
  };
  let board = $state<{ showWidget: (id: string) => void }>();

  export function revealTutorialWidget(key: Target) {
    const id = tutorialWidgets[key];
    if (id) board?.showWidget(id);
    if (key === target.monetization || key === target.premium) productTab = 'features';
  }
  let eventFilter = $state<'all' | 'active' | 'closed'>('all');
  let settingsTab = $state('general');
  let estimate = $state<Forecast>();
  let readiness = $state<Forecast>();
  let targetMarkets = $state(['europe']);
  const marketName = (id: string) => t(game.markets.find((market) => market.id === id)?.name ?? id);
  const marketOptions = $derived(game.markets.map((market) => ({
    value: market.id, label: t(market.name), disabled: market.stage !== 'active',
    reason: market.stage !== 'active' ? t('Launch the market to target it.') : undefined
  })));
  let budget = $state<number>();
  let campaignHours = $state<number>();
  let forecastError = $state('');
  let pending = $state(false);
  let range = $state('24');
  let historyComponent = $state('');
  let historyResource = $state('');
  let serviceChart = $state<string>();
  const serviceMetrics = $derived([
    { value: 'traffic', label: t('Request traffic') },
    { value: 'latency', label: t('Average latency') },
    { value: 'error', label: t('Error rate') }
  ]);
  const historyWindows = $derived([
    { value: '24', label: t('Last 24 game hours') },
    { value: '6', label: t('Last 6 game hours') }
  ]);
  function historyWindow(settings: DashboardSettings) {
    return settings.hours === '6' ? '6' : '24';
  }
  function preferredMetric(settings: DashboardSettings) {
    return settings.metric === 'latency' || settings.metric === 'error' ? settings.metric : 'traffic';
  }
  let forecastToken = 0;
  let lastReadiness = '';
  const metric = $derived(game.snapshot.metrics);
  const telemetry = $derived(Object.entries(game.snapshot.components));
  const pressured = $derived(telemetry.filter(([, item]) =>
    item.database?.diagnostic || ['failed', 'overloaded', 'warning'].includes(item.status)));
  const databaseCoverageMissing = $derived(game.production.nodes.some((node) =>
    (node.kind === 'database' || node.kind === 'replica') && !game.snapshot.components[node.id]));
  const history = $derived(game.history.slice(-Number(range) * 6));
  const historyComponents = $derived(game.production.nodes.filter((node) =>
    history.some((point) => point.peak_utilization?.[node.id] !== undefined) ||
    Object.values(game.snapshot.monitors).some((monitor) => monitor.history && monitor.covered.includes(node.id))));
  const inspectedHistory = $derived(historyComponents.find((node) => node.id === historyComponent) ?? historyComponents[0]);
  const resourceKeys = $derived(inspectedHistory ? [...new Set(
    history.flatMap((point) => Object.keys(point.resource_utilization?.[inspectedHistory.id] ?? {}))
  )].sort() : []);
  const resource = $derived(resourceKeys.includes(historyResource) ? historyResource : '');
  const currentCampaign = $derived(catalog.campaigns[detail]);
  const currentFeature = $derived(game.features.find((item) => item.id === detail));
  const activeCampaigns = $derived(game.campaigns.filter((item) => item.remaining > 0));
  const activeMarkets = $derived(game.markets.filter((item) => item.stage === 'developing'));
  const activeLanguages = $derived(game.languages.filter((item) => item.remaining > 0));
  const inDevelopment = $derived(game.features.filter((item) => item.state === 'developing' || item.state === 'ready'));
  const gameTime = (tick: number) => when(tick, game.start_minute, catalog.minutes_per_tick);
  const tickTime = (tick: number) => clock(tick, game.start_minute, catalog.minutes_per_tick);
  const incident = $derived(game.incidents.find((item) => item.id === detail));
  const events = $derived(game.incidents.filter((item) => eventFilter === 'all' || (eventFilter === 'active' ? item.active : !item.active)));
  const activeEvents = $derived(game.incidents.filter((item) => item.active));
  const eventPages = $derived(Math.max(1, Math.ceil(events.length / pageSize)));
  const deploymentPages = $derived(Math.max(1, Math.ceil(game.deployments.length / pageSize)));
  const visibleEvents = $derived(events.slice((Math.min(eventPage, eventPages) - 1) * pageSize, Math.min(eventPage, eventPages) * pageSize));
  const visibleDeployments = $derived(game.deployments.slice((Math.min(deploymentPage, deploymentPages) - 1) * pageSize, Math.min(deploymentPage, deploymentPages) * pageSize));

  $effect(() => {
    if (section !== 'events') return;
    const id = page.url.searchParams.get('event') ?? '';
    if (!id) { linkedEvent = ''; return; }
    if (id === linkedEvent) return;
    const index = game.incidents.findIndex((item) => item.id === id);
    if (index < 0) return;
    linkedEvent = id;
    eventFilter = 'all';
    eventPage = Math.floor(index / pageSize) + 1;
    openIncident(game.incidents[index]);
  });

  $effect(() => {
    if (section === 'product' && page.url.searchParams.get('engineering') === '1') productTab = 'engineering';
  });
  const deployment = $derived(game.deployments.find((item) => item.id === detail));
  const serviceStats = $derived([
    { label: 'Requests / sec', value: num(metric.rps), detail: t('{0} served', [rps(metric.throughput)]) },
    { label: 'Average latency', value: ms(metric.latency), detail: 'Successful requests' },
    { label: 'Error rate', value: pct(metric.errors / (metric.rps || 1), 2), detail: t('{0} rate-limited', [rps(metric.rejected)]) },
    { label: 'Availability', value: pct(metric.availability, 2), detail: 'Requests served' }
  ]);

  $effect(() => {
    if (section === 'growth') {
      const key = `${game.id}:${game.revision}:${Math.floor(game.tick / 6)}`;
      if (key !== lastReadiness) {
        lastReadiness = key;
        void api<Forecast>(`/${game.id}/campaigns/creator/forecast`).then((result) => {
          if (key === lastReadiness) readiness = result;
        }).catch(() => { if (key === lastReadiness) readiness = undefined; });
      }
    }
  });

  async function plan(id: string) {
    dialog = 'campaign';
    detail = id;
    targetMarkets = ['europe'];
    budget = catalog.campaigns[id].cost;
    campaignHours = catalog.campaigns[id].duration * catalog.minutes_per_tick / 60;
    await requestForecast(id);
  }

  async function requestForecast(id: string) {
    const token = ++forecastToken;
    const ticks = Math.round((campaignHours ?? 0) * 60 / catalog.minutes_per_tick);
    pending = true;
    estimate = undefined;
    forecastError = '';
    try {
      if (!targetMarkets.length) return;
      if (budget == null || budget < 10 || budget > 100_000 || ticks < 1 || ticks > 288) return;
      const query = new URLSearchParams({ budget: String(budget), duration: String(ticks) });
      for (const region of targetMarkets) query.append('regions', region);
      const result = await api<Forecast>(`/${game.id}/campaigns/${id}/forecast?${query}`);
      if (token === forecastToken) estimate = result;
    } catch (reason) {
      if (token === forecastToken) forecastError = apiMessage(reason);
    } finally {
      if (token === forecastToken) pending = false;
    }
  }

  let campaignTimer: ReturnType<typeof setTimeout>;
  onDestroy(() => clearTimeout(campaignTimer));
  function updatePlan() {
    forecastToken += 1;
    estimate = undefined;
    pending = true;
    clearTimeout(campaignTimer);
    campaignTimer = setTimeout(() => { if (dialog === 'campaign') void requestForecast(detail); }, 300);
  }

  async function confirm(path: string, body?: object) {
    if (await act(path, body)) {
      if (drawer) drawer.dismiss();
      else dialog = undefined;
    }
  }

  function openFeature(id: string) {
    detail = id;
    confirmDisable = false;
    dialog = 'feature';
  }

  function openIncident(item: Incident) { detail = item.id; dialog = 'incident'; }
  const settingsTabs = { general: 'General', accessibility: 'Accessibility', dashboards: 'Dashboard layouts', storage: 'Storage' } as const;

  const statuses = { locked: 'Locked', available: 'Available', developing: 'In development', ready: 'Ready to release' };
  function featureStatus(feature: Feature) {
    if (feature.state === 'released') return t(feature.enabled ? 'Released and enabled' : 'Released but disabled');
    return t(feature.state === 'ready' && !feature.can_release
      ? 'Ready for release — infrastructure requirements not met.'
      : statuses[feature.state]);
  }
  const headers: Partial<Record<Section, { tag: string; title: string; subtitle?: string }>> = {
    home: { tag: 'Production', title: 'Service overview', subtitle: 'Current service state and recent activity.' },
    monitor: { tag: 'Observability', title: 'System telemetry' },
    growth: { tag: 'Audience / Campaigns', title: 'Audience & campaigns', subtitle: 'Plan campaigns and forecast additional traffic.' },
    finance: { tag: 'Economy', title: 'Finance', subtitle: 'Balance, income and expenses.' },
    events: { tag: 'Operations / Events', title: 'Events and incidents', subtitle: 'Review service changes and investigate degraded performance.' },
    product: { tag: 'Product / Development', title: 'Product features', subtitle: 'Develop features and review their infrastructure requirements.' },
    guide: { tag: '', title: 'Guide' },
    settings: { tag: 'Service preferences', title: 'Settings' },
    more: { tag: '', title: 'More', subtitle: 'Service management' }
  };
  const heading = $derived(headers[section]);
  const helpArticles: Partial<Record<Section, string>> = {
    home: 'game-basics', monitor: 'monitoring-charts', growth: 'campaigns', finance: 'finances',
    events: 'availability', product: 'product-features', settings: 'save-files'
  };
</script>

{#snippet featureRequirements(feature: Feature)}
  {@const definition = catalog.features[feature.id]}
  <section class="stack">
    <h3>{t('Development prerequisites')}</h3>
    {#if definition.prereq.length}
      <ul class="requirement-list">
        {#each definition.prereq as id}
          {@const met = game.features.some((item) => item.id === id && item.enabled)}
          <li><span class:warning={!met}>{t(met ? 'Met' : 'Missing')}</span> · {t(catalog.features[id].name)}</li>
        {/each}
      </ul>
    {:else}<p class="muted">{t('None')}</p>{/if}
    <h3>{t('Production infrastructure')}</h3>
    <ul class="requirement-list">
      {#each feature.infrastructure as requirement (requirement.id)}
        <li><span class:warning={!requirement.met}>{t(requirement.met ? 'Met' : 'Missing')}</span> · {t(requirement.description)}</li>
      {/each}
    </ul>
    {#if feature.infrastructure.some((requirement) => !requirement.met)}
      <Button href={link('build')}>{t('Open topology')} <ArrowRight size={14} /></Button>
    {/if}
  </section>
{/snippet}

{#snippet statCards()}
  <PageColumns columns={4} minWidth="8rem">
    {#each serviceStats as stat (stat.label)}
      <div class="panel pad"><Stat label={t(stat.label)} value={stat.value} detail={t(stat.detail)} /></div>
    {/each}
  </PageColumns>
{/snippet}

{#snippet incidentDetails(item: Incident)}
  <div class="stack">
    <div class="row wrap">
      <Badge tone={item.active ? 'warning' : 'neutral'}>{item.active ? t("Active") : t("Closed")}</Badge>
      <Badge tone="neutral">{t(item.severity)}</Badge>
      {#if item.acknowledged}<Badge tone="success">{t("Acknowledged")}</Badge>{/if}
    </div>
    <p>{message(item.symptom)}</p>
    <dl class="breakdown">
      {#if item.category}<div><dt>{t('Event category')}</dt><dd>{t(item.category)}</dd></div>{/if}
      {#if item.cause || item.category === 'Player action'}<div><dt>{t('Event ID')}</dt><dd>{item.id}</dd></div>{/if}
      <div><dt>{t("Started")}</dt><dd>{gameTime(item.start)}</dd></div>
      <div><dt>{item.active ? t("Expected end") : t("Ended")}</dt><dd>{item.active && item.cause === "Resource saturation" ? t("Awaiting recovery") : gameTime(item.end)}</dd></div>
      <div><dt>{t("Duration")}</dt><dd>{duration(item.end - item.start)}</dd></div>
      <div><dt>{t("Failed requests during incident")}</dt><dd>{num(item.failed_requests)}</dd></div>
      {#if item.cause}<div><dt>{t("Diagnosed cause")}</dt><dd>{t(({ failure: 'Instance failure', degradation: 'Reduced capacity', storage: 'Storage pressure' } as Record<string, string>)[item.cause] ?? item.cause)}</dd></div>{/if}
      {#if item.target}<div><dt>{t("Affected component")}</dt><dd>{t(game.production.nodes.find((node) => node.id === item.target)?.name ?? item.target)}</dd></div>{/if}
      {#if item.resolution}<div><dt>{t("Resolution")}</dt><dd>{message(item.resolution)}</dd></div>{/if}
    </dl>
    {#if !item.cause && item.active}<p class="muted">{t("Component-level diagnostics require Monitoring linked to the affected service.")}</p>{/if}
  </div>
{/snippet}

{#snippet incidentActions(item: Incident)}
  <div class="row spread wrap">
    <Button variant="primary" href={item.target ? link('build', item.target) : link('monitor')}>{item.target ? t("Open in topology") : t("Open telemetry")} <ArrowRight size={14} /></Button>
    {#if !item.acknowledged}<Button disabled={busy} onclick={() => act(`/incidents/${item.id}/acknowledge`)}>{t("Acknowledge")}</Button>{/if}
  </div>
{/snippet}

{#snippet timeline(limit = 6)}
  {#if game.incidents.length}
    <ul class="list timeline">
      {#each game.incidents.slice(0, limit) as item (item.id)}
        <li><button onclick={() => openIncident(item)}><span class:item-warn={item.severity !== 'info'} class="dot"></span><span class="mono muted">{tickTime(item.start)}</span><span>{message(item.title)}</span></button></li>
      {/each}
    </ul>
  {:else}<p class="muted">{t("No events recorded.")}</p>{/if}
{/snippet}

{#snippet boardTools()}
  {#if section === 'monitor'}
    <div class="time-range"><Select label={t('History range')} bind:value={range}
      options={[24, 6, 1].map((hours) => ({ value: String(hours), label: t('{0}h', [hours]) }))} /></div>
  {:else if section === 'growth'}
    <Badge tone="neutral">{t('Budget ·')} {money(game.balance)}</Badge>
  {/if}
  <Button href={guideArticleHref(link('guide'), helpArticles[section]!)}>{t('Guide')}</Button>
{/snippet}

{#snippet requests()}<Stat value={serviceStats[0].value} detail={t(serviceStats[0].detail)} />{/snippet}
{#snippet latency()}<Stat value={serviceStats[1].value} detail={t(serviceStats[1].detail)} />{/snippet}
{#snippet errors()}<Stat value={serviceStats[2].value} detail={t(serviceStats[2].detail)} />{/snippet}
{#snippet availability()}<Stat value={serviceStats[3].value} detail={t(serviceStats[3].detail)} />{/snippet}

{#snippet serviceHistory(widget: DashboardWidgetState)}
  {@const chart = serviceChart ?? preferredMetric(widget.settings)}
  <div class="stack">
    <Select label={t('Service history metric')} value={chart} options={serviceMetrics} onchange={(value) => serviceChart = value} />
    <Chart title={t(chart === 'latency' ? 'Average latency' : chart === 'error' ? 'Error rate' : 'Request traffic')} primaryTitle={chart === 'traffic' ? t('Incoming requests') : undefined}
      secondaryTitle={t('Successful requests')} format={chart === 'latency' ? ms : chart === 'error' ? (value) => pct(value, 2) : rps}
      values={history.map(({ metrics }) => chart === 'latency' ? (metrics.throughput ? metrics.latency : null)
        : chart === 'error' ? metrics.errors / (metrics.rps || 1) : metrics.rps)}
      secondary={chart === 'traffic' ? history.map((point) => point.metrics.throughput) : []}
      ticks={history.map((point) => point.tick)} time={tickTime} sampleTime={gameTime} />
  </div>
{/snippet}

{#snippet historySettings(widget: DashboardWidgetState, patch: (patch: DashboardSettings) => void)}
  <div class="field">
    <span>{t('Default chart metric')}</span>
    <Select label={t('Default chart metric')} value={preferredMetric(widget.settings)} options={serviceMetrics}
      onchange={(metric) => patch({ metric })} />
  </div>
{/snippet}

{#snippet audienceSettings(widget: DashboardWidgetState, patch: (patch: DashboardSettings) => void)}
  <div class="field">
    <span>{t('Audience history window')}</span>
    <Select label={t('Audience history window')} value={historyWindow(widget.settings)} options={historyWindows}
      onchange={(hours) => patch({ hours })} />
  </div>
{/snippet}

{#snippet incidentTimeline()}
  <div class="stack">{@render timeline(3)}<Button href={link('events')}>{t('View events')} <ArrowRight size={14} /></Button></div>
{/snippet}

{#snippet regional()}
  {#if game.snapshot.demand_overview}<RegionalDemand demand={game.snapshot.demand_overview} markets={game.markets} />
  {:else}<p class="muted">{t('No regional data available.')}</p>{/if}
{/snippet}

{#snippet responsibilities()}<ServiceTelemetry {game} {catalog} {link} />{/snippet}

{#snippet coverage()}
  <div class="stack">
    <div class="row spread wrap" data-tutorial={target.coverage}><Button href={link('build')}>{t("Edit coverage in topology")}</Button></div>

    {#each Object.entries(game.snapshot.monitors ?? {}) as [id, collector]}
      {@const name = game.production.nodes.find((node) => node.id === id)?.name}
      <div class="stack">
        <a href={link('build', id)}>{t(name ?? '')}</a>
        <p class="muted">{collector.covered.length} / {collector.capacity - (collector.history ? 2 : 0)} {t("component slots ·")} {collector.history ? t("Service history enabled") : t("Component metrics only")}</p>
        {#if collector.failed}<p class="notice error">{t("Collection is unavailable. Check the collector for a failure.")}</p>
        {:else if collector.dropped.length}<p class="notice warn">{t("Collection capacity exceeded. Increase slots or add another collector.")}</p>{/if}
      </div>
    {:else}
      <p class="muted">{t("Add Monitoring in Topology and link components to it to collect detailed metrics.")}</p>
    {/each}
    {#each game.production.nodes.filter((node) => !['source', 'monitor'].includes(node.kind)) as node (node.id)}
      <div class="row spread wrap"><a href={link('build', node.id)}>{t(node.name)}</a>
        <span class="mono muted">{game.snapshot.components[node.id] ? t("Collecting metrics") :
          Object.values(game.snapshot.monitors ?? {}).some((collector) => collector.dropped.includes(node.id)) ? t("Linked · No collection slots") : t("Coverage missing")}</span>
      </div>
    {/each}
  </div>
{/snippet}

{#snippet resources()}
  {#if inspectedHistory}
      <div class="stack">
        <div class="row spread wrap">
          <div class="field">
            <span>{t('Component')}</span>
            <Select label={t('Component')} value={inspectedHistory.id} onchange={(value) => historyComponent = value}
              options={historyComponents.map((item) => ({ value: item.id, label: t(item.name) }))} />
          </div>
          <div class="field"><span>{t('Resource')}</span><Select label={t('Resource')} value={resource} onchange={(value) => historyResource = value}
            options={[{ value: '', label: t('Peak resource load') }, ...resourceKeys.map((value) => ({ value, label: t(value) }))]} /></div>
        </div>
        <Chart title={resource ? t('{0} load for {1}', [t(resource), t(inspectedHistory.name)]) : t('Peak resource load for {0}', [t(inspectedHistory.name)])}
          values={history.map((point) => (resource
            ? point.resource_utilization?.[inspectedHistory.id]?.[resource]
            : point.peak_utilization?.[inspectedHistory.id]) ?? null)}
          ticks={history.map((point) => point.tick)} time={tickTime} sampleTime={(tick) => when(tick, game.start_minute, catalog.minutes_per_tick)} format={pct}
          emptyText={t('Resume the simulation to record resource load for this component.')} />
      </div>
    {:else}<p class="muted">{t("Connect components to Monitoring to inspect utilization and component health.")}</p>{/if}
{/snippet}

{#snippet health()}
  <div class="stack">
    <p class="muted">{t("Metrics are collected only for components with an available collection slot.")}</p>
    {#if telemetry.length}
      {#each telemetry as [id, item]}
        <div class="stack node-meter"><div class="row spread"><span>{t(game.production.nodes.find((node) => node.id === id)?.name ?? '')}</span><span class="mono muted">{t(statusLabel[item.status])}</span></div>
          {#if Object.keys(item.utilization).length}<Meter label={t("Peak resource utilization")} value={Math.max(...Object.values(item.utilization))} show={false} />{/if}
        </div>
      {/each}
    {:else}<p class="muted">{t("Connect components to Monitoring to inspect utilization and component health.")}</p>{/if}
  </div>
{/snippet}

{#snippet diagnostics()}
  <div class="stack">
    {#if pressured.length}
      {#each pressured as [id, item]}
        {@const peak = Object.entries(item.utilization).sort((a, b) => b[1] - a[1])[0]}
        <p><a class="warning" href={link('build', id)}>{t(game.production.nodes.find((node) => node.id === id)?.name ?? '')}</a> · {t(statusLabel[item.status])}{#if peak} · {t(peak[0])} {pct(peak[1])}{/if}</p>
      {/each}
    {:else}<p class="muted">{telemetry.length ? t("Monitored components are within their limits.") : t("Only service-level symptoms are available.")}</p>{/if}
    {#if databaseCoverageMissing}
      <p class="muted">{t('Database causes require deployed Monitoring with a free slot linked from each database.')}
        <a class="accent" href={guideArticleHref(link('guide'), 'monitoring-setup')}>{t('Monitoring setup')}</a></p>
      {#if metric.errors > 0}<p>{t('{0} requests per second are failing across the service.', [num(metric.errors)])}</p>{/if}
    {/if}
    <Button href={link('build')}>{t("Open topology")} <ArrowRight size={14} /></Button>
  </div>
{/snippet}

{#snippet audience(widget: DashboardWidgetState)}
  {@const points = game.business_history.slice(-Number(historyWindow(widget.settings)) * 60 / catalog.minutes_per_tick)}
  <div class="stack">
    <Stat value={num(game.audience)} detail={t('Satisfaction ·') + ' ' + pct(game.satisfaction, 1)} />

    <Chart title={t("Registered users")} values={points.map((point) => point.audience)} ticks={points.map((point) => point.tick)} time={tickTime} sampleTime={gameTime} emptyText={t('Run the simulation to record audience history.')} />
  </div>
{/snippet}

{#snippet growthReadiness()}
  <div class="stack">
    <p class="muted" data-tutorial={target.growth}>{t("Projected load during a creator campaign")}</p>
    {#if readiness}
      <strong class="stat">{t('{0}–{1} RPS', [num(readiness.rps.low), num(readiness.rps.high)])}</strong>
      <Meter value={readiness.availability.low} label={t("Forecast minimum availability")} tone={readiness.availability.low < .95 ? 'warn' : 'good'} />
      <Badge tone={readiness.availability.low < .95 ? 'warning' : 'success'}>{readiness.availability.low < .95 ? t("Capacity may be exceeded") : t("Likely within capacity")}</Badge>
    {:else}<p class="muted">{t("Open a campaign to request a forecast.")}</p>{/if}
  </div>
{/snippet}

{#snippet markets()}<MarketProjects {game} {busy} {act} />{/snippet}
{#snippet languages()}<MarketProjects {game} {busy} {act} localization />{/snippet}

{#snippet campaigns()}
  <PageColumns columns={3} minWidth="12rem" gap="12px" class="campaigns">

      {#each Object.entries(catalog.campaigns) as [id, campaign]}
        {@const running = game.campaigns.find((item) => item.id === id)}
        <article class="panel pad stack campaign-card" class:emphasis={id === 'creator'}>
          <div class="row spread"><p class="eyebrow">{id === 'community' ? t("Small campaign") : id === 'creator' ? t("Medium campaign") : t("Large campaign")}</p><ArrowUpRight size={17} class="accent" /></div>
          <h2>{t(campaign.name)}</h2>
          <div class="row spread"><strong class="stat">{money(campaign.cost)}</strong><span class="mono muted">{duration(campaign.duration)}</span></div>
          <p class="muted">≈ {num(campaign.audience)} {t("new users")}</p>
          {#if running}
            {#if running.region}<p>{(running.regions?.length ? running.regions : [running.region]).map(marketName).join(', ')} · {money(running.budget ?? 0)}</p>{/if}
            <Meter value={running.progress} label={t("{0} remaining", [duration(running.remaining)])} />
          {:else}<Button variant={id === 'creator' ? 'primary' : 'secondary'} onclick={() => plan(id)}>{t("Plan campaign")} <ArrowRight size={14} /></Button>{/if}
        </article>
      {/each}
  </PageColumns>
{/snippet}

{#snippet activeProjects()}
  <div class="stack">
    {#if !activeCampaigns.length && !activeMarkets.length && !activeLanguages.length}<p class="muted">{t('No active projects or campaigns.')}</p>{/if}

    {#each activeCampaigns as item (item.id)}
      <div class="row spread wrap"><strong>{t(catalog.campaigns[item.id].name)}</strong><span>{duration(item.remaining)}</span></div>
    {/each}
    {#each activeMarkets as item (item.id)}
      <div class="row spread wrap"><strong>{t(item.name)}</strong><span>{duration(item.remaining)}</span></div>
    {/each}
    {#each activeLanguages as item (item.name)}
      <div class="row spread wrap"><strong>{t(item.name)}</strong><span>{duration(item.remaining)}</span></div>
    {/each}
  </div>
{/snippet}

<main class="dashboard stack">
  {#if heading && !['monitor', 'growth', 'finance'].includes(section)}
    <header class="dash-header row spread">
      <div>{#if heading.tag}<p class="eyebrow">{t(heading.tag)}</p>{/if}<h1>{t(heading.title)}</h1>{#if heading.subtitle}<p class="muted">{t(heading.subtitle)}</p>{/if}</div>
      <div class="row wrap">
      {#if helpArticles[section]}<Button href={guideArticleHref(link('guide'), helpArticles[section]!)}>{t('Guide')}</Button>{/if}
      {#if section === 'product'}<Badge tone="neutral">{t("Budget ·")} {money(game.balance)}</Badge>
      {:else if section === 'events'}<Badge tone={activeEvents.length ? 'warning' : 'neutral'}>{activeEvents.length} {t("active")}</Badge>{/if}
      </div>
    </header>
  {/if}

  {#if section === 'home'}
    <section class="panel pad stack">
      <div class="row spread"><div><p class="eyebrow">{t(catalog.scenarios[game.scenario]?.name ?? '')} / {gameTime(game.tick)}</p><h2>{game.name}</h2></div><Badge tone={metric.availability >= .95 ? 'success' : 'warning'}><i class="dot"></i>{metric.availability >= .95 ? t("Operational") : t("Degraded")}</Badge></div>
      <div class="overview">
        <div><p class="eyebrow">{t("Registered users")}</p><strong>{num(game.audience)}</strong></div>
        <div><p class="eyebrow">{t("Balance")}</p><strong>{money(game.balance)}</strong></div>
        <div><p class="eyebrow">{t("Satisfaction")}</p><strong>{pct(game.satisfaction)}</strong></div>
      </div>
      <Button variant="primary" href={link('build')}>{t("Open topology")} <ArrowRight size={15} /></Button>
    </section>
    {@render statCards()}
    <section class="panel pad stack"><h2>{t("Recent events")}</h2>{@render timeline()}</section>
  {:else if section === 'monitor'}
    <GameDashboard bind:this={board} gameId={game.id} section="monitor" title={t('System telemetry')} tools={boardTools} widgets={[
      { id: 'requests', title: t('Requests / sec'), placement: { x: 0, y: 0, width: 3, height: 3 }, content: requests },
      { id: 'latency', title: t('Average latency'), placement: { x: 3, y: 0, width: 3, height: 3 }, content: latency },
      { id: 'errors', title: t('Error rate'), placement: { x: 6, y: 0, width: 3, height: 3 }, content: errors },
      { id: 'availability', title: t('Availability'), placement: { x: 9, y: 0, width: 3, height: 3 }, content: availability },
      { id: 'traffic-history', title: t('Service history'), placement: { x: 0, y: 3, width: 7, height: 8 }, content: serviceHistory, settings: historySettings },
      { id: 'timeline', title: t('Incident timeline'), placement: { x: 7, y: 3, width: 5, height: 4 }, content: incidentTimeline },
      { id: 'diagnostics', title: t('Diagnostics'), placement: { x: 7, y: 7, width: 5, height: 4 }, content: diagnostics },
      { id: 'coverage', title: t('Monitoring coverage'), placement: { x: 7, y: 11, width: 5, height: 7 }, content: coverage },
      { id: 'resources', title: t('Resource load over time'), placement: { x: 0, y: 11, width: 7, height: 7 }, content: resources },
      { id: 'node-health', title: t('Node health'), placement: { x: 0, y: 18, width: 5, height: 6 }, content: health },
      { id: 'responsibilities', title: t('Service responsibilities'), placement: { x: 5, y: 18, width: 7, height: 6 }, content: responsibilities },
      { id: 'regional-demand', title: t('Demand by region'), placement: { x: 0, y: 24, width: 12, height: 8 }, content: regional }
    ]} />
  {:else if section === 'growth'}
    <GameDashboard bind:this={board} gameId={game.id} section="growth" title={t('Audience & campaigns')} tools={boardTools} widgets={[
      { id: 'audience', title: t('Registered users'), placement: { x: 0, y: 0, width: 7, height: 8 }, content: audience, settings: audienceSettings },
      { id: 'readiness', title: t('Growth readiness'), placement: { x: 7, y: 0, width: 5, height: 4 }, content: growthReadiness },
      { id: 'active-projects', title: t('Active projects and campaigns'), placement: { x: 7, y: 4, width: 5, height: 4 }, content: activeProjects },
      { id: 'campaign-catalog', title: t('Campaign catalog'), placement: { x: 0, y: 8, width: 12, height: 6 }, content: campaigns },
      { id: 'markets', title: t('Market expansion'), placement: { x: 0, y: 14, width: 7, height: 10 }, content: markets },
      { id: 'localization', title: t('Messenger languages'), placement: { x: 7, y: 14, width: 5, height: 10 }, content: languages },
      { id: 'regional-demand', title: t('Demand by region'), placement: { x: 0, y: 24, width: 12, height: 8 }, content: regional }
    ]} />
  {:else if section === 'product'}
    <PageColumns columns={4} minWidth="9rem">
      {#each [
        { label: 'Active features', value: game.features.filter((item) => item.enabled).length },
        { label: 'Features in progress', value: inDevelopment.length },
        { label: 'Projected additional load', value: `+${pct(inDevelopment.reduce((sum, item) => sum + item.demand_change, 0), 1)}` },
        { label: 'Development spend', value: money(game.economy.development) }
      ] as item}
        <div class="panel pad"><Stat label={t(item.label)} value={item.value} compact /></div>
      {/each}
    </PageColumns>
    <Tabs label={t('Product sections')} bind:value={productTab} items={[
      { value: 'features', label: t('Feature catalog') },
      { value: 'engineering', label: t('Engineering') },
      { value: 'settings', label: t('Product settings') }
    ]}>
      {#snippet children(item)}
        {#if item.value === 'features'}
          <section class="stack" aria-label={t('Feature catalog')}>
        {#each game.features as feature (feature.id)}
          {@const definition = catalog.features[feature.id]}
          <article data-tutorial={feature.id === 'advertising' ? target.monetization : feature.id === 'premium' ? target.premium : undefined}>
            <ActionRow title={t(definition.name)}
              description={t(feature.id === 'premium' ? 'Additional synchronization for subscribers'
                : definition.operation ? catalog.operations[definition.operation] : 'Base messenger workload')}
              onclick={() => openFeature(feature.id)}>
              {#snippet status()}
                <Badge tone={feature.enabled || feature.can_release ? 'success' : inDevelopment.includes(feature) ? 'warning' : 'neutral'}>
                  {feature.state === 'ready' && !feature.can_release ? t('Release blocked') : featureStatus(feature)}
                </Badge>
              {/snippet}
            </ActionRow>
          </article>
        {/each}
          </section>
        {:else if item.value === 'engineering'}
          <Engineering {game} {catalog} {act} {busy} {link} {error} />
        {:else}
          <ProductSettings {game} {catalog} {busy} {error} save={(product) => act('/product', { product }, 'PUT')} />
        {/if}
      {/snippet}
    </Tabs>
  {:else if section === 'finance'}
    <Finance bind:this={board} {game} {catalog} tools={boardTools} />
  {:else if section === 'events'}
    <section class="panel pad stack">
      <div class="row spread wrap"><h2>{t("Incident history")}</h2><Button disabled={busy || game.incidents.some((item) => item.title === 'Instance failure drill')} onclick={() => dialog = 'drill'}>{t("Run failure drill")}</Button></div>
      <div class="row wrap" role="group" aria-label={t("Filter events")}>
        {#each eventFilters as filter (filter)}
          <Button aria-pressed={eventFilter === filter} onclick={() => { eventFilter = filter; eventPage = 1; }}>{t(filter === 'all' ? 'All events' : filter === 'active' ? 'Active' : 'Closed')}</Button>
        {/each}
      </div>
      <ul class="list">
        {#each visibleEvents as item (item.id)}
          <li>
            <ActionRow title={message(item.title)} description={`${gameTime(item.start)} · ${message(item.symptom)}`} onclick={() => openIncident(item)}>
              {#snippet status()}<Badge tone={item.active ? 'warning' : 'neutral'}>{t(item.active ? 'Active' : 'Closed')}</Badge>{/snippet}
            </ActionRow>
          </li>
        {:else}<li class="muted">{t("No matching events.")}</li>{/each}
      </ul>
      <Pagination page={eventPage} pages={eventPages} label={t('Incident pages')} previousLabel={t('Previous page')} nextLabel={t('Next page')}
        pageLabel={(current, total) => t('Page {0} of {1}', [current, total])} onchange={(next) => eventPage = next} />
    </section>
    <section class="panel pad stack">
      <h2>{t("Deployment history")}</h2>
      <ul class="list">
        {#each visibleDeployments as item (item.id)}
          <li class="event stack">
            <div class="row spread wrap"><div><strong>{message(item.summary)}</strong><small>{gameTime(item.tick)} · {preciseMoney(item.cost)}</small></div><Button disabled={busy || Boolean(game.draft)} onclick={() => { detail = item.id; dialog = 'rollback'; }}>{t("Review rollback")}</Button></div>
            {#if item.comparison}
              <Disclosure label={t('View before and after')} summaryAttributes={{ 'data-tutorial': item.id === game.deployments[0]?.id ? target.eventComparison : undefined }}>
                <DeploymentComparison comparison={item.comparison} />
              </Disclosure>
            {/if}
          </li>
        {:else}<li class="muted">{t("No deployments yet.")}</li>{/each}
      </ul>
      {#if game.draft && game.deployments.length}<p class="muted">{t("Discard the current draft to roll back.")}</p>{/if}
      <Pagination page={deploymentPage} pages={deploymentPages} label={t('Deployment pages')} previousLabel={t('Previous page')} nextLabel={t('Next page')}
        pageLabel={(current, total) => t('Page {0} of {1}', [current, total])} onchange={(next) => deploymentPage = next} />
    </section>
  {:else if section === 'guide'}
    <Guide {catalog} {game} {link} {busy} {tutorialAction} />
  {:else if section === 'settings'}
    <Tabs label={t('Settings sections')} bind:value={settingsTab}
      items={Object.entries(settingsTabs).map(([value, label]) => ({ value, label: t(label) }))}>
      {#snippet children(item)}
        <section class="panel pad stack settings-panel">
        {#if item.value === 'general'}
          <Language />
          <div><h2>{t("Game preferences")}</h2><p class="muted">{t("Settings are saved automatically.")}</p></div>
          <div><p class="eyebrow">{t("Game speed")}</p><div class="row wrap option-row">
            {#each [{ speed: 0, label: 'Paused' }, { speed: 1, label: '1×' }, { speed: 3, label: '3×' }] as option}
              <Button aria-pressed={game.speed === option.speed} disabled={busy} onclick={() => act('/clock', { speed: option.speed }, 'PUT')}>{t(option.label)}</Button>
            {/each}
          </div></div>
          <Switch label={t("Show onboarding prompts")} description={t("Display the current tutorial step in the workbench.")} checked={game.settings.show_tutorial} disabled={busy} onchange={({ currentTarget }) => act('/settings', { settings: { ...game.settings, show_tutorial: currentTarget.checked } }, 'PUT')} />
          <TutorialControls {game} {busy} change={tutorialAction} />
          <div class="stack"><h3>{t('Keyboard shortcuts')}</h3>
            <dl class="breakdown">
              {#each [['Ctrl/Cmd + S', 'Save game'], ['Space', 'Pause or resume'], ['1 / 2 / 3', 'Set speed to 1× / 3× / 5×'], ['Escape', 'Close a dialog or clear selection']] as [key, label]}
                <div><dt>{t(label)}</dt><dd><kbd>{t(key)}</kbd></dd></div>
              {/each}
            </dl>
          </div>
          <div class="row wrap"><Button disabled={busy} onclick={() => act('/settings', { settings: { show_tutorial: true, reduced_motion: false } }, 'PUT')}>{t("Restore defaults")}</Button><Button variant="primary" disabled={busy} onclick={() => act('/save')}>{t("Save game")}</Button></div>
        {:else if item.value === 'accessibility'}
          <h2>{t("Accessibility")}</h2>
          <Switch label={t("Reduce motion")} description={t("Reduce animation and transitions.")} checked={game.settings.reduced_motion} disabled={busy} onchange={({ currentTarget }) => act('/settings', { settings: { ...game.settings, reduced_motion: currentTarget.checked } }, 'PUT')} />

        {:else if item.value === 'dashboards'}
          <DashboardLayouts gameId={game.id} {toasts} />
        {:else}
          <div><h2>{t("Save management")}</h2><p class="muted">{t("The server saves progress as you play.")}</p></div>
          <div class="row wrap"><Button variant="primary" disabled={busy} onclick={() => act('/save')}>{t("Save game")}</Button><Button href="/?view=saves">{t("Saved games")}</Button><Button href="/">{t("Main menu")}</Button></div>
        {/if}
        </section>
      {/snippet}
    </Tabs>
  {:else if section === 'more'}
    <div class="stack">
      {#each more as item}
        {@const Icon = sections[item].icon}
        <ActionRow title={t(sections[item].name)} description={t(sections[item].description)}
          href={item === 'saves' ? '/?view=saves' : link(item)} attributes={{ 'data-tutorial': nav(item) }}>
          {#snippet icon()}<Icon size={20} />{/snippet}
        </ActionRow>
      {/each}
    </div>
  {/if}
</main>

{#if dialog === 'campaign' && currentCampaign}
  <Modal title={t("Campaign planning")} subtitle={t(currentCampaign.name)} close={() => dialog = undefined} wide>
    <div class="stack">
      <p>{t('Shorter campaigns acquire the same expected number of users faster and can create a sharper traffic peak.')}</p>
      <div class="stack">
        <div class="field">
          <SearchSelect {t} label={t('Target markets')} options={marketOptions} selected={targetMarkets} multiple searchable
            choose={(regions) => { targetMarkets = regions; updatePlan(); }} />
        </div>
        <div class="split">
          <div class="field"><span>{t('Campaign budget')}</span><NumberInput label={t('Campaign budget')} bind:value={budget} min={10} max={100000} step={50} precision={2} unit="USD" onchange={updatePlan} /></div>
          <div class="field"><span>{t('Duration (game hours)')}</span><NumberInput label={t('Duration (game hours)')} bind:value={campaignHours} min={.16} max={48} precision={2} onchange={updatePlan} /></div>
        </div>
      </div>
      {#if estimate?.plan}
        {@const preview = estimate.plan}
        <div class="split">
          <section class="stack">
            <h3>{t('Regional allocation')}</h3>
            <p class="muted">{t('The total budget is split evenly across selected markets.')}</p>
            <dl class="breakdown">
              <div><dt>{t('Total budget')}</dt><dd>{preciseMoney(preview.budget)}</dd></div>
              {#each Object.entries(preview.allocations) as [id, allocation] (id)}
                <div><dt>{marketName(id)}</dt><dd>{preciseMoney(allocation.budget)} · {t('{0} users', [num(Math.round(allocation.audience))])}</dd></div>
              {/each}
              <div><dt>{t("Expected acquisition")}</dt><dd>≈ {t('{0} users', [num(Math.round(preview.acquired))])}</dd></div>
              <div><dt>{t("Average acquisition rate")}</dt><dd>{t('{0} users/hour', [num(preview.acquired / (preview.duration * catalog.minutes_per_tick / 60))])}</dd></div>
              <div><dt>{t("Duration")}</dt><dd>{duration(preview.duration)}</dd></div>
            </dl>
          </section>
          <section class="stack">
            <h3>{t('Expected user arrivals')}</h3>
            <Chart title={t('Users per simulation step')} values={[0, ...preview.arrivals]}
              ticks={Array.from({ length: preview.arrivals.length + 1 }, (_, i) => i)}
              time={(tick) => duration(tick)} sampleTime={(tick) => t('{0} after launch', [duration(tick)])} />
            {#if preview.peak_rps != null}
              <p>{t('Expected peak traffic: {0}', [rps(preview.peak_rps)])}
                {#if preview.baseline_peak_rps != null}<small>{t('Baseline peak: {0}', [rps(preview.baseline_peak_rps)])}</small>{/if}
              </p>
            {/if}
            <ForecastCard forecast={estimate} />
          </section>
        </div>
        {#if estimate.availability.low < .95}<p class="notice warn">{t('Capacity may be exceeded')}</p>{/if}
      {:else if !pending && !forecastError}
        <p class="notice warn">{t(targetMarkets.length ? 'Enter a valid budget and duration to see the forecast.' : 'Select at least one active market.')}</p>
      {/if}
      {#if pending}<p aria-live="polite">{t("Calculating forecast…")}</p>{/if}
      {#if forecastError || error}<p class="notice error" role="alert">{message(forecastError || error)}</p>{/if}
      {#if budget != null && game.balance < budget}<p class="notice warn">{t("Insufficient funds.")}</p>{/if}
    </div>
    {#snippet footer()}
      <div class="row spread"><Button onclick={() => dialog = undefined}>{t("Cancel")}</Button><Button variant="primary" disabled={busy || pending || !estimate?.plan?.acquired || game.balance < (estimate?.plan?.budget ?? Infinity) || game.campaigns.some((item) => item.id === detail)} onclick={() => confirm(`/campaigns/${detail}`, { regions: targetMarkets, budget: estimate?.plan?.budget, duration: estimate?.plan?.duration })}>{t("Start campaign")}</Button></div>
    {/snippet}
  </Modal>
{:else if dialog === 'feature' && currentFeature}
  {@const definition = catalog.features[detail]}
  <Modal bind:this={drawer} title={t("Feature details")} side="end" subtitle={t(definition.name)} close={() => dialog = undefined}>
    <div class="stack">
      <p class:warning={currentFeature.state === 'ready' && !currentFeature.can_release}>{featureStatus(currentFeature)}</p>
      <dl class="breakdown">
        <div><dt>{t("Development cost")}</dt><dd>{money(definition.cost)}</dd></div>
        <div><dt>{t("Development duration")}</dt><dd>{duration(definition.duration)}</dd></div>
        <div><dt>{t("Generated demand")}</dt><dd>{detail === 'premium' ? t('Optional faster synchronization and larger media uploads') : definition.operation ? t(catalog.operations[definition.operation]) : t("Base messenger operations")}</dd></div>
        {#if currentFeature.state !== 'released' && currentFeature.demand_change > 0}<div><dt>{t("Additional request load")}</dt><dd>+{pct(currentFeature.demand_change, 1)}</dd></div>{/if}
        <div><dt>{t("Appeal contribution")}</dt><dd>+{pct(definition.appeal)}</dd></div>
      </dl>
      {@render featureRequirements(currentFeature)}
      {#if currentFeature.dependents.length}
        <p class="notice warn">{t('Disable these features first: {0}', [currentFeature.dependents.map((id) => t(catalog.features[id].name)).join(', ')])}</p>
      {/if}
      {#if detail === 'premium' && currentFeature.state === 'released'}
        <p class="muted">{t('Disabling Premium stops new sales and renewals. Paid benefits continue until each term ends.')}</p>
      {/if}
      {#if confirmDisable}
        <p class="notice warn" role="status">{t('Disable {0}?', [t(definition.name)])}</p>
      {/if}
      {#if currentFeature.state === 'developing'}<Meter value={1 - currentFeature.remaining / definition.duration} label={t("{0} remaining", [duration(currentFeature.remaining)])} />{/if}
      {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    </div>
    {#snippet footer()}
      <div class="row spread"><Button onclick={() => drawer?.dismiss()}>{t("Close")}</Button>
        {#if currentFeature.state === 'available'}<Button variant="primary" disabled={busy || game.balance < definition.cost} onclick={() => confirm(`/features/${detail}`, { action: 'develop' })}>{t("Start development")}</Button>
        {:else if currentFeature.state === 'ready'}<Button variant="primary" disabled={busy || !currentFeature.can_release} onclick={() => confirm(`/features/${detail}`, { action: 'release' })}>{t("Release feature")}</Button>
        {:else if currentFeature.state === 'released' && !currentFeature.enabled}
          <Button variant="primary" disabled={busy || !currentFeature.can_enable} onclick={() => confirm(`/features/${detail}`, { action: 'enable' })}>{t('Enable feature')}</Button>
        {:else if currentFeature.enabled && currentFeature.can_disable}
          <Button variant="danger" disabled={busy} onclick={() => confirmDisable ? confirm(`/features/${detail}`, { action: 'disable' }) : confirmDisable = true}>{t(confirmDisable ? 'Confirm disable' : 'Disable feature')}</Button>
        {/if}
      </div>
    {/snippet}
  </Modal>
{:else if dialog === 'incident' && incident}
  <Modal bind:this={drawer} title={t("Incident details")} side="end" subtitle={message(incident.title)} close={() => dialog = undefined}>
    {@render incidentDetails(incident)}
    {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    {#snippet footer()}{@render incidentActions(incident)}{/snippet}
  </Modal>
{:else if dialog === 'rollback' && deployment}
  <Modal title={t("Review rollback")} close={() => dialog = undefined}>
    <div class="stack"><p>{t("Restore the topology that was in production before “")}{message(deployment.summary)}{t("” on")} {gameTime(deployment.tick)}{t(". The server revalidates the topology and charges any installation cost.")}</p>{#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}</div>
    {#snippet footer()}<div class="row spread"><Button onclick={() => dialog = undefined}>{t("Cancel")}</Button><Button variant="danger" disabled={busy} onclick={() => confirm(`/deployments/${detail}/rollback`, { revision: game.revision })}>{t("Roll back")}</Button></div>{/snippet}
  </Modal>
{:else if dialog === 'drill'}
  <Modal title={t("Run failure drill")} close={() => dialog = undefined}>
    <div class="stack"><p>{t("Take one API instance offline for two in-game hours to test routing and recovery. The drill affects live traffic.")}</p>{#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}</div>
    {#snippet footer()}<div class="row spread"><Button onclick={() => dialog = undefined}>{t("Cancel")}</Button><Button variant="danger" disabled={busy} onclick={() => confirm('/incidents/drill')}>{t("Start drill")}</Button></div>{/snippet}
  </Modal>
{/if}

<style>
  .requirement-list { margin: 0; padding-inline-start: 18px; }
  .requirement-list li + li { margin-top: 6px; }
  .dashboard { gap: 22px; padding: 27px 30px 35px; max-width: 1700px; margin: 0 auto; align-content: start; }
  .dash-header { align-items: flex-start; min-height: 75px; gap: 14px; }
  .dash-header h1 { margin: 7px 0 4px; }
  .dash-header p { margin-top: 2px; }
  .time-range { width: 90px; flex: 0 0 auto; }
  .split { display: grid; gap: 21px; align-items: start; }
  .stat { display: block; font-size: clamp(22px, 2.4vw, 34px); line-height: 1.15; margin: 8px 0 4px; }
  .split { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .split > .stack { align-content: start; }
  .campaign-card { align-content: start; gap: 10px; }
  :global(.campaigns) .emphasis { border-color: var(--primary); }
  .dashboard h2 { font-size: 18px; }
  .dashboard h2 + p { margin-top: 4px; font-size: 13px; }
  .timeline { gap: 9px; }
  .timeline button { display: grid; align-items: start; grid-template-columns: 7px auto 1fr; gap: 11px; padding: 8px 0; width: 100%; text-align: left; background: transparent; border: 0; color: var(--text); font-size: 12px; }
  .timeline button:hover { color: var(--primary); }
  .timeline .dot { color: var(--primary); margin-top: 6px; }
  .timeline .dot.item-warn { color: var(--warning); }
  .node-meter { gap: 6px; font-size: 12px; }
  .event { text-align: left; padding: 13px; width: 100%; border: 1px solid var(--border); border-radius: 9px; background: var(--rail); color: var(--text); }
  .event strong { font-size: 15px; }
  .settings-panel { min-height: 360px; align-content: start; }
  .option-row { margin-top: 7px; }
  .option-row :global(.sui-button) { min-width: 74px; }
  .event small { display: block; margin-top: 3px; }
  .event > :first-child { flex: 1 1 auto; }
  .breakdown { margin: 0; display: grid; gap: 8px; }
  .breakdown > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); padding: 6px 0; }
  .breakdown dd { font: 400 12px var(--mono); text-align: right; }
  .overview { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .overview strong { font-size: 21px; }
  @media (max-width: 1050px) {
    .dashboard { padding: 24px 20px; }
    .split { gap: 12px; }
  }
  @media (max-width: 850px) {
    .dashboard { padding: 16px 17px 25px; gap: 15px; }
    .dash-header { min-height: 0; }
    .dash-header h1 { margin-top: 4px; }
    .split { grid-template-columns: 1fr; }
    .settings-panel { min-height: 0; }
    .overview { gap: 7px; }
    .overview strong { font-size: 19px; }
  }
  @media (max-width: 400px) {
    .dashboard .pad { padding: 13px; }
    .dash-header :global(.sui-badge) { max-width: 100px; }
  }
</style>
