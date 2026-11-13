<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { ArrowRight, ChevronRight, GitBranch, List, MousePointer2, Plus, Redo2, Search,
    Trash2, Undo2, X } from '@lucide/svelte';
  import Modal from '../Modal.svelte';
  import Meter from '../Meter.svelte';
  import TopologyGraph from './TopologyGraph.svelte';
  import Configuration from './Configuration.svelte';
  import Forecast from './Forecast.svelte';
  import { api } from '../api';
  import { componentIcon, statusLabel } from '../labels';
  import { ms, num, pct, preciseMoney, rps, when } from '../format';
  import type { Catalog, Component, Connection, Game, Kind, Point, Review, Setting, Topology } from '../types';

  let { game, catalog, act, busy, error, note, focusId }: {
    game: Game; catalog: Catalog; busy: boolean; error: string;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    note: (interaction: 'inspect' | 'monitor') => void; focusId?: string;
  } = $props();

  let compact = $state(false);
  let layout = $state<'canvas' | 'list'>('canvas');
  let selected = $state('api');
  let selectedEdge = $state('');
  let search = $state('');
  let inspectorTab = $state<'configuration' | 'metrics'>('configuration');
  let dialog = $state<'catalog' | 'inspector' | 'configuration' | 'review' | 'discard' | 'connect'>();
  let source = $state('');
  let target = $state('');
  let history = $state.raw<Topology[]>([]);
  let future = $state.raw<Topology[]>([]);
  let review = $state<Review>();
  let reviewError = $state('');
  let reviewing = $state(false);
  let context = $state<{ x: number; y: number }>();
  let cluster = $state(false);
  let editError = $state('');
  let localRevision = -1;
  let editingDraft = false;
  let canvas: HTMLDivElement | undefined = $state();

  const topology = $derived(game.draft ?? game.production);
  const active = $derived(topology.nodes.find((node) => node.id === selected));
  const metric = $derived(game.snapshot.components[selected]);
  const activeConfig = $derived(active && Object.fromEntries(Object.entries(catalog.components[active.kind].fields).map(([key, field]) => [key, active.config[key] ?? field.default])));
  const removed = $derived(game.draft ? game.production.nodes.filter((node) => !topology.nodes.some((item) => item.id === node.id)) : []);
  const kinds = $derived((Object.keys(catalog.components) as Kind[]).filter((kind) => kind !== 'source'));
  const categories = ['Traffic', 'Compute', 'Data', 'Operations'];
  const edgeKey = (edge: Connection) => `${edge.source}:${edge.target}`;
  const edge = $derived(topology.edges.find((item) => edgeKey(item) === selectedEdge));
  const origin = $derived(topology.nodes.find((node) => node.id === source));
  const targets = $derived(origin ? topology.nodes.filter((node) => catalog.connections[origin.kind].includes(node.kind) &&
    !topology.edges.some((item) => item.source === origin?.id && item.target === node.id)) : []);
  const delta = $derived(Object.entries(game.draft_costs).reduce((sum, [, cost]) => sum + cost, 0) - game.economy.daily_infrastructure);
  const pendingChanges = $derived.by(() => {
    if (!game.draft) return [];
    const live = new Map(game.production.nodes.map((node) => [node.id, node]));
    const items: { label: string; note: string; tone: string }[] = [];
    for (const node of topology.nodes) {
      const before = live.get(node.id);
      if (!before) { items.push({ label: node.name, note: 'Component added', tone: 'good' }); continue; }
      const fields = catalog.components[node.kind].fields;
      const settings = Object.keys(fields).filter((key) => (before.config[key] ?? fields[key].default) !== (node.config[key] ?? fields[key].default));
      if (before.name !== node.name || settings.length) items.push({ label: node.name, note: settings.map((key) => fields[key].label).join(', ') || 'Name changed', tone: 'warn' });
      if (before.position.x !== node.position.x || before.position.y !== node.position.y) items.push({ label: node.name, note: 'Position updated', tone: 'dim' });
    }
    for (const node of removed) items.push({ label: node.name, note: 'Component removed', tone: 'bad' });
    const oldEdges = new Set(game.production.edges.map(edgeKey));
    const draftEdges = new Set(topology.edges.map(edgeKey));
    const connected = topology.edges.filter((edge) => !oldEdges.has(edgeKey(edge))).length;
    const disconnected = game.production.edges.filter((edge) => !draftEdges.has(edgeKey(edge))).length;
    if (connected) items.push({ label: 'Connections added', note: `${connected} new`, tone: 'good' });
    if (disconnected) items.push({ label: 'Connections removed', note: `${disconnected} removed`, tone: 'bad' });
    return items;
  });
  const changeLabels: Record<string, string> = { added: 'Added', removed: 'Removed', modified: 'Modified', moved: 'Moved', connected: 'Connections added', disconnected: 'Connections removed' };
  const last = $derived(game.incidents[0]);
  const metrics = $derived(game.snapshot.metrics);
  const summary = $derived([
    { label: 'Active users', value: num(game.audience) },
    { label: 'Request rate', value: rps(metrics.rps) },
    { label: 'Average latency', value: ms(metrics.latency) },
    { label: 'Error rate', value: pct(metrics.errors / (metrics.rps || 1), 2) }
  ]);

  onMount(() => {
    if (focusId && topology.nodes.some((item) => item.id === focusId)) select(focusId);
    const query = matchMedia('(max-width: 850px)');
    const update = () => { compact = query.matches; };
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  });

  $effect(() => {
    if (!editingDraft && localRevision >= 0 && game.revision !== localRevision) {
      history = [];
      future = [];
      localRevision = game.revision;
    }
  });

  function select(id: string) {
    selected = id;
    selectedEdge = '';
    cluster = false;
    context = undefined;
    if (topology.nodes.find((node) => node.id === id)?.kind === 'api') note('inspect');
  }

  function selectEdge(id: string) {
    selectedEdge = id;
    selected = '';
    context = undefined;
  }

  async function draft() {
    if (game.draft) return game;
    const result = await act('/draft', { revision: game.revision });
    if (result) { history = []; future = []; localRevision = result.revision; }
    return result;
  }

  async function edit(change: (value: Topology) => Topology) {
    editError = '';
    const state = await draft();
    if (!state?.draft) return false;
    const before = state.draft;
    const after = change(before);
    if (JSON.stringify(before) === JSON.stringify(after)) return true;
    editingDraft = true;
    const result = await act('/draft', { revision: state.revision, topology: after }, 'PUT');
    editingDraft = false;
    if (!result) return false;
    localRevision = result.revision;
    history = [...history, before].slice(-50);
    future = [];
    return true;
  }

  async function undo(redo = false) {
    const list = redo ? future : history;
    const item = list.at(-1);
    if (!item || !game.draft || busy) return;
    const before = game.draft;
    if (localRevision !== game.revision) { history = []; future = []; return; }
    editingDraft = true;
    const result = await act('/draft', { revision: game.revision, topology: item }, 'PUT');
    editingDraft = false;
    if (!result) return;
    localRevision = result.revision;
    if (redo) { future = list.slice(0, -1); history = [...history, before]; }
    else { history = list.slice(0, -1); future = [...future, before]; }
  }

  async function add(kind: Kind) {
    const id = crypto.randomUUID();
    if (await edit((value) => {
      const right = Math.max(...value.nodes.map((node) => node.position.x));
      const index = value.nodes.length;
      const position = { x: index < 7 ? 505 + (index - 4) * 225 : right + 220, y: index < 7 ? 365 : 185 };
      return { ...value, nodes: [...value.nodes, { id, kind, position, name: catalog.components[kind].name, config: {} }] };
    })) {
      select(id);
      dialog = undefined;
    }
  }

  function openConnect() {
    source = active && catalog.connections[active.kind].length ? active.id : 'traffic';
    target = '';
    dialog = 'connect';
  }

  async function connect(connection: Connection) {
    if (await edit((value) => ({ ...value, edges: [...value.edges, connection] }))) {
      dialog = undefined;
      select(connection.target);
    }
  }

  async function remove() {
    if (!game.draft || busy) return;
    if (edge) {
      const key = edgeKey(edge);
      if (await edit((value) => ({ ...value, edges: value.edges.filter((item) => edgeKey(item) !== key) }))) selectedEdge = '';
    } else if (active && active.kind !== 'source') {
      const id = active.id;
      if (await edit((value) => ({
        nodes: value.nodes.filter((node) => node.id !== id),
        edges: value.edges.filter((item) => item.source !== id && item.target !== id)
      }))) selected = '';
    }
    context = undefined;
  }

  function move(id: string, position: Point) {
    void edit((value) => ({ ...value, nodes: value.nodes.map((node) => node.id === id ? { ...node, position } : node) }));
  }

  async function configure() {
    if (active && active.kind !== 'source' && await draft()) {
      editError = '';
      dialog = 'configuration';
    }
  }

  async function updateConfig(name: string, config: Record<string, Setting>) {
    if (await edit((value) => ({ ...value, nodes: value.nodes.map((node) => node.id === selected ? { ...node, name, config } : node) }))) {
      dialog = compact ? 'inspector' : undefined;
    } else editError = 'The server could not save this configuration. Check the values and retry.';
  }

  async function inspectReview() {
    if (!game.draft) return;
    dialog = 'review';
    review = undefined;
    reviewError = '';
    reviewing = true;
    try { review = await api<Review>(`/${game.id}/draft/review`, 'POST', { revision: game.revision }); }
    catch (reason) { reviewError = (reason as Error).message; }
    finally { reviewing = false; }
  }

  async function finish(deploy: boolean) {
    if (await act(deploy ? '/deployments' : '/draft/discard', { revision: review?.revision ?? game.revision })) {
      dialog = undefined;
      history = [];
      future = [];
      review = undefined;
    }
  }

  function openMenu(event: MouseEvent, id?: string) {
    event.preventDefault();
    if (id) select(id);
    context = { x: Math.min(event.clientX, innerWidth - 185), y: Math.min(event.clientY, innerHeight - 172) };
    void tick().then(() => document.querySelector<HTMLButtonElement>('.context button')?.focus());
  }

  function shortcuts(event: KeyboardEvent) {
    if (dialog || event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || event.target instanceof HTMLTextAreaElement) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); void undo(event.shiftKey); }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') { event.preventDefault(); void undo(true); }
    if (event.key === 'Delete' && game.draft) { event.preventDefault(); void remove(); }
    if (event.key === 'Escape') context = undefined;
    if (event.key === 'Enter' && event.target instanceof HTMLElement) {
      const node = event.target.closest<HTMLElement>('.svelte-flow__node');
      if (node?.dataset.id) select(node.dataset.id);
    }
  }
</script>

<svelte:window onkeydown={shortcuts} />

{#snippet catalogList()}
  <label class="search"><Search size={14} /><input type="search" aria-label="Search components" placeholder="Search nodes…" bind:value={search} /></label>
  {#each categories as category}
    {@const matches = kinds.filter((kind) => catalog.components[kind].category === category && catalog.components[kind].name.toLowerCase().includes(search.trim().toLowerCase()))}
    {#if matches.length}
      <div class="catalog-group">
        <h3 class="eyebrow">{category === 'Data' ? 'Data & storage' : category}</h3>
        {#each matches as kind}
          {@const Icon = componentIcon[kind]}
          <button class="btn catalog-item" disabled={busy} onclick={() => add(kind)} title={catalog.components[kind].description}><Icon size={19} /><span>{catalog.components[kind].name}</span></button>
        {/each}
      </div>
    {/if}
  {/each}
  {#if search && !kinds.some((kind) => catalog.components[kind].name.toLowerCase().includes(search.trim().toLowerCase()))}<p class="muted">No matching components.</p>{/if}
{/snippet}

{#snippet inspect(full: boolean)}
  {#if active}
    {@const definition = catalog.components[active.kind]}
    {@const Icon = componentIcon[active.kind]}
    <div class="panel identity row">
      <span class="component-symbol"><Icon size={22} /></span>
      <div><h2>{active.name}</h2><p class="eyebrow {metric?.status === 'failed' ? 'danger' : 'accent'}">{definition.name}{metric ? ` / ${statusLabel[metric.status]}` : ''}</p></div>
    </div>
    {#if full}
      <div class="switch" aria-label="Inspector view">
        <button aria-pressed={inspectorTab === 'configuration'} onclick={() => inspectorTab = 'configuration'}>Configuration</button>
        <button aria-pressed={inspectorTab === 'metrics'} onclick={() => inspectorTab = 'metrics'}>Metrics</button>
      </div>
      {#if inspectorTab === 'configuration'}
        {#if active.kind === 'api' && activeConfig}
          <div class="stack">
            <div><p class="eyebrow">Instance size</p><button class="btn block instance" disabled={busy} onclick={configure}>{activeConfig.cpu} vCPU / {activeConfig.memory} GB <ChevronRight size={15} /></button></div>
            <div class="row spread"><span class="eyebrow">Replicas</span>
              <div class="row counter">
                <button class="btn icon-btn" aria-label="Remove replica" disabled={busy || Number(activeConfig.instances) <= 1} onclick={() => active && updateConfig(active.name, { ...active.config, instances: Number(activeConfig?.instances) - 1 })}>−</button>
                <strong>{activeConfig.instances}</strong>
                <button class="btn icon-btn accent" aria-label="Add replica" disabled={busy || Number(activeConfig.instances) >= 24} onclick={() => active && updateConfig(active.name, { ...active.config, instances: Number(activeConfig?.instances) + 1 })}>+</button>
              </div>
            </div>
          </div>
        {:else}<p class="muted">{definition.description}</p>{/if}
      {:else if metric}
        <dl class="metrics">
          <div><dt>Incoming</dt><dd>{rps(metric.rps)}</dd></div><div><dt>Processed</dt><dd>{rps(metric.throughput)}</dd></div>
          <div><dt>Local latency</dt><dd>{ms(metric.latency)}</dd></div>
          {#if metric.cache_hit !== null}<div><dt>Cache hit rate</dt><dd>{pct(metric.cache_hit, 1)}</dd></div>{/if}
          {#if metric.backlog !== null}<div><dt>Queued jobs</dt><dd>{num(metric.backlog)}</dd></div>{/if}
          {#if metric.storage_used !== null}<div><dt>Storage used</dt><dd>{num(metric.storage_used)} GB</dd></div>{/if}
          {#if metric.active_instances !== null}<div><dt>Active instances</dt><dd>{metric.active_instances}</dd></div>{/if}
        </dl>
      {/if}
      {#if active.kind === 'source'}
        <div class="bars">
          {#each Object.entries(game.snapshot.demand) as [key, value]}
            <div class="row spread"><span>{catalog.operations[key]}</span><strong class="mono">{rps(value)}</strong></div>
          {/each}
        </div>
      {:else if metric}
        <div class="bars">
          {#each Object.entries(metric.utilization).slice(0, inspectorTab === 'configuration' ? 2 : undefined) as [label, value]}
            <div><Meter {value} {label} /></div>
          {/each}
        </div>
      {:else}<p class="notice muted">Connect this component to deployed Monitoring to see its resource utilization.</p>{/if}
      <div class="row spread cost"><span class="eyebrow">Daily cost</span><strong>{preciseMoney((game.draft ? game.draft_costs : game.component_costs)[active.id] ?? 0)}</strong></div>
      {#if active.kind !== 'source'}<button class="btn primary block large" disabled={busy} onclick={configure}>Edit configuration <ArrowRight size={15} /></button>{/if}
      {#if Number(activeConfig?.instances) > 1}<button class="btn block" aria-pressed={cluster} onclick={() => { cluster = !cluster; if (compact) dialog = undefined; }}>{cluster ? 'Collapse instances' : 'Expand instances'}</button>{/if}
      {#if game.draft}
        <div class="row wrap"><button class="btn" onclick={openConnect} disabled={busy || !catalog.connections[active.kind].length}>Connect component</button>
        {#if active.kind !== 'source'}<button class="btn danger" disabled={busy} onclick={remove}><Trash2 size={13} /> Remove</button>{/if}</div>
      {/if}
    {:else}
      <p class="muted">{metric ? `${statusLabel[metric.status]} · ${rps(metric.rps)}` : definition.name}</p>
      <button class="btn primary block" onclick={() => dialog = 'inspector'}>Open component <ArrowRight size={15} /></button>
    {/if}
  {:else if edge}
    <div class="stack"><h2>Connection</h2><p>{topology.nodes.find((node) => node.id === edge?.source)?.name} → {topology.nodes.find((node) => node.id === edge?.target)?.name}</p>
    {#if game.draft}<button class="btn danger" disabled={busy} onclick={remove}>Remove connection</button>{:else}<button class="btn" onclick={draft} disabled={busy}>Create draft</button>{/if}</div>
  {:else}<p class="muted">Select a component or connection to inspect it.</p>{/if}
{/snippet}

<section class="architecture">
  <header class="topology-header">
    <div><p class="eyebrow">Production / {game.name}</p><h1><span class="desktop-heading">Infrastructure topology</span><span class="mobile-heading">Topology</span></h1><p class="mobile-sub muted">{game.draft ? 'Draft' : 'Production'} · {topology.nodes.length} components</p></div>
    <div class="service-metrics">
      {#each summary as item}<div><span class="eyebrow">{item.label}</span><strong>{item.value}</strong></div>{/each}
    </div>
  </header>
  <div class="workspace">
    <aside class="library" aria-label="Component library"><h2 class="eyebrow">Component library</h2>{@render catalogList()}</aside>
    <div class="drawing">
      <div class="canvas-bar row spread wrap" class:editing={game.draft}>
        <div class="row wrap">
          <span class="eyebrow desktop-only">{game.draft ? 'Draft topology' : 'Production topology'}</span>
          <span class="badge good"><i class="dot"></i>{game.draft ? `Editing draft / ${pendingChanges.length} changes` : 'Production'}</span>
        </div>
        <div class="row wrap">
          <button class="btn icon-btn" aria-label={layout === 'canvas' ? 'Show component list' : 'Show topology canvas'} title={layout === 'canvas' ? 'Show component list' : 'Show topology canvas'} onclick={() => layout = layout === 'canvas' ? 'list' : 'canvas'}>{#if layout === 'canvas'}<List size={16} />{:else}<MousePointer2 size={16} />{/if}</button>
          <button class="btn" disabled={busy} onclick={() => { search = ''; dialog = 'catalog'; }}><Plus size={14} /> Add node</button>
        </div>
      </div>
      {#if layout === 'canvas'}
        <div class="canvas" bind:this={canvas}>
          {#if canvas}
          {#key compact}
            <TopologyGraph {topology} {game} {catalog} {selected} edgeSelected={selectedEdge} editable={Boolean(game.draft) && !busy}
              {compact} {removed} {select} {selectEdge} {connect} {move} {cluster} container={canvas} menu={openMenu} clear={() => context = undefined} />
          {/key}
          {/if}
          <p class="canvas-hint mono">{compact ? 'Pinch to zoom · Drag to pan' : 'Flow direction →'}</p>
        </div>
      {:else}
        <div class="component-list stack">
          {#each [...topology.nodes, ...removed] as node (node.id)}
            {@const Icon = componentIcon[node.kind]}
            <button class="btn row spread" aria-pressed={selected === node.id} disabled={removed.includes(node)} onclick={() => select(node.id)}>
              <span class="row"><Icon size={17} /> {node.name}</span><span class="muted">{removed.includes(node) ? 'Pending removal' : catalog.components[node.kind].name}</span>
            </button>
          {/each}
          {#if topology.edges.length}<p class="eyebrow">Connections</p>{/if}
          {#each topology.edges as item (edgeKey(item))}
            <button class="btn" aria-pressed={selectedEdge === edgeKey(item)} onclick={() => selectEdge(edgeKey(item))}>{topology.nodes.find((n) => n.id === item.source)?.name} → {topology.nodes.find((n) => n.id === item.target)?.name}</button>
          {/each}
        </div>
      {/if}
      <div class="edit-bar row wrap">
        {#if game.draft}
          <button class="btn icon-btn" aria-label="Undo draft edit" title="Undo" disabled={busy || !history.length} onclick={() => undo()}><Undo2 size={16} /></button>
          <button class="btn icon-btn" aria-label="Redo draft edit" title="Redo" disabled={busy || !future.length} onclick={() => undo(true)}><Redo2 size={16} /></button>
          <button class="btn" disabled={busy} onclick={openConnect}>Connect</button>
          <button class="btn" disabled={busy} onclick={() => { review = undefined; dialog = 'discard'; }}>Discard</button>
          <button class="btn primary" disabled={busy} onclick={inspectReview}>Review deployment <ArrowRight size={14} /></button>
        {:else}<button class="btn" disabled={busy} onclick={draft}><GitBranch size={15} /> Create draft</button>{/if}
      </div>
    </div>
    <aside class="inspector" aria-label="Component inspector">
      <p class="eyebrow desktop-only">Component inspector</p>
      {@render inspect(!compact)}
      {#if game.draft && !compact}
        <section class="draft-summary stack">
          <div><p class="eyebrow accent">Draft summary</p><h2>{pendingChanges.length} pending changes</h2></div>
          {#each pendingChanges.slice(0, 3) as item}
            <div class="panel draft-item"><strong class={item.tone === 'good' ? 'accent' : item.tone === 'bad' ? 'danger' : item.tone === 'warn' ? 'warning' : ''}>{item.label}</strong><small>{item.note}</small></div>
          {/each}
          {#if pendingChanges.length > 3}<small>+{pendingChanges.length - 3} more in review</small>{/if}
          <div class="row spread"><span class="eyebrow">Daily cost change</span><strong>{delta >= 0 ? '+' : ''}{preciseMoney(delta)}</strong></div>
        </section>
      {/if}
    </aside>
  </div>
  <footer class="live row spread">
    <div><p class="eyebrow">Live events</p><p>{last ? `${when(last.start)} · ${last.title}` : 'No events recorded'}</p></div>
    <span class="mono {metrics.availability < .95 ? 'warning' : 'accent'}">● {pct(metrics.availability, 1)} availability</span>
  </footer>
</section>

{#if context}
  <div class="context panel stack" style:left={`${context.x}px`} style:top={`${context.y}px`}>
    <button class="btn" onclick={() => { dialog = 'catalog'; context = undefined; }}>Add node</button>
    {#if active && active.kind !== 'source'}<button class="btn" onclick={() => { context = undefined; void configure(); }}>Edit configuration</button>{/if}
    {#if game.draft && (edge || (active && active.kind !== 'source'))}<button class="btn danger" onclick={remove}>Remove selected</button>{/if}
    <button class="btn" onclick={() => context = undefined}><X size={14} /> Close menu</button>
  </div>
{/if}

{#if dialog === 'catalog'}
  <Modal title="Component library" subtitle="Add a component to the architecture draft." close={() => dialog = undefined}>
    {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    {@render catalogList()}
  </Modal>
{:else if dialog === 'inspector'}
  <Modal title="Component inspector" close={() => dialog = undefined}>
    <div class="stack">{@render inspect(true)}</div>
  </Modal>
{:else if dialog === 'configuration' && active}
  <Configuration component={active} definition={catalog.components[active.kind]} {busy} error={error || editError}
    close={() => dialog = compact ? 'inspector' : undefined} apply={updateConfig} />
{:else if dialog === 'connect'}
  <Modal title="Connect components" close={() => dialog = undefined}>
    <form id="connect-components" class="stack" onsubmit={(event) => { event.preventDefault(); if (target) void connect({ source, target }); }}>
      {#if error}<p class="notice error" role="alert">{error}</p>{/if}
      <label class="field"><span>Source component</span><select bind:value={source} onchange={() => target = ''}>
        {#each topology.nodes.filter((node) => catalog.connections[node.kind].length) as node}<option value={node.id}>{node.name}</option>{/each}
      </select></label>
      <label class="field"><span>Target component</span><select bind:value={target} required>
        <option value="">Select a compatible target</option>{#each targets as node}<option value={node.id}>{node.name}</option>{/each}
      </select></label>
      {#if !targets.length}<p class="muted">There are no new compatible connections from this component.</p>{/if}
    </form>
    {#snippet footer()}<button class="btn primary block" type="submit" form="connect-components" disabled={busy || !target}>Connect components</button>{/snippet}
  </Modal>
{:else if dialog === 'discard'}
  <Modal title="Discard draft" close={() => dialog = undefined}>
    <p>Remove all edits in the current draft?</p>
    {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    {#snippet footer()}<div class="row spread"><button class="btn" onclick={() => dialog = undefined}>Cancel</button><button class="btn danger" disabled={busy} onclick={() => finish(false)}>Discard draft</button></div>{/snippet}
  </Modal>
{:else if dialog === 'review'}
  <Modal title="Deployment review" subtitle="Validate the draft and check its impact before deploying." wide close={() => dialog = undefined}>
    <div class="stack">
      {#if reviewing}<p aria-live="polite">Checking topology…</p>{/if}
      {#if error || reviewError}<p class="notice error" role="alert">{error || reviewError}</p>{/if}
      {#if review}
        {#each review.errors as issue}<p class="notice error" role="alert">{issue}</p>{/each}
        <div class="panel inset pad stack">
          <h3>Change summary</h3>
          {#each Object.entries(review.changes) as [key, changes]}
            {#if changes.length && key !== 'modified'}
              <div class="review-item"><p class="eyebrow">{changeLabels[key]} · {changes.length}</p><p>{changes.join(', ')}</p></div>
            {/if}
          {/each}
          {#each review.details as item}
            <div class="review-item"><p class="eyebrow">{item.component} / {item.field}</p><p class="mono">{item.before} → {item.after}</p></div>
          {/each}
          {#if !Object.values(review.changes).some((items) => items.length)}<p class="muted">No changes to deploy.</p>{/if}
          <div class="row spread wrap"><span>Daily infrastructure</span><strong>{preciseMoney(review.daily_before)} → {preciseMoney(review.daily_after)}</strong></div>
          <div class="row spread"><span>One-time deployment cost</span><strong>{preciseMoney(review.install)}</strong></div>
        </div>
        {#each review.warnings as warning}<p class="notice warn">{warning}</p>{/each}
        {#if review.forecast}<Forecast forecast={review.forecast} />{/if}
      {/if}
    </div>
    {#snippet footer()}
      <div class="row spread wrap"><button class="btn" onclick={() => dialog = undefined}>Back to draft</button>
        <button class="btn primary" disabled={busy || !review || review.errors.length > 0 || !Object.values(review.changes).some((items) => items.length)}
          onclick={() => finish(true)}>Deploy changes <ArrowRight size={15} /></button>
      </div>
    {/snippet}
  </Modal>
{/if}

<style>
  .architecture { min-width: 0; display: grid; grid-template-rows: auto minmax(550px, 1fr) auto; min-height: calc(100dvh - 65px); }
  .topology-header { display: grid; grid-template-columns: .95fr 1.1fr; align-items: center; gap: 12px; min-height: 91px; background: var(--background); padding: 12px 26px; }
  .topology-header h1 { font-size: 26px; margin-top: 5px; }
  .service-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; }
  .service-metrics strong { display: block; font-size: clamp(17px, 1.7vw, 25px); white-space: nowrap; margin-top: 4px; }
  .service-metrics span { font-size: 10px; }
  .workspace { min-width: 0; display: grid; grid-template-columns: 220px minmax(0, 1fr) 341px; border-block: 1px solid var(--border); }
  .library, .inspector { min-width: 0; background: var(--rail); padding: 22px 20px; }
  .library { border-right: 1px solid var(--border); padding-bottom: 14px; }
  .library > h2 { color: var(--text); margin-bottom: 17px; }
  .inspector { display: grid; align-content: start; gap: 16px; border-left: 1px solid var(--border); }
  .catalog-group { display: grid; gap: 5px; margin: 17px 0 0; }
  .catalog-group h3 { margin-bottom: 2px; }
  .catalog-item { min-height: 40px; justify-content: flex-start; text-align: left; }
  .catalog-item :global(svg) { color: var(--primary); flex: 0 0 auto; margin-right: 7px; }
  .search { display: flex; align-items: center; gap: 4px; padding-left: 8px; color: var(--muted); background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
  .search :global(input) { border: 0; background: none; min-height: 35px; font-size: 12px; padding-left: 5px; }
  .drawing { min-width: 0; min-height: 550px; position: relative; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; background: var(--background); }
  .canvas-bar { z-index: 1; padding: 11px 15px; min-height: 55px; border-bottom: 1px solid var(--border); }
  .canvas-bar.editing { background: #223323; }
  .draft-summary { border-top: 1px solid var(--border); padding-top: 12px; gap: 8px; }
  .draft-summary h2 { margin-top: 4px; }
  .draft-item { padding: 8px 10px; }
  .draft-item small { display: block; }
  .review-item { border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px; background: var(--background); }
  .review-item p + p { margin-top: 4px; font-size: 13px; }
  .canvas { position: relative; min-width: 0; overflow: hidden; }
  .canvas-hint { position: absolute; bottom: 10px; left: 16px; font-size: 10px; color: var(--muted); pointer-events: none; }
  .edit-bar { z-index: 1; justify-content: flex-end; padding: 10px 15px; border-top: 1px solid var(--border); }
  .component-list { padding: 16px; align-content: start; overflow: auto; }
  .component-list button { justify-content: space-between; text-align: left; }
  .identity { padding: 13px; }
  .identity h2 { overflow-wrap: anywhere; }
  .identity p { margin-top: 3px; }
  .component-symbol { display: grid; place-items: center; flex: 0 0 40px; width: 40px; height: 40px; border-radius: 10px; background: var(--tint); color: var(--primary); }
  .switch { display: grid; grid-template-columns: 1fr 1fr; border-radius: 8px; background: var(--surface); overflow: hidden; }
  .switch button { min-height: 36px; color: var(--muted); border: 0; background: transparent; font-size: 12px; }
  .switch button[aria-pressed="true"] { color: var(--text); background: var(--tint); font-weight: 600; }
  .instance { margin-top: 5px; justify-content: space-between; }
  .counter { gap: 7px; padding-inline: 1px; }
  .counter button { min-height: 32px; }
  .cost { padding-top: 13px; border-top: 1px solid var(--border); }
  .cost strong { font-size: 22px; }
  .metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 0; font-size: 12px; }
  .metrics dd { font-family: var(--mono); }
  .live { min-height: 76px; padding: 15px 26px; background: var(--background); font-size: 12px; }
  .live p + p { margin-top: 5px; }
  .context { position: fixed; z-index: 10; width: 175px; padding: 8px; gap: 5px; }
  .mobile-sub, .mobile-heading { display: none; }
  @media (min-width: 1600px) {
    .workspace { grid-template-columns: 240px minmax(0, 1fr) 355px; }
  }
  @media (min-width: 851px) and (max-width: 1200px) {
    .workspace { grid-template-columns: 170px minmax(0, 1fr) 259px; }
    .library, .inspector { padding: 17px 13px; }
    .topology-header { padding-inline: 18px; }
  }
  @media (max-width: 850px) {
    .architecture { display: block; padding: 14px 17px 20px; min-height: 0; }
    .topology-header { display: block; padding: 0; background: none; min-height: 0; }
    .topology-header h1 { margin: 0; }
    .desktop-heading { display: none; }
    .mobile-heading { display: inline; }
    .topology-header .eyebrow, .service-metrics, .desktop-only, .library, .live { display: none; }
    .mobile-sub { display: block; font-size: 12px; }
    .workspace { display: flex; flex-direction: column; gap: 13px; border: 0; }
    .drawing { min-height: 0; background: none; display: flex; flex-direction: column; }
    .canvas-hint { top: 12px; bottom: auto; }
    .canvas { height: clamp(310px, 45dvh, 490px); border: 1px solid var(--border); border-radius: 10px; }
    .canvas-bar, .edit-bar { padding: 8px 0; border: 0; }
    .canvas-bar { min-height: 58px; }
    .canvas-bar.editing { background: transparent; }
    .edit-bar { padding-bottom: 0; }
    .inspector { padding: 12px; border: 1px solid var(--border); border-radius: 11px; background: var(--surface); gap: 7px; }
    .inspector .identity { padding: 0; border: 0; }
    .inspector .component-symbol { width: 35px; height: 35px; flex-basis: 35px; }
    .component-list { border: 1px solid var(--border); border-radius: 10px; background: var(--background); }
  }
</style>
