<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowRight, ArrowUpRight, ChevronRight } from '@lucide/svelte';
  import Modal from '../Modal.svelte';
  import Meter from '../Meter.svelte';
  import Guide from '../Guide.svelte';
  import Chart from './Chart.svelte';
  import ForecastCard from './Forecast.svelte';
  import { api } from '../api';
  import { more, sections, statusLabel, type Section } from '../labels';
  import { clock, duration, money, ms, num, pct, preciseMoney, rps, when } from '../format';
  import type { Catalog, Game, Forecast, Incident } from '../types';

  let { section, game, catalog, link, act, busy, error, note }: {
    section: Section; game: Game; catalog: Catalog; link: (section: Section, focus?: string) => string;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    busy: boolean; error: string; note: (interaction: 'inspect' | 'monitor') => void;
  } = $props();
  let dialog = $state<'campaign' | 'feature' | 'incident' | 'rollback' | 'drill'>();
  let detail = $state('');
  let featureId = $state('groups');
  let eventId = $state('');
  let eventFilter = $state<'all' | 'active' | 'closed'>('all');
  let settingsTab = $state<'general' | 'accessibility' | 'storage'>('general');
  let estimate = $state<Forecast>();
  let readiness = $state<Forecast>();
  let forecastError = $state('');
  let pending = $state(false);
  let range = $state('24');
  let forecastToken = 0;
  let lastReadiness = '';
  const metric = $derived(game.snapshot.metrics);
  const telemetry = $derived(Object.entries(game.snapshot.components));
  const pressured = $derived(telemetry.filter(([, item]) => ['failed', 'overloaded', 'warning'].includes(item.status)));
  const history = $derived(game.history.slice(-Number(range) * 6));
  const currentCampaign = $derived(catalog.campaigns[detail]);
  const currentFeature = $derived(game.features.find((item) => item.id === detail));
  const selectedFeature = $derived(game.features.find((item) => item.id === featureId));
  const inDevelopment = $derived(game.features.filter((item) => item.state === 'developing' || item.state === 'ready'));
  const categories = $derived(Object.entries(catalog.components).reduce<Record<string, number>>((costs, [kind, item]) => {
    costs[item.category] = (costs[item.category] ?? 0) + game.production.nodes.filter((node) => node.kind === kind).reduce((sum, node) => sum + (game.component_costs[node.id] ?? 0), 0);
    return costs;
  }, {}));
  const incident = $derived(game.incidents.find((item) => item.id === detail));
  const events = $derived(game.incidents.filter((item) => eventFilter === 'all' || (eventFilter === 'active' ? item.active : !item.active)));
  const activeEvents = $derived(game.incidents.filter((item) => item.active));
  const selectedIncident = $derived(events.find((item) => item.id === eventId) ?? events[0]);
  const deployment = $derived(game.deployments.find((item) => item.id === detail));
  const serviceStats = $derived([
    { label: 'Requests / sec', value: num(metric.rps), detail: `${rps(metric.throughput)} served` },
    { label: 'Average latency', value: ms(metric.latency), detail: 'Successful requests' },
    { label: 'Error rate', value: pct(metric.errors / (metric.rps || 1), 2), detail: `${rps(metric.rejected)} rate-limited` },
    { label: 'Availability', value: pct(metric.availability, 2), detail: 'Requests served' }
  ]);

  onMount(() => { if (section === 'monitor') note('monitor'); });

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
    const token = ++forecastToken;
    dialog = 'campaign';
    detail = id;
    pending = true;
    estimate = undefined;
    forecastError = '';
    try {
      const result = await api<Forecast>(`/${game.id}/campaigns/${id}/forecast`);
      if (token === forecastToken) estimate = result;
    } catch (reason) {
      if (token === forecastToken) forecastError = (reason as Error).message;
    } finally {
      if (token === forecastToken) pending = false;
    }
  }

  async function confirm(path: string, body?: object) {
    if (await act(path, body)) dialog = undefined;
  }

  function openIncident(item: Incident) { eventId = item.id; detail = item.id; dialog = 'incident'; }
  const settingsTabs = { general: 'General', accessibility: 'Accessibility', storage: 'Storage' } as const;

  const statuses = { locked: 'Locked', available: 'Available', developing: 'In development', ready: 'Ready to release', released: 'Released' };
  const headers: Partial<Record<Section, { tag: string; title: string; subtitle?: string }>> = {
    home: { tag: 'Production', title: 'Service overview', subtitle: 'Current service state and recent activity.' },
    monitor: { tag: 'Observability', title: 'System telemetry' },
    growth: { tag: 'Audience / Campaigns', title: 'Audience & campaigns', subtitle: 'Plan campaigns and forecast additional traffic.' },
    finance: { tag: 'Economy', title: 'Finance', subtitle: 'Balance, income and expenses.' },
    events: { tag: 'Operations / Events', title: 'Events and incidents', subtitle: 'Review service changes and investigate degraded performance.' },
    product: { tag: 'Product / Development', title: 'Product features', subtitle: 'Develop features and review their infrastructure requirements.' },
    guide: { tag: 'Reference', title: 'Guide', subtitle: 'Tutorials and component mechanics.' },
    settings: { tag: 'Service preferences', title: 'Settings' },
    more: { tag: '', title: 'More', subtitle: 'Service management' }
  };
  const heading = $derived(headers[section]);
</script>

{#snippet statCards()}
  <div class="cards stats">
    {#each serviceStats as stat}
      <article class="panel pad"><p class="eyebrow">{stat.label}</p><strong class="stat">{stat.value}</strong><small>{stat.detail}</small></article>
    {/each}
  </div>
{/snippet}

{#snippet incidentDetails(item: Incident)}
  <div class="stack">
    <div class="row wrap">
      <span class="badge {item.active ? 'warn' : 'dim'}">{item.active ? 'Active' : 'Closed'}</span>
      <span class="badge dim">{item.severity}</span>
      {#if item.acknowledged}<span class="badge good">Acknowledged</span>{/if}
    </div>
    <p>{item.symptom}</p>
    <dl class="breakdown">
      <div><dt>Started</dt><dd>{when(item.start)}</dd></div>
      <div><dt>{item.active ? 'Expected end' : 'Ended'}</dt><dd>{when(item.end)}</dd></div>
      <div><dt>Duration</dt><dd>{duration(item.end - item.start)}</dd></div>
      <div><dt>Failed requests during incident</dt><dd>{num(item.failed_requests)}</dd></div>
      {#if item.cause}<div><dt>Diagnosed cause</dt><dd>{item.cause === 'failure' ? 'Instance failure' : item.cause === 'degradation' ? 'Reduced capacity' : 'Storage pressure'}</dd></div>{/if}
      {#if item.target}<div><dt>Affected component</dt><dd>{game.production.nodes.find((node) => node.id === item.target)?.name ?? item.target}</dd></div>{/if}
      {#if item.resolution}<div><dt>Resolution</dt><dd>{item.resolution}</dd></div>{/if}
    </dl>
    {#if !item.cause && item.active}<p class="muted">Component-level diagnostics require Monitoring linked to the affected service.</p>{/if}
  </div>
{/snippet}

{#snippet incidentActions(item: Incident)}
  <div class="row spread wrap">
    <a class="btn primary" href={item.target ? link('build', item.target) : link('monitor')} onclick={() => dialog = undefined}>{item.target ? 'Open in topology' : 'Open telemetry'} <ArrowRight size={14} /></a>
    {#if !item.acknowledged}<button class="btn" disabled={busy} onclick={() => act(`/incidents/${item.id}/acknowledge`)}>Acknowledge</button>{/if}
  </div>
{/snippet}

{#snippet timeline()}
  {#if game.incidents.length}
    <ul class="list timeline">
      {#each game.incidents.slice(0, 6) as item (item.id)}
        <li><button onclick={() => openIncident(item)}><span class:item-warn={item.severity !== 'info'} class="dot"></span><span class="mono muted">{clock(item.start)}</span><span>{item.title}</span></button></li>
      {/each}
    </ul>
  {:else}<p class="muted">No events recorded.</p>{/if}
{/snippet}

<main class="dashboard stack">
  {#if heading}
    <header class="dash-header row spread">
      <div>{#if heading.tag}<p class="eyebrow">{heading.tag}</p>{/if}<h1>{heading.title}</h1>{#if heading.subtitle}<p class="muted">{heading.subtitle}</p>{/if}</div>
      {#if section === 'monitor'}
        <label class="time-range"><span class="sr-only">History range</span><select bind:value={range}><option value="24">Last 24h</option><option value="6">Last 6h</option><option value="1">Last hour</option></select></label>
      {:else if section === 'growth' || section === 'product'}<span class="badge dim">Budget · {money(game.balance)}</span>
      {:else if section === 'events'}<span class="badge {activeEvents.length ? 'warn' : 'dim'}">{activeEvents.length} active</span>{/if}
    </header>
  {/if}

  {#if section === 'home'}
    <section class="panel pad stack">
      <div class="row spread"><div><p class="eyebrow">{catalog.scenarios[game.scenario]?.name} / {when(game.tick)}</p><h2>{game.name}</h2></div><span class="badge {metric.availability >= .95 ? 'good' : 'warn'}"><i class="dot"></i>{metric.availability >= .95 ? 'Operational' : 'Degraded'}</span></div>
      <div class="overview">
        <div><p class="eyebrow">Active users</p><strong>{num(game.audience)}</strong></div>
        <div><p class="eyebrow">Balance</p><strong>{money(game.balance)}</strong></div>
        <div><p class="eyebrow">Satisfaction</p><strong>{pct(game.satisfaction)}</strong></div>
      </div>
      <a class="btn primary" href={link('build')}>Open topology <ArrowRight size={15} /></a>
    </section>
    {@render statCards()}
    <section class="panel pad stack"><h2>Recent events</h2>{@render timeline()}</section>
  {:else if section === 'monitor'}
    {@render statCards()}
    <div class="split">
      <section class="panel pad stack">
        <div class="row spread"><div><h2>Traffic / throughput</h2><p class="muted">Incoming and successful requests per second</p></div><span class="badge good">RPS</span></div>
        <Chart title="Request traffic" values={history.map((point) => point.metrics.rps)} secondary={history.map((point) => point.metrics.throughput)} ticks={history.map((point) => point.tick)} />
        {#if history.length}<small><span class="accent">━ Incoming</span> &nbsp; <span class="throughput">┄ Successful</span></small>{/if}
      </section>
      <section class="panel inset pad stack"><h2>Incident timeline</h2>{@render timeline()}<a class="btn" href={link('events')}>View events <ArrowRight size={14} /></a></section>
    </div>
    <div class="split equal">
      <section class="panel pad stack">
        <h2>Node health</h2>
        {#if telemetry.length}
          {#each telemetry as [id, item]}
            <div class="stack node-meter"><div class="row spread"><span>{game.production.nodes.find((node) => node.id === id)?.name}</span><span class="mono muted">{statusLabel[item.status]}</span></div>
              {#if Object.keys(item.utilization).length}<Meter label="Peak resource utilization" value={Math.max(...Object.values(item.utilization))} show={false} />{/if}
            </div>
          {/each}
        {:else}<p class="muted">Connect components to Monitoring to inspect utilization and component health.</p>{/if}
      </section>
      <section class="panel pad stack">
        <h2>Diagnostics</h2>
        {#if pressured.length}
          {#each pressured as [id, item]}
            <p><span class="warning">{game.production.nodes.find((node) => node.id === id)?.name}</span> · {statusLabel[item.status]}{#if Object.keys(item.utilization).length} · {Object.entries(item.utilization).sort((a, b) => b[1] - a[1])[0][0]}{/if}</p>
          {/each}
        {:else}<p class="muted">{telemetry.length ? 'Monitored components are within their limits.' : 'Only service-level symptoms are available.'}</p>{/if}
        <a class="btn" href={link('build')}>Open topology <ArrowRight size={14} /></a>
      </section>
    </div>
  {:else if section === 'growth'}
    <div class="split">
      <section class="panel pad stack">
        <div><p class="eyebrow">Active audience</p><strong class="big-stat">{num(game.audience)}</strong><p class="muted">Satisfaction · {pct(game.satisfaction, 1)}</p></div>
        <Chart title="Active audience" values={game.business_history.map((point) => point.audience)} ticks={game.business_history.map((point) => point.tick)} />
      </section>
      <section class="panel inset pad stack">
        <h2>Growth readiness</h2><p class="muted">Projected load during a creator campaign</p>
        {#if readiness}
          <strong class="stat">{num(readiness.rps.low)}–{num(readiness.rps.high)} RPS</strong>
          <Meter value={readiness.availability.low} label="Forecast minimum availability" tone={readiness.availability.low < .95 ? 'warn' : 'good'} />
          <span class="badge {readiness.availability.low < .95 ? 'warn' : 'good'}">{readiness.availability.low < .95 ? 'Capacity may be exceeded' : 'Likely within capacity'}</span>
        {:else}<p class="muted">Open a campaign to request a forecast.</p>{/if}
      </section>
    </div>
    <div><h2>Campaign catalog</h2><p class="muted">Compare cost, reach and projected demand.</p></div>
    <div class="cards campaigns">
      {#each Object.entries(catalog.campaigns) as [id, campaign]}
        {@const running = game.campaigns.find((item) => item.id === id)}
        <article class="panel pad stack" class:emphasis={id === 'creator'}>
          <div class="row spread"><p class="eyebrow">{id === 'community' ? 'Small campaign' : id === 'creator' ? 'Medium campaign' : 'Large campaign'}</p><ArrowUpRight size={17} class="accent" /></div>
          <h2>{campaign.name}</h2>
          <div class="row spread"><strong class="stat">{money(campaign.cost)}</strong><span class="mono muted">{duration(campaign.duration)}</span></div>
          <p class="muted">≈ {num(campaign.audience)} new users</p>
          {#if running}<Meter value={running.progress} label={`${duration(running.remaining)} remaining`} />
          {:else}<button class="btn {id === 'creator' ? 'primary' : ''}" onclick={() => plan(id)}>Plan campaign <ArrowRight size={14} /></button>{/if}
        </article>
      {/each}
    </div>
  {:else if section === 'product'}
    <div class="cards stats">
      {#each [
        { label: 'Active features', value: game.features.filter((item) => item.state === 'released').length },
        { label: 'Features in progress', value: inDevelopment.length },
        { label: 'Projected additional load', value: `+${pct(inDevelopment.reduce((sum, item) => sum + item.demand_change, 0), 1)}` },
        { label: 'Development spend', value: money(game.economy.development) }
      ] as item}
        <section class="panel pad"><p class="eyebrow">{item.label}</p><strong class="stat">{item.value}</strong></section>
      {/each}
    </div>
    <div class="split">
      <section class="panel pad stack">
        <div><h2>Feature catalog</h2><p class="muted">Select a feature to review its status and workload.</p></div>
        {#each game.features as feature (feature.id)}
          {@const definition = catalog.features[feature.id]}
          <article class="feature-row" class:active={feature.id === featureId}>
            <button class="feature-select" aria-pressed={feature.id === featureId} onclick={() => featureId = feature.id}>
              <span class="dot {feature.state === 'released' ? 'accent' : feature.state === 'developing' ? 'warning' : 'muted'}"></span>
              <span><h3>{definition.name}</h3><small>{definition.operation ? catalog.operations[definition.operation] : 'Base messenger workload'}</small></span>
              <span class="badge {feature.state === 'released' || feature.state === 'ready' ? 'good' : feature.state === 'developing' ? 'warn' : 'dim'}">{statuses[feature.state]}</span>
            </button>
            <button class="btn icon-btn" aria-label="Feature details" title="Feature details" onclick={() => { featureId = feature.id; detail = feature.id; dialog = 'feature'; }}><ChevronRight size={16} /></button>
          </article>
        {/each}
      </section>
      {#if selectedFeature}
        {@const definition = catalog.features[selectedFeature.id]}
        <aside class="panel pad stack feature-detail">
          <div><h2>{definition.name}</h2><p class="muted">Development details</p></div>
          <span class="badge {selectedFeature.state === 'developing' ? 'warn' : 'good'}">{statuses[selectedFeature.state]}</span>
          {#if selectedFeature.state === 'developing'}<Meter value={1 - selectedFeature.remaining / definition.duration} label={`${duration(selectedFeature.remaining)} remaining`} tone="warn" />{/if}
          <dl class="breakdown">
            <div><dt>Development cost</dt><dd>{money(definition.cost)}</dd></div>
            <div><dt>Development time</dt><dd>{duration(definition.duration)}</dd></div>
            {#if selectedFeature.state !== 'released'}<div><dt>Additional request load</dt><dd>+{pct(selectedFeature.demand_change, 1)}</dd></div>{/if}
          </dl>
          {#if selectedFeature.requirements.length}<p class="muted">Requires {selectedFeature.requirements.join(', ')}.</p>{/if}
          <button class="btn {selectedFeature.state === 'ready' ? 'primary' : ''}" onclick={() => { detail = selectedFeature!.id; dialog = 'feature'; }}>Open feature <ArrowRight size={14} /></button>
        </aside>
      {/if}
    </div>
  {:else if section === 'finance'}
    <div class="cards stats">
      {#each [
        { label: 'Balance', amount: game.economy.balance, detail: `${preciseMoney(game.economy.profit)} net to date` },
        { label: 'Revenue / day', amount: game.economy.daily_revenue, detail: `${preciseMoney(game.economy.revenue)} earned` },
        { label: 'Operating costs / day', amount: game.economy.daily_operating, detail: `${preciseMoney(game.economy.operating)} spent` },
        { label: 'Net profit / day', amount: game.economy.daily_profit, detail: `${pct(game.economy.daily_profit / (game.economy.daily_revenue || 1), 1)} margin` }
      ] as stat}
        <section class="panel pad"><p class="eyebrow">{stat.label}</p><strong class="stat" class:danger={stat.amount < 0}>{preciseMoney(stat.amount)}</strong><small>{stat.detail}</small></section>
      {/each}
    </div>
    <div class="split">
      <section class="panel pad stack"><div><h2>Cash flow</h2><p class="muted">Balance over the last in-game day</p></div><Chart title="Game balance" values={game.business_history.map((point) => point.balance)} ticks={game.business_history.map((point) => point.tick)} /></section>
      <section class="panel inset pad stack">
        <h2>Expense breakdown</h2>
        {#each Object.entries(categories) as [label, amount]}
          <div class="stack node-meter"><div class="row spread"><span>{label}</span><strong>{preciseMoney(amount)} / day</strong></div><Meter value={amount / (game.economy.daily_infrastructure || 1)} {label} show={false} /></div>
        {/each}
        <dl class="breakdown">
          <div><dt>Development to date</dt><dd>{preciseMoney(game.economy.development)}</dd></div>
          <div><dt>Marketing to date</dt><dd>{preciseMoney(game.economy.marketing)}</dd></div>
          <div><dt>Deployments to date</dt><dd>{preciseMoney(game.economy.deployment)}</dd></div>
        </dl>
      </section>
    </div>
    <section class="panel pad stack">
      <h2>Production infrastructure</h2>
      <dl class="breakdown">
        {#each game.production.nodes as node (node.id)}<div><dt>{node.name}</dt><dd>{preciseMoney(game.component_costs[node.id] ?? 0)} / day</dd></div>{/each}
      </dl>
    </section>
  {:else if section === 'events'}
    <div class="split event-layout">
      <section class="panel pad stack">
        <div class="row spread wrap"><h2>Incident history</h2><button class="btn" disabled={busy || game.incidents.some((item) => item.title === 'Instance failure drill')} onclick={() => dialog = 'drill'}>Run failure drill</button></div>
        <div class="row wrap" aria-label="Filter events">
          {#each ['all', 'active', 'closed'] as filter}
            <button class="btn" aria-pressed={eventFilter === filter} onclick={() => eventFilter = filter as typeof eventFilter}>{filter === 'all' ? 'All events' : filter === 'active' ? 'Active' : 'Closed'}</button>
          {/each}
        </div>
        {#if !events.length}<p class="muted">No matching events.</p>{/if}
        {#each events as item (item.id)}
          <button class="event row spread" class:active={selectedIncident?.id === item.id} onclick={() => openIncident(item)}>
            <span><strong>{item.title}</strong><small>{when(item.start)} · {item.symptom}</small></span>
            <span class="badge {item.active ? 'warn' : 'dim'}">{item.active ? 'Active' : 'Closed'}</span><ChevronRight size={16} />
          </button>
        {/each}
      </section>
      <aside class="panel pad stack incident-preview">
        <div><h2>Incident details</h2>{#if selectedIncident}<p class="muted">{selectedIncident.title}</p>{/if}</div>
        {#if selectedIncident}{@render incidentDetails(selectedIncident)}{@render incidentActions(selectedIncident)}
        {:else}<p class="muted">Incident details appear here as events are recorded.</p>{/if}
      </aside>
    </div>
    <section class="panel pad stack">
      <h2>Deployment history</h2>
      {#if !game.deployments.length}<p class="muted">No deployments yet.</p>{/if}
      {#each game.deployments as item (item.id)}
        <div class="event row spread"><div><strong>{item.summary}</strong><small>{when(item.tick)} · {preciseMoney(item.cost)}</small></div><button class="btn" disabled={busy || Boolean(game.draft)} onclick={() => { detail = item.id; dialog = 'rollback'; }}>Review rollback</button></div>
      {/each}
      {#if game.draft && game.deployments.length}<p class="muted">Discard the current draft to roll back.</p>{/if}
    </section>
  {:else if section === 'guide'}
    <Guide {catalog} {game} {link} />
  {:else if section === 'settings'}
    <div class="split settings-layout">
      <nav class="panel inset pad settings-tabs" aria-label="Settings sections">
        {#each Object.entries(settingsTabs) as [key, label]}
          <button class="btn" aria-pressed={settingsTab === key} onclick={() => settingsTab = key as typeof settingsTab}>{label}</button>
        {/each}
      </nav>
      <section class="panel pad stack settings-panel">
        {#if settingsTab === 'general'}
          <div><h2>Game preferences</h2><p class="muted">Settings are saved automatically.</p></div>
          <div><p class="eyebrow">Game speed</p><div class="row wrap option-row">
            {#each [{ speed: 0, label: 'Paused' }, { speed: 1, label: '1×' }, { speed: 3, label: '3×' }] as option}
              <button class="btn" aria-pressed={game.speed === option.speed} disabled={busy} onclick={() => act('/clock', { speed: option.speed }, 'PUT')}>{option.label}</button>
            {/each}
          </div></div>
          <label class="row spread setting"><span><strong>Show onboarding prompts</strong><small>Display the current tutorial step in the workbench.</small></span><input type="checkbox" checked={game.settings.show_tutorial} disabled={busy} onchange={(event) => act('/settings', { settings: { ...game.settings, show_tutorial: event.currentTarget.checked } }, 'PUT')} /></label>
          <div class="row wrap"><button class="btn" disabled={busy} onclick={() => act('/settings', { settings: { show_tutorial: true, reduced_motion: false } }, 'PUT')}>Restore defaults</button><button class="btn primary" disabled={busy} onclick={() => act('/save')}>Save game</button></div>
        {:else if settingsTab === 'accessibility'}
          <h2>Accessibility</h2>
          <label class="row spread setting"><span><strong>Reduce motion</strong><small>Reduce animation and transitions.</small></span><input type="checkbox" checked={game.settings.reduced_motion} disabled={busy} onchange={(event) => act('/settings', { settings: { ...game.settings, reduced_motion: event.currentTarget.checked } }, 'PUT')} /></label>
          <p class="muted">Interface language · English</p>
        {:else}
          <div><h2>Save management</h2><p class="muted">The server saves progress as you play.</p></div>
          <div class="row wrap"><button class="btn primary" disabled={busy} onclick={() => act('/save')}>Save game</button><a class="btn" href="/?view=saves">Saved games</a><a class="btn" href="/">Main menu</a></div>
        {/if}
      </section>
    </div>
  {:else if section === 'more'}
    <div class="stack">
      {#each more as item}
        {@const Icon = sections[item].icon}
        <a class="event row spread" href={item === 'saves' ? '/?view=saves' : link(item)}>
          <Icon size={20} class="accent" /><span class="more-label"><strong>{sections[item].name}</strong><small>{sections[item].description}</small></span><ChevronRight size={17} />
        </a>
      {/each}
    </div>
  {/if}
</main>

{#if dialog === 'campaign' && currentCampaign}
  <Modal title="Campaign planning" subtitle={currentCampaign.name} close={() => dialog = undefined}>
    <div class="stack">
      <p>{currentCampaign.description}</p>
      <dl class="breakdown">
        <div><dt>Campaign cost</dt><dd>{money(currentCampaign.cost)}</dd></div>
        <div><dt>Duration</dt><dd>{duration(currentCampaign.duration)}</dd></div>
        <div><dt>Expected acquisition</dt><dd>≈ {num(currentCampaign.audience)} users</dd></div>
      </dl>
      {#if pending}<p aria-live="polite">Calculating forecast…</p>{/if}
      {#if estimate}<ForecastCard forecast={estimate} />{/if}
      {#if forecastError || error}<p class="notice error" role="alert">{forecastError || error}</p>{/if}
      {#if game.balance < currentCampaign.cost}<p class="notice warn">Insufficient funds.</p>{/if}
    </div>
    {#snippet footer()}
      <div class="row spread"><button class="btn" onclick={() => dialog = undefined}>Cancel</button><button class="btn primary" disabled={busy || pending || !estimate || game.balance < currentCampaign.cost || game.campaigns.some((item) => item.id === detail)} onclick={() => confirm(`/campaigns/${detail}`)}>Start campaign</button></div>
    {/snippet}
  </Modal>
{:else if dialog === 'feature' && currentFeature}
  {@const definition = catalog.features[detail]}
  <Modal title="Feature details" subtitle={definition.name} close={() => dialog = undefined}>
    <div class="stack">
      <span class="badge good">{statuses[currentFeature.state]}</span>
      <dl class="breakdown">
        <div><dt>Development cost</dt><dd>{money(definition.cost)}</dd></div>
        <div><dt>Development duration</dt><dd>{duration(definition.duration)}</dd></div>
        <div><dt>Generated demand</dt><dd>{definition.operation ? catalog.operations[definition.operation] : 'Base messenger operations'}</dd></div>
        {#if currentFeature.state !== 'released'}<div><dt>Additional request load</dt><dd>+{pct(currentFeature.demand_change, 1)}</dd></div>{/if}
        <div><dt>Appeal contribution</dt><dd>+{pct(definition.appeal)}</dd></div>
        {#if definition.requires.length}<div><dt>Required infrastructure</dt><dd>{definition.requires.map((kind) => catalog.components[kind].name).join(', ')}</dd></div>{/if}
      </dl>
      {#if currentFeature.requirements.length}<p class="notice warn">Requires {currentFeature.requirements.join(', ')}.</p>{/if}
      {#if currentFeature.state === 'developing'}<Meter value={1 - currentFeature.remaining / definition.duration} label={`${duration(currentFeature.remaining)} remaining`} />{/if}
      {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    </div>
    {#snippet footer()}
      <div class="row spread"><button class="btn" onclick={() => dialog = undefined}>Close</button>
        {#if currentFeature.state === 'available'}<button class="btn primary" disabled={busy || game.balance < definition.cost} onclick={() => confirm(`/features/${detail}`, { action: 'develop' })}>Start development</button>
        {:else if currentFeature.state === 'ready'}<button class="btn primary" disabled={busy || !!currentFeature.requirements.length} onclick={() => confirm(`/features/${detail}`, { action: 'release' })}>Release feature</button>{/if}
      </div>
    {/snippet}
  </Modal>
{:else if dialog === 'incident' && incident}
  <Modal title="Incident details" subtitle={incident.title} close={() => dialog = undefined}>
    {@render incidentDetails(incident)}
    {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    {#snippet footer()}{@render incidentActions(incident)}{/snippet}
  </Modal>
{:else if dialog === 'rollback' && deployment}
  <Modal title="Review rollback" close={() => dialog = undefined}>
    <div class="stack"><p>Restore the topology that was in production before “{deployment.summary}” on {when(deployment.tick)}. The server revalidates the topology and charges any installation cost.</p>{#if error}<p class="notice error" role="alert">{error}</p>{/if}</div>
    {#snippet footer()}<div class="row spread"><button class="btn" onclick={() => dialog = undefined}>Cancel</button><button class="btn danger" disabled={busy} onclick={() => confirm(`/deployments/${detail}/rollback`, { revision: game.revision })}>Roll back</button></div>{/snippet}
  </Modal>
{:else if dialog === 'drill'}
  <Modal title="Run failure drill" close={() => dialog = undefined}>
    <div class="stack"><p>Take one API instance offline for two in-game hours to test routing and recovery. The drill affects live traffic.</p>{#if error}<p class="notice error" role="alert">{error}</p>{/if}</div>
    {#snippet footer()}<div class="row spread"><button class="btn" onclick={() => dialog = undefined}>Cancel</button><button class="btn danger" disabled={busy} onclick={() => confirm('/incidents/drill')}>Start drill</button></div>{/snippet}
  </Modal>
{/if}

<style>
  .dashboard { gap: 22px; padding: 27px 30px 35px; max-width: 1700px; margin: 0 auto; align-content: start; }
  .dash-header { align-items: flex-start; min-height: 75px; gap: 14px; }
  .dash-header h1 { margin: 7px 0 4px; }
  .dash-header p { margin-top: 2px; }
  .time-range { width: 146px; flex: 0 0 auto; }
  .cards, .split { display: grid; gap: 21px; }
  .stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .stat { display: block; font-size: clamp(22px, 2.4vw, 34px); line-height: 1.15; margin: 8px 0 4px; }
  .big-stat { display: block; font-size: clamp(34px, 4vw, 52px); line-height: 1.1; margin: 10px 0 4px; }
  .split { grid-template-columns: 2.05fr 1fr; }
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
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
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
    .time-range { width: 109px; }
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
    .dash-header > .badge { max-width: 100px; }
  }
</style>
