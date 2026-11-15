<script lang="ts">
  import ServiceTelemetry from './ServiceTelemetry.svelte';
  import Engineering from './Engineering.svelte';
  import { apiMessage, message, t } from '../i18n.svelte';
  import Language from '../Language.svelte';
  import DatabaseDiagnostics from './DatabaseDiagnostics.svelte';
  import DeploymentComparison from './DeploymentComparison.svelte';
  import { onDestroy } from 'svelte';
  import { ArrowRight, ArrowUpRight, ChevronRight } from '@lucide/svelte';
  import Modal from '../Modal.svelte';
  import { page } from '$app/state';
  import Toggle from '../controls/Toggle.svelte';
  import Choice from '../controls/Choice.svelte';
  import Select from '../controls/Select.svelte';
  import NumberInput from '../controls/NumberInput.svelte';
  import Meter from '../Meter.svelte';
  import Guide from '../Guide.svelte';
  import TutorialControls from './TutorialControls.svelte';
  import { nav, target, type TutorialAction } from './onboarding';
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

  let { section, game, catalog, link, act, busy, error, tutorialAction }: {
    section: Section; game: Game; catalog: Catalog; link: (section: Section, focus?: string) => string;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    busy: boolean; error: string; tutorialAction: (action: TutorialAction) => void;
  } = $props();
  let dialog = $state<'campaign' | 'feature' | 'incident' | 'rollback' | 'drill'>();
  let detail = $state('');
  let confirmDisable = $state(false);
  let featureId = $state('groups');
  let eventId = $state('');
  let eventFilter = $state<'all' | 'active' | 'closed'>('all');
  let settingsTab = $state<'general' | 'accessibility' | 'storage'>('general');
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
  let serviceChart = $state('traffic');
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
  const selectedFeature = $derived(game.features.find((item) => item.id === featureId));
  const activeCampaigns = $derived(game.campaigns.filter((item) => item.remaining > 0));
  const activeMarkets = $derived(game.markets.filter((item) => item.stage === 'developing'));
  const activeLanguages = $derived(game.languages.filter((item) => item.remaining > 0));
  const inDevelopment = $derived(game.features.filter((item) => item.state === 'developing' || item.state === 'ready'));
  const gameTime = (tick: number) => when(tick, game.start_minute, catalog.minutes_per_tick);
  const tickTime = (tick: number) => clock(tick, game.start_minute, catalog.minutes_per_tick);
  const incident = $derived(game.incidents.find((item) => item.id === detail));
  const events = $derived(game.incidents.filter((item) => eventFilter === 'all' || (eventFilter === 'active' ? item.active : !item.active)));
  const activeEvents = $derived(game.incidents.filter((item) => item.active));
  const selectedIncident = $derived(events.find((item) => item.id === (eventId || page.url.searchParams.get('event'))) ?? events[0]);
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
    if (await act(path, body)) dialog = undefined;
  }

  function openFeature(id: string) {
    detail = id;
    confirmDisable = false;
    dialog = 'feature';
  }

  function openIncident(item: Incident) { eventId = item.id; detail = item.id; dialog = 'incident'; }
  const settingsTabs = { general: 'General', accessibility: 'Accessibility', storage: 'Storage' } as const;

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
      <a class="btn" href={link('build')}>{t('Open topology')} <ArrowRight size={14} /></a>
    {/if}
  </section>
{/snippet}

{#snippet statCards()}
  <div class="cards stats">
    {#each serviceStats as stat}
      <article class="panel pad"><p class="eyebrow">{t(stat.label)}</p><strong class="stat">{stat.value}</strong><small>{t(stat.detail)}</small></article>
    {/each}
  </div>
{/snippet}

{#snippet incidentDetails(item: Incident)}
  <div class="stack">
    <div class="row wrap">
      <span class="badge {item.active ? 'warn' : 'dim'}">{item.active ? t("Active") : t("Closed")}</span>
      <span class="badge dim">{t(item.severity)}</span>
      {#if item.acknowledged}<span class="badge good">{t("Acknowledged")}</span>{/if}
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
    <a class="btn primary" href={item.target ? link('build', item.target) : link('monitor')} onclick={() => dialog = undefined}>{item.target ? t("Open in topology") : t("Open telemetry")} <ArrowRight size={14} /></a>
    {#if !item.acknowledged}<button class="btn" disabled={busy} onclick={() => act(`/incidents/${item.id}/acknowledge`)}>{t("Acknowledge")}</button>{/if}
  </div>
{/snippet}

{#snippet timeline()}
  {#if game.incidents.length}
    <ul class="list timeline">
      {#each game.incidents.slice(0, 6) as item (item.id)}
        <li><button onclick={() => openIncident(item)}><span class:item-warn={item.severity !== 'info'} class="dot"></span><span class="mono muted">{tickTime(item.start)}</span><span>{message(item.title)}</span></button></li>
      {/each}
    </ul>
  {:else}<p class="muted">{t("No events recorded.")}</p>{/if}
{/snippet}

<main class="dashboard stack">
  {#if heading}
    <header class="dash-header row spread">
      <div>{#if heading.tag}<p class="eyebrow">{t(heading.tag)}</p>{/if}<h1>{t(heading.title)}</h1>{#if heading.subtitle}<p class="muted">{t(heading.subtitle)}</p>{/if}</div>
      <div class="row wrap">
      {#if helpArticles[section]}<a class="btn" href={guideArticleHref(link('guide'), helpArticles[section]!)}>{t('Guide')}</a>{/if}
      {#if section === 'monitor'}
        <div class="time-range"><Select label={t("History range")} bind:value={range}
          options={[24, 6, 1].map((hours) => ({ value: String(hours), label: t("{0}h", [hours]) }))} /></div>
      {:else if section === 'growth' || section === 'product'}<span class="badge dim">{t("Budget ·")} {money(game.balance)}</span>
      {:else if section === 'events'}<span class="badge {activeEvents.length ? 'warn' : 'dim'}">{activeEvents.length} {t("active")}</span>{/if}
      </div>
    </header>
  {/if}

  {#if section === 'home'}
    <section class="panel pad stack">
      <div class="row spread"><div><p class="eyebrow">{t(catalog.scenarios[game.scenario]?.name ?? '')} / {gameTime(game.tick)}</p><h2>{game.name}</h2></div><span class="badge {metric.availability >= .95 ? 'good' : 'warn'}"><i class="dot"></i>{metric.availability >= .95 ? t("Operational") : t("Degraded")}</span></div>
      <div class="overview">
        <div><p class="eyebrow">{t("Registered users")}</p><strong>{num(game.audience)}</strong></div>
        <div><p class="eyebrow">{t("Balance")}</p><strong>{money(game.balance)}</strong></div>
        <div><p class="eyebrow">{t("Satisfaction")}</p><strong>{pct(game.satisfaction)}</strong></div>
      </div>
      <a class="btn primary" href={link('build')}>{t("Open topology")} <ArrowRight size={15} /></a>
    </section>
    {@render statCards()}
    <section class="panel pad stack"><h2>{t("Recent events")}</h2>{@render timeline()}</section>
  {:else if section === 'monitor'}
    {@render statCards()}
    {#if game.snapshot.demand_overview}<RegionalDemand demand={game.snapshot.demand_overview} markets={game.markets} />{/if}
    <div class="split">
      <section class="panel pad stack">
        <div><h2>{t("Traffic / throughput")}</h2><p class="muted">{t("Incoming and successful requests per second")}</p></div>
        <Select label={t('Service history metric')} bind:value={serviceChart} options={[
          { value: 'traffic', label: t('Request traffic') }, { value: 'latency', label: t('Average latency') },
          { value: 'error', label: t('Error rate') }
        ]} />
        <Chart title={t(serviceChart === 'latency' ? 'Average latency' : serviceChart === 'error' ? 'Error rate' : 'Request traffic')} primaryTitle={serviceChart === 'traffic' ? t('Incoming requests') : undefined}
          secondaryTitle={t('Successful requests')} format={serviceChart === 'latency' ? ms : serviceChart === 'error' ? (value) => pct(value, 2) : rps}
          values={history.map(({ metrics }) => serviceChart === 'latency' ? (metrics.throughput ? metrics.latency : null)
            : serviceChart === 'error' ? metrics.errors / (metrics.rps || 1) : metrics.rps)}
          secondary={serviceChart === 'traffic' ? history.map((point) => point.metrics.throughput) : []}
          ticks={history.map((point) => point.tick)} time={tickTime} sampleTime={gameTime} />
        {#if history.length}<small><span class="accent">{t("━ Incoming")}</span> &nbsp; <span class="throughput">{t("┄ Successful")}</span></small>{/if}
      </section>
      <section class="panel inset pad stack"><h2>{t("Incident timeline")}</h2>{@render timeline()}<a class="btn" href={link('events')}>{t("View events")} <ArrowRight size={14} /></a></section>
    </div>
    <ServiceTelemetry {game} {catalog} {link} />
    <section class="panel pad stack">
      <div class="row spread wrap"><h2 data-tutorial={target.coverage}>{t("Monitoring coverage")}</h2><a class="btn" href={link('build')}>{t("Edit coverage in topology")}</a></div>
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
    </section>
    {#if inspectedHistory}
      <section class="panel pad stack">
        <div class="row spread wrap">
          <h2>{t('Resource load over time')}</h2>
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
      </section>
    {/if}
    <div class="split equal">
      <section class="panel pad stack">
        <h2>{t("Node health")}</h2>
        <p class="muted">{t("Metrics are collected only for components with an available collection slot.")}</p>
        {#if telemetry.length}
          {#each telemetry as [id, item]}
            <div class="stack node-meter"><div class="row spread"><span>{t(game.production.nodes.find((node) => node.id === id)?.name ?? '')}</span><span class="mono muted">{t(statusLabel[item.status])}</span></div>
              {#if Object.keys(item.utilization).length}<Meter label={t("Peak resource utilization")} value={Math.max(...Object.values(item.utilization))} show={false} />{/if}
            </div>
          {/each}
        {:else}<p class="muted">{t("Connect components to Monitoring to inspect utilization and component health.")}</p>{/if}
      </section>
      <section class="panel pad stack" aria-labelledby="telemetry-diagnostics">
        <h2 id="telemetry-diagnostics">{t("Diagnostics")}</h2>
        {#if pressured.length}
          {#each pressured as [id, item]}
            <div class="stack">
              <p><a class="warning" href={link('build', id)}>{t(game.production.nodes.find((node) => node.id === id)?.name ?? '')}</a> · {t(statusLabel[item.status])}{#if !item.database?.diagnostic && Object.keys(item.utilization).length} · {t(Object.entries(item.utilization).sort((a, b) => b[1] - a[1])[0][0])}{/if}</p>
              <DatabaseDiagnostics metric={item} guide={link('guide')}
                configureHref={game.draft?.nodes.every((node) => node.id !== id) ? undefined : `${link('build', id)}&configure=1`} />
            </div>
          {/each}
        {:else}<p class="muted">{telemetry.length ? t("Monitored components are within their limits.") : t("Only service-level symptoms are available.")}</p>{/if}
        {#if databaseCoverageMissing}
          <p class="muted">{t('Database causes require deployed Monitoring with a free slot linked from each database.')}
            <a class="accent" href={guideArticleHref(link('guide'), 'monitoring-setup')}>{t('Monitoring setup')}</a></p>
          {#if metric.errors > 0}<p>{t('{0} requests per second are failing across the service.', [num(metric.errors)])}</p>{/if}
        {/if}
        <a class="btn" href={link('build')}>{t("Open topology")} <ArrowRight size={14} /></a>
      </section>
    </div>
  {:else if section === 'growth'}
    <div class="split growth-summary">
      <section class="panel pad stack">
        <div><p class="eyebrow">{t("Registered users")}</p><strong class="big-stat">{num(game.audience)}</strong><p class="muted">{t("Satisfaction ·")} {pct(game.satisfaction, 1)}</p></div>
        <Chart title={t("Registered users")} values={game.business_history.map((point) => point.audience)} ticks={game.business_history.map((point) => point.tick)} time={tickTime} sampleTime={(tick) => when(tick, game.start_minute, catalog.minutes_per_tick)} />
      </section>
      <section class="panel inset pad stack">
        <h2 data-tutorial={target.growth}>{t("Growth readiness")}</h2><p class="muted">{t("Projected load during a creator campaign")}</p>
        {#if readiness}
          <strong class="stat">{t('{0}–{1} RPS', [num(readiness.rps.low), num(readiness.rps.high)])}</strong>
          <Meter value={readiness.availability.low} label={t("Forecast minimum availability")} tone={readiness.availability.low < .95 ? 'warn' : 'good'} />
          <span class="badge {readiness.availability.low < .95 ? 'warn' : 'good'}">{readiness.availability.low < .95 ? t("Capacity may be exceeded") : t("Likely within capacity")}</span>
        {:else}<p class="muted">{t("Open a campaign to request a forecast.")}</p>{/if}
      </section>
    </div>
    {#if game.snapshot.demand_overview}<RegionalDemand demand={game.snapshot.demand_overview} markets={game.markets} />{/if}
    <MarketProjects {game} {busy} {act} />
    <MarketProjects {game} {busy} {act} localization />
    <div><h2>{t("Campaign catalog")}</h2><p class="muted">{t("Compare cost, reach and projected demand.")}</p></div>
    <div class="cards campaigns">
      {#each Object.entries(catalog.campaigns) as [id, campaign]}
        {@const running = game.campaigns.find((item) => item.id === id)}
        <article class="panel pad stack" class:emphasis={id === 'creator'}>
          <div class="row spread"><p class="eyebrow">{id === 'community' ? t("Small campaign") : id === 'creator' ? t("Medium campaign") : t("Large campaign")}</p><ArrowUpRight size={17} class="accent" /></div>
          <h2>{t(campaign.name)}</h2>
          <div class="row spread"><strong class="stat">{money(campaign.cost)}</strong><span class="mono muted">{duration(campaign.duration)}</span></div>
          <p class="muted">≈ {num(campaign.audience)} {t("new users")}</p>
          {#if running}
            {#if running.region}<p>{(running.regions?.length ? running.regions : [running.region]).map(marketName).join(', ')} · {money(running.budget ?? 0)}</p>{/if}
            <Meter value={running.progress} label={t("{0} remaining", [duration(running.remaining)])} />
          {:else}<button class="btn {id === 'creator' ? 'primary' : ''}" onclick={() => plan(id)}>{t("Plan campaign")} <ArrowRight size={14} /></button>{/if}
        </article>
      {/each}
    </div>
    {#if activeCampaigns.length || activeMarkets.length || activeLanguages.length}
      <section class="panel pad stack">
        <h2>{t('Active projects and campaigns')}</h2>
        {#each activeCampaigns as item (item.id)}
          <div class="row spread wrap"><strong>{t(catalog.campaigns[item.id].name)}</strong><span>{duration(item.remaining)}</span></div>
        {/each}
        {#each activeMarkets as item (item.id)}
          <div class="row spread wrap"><strong>{t(item.name)}</strong><span>{duration(item.remaining)}</span></div>
        {/each}
        {#each activeLanguages as item (item.name)}
          <div class="row spread wrap"><strong>{t(item.name)}</strong><span>{duration(item.remaining)}</span></div>
        {/each}
      </section>
    {/if}
  {:else if section === 'product'}
    <Engineering {game} {catalog} {act} {busy} {link} />
    <div class="cards stats">
      {#each [
        { label: 'Active features', value: game.features.filter((item) => item.enabled).length },
        { label: 'Features in progress', value: inDevelopment.length },
        { label: 'Projected additional load', value: `+${pct(inDevelopment.reduce((sum, item) => sum + item.demand_change, 0), 1)}` },
        { label: 'Development spend', value: money(game.economy.development) }
      ] as item}
        <section class="panel pad"><p class="eyebrow">{t(item.label)}</p><strong class="stat">{item.value}</strong></section>
      {/each}
    </div>
    <div class="split">
      <section class="panel pad stack">
        <div><h2>{t("Feature catalog")}</h2><p class="muted">{t("Select a feature to review its status and workload.")}</p></div>
        {#each game.features as feature (feature.id)}
          {@const definition = catalog.features[feature.id]}
          <article class="feature-row" data-tutorial={feature.id === 'advertising' ? target.monetization : feature.id === 'premium' ? target.premium : undefined} class:active={feature.id === featureId}>
            <button class="feature-select" aria-pressed={feature.id === featureId} onclick={() => featureId = feature.id}>
              <span class="dot {feature.enabled ? 'accent' : feature.state === 'developing' ? 'warning' : 'muted'}"></span>
              <span><h3>{t(definition.name)}</h3><small>{feature.id === 'premium' ? t('Additional synchronization for subscribers') : definition.operation ? t(catalog.operations[definition.operation]) : t("Base messenger workload")}</small></span>
              <span class="badge {feature.enabled || feature.can_release ? 'good' : inDevelopment.includes(feature) ? 'warn' : 'dim'}">{feature.state === 'ready' && !feature.can_release ? t('Release blocked') : featureStatus(feature)}</span>
            </button>
            <button class="btn icon-btn" aria-label={t("Feature details")} title={t("Feature details")} onclick={() => { featureId = feature.id; openFeature(feature.id); }}><ChevronRight size={16} /></button>
          </article>
        {/each}
      </section>
      {#if selectedFeature}
        {@const definition = catalog.features[selectedFeature.id]}
        <aside class="panel pad stack feature-detail">
          <div><h2>{t(definition.name)}</h2><p class="muted">{t("Development details")}</p></div>
          <p class:warning={selectedFeature.state === 'ready' && !selectedFeature.can_release}>{featureStatus(selectedFeature)}</p>
          {#if selectedFeature.state === 'developing'}<Meter value={1 - selectedFeature.remaining / definition.duration} label={t("{0} remaining", [duration(selectedFeature.remaining)])} tone="warn" />{/if}
          <dl class="breakdown">
            <div><dt>{t("Development cost")}</dt><dd>{money(definition.cost)}</dd></div>
            <div><dt>{t("Development time")}</dt><dd>{duration(definition.duration)}</dd></div>
            {#if selectedFeature.state !== 'released' && selectedFeature.demand_change > 0}<div><dt>{t("Additional request load")}</dt><dd>+{pct(selectedFeature.demand_change, 1)}</dd></div>{/if}
          </dl>
          {@render featureRequirements(selectedFeature)}
          <button class="btn {selectedFeature.state === 'ready' ? 'primary' : ''}" onclick={() => openFeature(selectedFeature!.id)}>{t("Open feature")} <ArrowRight size={14} /></button>
        </aside>
      {/if}
    </div>
    <ProductSettings {game} {catalog} {busy} {error} save={(product) => act('/product', { product }, 'PUT')} />
  {:else if section === 'finance'}
    <Finance {game} {catalog} />
  {:else if section === 'events'}
    <div class="split event-layout">
      <section class="panel pad stack">
        <div class="row spread wrap"><h2>{t("Incident history")}</h2><button class="btn" disabled={busy || game.incidents.some((item) => item.title === 'Instance failure drill')} onclick={() => dialog = 'drill'}>{t("Run failure drill")}</button></div>
        <div class="row wrap" aria-label={t("Filter events")}>
          {#each ['all', 'active', 'closed'] as filter}
            <button class="btn" aria-pressed={eventFilter === filter} onclick={() => eventFilter = filter as typeof eventFilter}>{filter === 'all' ? t("All events") : filter === 'active' ? t("Active") : t("Closed")}</button>
          {/each}
        </div>
        {#if !events.length}<p class="muted">{t("No matching events.")}</p>{/if}
        {#each events as item (item.id)}
          <button class="event row spread" class:active={selectedIncident?.id === item.id} onclick={() => openIncident(item)}>
            <span><strong>{message(item.title)}</strong><small>{gameTime(item.start)} · {message(item.symptom)}</small></span>
            <span class="badge {item.active ? 'warn' : 'dim'}">{item.active ? t("Active") : t("Closed")}</span><ChevronRight size={16} />
          </button>
        {/each}
      </section>
      <aside class="panel pad stack incident-preview">
        <div><h2>{t("Incident details")}</h2>{#if selectedIncident}<p class="muted">{message(selectedIncident.title)}</p>{/if}</div>
        {#if selectedIncident}{@render incidentDetails(selectedIncident)}{@render incidentActions(selectedIncident)}
        {:else}<p class="muted">{t("Incident details appear here as events are recorded.")}</p>{/if}
      </aside>
    </div>
    <section class="panel pad stack">
      <h2>{t("Deployment history")}</h2>
      {#if !game.deployments.length}<p class="muted">{t("No deployments yet.")}</p>{/if}
      {#each game.deployments as item (item.id)}
        <div class="event row spread"><div><strong>{message(item.summary)}</strong><small>{gameTime(item.tick)} · {preciseMoney(item.cost)}</small></div><button class="btn" disabled={busy || Boolean(game.draft)} onclick={() => { detail = item.id; dialog = 'rollback'; }}>{t("Review rollback")}</button></div>
        {#if item.comparison}<details class="event"><summary data-tutorial={item.id === game.deployments[0]?.id ? target.eventComparison : undefined}>{t("View before and after")}</summary><DeploymentComparison comparison={item.comparison} /></details>{/if}
      {/each}
      {#if game.draft && game.deployments.length}<p class="muted">{t("Discard the current draft to roll back.")}</p>{/if}
    </section>
  {:else if section === 'guide'}
    <Guide {catalog} {game} {link} {busy} {tutorialAction} />
  {:else if section === 'settings'}
    <div class="split settings-layout">
      <nav class="panel inset pad settings-tabs" aria-label={t("Settings sections")}>
        {#each Object.entries(settingsTabs) as [key, label]}
          <button class="btn" aria-pressed={settingsTab === key} onclick={() => settingsTab = key as typeof settingsTab}>{t(label)}</button>
        {/each}
      </nav>
      <section class="panel pad stack settings-panel">
        {#if settingsTab === 'general'}
          <Language />
          <div><h2>{t("Game preferences")}</h2><p class="muted">{t("Settings are saved automatically.")}</p></div>
          <div><p class="eyebrow">{t("Game speed")}</p><div class="row wrap option-row">
            {#each [{ speed: 0, label: 'Paused' }, { speed: 1, label: '1×' }, { speed: 3, label: '3×' }] as option}
              <button class="btn" aria-pressed={game.speed === option.speed} disabled={busy} onclick={() => act('/clock', { speed: option.speed }, 'PUT')}>{t(option.label)}</button>
            {/each}
          </div></div>
          <label class="row spread setting"><span><strong>{t("Show onboarding prompts")}</strong><small>{t("Display the current tutorial step in the workbench.")}</small></span><Toggle switchStyle checked={game.settings.show_tutorial} disabled={busy} onchange={(value) => act('/settings', { settings: { ...game.settings, show_tutorial: value } }, 'PUT')} /></label>
          <TutorialControls {game} {busy} change={tutorialAction} />
          <div class="stack"><h3>{t('Keyboard shortcuts')}</h3>
            <dl class="breakdown">
              {#each [['Ctrl/Cmd + S', 'Save game'], ['Space', 'Pause or resume'], ['1 / 2 / 3', 'Set speed to 1× / 3× / 5×'], ['Escape', 'Close a dialog or clear selection']] as [key, label]}
                <div><dt>{t(label)}</dt><dd><kbd>{t(key)}</kbd></dd></div>
              {/each}
            </dl>
          </div>
          <div class="row wrap"><button class="btn" disabled={busy} onclick={() => act('/settings', { settings: { show_tutorial: true, reduced_motion: false } }, 'PUT')}>{t("Restore defaults")}</button><button class="btn primary" disabled={busy} onclick={() => act('/save')}>{t("Save game")}</button></div>
        {:else if settingsTab === 'accessibility'}
          <h2>{t("Accessibility")}</h2>
          <label class="row spread setting"><span><strong>{t("Reduce motion")}</strong><small>{t("Reduce animation and transitions.")}</small></span><Toggle switchStyle checked={game.settings.reduced_motion} disabled={busy} onchange={(value) => act('/settings', { settings: { ...game.settings, reduced_motion: value } }, 'PUT')} /></label>

        {:else}
          <div><h2>{t("Save management")}</h2><p class="muted">{t("The server saves progress as you play.")}</p></div>
          <div class="row wrap"><button class="btn primary" disabled={busy} onclick={() => act('/save')}>{t("Save game")}</button><a class="btn" href="/?view=saves">{t("Saved games")}</a><a class="btn" href="/">{t("Main menu")}</a></div>
        {/if}
      </section>
    </div>
  {:else if section === 'more'}
    <div class="stack">
      {#each more as item}
        {@const Icon = sections[item].icon}
        <a class="event row spread" data-tutorial={nav(item)} href={item === 'saves' ? '/?view=saves' : link(item)}>
          <Icon size={20} class="accent" /><span class="more-label"><strong>{t(sections[item].name)}</strong><small>{t(sections[item].description)}</small></span><ChevronRight size={17} />
        </a>
      {/each}
    </div>
  {/if}
</main>

{#if dialog === 'campaign' && currentCampaign}
  <Modal title={t("Campaign planning")} subtitle={t(currentCampaign.name)} close={() => dialog = undefined} wide>
    <div class="stack">
      <p>{t('Shorter campaigns acquire the same expected number of users faster and can create a sharper traffic peak.')}</p>
      <div class="stack">
        <div class="field"><span>{t('Target markets')}</span>
          <Choice label={t('Target markets')} options={marketOptions} selected={targetMarkets} multiple searchable
            choose={(regions) => { targetMarkets = regions; updatePlan(); }} />
        </div>
        <div class="split equal">
          <div class="field"><span>{t('Campaign budget')}</span><NumberInput label={t('Campaign budget')} bind:value={budget} min={10} max={100000} step={50} precision={2} unit="USD" onchange={updatePlan} /></div>
          <div class="field"><span>{t('Duration (game hours)')}</span><NumberInput label={t('Duration (game hours)')} bind:value={campaignHours} min={.16} max={48} precision={2} onchange={updatePlan} /></div>
        </div>
      </div>
      {#if estimate?.plan}
        {@const preview = estimate.plan}
        <div class="split equal">
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
      <div class="row spread"><button class="btn" onclick={() => dialog = undefined}>{t("Cancel")}</button><button class="btn primary" disabled={busy || pending || !estimate?.plan?.acquired || game.balance < (estimate?.plan?.budget ?? Infinity) || game.campaigns.some((item) => item.id === detail)} onclick={() => confirm(`/campaigns/${detail}`, { regions: targetMarkets, budget: estimate?.plan?.budget, duration: estimate?.plan?.duration })}>{t("Start campaign")}</button></div>
    {/snippet}
  </Modal>
{:else if dialog === 'feature' && currentFeature}
  {@const definition = catalog.features[detail]}
  <Modal title={t("Feature details")} subtitle={t(definition.name)} close={() => dialog = undefined}>
    <div class="stack">
      <p class:warning={currentFeature.state === 'ready' && !currentFeature.can_release}>{featureStatus(currentFeature)}</p>
      <dl class="breakdown">
        <div><dt>{t("Development cost")}</dt><dd>{money(definition.cost)}</dd></div>
        <div><dt>{t("Development duration")}</dt><dd>{duration(definition.duration)}</dd></div>
        <div><dt>{t("Generated demand")}</dt><dd>{detail === 'premium' ? t('Additional synchronization for subscribers') : definition.operation ? t(catalog.operations[definition.operation]) : t("Base messenger operations")}</dd></div>
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
      <div class="row spread"><button class="btn" onclick={() => dialog = undefined}>{t("Close")}</button>
        {#if currentFeature.state === 'available'}<button class="btn primary" disabled={busy || game.balance < definition.cost} onclick={() => confirm(`/features/${detail}`, { action: 'develop' })}>{t("Start development")}</button>
        {:else if currentFeature.state === 'ready'}<button class="btn primary" disabled={busy || !currentFeature.can_release} onclick={() => confirm(`/features/${detail}`, { action: 'release' })}>{t("Release feature")}</button>
        {:else if currentFeature.state === 'released' && !currentFeature.enabled}
          <button class="btn primary" disabled={busy || !currentFeature.can_enable} onclick={() => confirm(`/features/${detail}`, { action: 'enable' })}>{t('Enable feature')}</button>
        {:else if currentFeature.enabled && currentFeature.can_disable}
          <button class="btn danger" disabled={busy} onclick={() => confirmDisable ? confirm(`/features/${detail}`, { action: 'disable' }) : confirmDisable = true}>{t(confirmDisable ? 'Confirm disable' : 'Disable feature')}</button>
        {/if}
      </div>
    {/snippet}
  </Modal>
{:else if dialog === 'incident' && incident}
  <Modal title={t("Incident details")} subtitle={message(incident.title)} close={() => dialog = undefined}>
    {@render incidentDetails(incident)}
    {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    {#snippet footer()}{@render incidentActions(incident)}{/snippet}
  </Modal>
{:else if dialog === 'rollback' && deployment}
  <Modal title={t("Review rollback")} close={() => dialog = undefined}>
    <div class="stack"><p>{t("Restore the topology that was in production before “")}{message(deployment.summary)}{t("” on")} {gameTime(deployment.tick)}{t(". The server revalidates the topology and charges any installation cost.")}</p>{#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}</div>
    {#snippet footer()}<div class="row spread"><button class="btn" onclick={() => dialog = undefined}>{t("Cancel")}</button><button class="btn danger" disabled={busy} onclick={() => confirm(`/deployments/${detail}/rollback`, { revision: game.revision })}>{t("Roll back")}</button></div>{/snippet}
  </Modal>
{:else if dialog === 'drill'}
  <Modal title={t("Run failure drill")} close={() => dialog = undefined}>
    <div class="stack"><p>{t("Take one API instance offline for two in-game hours to test routing and recovery. The drill affects live traffic.")}</p>{#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}</div>
    {#snippet footer()}<div class="row spread"><button class="btn" onclick={() => dialog = undefined}>{t("Cancel")}</button><button class="btn danger" disabled={busy} onclick={() => confirm('/incidents/drill')}>{t("Start drill")}</button></div>{/snippet}
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
  .cards, .split { display: grid; gap: 21px; }
  .stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .stat { display: block; font-size: clamp(22px, 2.4vw, 34px); line-height: 1.15; margin: 8px 0 4px; }
  .big-stat { display: block; font-size: clamp(34px, 4vw, 52px); line-height: 1.1; margin: 10px 0 4px; }
  .split { grid-template-columns: 2.05fr 1fr; }
  .growth-summary { align-items: start; }
  .growth-summary :global(.chart) { max-width: 740px; }
  .split.equal { grid-template-columns: 1fr 1fr; }
  .split > .stack { align-content: start; }
  .campaigns { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .campaigns > article { align-content: start; grid-template-rows: auto auto auto 1fr auto; gap: 10px; }
  .campaigns .emphasis { border-color: var(--primary); }
  .feature-row { display: flex; gap: 5px; align-items: center; padding-right: 9px; border: 1px solid var(--border); border-radius: 9px; background: var(--rail); }
  .feature-row.active { background: var(--tint); border-color: var(--primary); }
  .feature-select { flex: 1; display: grid; grid-template-columns: 7px 1fr auto; align-items: center; gap: 13px; border: 0; background: transparent; color: var(--text); min-height: 56px; padding: 9px 12px; text-align: left; }
  .feature-select h3 { text-transform: uppercase; font-size: 14px; }
  .feature-select small { display: block; }
  .feature-detail { align-content: start; }
  .dashboard h2 { font-size: 18px; }
  .dashboard h2 + p { margin-top: 4px; font-size: 13px; }
  .timeline { gap: 9px; }
  .timeline button { display: grid; align-items: start; grid-template-columns: 7px auto 1fr; gap: 11px; padding: 8px 0; width: 100%; text-align: left; background: transparent; border: 0; color: var(--text); font-size: 12px; }
  .timeline button:hover { color: var(--primary); }
  .timeline .dot { color: var(--primary); margin-top: 6px; }
  .timeline .dot.item-warn { color: var(--warning); }
  .throughput { color: #77b9ba; }
  .node-meter { gap: 6px; font-size: 12px; }
  .event { text-align: left; padding: 13px; width: 100%; border: 1px solid var(--border); border-radius: 9px; background: var(--rail); color: var(--text); }
  button.event:hover, a.event:hover { border-color: var(--primary); }
  .event strong { font-size: 15px; }
  .event.active { background: var(--tint); border-color: var(--warning); }
  .event-layout { grid-template-columns: .8fr 1.2fr; }
  .settings-layout { grid-template-columns: minmax(200px, .36fr) 1fr; }
  .settings-tabs { display: grid; gap: 8px; align-content: start; }
  .settings-tabs .btn { justify-content: flex-start; min-height: 43px; background: transparent; border-color: transparent; }
  .settings-tabs .btn[aria-pressed="true"] { background: var(--tint); color: var(--primary); }
  .settings-panel { min-height: 360px; align-content: start; }
  .setting { border-block: 1px solid var(--border); padding: 15px 0; }
  .setting small { display: block; }
  .option-row { margin-top: 7px; }
  .option-row .btn { min-width: 74px; }
  .event small { display: block; margin-top: 3px; }
  .event > :first-child { flex: 1 1 auto; }
  .more-label { flex: 1; }
  a.event > :first-child { flex: 0 0 auto; }
  .breakdown { margin: 0; display: grid; gap: 8px; }
  .breakdown > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); padding: 6px 0; }
  .breakdown dd { font: 400 12px var(--mono); text-align: right; }
  .overview { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .overview strong { font-size: 21px; }
  @media (max-width: 1050px) {
    .dashboard { padding: 24px 20px; }
    .cards, .split { gap: 12px; }
  }
  @media (max-width: 850px) {
    .dashboard { padding: 16px 17px 25px; gap: 15px; }
    .dash-header { min-height: 0; }
    .dash-header h1 { margin-top: 4px; }
    .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .split, .split.equal, .campaigns { grid-template-columns: 1fr; }
    .campaigns > article { grid-template-rows: none; }
    .feature-detail, .incident-preview { display: none; }
    .settings-tabs { display: flex; flex-wrap: wrap; }
    .settings-tabs .btn { flex: 1; justify-content: center; }
    .settings-panel { min-height: 0; }
    .feature-select { gap: 7px; padding-inline: 8px; }
    .overview { gap: 7px; }
    .overview strong { font-size: 19px; }
  }
  @media (max-width: 400px) {
    .dashboard .pad { padding: 13px; }
    .dash-header .badge { max-width: 100px; }
  }
</style>
