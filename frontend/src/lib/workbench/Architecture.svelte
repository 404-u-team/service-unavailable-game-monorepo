<script lang="ts">
  import { apiMessage, count, message, t } from '../i18n.svelte';
  import { onMount, tick } from 'svelte';
  import { ArrowLeft, ArrowRight, ChevronRight, Copy, GitBranch, Info, List, Minus, MousePointer2, Plus, Redo2, Scan, Search, SlidersHorizontal,
    Trash2, Undo2, X } from '@lucide/svelte';
  import Modal from '../Modal.svelte';
  import Meter from '../Meter.svelte';
  import { componentNotes } from './details';
  import TopologyGraph from './TopologyGraph.svelte';
  import DatabaseForecast from './DatabaseForecast.svelte';
  import Configuration from './Configuration.svelte';
  import Forecast from './Forecast.svelte';
  import Select from '../controls/Select.svelte';
  import { Alert, Badge, Button, Checkbox, Disclosure, Form, Switch, TextInput, Tooltip } from '@service-unavailable/ui';
  import DeploymentComparison from './DeploymentComparison.svelte';
  import { api } from '../api';
  import { inspectorPreference } from './layout-sync';
  import { guideArticleHref, resourceArticle } from '../guide';
  import { target as guideTarget, tutorialApi, type TutorialArchitecture, type TutorialEvent } from './onboarding';
  import { findPlacement, type CanvasTools } from './placement';
  import { groupComponents, nestedGroups, removeGroup } from './groups';
  import { connectionCategory, connectionError, connectionKind, connectionLabels, connectionStyles, type ConnectionCategory } from './connections';
  import { componentIcon, statusLabel } from '../labels';
  import { ms, num, pct, preciseMoney, rps } from '../format';
  import type { Catalog, Component, Connection, Diagram, DiagramViewport, Game, Kind, Point, Review, Setting, Topology } from '../types';

  let { game, catalog, act, busy, error, tutorial, tutorialSelect, tutorialLink, tutorialState, tutorialEvent, focusId, openConfiguration, guideHref, savedDiagram, saveDiagram, layoutFailed, retryDiagram }: {
    game: Game; catalog: Catalog; busy: boolean; error: string;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    tutorial: boolean; tutorialSelect: boolean; tutorialLink?: Connection; tutorialState: (state: TutorialArchitecture) => void; tutorialEvent: (event: TutorialEvent) => void; focusId?: string; openConfiguration?: boolean; guideHref: string;
    savedDiagram: Diagram; saveDiagram: (diagram: Diagram) => void;
    layoutFailed: boolean; retryDiagram: () => void;
  } = $props();

  let compact = $state(false);
  const defaultInspectorWidth = 410;
  let inspectorWidth = $state(defaultInspectorWidth);

  function saveInspectorWidth(width: number) {
    inspectorWidth = width;
    inspectorPreference(width);
  }

  let layout = $state<'canvas' | 'list'>('canvas');
  let showProduction = $state(false);
  let selected = $state('api');
  let selectedEdge = $state('');
  let search = $state('');
  let requestType = $state('');
  let hiddenConnections = $state.raw<ConnectionCategory[]>([]);
  let alignment = $state(false);
  const mapPreferenceKey = 'workbench-map-preferences';

  function setMapPreferences(hidden: ConnectionCategory[], guides: boolean) {
    hiddenConnections = hidden;
    alignment = guides;
    try { localStorage.setItem(mapPreferenceKey, JSON.stringify({ hidden, guides })); }
    catch { /* Preferences still apply for this session. */ }
  }

  function toggleConnection(category: ConnectionCategory, visible: boolean) {
    setMapPreferences(visible ? hiddenConnections.filter((item) => item !== category) : [...hiddenConnections, category], alignment);
  }
  let inspectorTab = $state<'configuration' | 'metrics'>('configuration');
  let dialog = $state<'deployed' | 'map-settings' | 'reference' | 'group' | 'catalog' | 'inspector' | 'configuration' | 'review' | 'discard' | 'connect'>();
  let drawer = $state<{ dismiss: (after?: () => void) => void }>();
  let source = $state('');
  let target = $state('');
  let history = $state.raw<Topology[]>([]);
  let future = $state.raw<Topology[]>([]);
  let deployed = $state<Game['deployments'][number]>();
  let review = $state<Review>();
  let reviewError = $state('');
  let reviewVersion = 0;
  let changedConfig = $state(false);
  let configurationReturn: 'inspector' | undefined;
  let referenceReturn: 'catalog' | undefined;
  let reviewing = $state(false);
  let context = $state<{ x: number; y: number; kind: 'canvas' | 'edge' | 'component'; origin?: HTMLElement }>();
  let contextPanel = $state<HTMLDivElement>();
  let cluster = $state(false);
  let editError = $state('');
  let localRevision = -1;
  let editingDraft = false;
  const canShard = $derived(game.engineering.some((item) => item.id === 'sharding' && item.state === 'completed'));
  let canvas: HTMLDivElement | undefined = $state();
  let placement = $state.raw<CanvasTools>();
  const bindPlacement = (tools?: typeof placement) => { placement = tools; };

  export function revealTutorialApi() {
    if (!guideApi) return;
    if (touchSelect) touchSelect = false;
    if (!canvas?.querySelector(`[data-tutorial="${guideTarget.api}"]`)) {
      layout = 'list';
      return;
    }
    placement?.revealNode(guideApi);
  }

  export function revealTutorialLink() {
    if (tutorialLink) placement?.revealNodes([tutorialLink.source, tutorialLink.target]);
  }

  function saveViewport(viewport: DiagramViewport) {
    const mode = compact ? 'compact' : 'wide';
    const last = savedDiagram.viewports?.[mode];
    if (last?.x === viewport.x && last.y === viewport.y && last.zoom === viewport.zoom) return;
    saveDiagram({ ...savedDiagram, viewports: { ...savedDiagram.viewports, [mode]: viewport } });
  }

  let diagramHistory = $state.raw<Diagram[]>([]);
  let diagramFuture = $state.raw<Diagram[]>([]);
  let lastEdit = $state<'diagram' | 'topology'>('topology');
  let previewRoute = $state.raw<{ key: string; points: Point[] }>();
  let groupSelected = $state('');
  let selection = $state.raw(['api']);
  let touchSelect = $state(false);
  let helpKind = $state<Kind>('api');
  let groupName = $state('');
  let groupMembers = $state.raw<string[]>([]);
  let groupParent = $state('');
  let replacedEdge = $state('');
  const diagram = $derived(previewRoute
    ? { ...savedDiagram, routes: { ...savedDiagram.routes, [previewRoute.key]: previewRoute.points } }
    : savedDiagram);
  const group = $derived(diagram.groups.find((item) => item.id === groupSelected));

  function changeDiagram(next: Diagram) {
    diagramHistory = [...diagramHistory, savedDiagram].slice(-50);
    diagramFuture = [];
    saveDiagram(next);
    lastEdit = 'diagram';
  }

  function undoDiagram(redo: boolean) {
    const stack = redo ? diagramFuture : diagramHistory;
    const next = stack.at(-1);
    if (!next) return;
    if (redo) {
      diagramHistory = [...diagramHistory, savedDiagram];
      diagramFuture = stack.slice(0, -1);
    } else {
      diagramFuture = [...diagramFuture, savedDiagram];
      diagramHistory = stack.slice(0, -1);
    }
    saveDiagram({ ...next, viewports: savedDiagram.viewports });
  }

  function chooseGroup(id: string) {
    groupSelected = id;
    selected = '';
    selectedEdge = '';
    selection = [];
  }

  function selectMany(ids: string[]) {
    if (ids.length === selection.length && ids.every((id) => selection.includes(id))) return;
    selection = ids;
    if (ids.length > 1) {
      selected = '';
      groupSelected = '';
      selectedEdge = '';
    }
  }

  function groupDialog(editing: boolean) {
    groupName = editing ? group?.name ?? '' : '';
    groupMembers = editing ? [...(group?.members ?? [])] : [...selection];
    groupParent = editing ? diagram.groups.find((item) => item.members.includes(group?.id ?? ''))?.id ?? '' : '';
    dialog = 'group';
  }

  function saveGroup() {
    if (!groupName.trim() || !groupMembers.length) return;
    const current = group;
    const members = new Set(groupMembers);
    const id = current?.id ?? crypto.randomUUID();
    const groups = savedDiagram.groups.filter((item) => item.id !== id)
      .map((item) => ({
        ...item,
        members: [...item.members.filter((member) => member !== id && !members.has(member)), ...(item.id === groupParent ? [id] : [])]
      }));
    groups.push({ id, name: groupName.trim(), members: groupMembers, collapsed: current?.collapsed ?? false });
    let clean = groups;
    while (clean.some((item) => item.members.length === 0)) {
      const empty = new Set(clean.filter((item) => !item.members.length).map((item) => item.id));
      clean = clean.filter((item) => !empty.has(item.id)).map((item) => ({ ...item, members: item.members.filter((member) => !empty.has(member)) }));
    }
    changeDiagram({ ...savedDiagram, groups: clean });
    chooseGroup(id);
    dialog = undefined;
  }

  function toggleGroup(id: string) {
    changeDiagram({ ...savedDiagram, groups: savedDiagram.groups.map((item) => item.id === id ? { ...item, collapsed: !item.collapsed } : item) });
    chooseGroup(id);
  }

  function disband() {
    changeDiagram({ ...savedDiagram, groups: removeGroup(groupSelected, savedDiagram.groups) });
    chooseGroup('');
  }

  function updateRoute(key: string, points: Point[], save: boolean) {
    const clamp = (value: number) => Math.max(-100_000, Math.min(100_000, value));
    points = points.map(({ x, y }) => ({ x: clamp(x), y: clamp(y) }));
    previewRoute = save ? undefined : { key, points };
    if (!save) return;
    const routes = { ...savedDiagram.routes };
    if (points.length) routes[key] = points;
    else delete routes[key];
    if (JSON.stringify(routes) === JSON.stringify(savedDiagram.routes)) return;
    changeDiagram({ ...savedDiagram, routes });
  }

  function addWaypoint() {
    if (!edge) return;
    if ((diagram.routes[selectedEdge]?.length ?? 0) >= 24) return;
    const from = topology.nodes.find((node) => node.id === edge?.source);
    const to = topology.nodes.find((node) => node.id === edge?.target);
    if (!from || !to) return;
    const a = diagram.positions[from.id] ?? from.position;
    const b = diagram.positions[to.id] ?? to.position;
    const points = diagram.routes[selectedEdge] ?? [];
    const entry = points.at(-1) ?? { x: a.x + (compact ? 156 : 167), y: a.y + (compact ? 43 : 50.5) };
    updateRoute(selectedEdge, [...points, { x: (entry.x + b.x) / 2, y: (entry.y + b.y + (compact ? 43 : 50.5)) / 2 }], true);
  }

  const viewingDraft = $derived(Boolean(game.draft) && !showProduction);
  const topology = $derived(viewingDraft ? game.draft! : game.production);
  const guideApi = $derived(tutorial ? tutorialApi(topology)?.id : undefined);
  const missingDraftApi = $derived(tutorial && viewingDraft && !guideApi && Boolean(tutorialApi(game.production)));
  const active = $derived(topology.nodes.find((node) => node.id === selected));
  const metric = $derived(game.snapshot.components[selected]);
  const liveInstances = $derived(Number(game.production.nodes.find((node) => node.id === selected)?.config.instances ?? catalog.components.api.fields.instances.default));
  const monitors = $derived(game.snapshot.monitors ?? {});
  const connections = $derived(topology.edges.filter((item) => item.source === selected || item.target === selected));
  const activeConfig = $derived(active && Object.fromEntries(Object.entries(catalog.components[active.kind].fields).map(([key, field]) => [key, active.config[key] ?? field.default])));
  const removed = $derived(viewingDraft ? game.production.nodes.filter((node) => !topology.nodes.some((item) => item.id === node.id)) : []);
  const visibleGroups = $derived(diagram.groups.filter((item) => groupComponents(item, diagram.groups)
    .some((id) => topology.nodes.some((node) => node.id === id))));
  const kinds = $derived((Object.keys(catalog.components) as Kind[]).filter((kind) => kind !== 'source'));
  const categories = ['Traffic', 'Compute', 'Data', 'Operations'];
  const edgeKey = (edge: Connection) => `${edge.source}:${edge.target}`;
  const visibleConnections = $derived.by(() => {
    const kinds = new Map(topology.nodes.map((node) => [node.id, node.kind]));
    return topology.edges.filter((edge) => !hiddenConnections.includes(connectionCategory(connectionKind(catalog, kinds.get(edge.source), kinds.get(edge.target)))));
  });
  const edge = $derived(topology.edges.find((item) => edgeKey(item) === selectedEdge));
  const origin = $derived(topology.nodes.find((node) => node.id === source));
  const targets = $derived(origin ? topology.nodes.filter((node) =>
    !connectionError(topology, catalog, { source: origin.id, target: node.id }, replacedEdge)) : []);
  const delta = $derived(Object.entries(game.draft_costs).reduce((sum, [, cost]) => sum + cost, 0) - game.economy.daily_infrastructure);
  const pendingChanges = $derived.by(() => {
    if (!viewingDraft) return [];
    const live = new Map(game.production.nodes.map((node) => [node.id, node]));
    const items: { label: string; note: string; tone: string }[] = [];
    for (const node of topology.nodes) {
      const before = live.get(node.id);
      if (!before) { items.push({ label: node.name, note: 'Component added', tone: 'good' }); continue; }
      const fields = catalog.components[node.kind].fields;
      const settings = Object.keys(fields).filter((key) => (before.config[key] ?? fields[key].default) !== (node.config[key] ?? fields[key].default));
      if (before.name !== node.name || settings.length) items.push({ label: node.name, note: settings.map((key) => t(fields[key].label)).join(', ') || 'Name changed', tone: 'warn' });
    }
    for (const node of removed) items.push({ label: node.name, note: 'Component removed', tone: 'bad' });
    const oldEdges = new Set(game.production.edges.map(edgeKey));
    const draftEdges = new Set(topology.edges.map(edgeKey));
    const connected = topology.edges.filter((edge) => !oldEdges.has(edgeKey(edge))).length;
    const disconnected = game.production.edges.filter((edge) => !draftEdges.has(edgeKey(edge))).length;
    if (connected) items.push({ label: 'Connections added', note: `${connected}`, tone: 'good' });
    if (disconnected) items.push({ label: 'Connections removed', note: `${disconnected}`, tone: 'bad' });
    return items;
  });
  const changeLabels: Record<string, string> = { added: 'Added', removed: 'Removed', modified: 'Modified', moved: 'Moved', connected: 'Connections added', disconnected: 'Connections removed' };
  const metrics = $derived(game.snapshot.metrics);
  const summary = $derived([
    { label: 'Active users', value: num(game.audience) },
    { label: 'Request rate', value: rps(metrics.rps) },
    { label: 'Average latency', value: ms(metrics.latency) },
    { label: 'Error rate', value: pct(metrics.errors / (metrics.rps || 1), 2) }
  ]);

  onMount(() => {
    inspectorWidth = inspectorPreference() ?? defaultInspectorWidth;
    try {
      const preferences = JSON.parse(localStorage.getItem(mapPreferenceKey) ?? 'null');
      if (Array.isArray(preferences?.hidden)) hiddenConnections = Object.keys(connectionStyles)
        .filter((category): category is ConnectionCategory => preferences.hidden.includes(category));
      alignment = preferences?.guides === true;
    } catch { /* Keep the default preferences if browser storage is unavailable. */ }
    if (focusId && topology.nodes.some((item) => item.id === focusId)) {
      select(focusId, false);
      if (openConfiguration) void configure();
      else dialog = 'inspector';
    }
    const query = matchMedia('(max-width: 850px)');
    const update = () => compact = query.matches;
    update();
    query.addEventListener('change', update);
    return () => {
      query.removeEventListener('change', update);
    };
  });

  $effect(() => {
    if (!editingDraft && localRevision >= 0 && game.revision !== localRevision) {
      history = [];
      future = [];
      localRevision = game.revision;
    }
  });

  $effect(() => {
    tutorialState({
      api: guideApi, selected, missingDraftApi, inspector: dialog === 'inspector', tab: inspectorTab, dialog, layout,
      hiddenNodes: diagram.groups.filter((group) => group.collapsed).flatMap((group) => groupComponents(group, diagram.groups)),
      viewingDraft, connectSource: source, connectTarget: target, changedConfig, reviewReady: Boolean(review), reviewPending: reviewing, hasForecast: Boolean(review?.forecast),
      reviewValid: Boolean(review && !review.errors.length && Object.values(review.changes).some((items) => items.length)),
      comparison: dialog === 'deployed' && Boolean(deployed?.comparison),
      collectorVisible: t(catalog.components.monitor.name).toLowerCase().includes(search.trim().toLowerCase())
    });
  });

  function selectTab(tab: typeof inspectorTab) {
    inspectorTab = tab;
    tutorialEvent(tab === 'metrics' ? 'metrics-opened' : 'configuration-opened');
  }

  function select(id: string, interaction = true) {
    if (selected !== id) inspectorTab = 'configuration';
    selected = id;
    if (touchSelect && guideApi && id === guideApi && tutorialSelect && interaction) touchSelect = false;
    if (touchSelect && id) selectMany(selection.includes(id) ? selection.filter((item) => item !== id) : [...selection, id]);
    else selection = id ? [id] : [];
    groupSelected = '';
    selectedEdge = '';
    cluster = false;
    context = undefined;
    if (interaction && guideApi && id === guideApi && !touchSelect) tutorialEvent('component-selected');
  }

  function inspectComponent(id: string) {
    if (touchSelect) return;
    select(id);
    inspectorTab = 'configuration';
    dialog = 'inspector';
  }

  function changeDialog(next?: typeof dialog) {
    if (drawer) drawer.dismiss(() => dialog = next);
    else dialog = next;
  }

  function selectEdge(id: string) {
    selectedEdge = id;
    groupSelected = '';
    selection = [];
    selected = '';
    context = undefined;
  }

  async function draft() {
    showProduction = false;
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
    lastEdit = 'topology';
    history = [...history, before].slice(-50);
    future = [];
    return true;
  }

  async function undo(redo = false) {
    const list = redo ? future : history;
    const item = list.at(-1);
    if (!item || !viewingDraft || !game.draft || busy) return;
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

  async function add(kind: Kind, name = catalog.components[kind].name, config: Component['config'] = {}) {
    const id = crypto.randomUUID();
    const position = placement?.place() ?? findPlacement(
      { x: 0, y: 0, width: 960, height: 580 }, { width: 167, height: 101 },
      topology.nodes.map((node) => ({ ...(savedDiagram.positions[node.id] ?? node.position), width: 167, height: 101 }))
    );
    if (await edit((value) => ({
      ...value, nodes: [...value.nodes, { id, kind, position, name, config }]
    }))) {
      saveDiagram({ ...savedDiagram, positions: { ...savedDiagram.positions, [id]: position } });
      select(id);
      if (dialog === 'catalog') changeDialog();
      await tick();
      placement?.reveal(position);
    }
  }

  function copyComponent(component: Component) {
    const suffixLength = t('{0} (copy)', ['']).length;
    const name = Array.from(t(component.name)).slice(0, 60 - suffixLength).join('').trimEnd();
    closeMenu(true);
    return add(component.kind, t('{0} (copy)', [name]), { ...component.config });
  }

  function openConnect() {
    editError = '';
    replacedEdge = edge ? edgeKey(edge) : '';
    source = edge?.source ?? (active && catalog.connections[active.kind].length ? active.id : 'traffic');
    target = edge?.target ?? '';
    changeDialog('connect');
  }

  async function connect(connection: Connection, replaces = '') {
    if (busy) return;
    const problem = connectionError(topology, catalog, connection, replaces);
    if (problem) { editError = problem; return; }
    if (await edit((value) => ({ ...value, edges: [...value.edges.filter((item) => edgeKey(item) !== replaces), connection] }))) {
      dialog = undefined;
      select(connection.target);
    }
  }

  async function remove() {
    if (busy || !viewingDraft) return;
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

  function move(positions: Record<string, Point>) {
    const changed: Record<string, Point> = {};
    const clamp = (value: number) => Math.max(-100_000, Math.min(100_000, value));
    for (const node of topology.nodes) {
      const point = positions[node.id];
      if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) continue;
      const next = { x: clamp(point.x), y: clamp(point.y) };
      const prior = savedDiagram.positions[node.id] ?? node.position;
      if (next.x !== prior.x || next.y !== prior.y) changed[node.id] = next;
    }
    if (Object.keys(changed).length) changeDiagram({ ...savedDiagram, positions: { ...savedDiagram.positions, ...changed } });
  }

  async function configure() {
    const from = dialog;
    if (active && active.kind !== 'source' && await draft()) {
      configurationReturn = from === 'inspector' ? from : undefined;
      editError = '';
      changedConfig = false;
      changeDialog('configuration');
    }
  }

  async function updateConfig(name: string, config: Record<string, Setting>) {
    if (await edit((value) => ({ ...value, nodes: value.nodes.map((node) => node.id === selected ? { ...node, name, config } : node) }))) {
      if (dialog === 'configuration') dialog = configurationReturn;
    } else editError = 'The server could not save this configuration. Check the values and retry.';
  }

  async function inspectReview() {
    if (!game.draft) return;
    const version = ++reviewVersion;
    dialog = 'review';
    review = undefined;
    reviewError = '';
    reviewing = true;
    try {
      const result = await api<Review>(`/${game.id}/draft/review`, 'POST', { revision: game.revision });
      if (version === reviewVersion) review = result;
    } catch (reason) {
      if (version === reviewVersion) reviewError = apiMessage(reason);
    } finally {
      if (version === reviewVersion) reviewing = false;
    }
  }

  async function finish(deploy: boolean) {
    const result = await act(deploy ? '/deployments' : '/draft/discard', { revision: review?.revision ?? game.revision });
    if (result) {
      deployed = deploy && !result.migration ? result.deployments[0] : undefined;
      dialog = deployed?.comparison ? 'deployed' : undefined;
      history = [];
      future = [];
      review = undefined;
    }
  }

  function closeMenu(restoreFocus = false) {
    const origin = context?.origin;
    context = undefined;
    if (restoreFocus) origin?.focus({ preventScroll: true });
  }

  async function openMenu(event: MouseEvent | KeyboardEvent, subject?: { kind: 'edge' | 'component'; id: string }) {
    event.preventDefault();
    if (subject?.kind === 'component') select(subject.id);
    if (subject?.kind === 'edge') selectEdge(subject.id);
    const origin = event.target instanceof Element ? event.target.closest<HTMLElement>('.svelte-flow__node-workbench') ?? undefined : undefined;
    const bounds = origin?.getBoundingClientRect();
    const point = 'clientX' in event ? { x: event.clientX, y: event.clientY }
      : { x: bounds?.left ?? 8, y: bounds?.bottom ?? 8 };
    const kind = subject?.kind ?? 'canvas';
    context = { ...point, kind, origin };
    await tick();
    if (!contextPanel || context?.kind !== kind) return;
    const { width, height } = contextPanel.getBoundingClientRect();
    context.x = Math.max(8, Math.min(point.x, innerWidth - width - 8));
    context.y = point.y + 10 + height <= innerHeight - 8
      ? point.y + 10 : Math.max(8, point.y - height - 10);
    contextPanel.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus({ preventScroll: true });
  }

  function shortcuts(event: KeyboardEvent) {
    if (dialog || event.defaultPrevented || (event.target instanceof HTMLElement && event.target.closest('input, select, textarea, [contenteditable]:not([contenteditable=false]), [role=combobox]'))) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && canvas?.contains(document.activeElement)) {
      event.preventDefault();
      selectMany(topology.nodes.filter((node) => !diagram.groups.some((item) => item.collapsed && groupComponents(item, diagram.groups).includes(node.id))).map((node) => node.id));
    }
    if ((event.ctrlKey || event.metaKey) && ['z', 'y'].includes(event.key.toLowerCase())) {
      event.preventDefault();
      const redo = event.shiftKey || event.key.toLowerCase() === 'y';
      if (lastEdit === 'diagram') undoDiagram(redo);
      else void undo(redo);
    }
    if (event.key === 'Delete' && viewingDraft) { event.preventDefault(); void remove(); }
    if (event.key === 'Escape') { if (context) closeMenu(true); else select(''); }
    if (event.key === 'Enter' && event.target instanceof HTMLElement) {
      const node = event.target.closest<HTMLElement>('.svelte-flow__node');
      if (node?.dataset.id) select(node.dataset.id);
    }
  }
</script>

<svelte:window onkeydown={shortcuts}
  onpointerdowncapture={(event) => { if (context && event.target instanceof Node && !contextPanel?.contains(event.target)) closeMenu(); }}
  onresize={() => closeMenu()} onscrollcapture={(event) => { if (event.target !== contextPanel) closeMenu(); }} />

{#snippet inspectorFooter()}
  <Button variant="ghost" disabled={inspectorWidth === defaultInspectorWidth} onclick={() => {
    inspectorWidth = defaultInspectorWidth;
    inspectorPreference(null);
  }}>{t('Reset width')}</Button>
{/snippet}

{#snippet catalogList()}
  <label class="search"><Search size={14} /><TextInput data-tutorial={guideTarget.catalogSearch} type="search" aria-label={t("Search components")} placeholder={t("Search nodes…")} bind:value={search} /></label>
  {#each categories as category}
    {@const matches = kinds.filter((kind) => catalog.components[kind].category === category && t(catalog.components[kind].name).toLowerCase().includes(search.trim().toLowerCase()))}
    {#if matches.length}
      <div class="catalog-group">
        <h3 class="eyebrow">{category === 'Data' ? t("Data & storage") : t(category)}</h3>
        {#each matches as kind}
          {@const Icon = componentIcon[kind]}
          <div class="catalog-row">
            <Button class="catalog-item" data-tutorial={kind === 'monitor' ? guideTarget.collector : undefined}
              disabled={busy || (kind === 'shard_router' && !canShard)} onclick={() => add(kind)}><Icon size={19} /><span>{t(catalog.components[kind].name)}</span></Button>
            <Tooltip label={t("About {0}", [t(catalog.components[kind].name)])}
              text={kind === 'shard_router' && !canShard ? t('Complete Database Sharding research before using a shard router.')
                : t("{0} Base cost {1} per day.", [t(catalog.components[kind].description), preciseMoney(catalog.components[kind].daily)])}
              onclick={() => { helpKind = kind; referenceReturn = 'catalog'; changeDialog('reference'); }} />
          </div>
        {/each}
      </div>
    {/if}
  {/each}
  {#if search && !kinds.some((kind) => t(catalog.components[kind].name).toLowerCase().includes(search.trim().toLowerCase()))}<p class="muted">{t("No matching components.")}</p>{/if}
{/snippet}

{#snippet connectionReference()}
  <div class="stack">
    <div class="field"><span>{t("Component type")}</span>
      <Select label={t("Component type")} value={helpKind} onchange={(value) => helpKind = value as Kind}
        options={Object.entries(catalog.components).map(([value, definition]) => ({ value, label: t(definition.name) }))} />
    </div>
    <p>{t(catalog.components[helpKind].description)}</p>
    <p>{preciseMoney(catalog.components[helpKind].daily)} {t("base daily cost")}</p>
    <ul>{#each componentNotes[helpKind] as note}<li>{t(note)}</li>{/each}</ul>
    <h3>{t("Input connections")}</h3>
    <ul>{#each (Object.keys(catalog.components) as Kind[]).filter((kind) => catalog.connections[kind].includes(helpKind)) as kind}
      <li>{t(catalog.components[kind].name)} · {t(connectionLabels[connectionKind(catalog, kind, helpKind)])}</li>
    {:else}<li>{t("None")}</li>{/each}</ul>
    <h3>{t("Output connections")}</h3>
    <ul>{#each catalog.connections[helpKind] as kind}
      <li>{t(catalog.components[kind].name)} · {t(connectionLabels[connectionKind(catalog, helpKind, kind)])}</li>
    {:else}<li>{t("None")}</li>{/each}</ul>
  </div>
{/snippet}

{#snippet resourceUsage()}
  {#if metric && Object.keys(metric.utilization).length}
    <section class="inspector-section stack">
      <h3>{t('Resource utilization')}</h3>
      <div class="resource-list">
        {#each Object.entries(metric.utilization).sort((a, b) => b[1] - a[1]).slice(0, inspectorTab === 'configuration' ? 2 : undefined) as [label, value] (label)}
          <div class="resource-meter" data-tutorial={inspectorTab === 'metrics' && active?.id === guideApi && label === 'CPU' ? guideTarget.cpu : undefined}>
            <Meter {value} label={t(label)} />
            {#if metric.database}
              <Tooltip label={t('Help with {0}', [t(label)])} text={t('Open the relevant guide article.')} href={guideArticleHref(guideHref, resourceArticle(label))} />
            {/if}
          </div>
        {/each}
      </div>
    </section>
  {/if}
{/snippet}

{#snippet inspect()}
  {#if active}
    {@const definition = catalog.components[active.kind]}
    {@const Icon = componentIcon[active.kind]}
    <div class="identity">
      <span class="component-symbol"><Icon size={22} /></span>
      <div>
        <p>{t(definition.name)}</p>
        <h2>{t(active.name)}</h2>
        <div class="row wrap identity-meta">
          {#if metric}
            <Badge tone={metric.status === 'failed' || metric.status === 'overloaded' ? 'danger' : metric.status === 'warning' ? 'warning' : metric.status === 'healthy' ? 'success' : 'neutral'}>{t(statusLabel[metric.status])}</Badge>
          {/if}
          <a class="inspector-help" href={guideArticleHref(guideHref, active.kind)}>{t('Component guide')}</a>
        </div>
      </div>
    </div>
      <div class="switch" data-tutorial-obstruction="top" role="group" aria-label={t("Inspector view")}>
        <Button variant="ghost" data-tutorial={active.id === guideApi ? guideTarget.configuration : undefined} aria-pressed={inspectorTab === 'configuration'} onclick={() => selectTab('configuration')}>{t("Configuration")}</Button>
        <Button variant="ghost" data-tutorial={active.id === guideApi ? guideTarget.metrics : undefined} aria-pressed={inspectorTab === 'metrics'} onclick={() => selectTab('metrics')}>{t("Metrics")}</Button>
      </div>
      {#if metric?.status === 'failed'}
        {@const incident = game.incidents.find((item) => item.active && item.target === active?.id)}
        <Button variant="danger" href={guideHref.replace('view=guide', 'view=events') + (incident ? `&event=${encodeURIComponent(incident.id)}` : '')}>{t('View incident history')}</Button>
      {/if}
      {#if active.kind === 'api'}
        {@const dataLinks = topology.nodes.filter((node) => ['database', 'shard_router'].includes(node.kind) && topology.edges.some((edge) => edge.source === active?.id && edge.target === node.id))}
        <p class="muted">{dataLinks.length
          ? t(dataLinks.some((node) => node.kind === 'shard_router') ? 'Data connections: {0}' : 'Primary database: {0}', [dataLinks.map((node) => t(node.name)).join(', ')])
          : t('Connect this API to a primary database or a shard router.')}</p>
        {#if metric?.active_instances != null && metric.active_instances < liveInstances}
          <Alert tone="warning" title={t('{0} of {1} instances are serving.', [metric.active_instances, liveInstances])}>
            <a class="inspector-help" href={guideHref.replace('view=guide', 'view=events')}>{t('View incident history')}</a>
          </Alert>
        {/if}
      {/if}
      {#if active.kind === 'replica'}
        {@const primary = topology.nodes.find((node) => node.kind === 'database' && topology.edges.some((edge) => edge.source === active?.id && edge.target === node.id))}
        <div class="notice stack">
          <strong>{primary ? t('Primary database: {0}', [t(primary.name)]) : t('Connect this replica to a primary database.')}</strong>
          <small>{t('This replica serves ordinary reads from APIs or caches that use its primary. Writes and indexed search go to the primary.')}</small>
          <small>{t('Replication health: {0}', [t(!primary ? 'Disconnected' : !metric ? 'Metrics unavailable' : metric.database?.replication_backlog ? 'Lagging' : metric.replication_lag == null ? 'Metrics unavailable' : 'Healthy')])}</small>
        </div>
      {/if}
      {#if inspectorTab === 'configuration'}
        {#if active.kind === 'api' && activeConfig}
          <div class="stack" data-tutorial={active.id === guideApi ? guideTarget.capacity : undefined}>
            <div><p class="eyebrow">{t("Instance size")}</p><Button block class="instance" disabled={busy} onclick={configure}>{activeConfig.cpu} {t("vCPU /")} {activeConfig.memory} {t("GB")} <ChevronRight size={15} /></Button></div>
            <p class="muted">{t('Instances share the node settings and connections. Separate nodes have their own routing and dependencies.')}</p>
            <p class="mono">{t('Aggregate resources: {0} vCPU · {1} GB', [num(Number(activeConfig.cpu) * Number(activeConfig.instances)), num(Number(activeConfig.memory) * Number(activeConfig.instances))])}</p>
            <div class="row spread"><span class="eyebrow">{t("Replicas")}</span>
              <div class="row counter">
                <Button iconOnly aria-label={t("Remove replica")} disabled={busy || Number(activeConfig.instances) <= 1} onclick={() => active && updateConfig(active.name, { ...active.config, instances: Number(activeConfig?.instances) - 1 })}><Minus size={14} /></Button>
                <strong>{activeConfig.instances}</strong>
                <Button iconOnly class="accent" aria-label={t("Add replica")} disabled={busy || Number(activeConfig.instances) >= 24} onclick={() => active && updateConfig(active.name, { ...active.config, instances: Number(activeConfig?.instances) + 1 })}><Plus size={14} /></Button>
              </div>
            </div>
          </div>
        {:else}<p class="muted">{t(definition.description)}</p>{/if}
      {:else if metric}
        {@const background = active.kind === 'queue' || active.kind === 'worker'}
        <dl class="metric-overview" data-tutorial={active.id === guideApi ? guideTarget.throughput : undefined}>
          <div><dt>{t("Incoming")}</dt><dd>{background ? t('{0} jobs/s', [num(metric.rps)]) : rps(metric.rps)}</dd></div>
          <div><dt>{t(active.kind === 'queue' ? 'Accepted jobs' : 'Processed')}</dt><dd>{background ? t('{0} jobs/s', [num(metric.throughput)]) : rps(metric.throughput)}</dd></div>
          {#if !background}<div><dt>{t("Local latency")}</dt><dd>{ms(metric.latency)}</dd></div>{/if}
        </dl>
        {@render resourceUsage()}
        <section class="inspector-section stack">
          <h3>{t('Detailed metrics')}</h3>
          <dl class="metric-details">
            {#if metric.database}
              {@const data = metric.database}
              <div><dt>{t('Read demand')}</dt><dd>{t('{0} units/s', [num(data.read_demand)])}</dd></div>
              {#if data.disk_read_iops != null && data.disk_write_iops != null && data.disk_capacity_iops != null}
                <div><dt>{t('Modeled read IOPS')}</dt><dd>{num(data.disk_read_iops)}</dd></div>
                <div><dt>{t('Modeled write IOPS')}</dt><dd>{num(data.disk_write_iops)}</dd></div>
                <div><dt>{t('Modeled IOPS demand / capacity')}</dt><dd>{num(data.disk_read_iops + data.disk_write_iops)} / {num(data.disk_capacity_iops)}</dd></div>
              {/if}
              {#if data.write_capacity !== null}
                <div><dt>{t('Write demand')}</dt><dd>{t('{0} units/s', [num(data.write_demand)])}</dd></div>
                <div><dt>{t('Sustainable writes at current read load')}</dt><dd>{t('{0} units/s', [num(data.write_capacity)])}</dd></div>
              {:else}
                <div><dt>{t('Replication replay demand')}</dt><dd>{t('{0} units/s', [num(data.replication_demand)])}</dd></div>
                <div><dt>{t('Replication replay throughput')}</dt><dd>{t('{0} units/s', [num(data.replication_throughput)])}</dd></div>
                {#if data.replication_backlog > 0}
                  <div><dt>{t('Pending replication work')}</dt><dd>{t('{0} units', [num(data.replication_backlog)])}</dd></div>
                  {#if metric.replication_lag == null}<div><dt>{t('Replication lag')}</dt><dd>{t('Replay stalled')}</dd></div>{/if}
                {/if}
              {/if}
            {/if}
            {#if metric.cache_hit != null}<div><dt>{t("Cache hit rate")}</dt><dd>{pct(metric.cache_hit, 1)}</dd></div>{/if}
            {#if metric.backlog != null}<div><dt>{t("Queued jobs")}</dt><dd>{num(metric.backlog)}</dd></div>{/if}
            {#if metric.queue_wait_minutes != null}<div><dt>{t('Estimated wait to start')}</dt><dd>{t('{0} min', [num(metric.queue_wait_minutes)])}</dd></div>
            {:else if metric.backlog}<div><dt>{t('Estimated wait to start')}</dt><dd>{t('No active processing capacity')}</dd></div>{/if}
            {#if metric.jobs_dropped != null}<div><dt>{t('Rejected jobs per step')}</dt><dd>{num(metric.jobs_dropped)}</dd></div>{/if}
            {#if metric.jobs_expired != null}<div><dt>{t('Expired jobs per step')}</dt><dd>{num(metric.jobs_expired)}</dd></div>{/if}
            {#if metric.storage_used != null}<div><dt>{t("Storage used")}</dt><dd>{num(metric.storage_used)} {t("GB")}</dd></div>{/if}
            {#if metric.replication_lag != null}<div><dt>{t("Replication lag")}</dt><dd>{t('{0} s', [num(metric.replication_lag)])}</dd></div>{/if}
            {#if metric.service_errors != null}<div><dt>{t('Service errors')}</dt><dd>{rps(metric.service_errors)}</dd></div>{/if}
            {#if metric.service_latency != null}<div><dt>{t('Service latency')}</dt><dd>{ms(metric.service_latency)}</dd></div>{/if}
            {#if metric.service_role}<div><dt>{t('API service role')}</dt><dd>{t(metric.service_role)}</dd></div>{/if}
            {#if metric.data_domain}<div><dt>{t('Data domain')}</dt><dd>{t(metric.data_domain)}</dd></div>{/if}
            {#if metric.partition_share != null}<div><dt>{t('Partition traffic share')}</dt><dd>{pct(metric.partition_share, 1)}</dd></div>{/if}
            {#if metric.autoscaling}<div><dt>{t('Autoscaling')}</dt><dd>{t(metric.autoscaling)}</dd></div>{/if}
            {#each Object.entries(metric.operations ?? {}) as [op, rate]}<div><dt>{t(catalog.operations[op] ?? op)}</dt><dd>{rps(rate)}</dd></div>{/each}
            {#if metric.active_instances != null}<div><dt>{t("Active instances")}</dt><dd>{metric.active_instances}</dd></div>{/if}
          </dl>
        </section>
      {/if}
      {#if !metric && (active.kind === 'database' || active.kind === 'replica') &&
        game.production.nodes.some((node) => node.id === selected) && metrics.errors > 0}
        <p class="muted">{t('{0} requests per second are failing across the service.', [num(metrics.errors)])}</p>
      {/if}
      {#if active.kind === 'source'}
        <section class="inspector-section stack">
          <h3>{t('Request types')}</h3>
          <dl class="metric-details">
            {#each Object.entries(game.snapshot.demand) as [key, value] (key)}
              <div><dt>{t(catalog.operations[key] ?? key)}</dt><dd>{rps(value)}</dd></div>
            {/each}
          </dl>
        </section>
      {:else if metric}
        {#if inspectorTab === 'configuration'}{@render resourceUsage()}{/if}
      {:else if active.kind === 'monitor'}
        {@const coverage = monitors[active.id]}
        {#if coverage}
          <p class="notice" class:warn={coverage.dropped.length > 0}>
            {coverage.covered.length} / {coverage.capacity - (coverage.history ? 2 : 0)} {t("collection slots in use.")}
            {#if coverage.dropped.length} {t("Increase slots or add a collector for uncovered links.")} {/if}
          </p>
        {:else}<p class="muted">{t("Deploy the collector to start receiving metrics.")}</p>{/if}
      {:else if !game.production.nodes.some((node) => node.id === active?.id)}
        <p class="notice muted">{t("Deploy this component to start collecting metrics.")}</p>
      {:else if Object.values(monitors).some((monitor) => monitor.dropped.includes(selected))}
        <p class="notice warn" data-tutorial={active.id === guideApi ? guideTarget.missingMetrics : undefined}>{t("The collector has no free slots for this component. Increase slots or add another collector.")}</p>
      {:else}
        <p class="notice muted" data-tutorial={active.id === guideApi ? guideTarget.missingMetrics : undefined}>{t('Component metrics require a linked Monitoring collector.')}
          <a class="accent" href={guideArticleHref(guideHref, 'monitoring-setup')}>{t('Monitoring setup')}</a></p>
      {/if}
      {#if connections.length}
        <div class="inspector-section stack"><h3>{t("Dependencies")}</h3>
          {#each connections as item (edgeKey(item))}
            {@const peer = topology.nodes.find((node) => node.id === (item.source === selected ? item.target : item.source))}
            {@const rate = game.snapshot.traffic.find((traffic) => edgeKey(traffic) === edgeKey(item))?.rps}
            {#if peer}
              <Button class="dependency" onclick={() => select(peer.id)}>
                <span class="row">{#if item.source === selected}<ArrowRight size={13} />{:else}<ArrowLeft size={13} />{/if} {t(peer.name)}</span>
                <small>{t(connectionLabels[connectionKind(catalog, topology.nodes.find((node) => node.id === item.source)?.kind, topology.nodes.find((node) => node.id === item.target)?.kind)])}{rate === undefined ? '' : ` · ${rps(rate)}`}</small>
              </Button>
            {/if}
          {/each}
        </div>
      {/if}
      <div class="row spread cost"><span class="eyebrow">{t("Daily cost")}</span><strong>{preciseMoney((viewingDraft ? game.draft_costs : game.component_costs)[active.id] ?? 0)}</strong></div>
      {#if active.kind !== 'source'}<Button variant="primary" block class="large" data-tutorial={active.id === guideApi ? guideTarget.edit : undefined} disabled={busy} onclick={configure}>{t("Edit configuration")} <ArrowRight size={15} /></Button>{/if}
      {#if Number(activeConfig?.instances) > 1}<Button block aria-pressed={cluster} onclick={() => { cluster = !cluster; changeDialog(); }}>{cluster ? t("Collapse instances") : t("Expand instances")}</Button>{/if}
      {#if viewingDraft}
        <div class="row wrap"><Button onclick={openConnect} disabled={busy || !catalog.connections[active.kind].length}>{t("Connect component")}</Button>
        {#if active.kind !== 'source'}<Button variant="danger" disabled={busy} onclick={remove}><Trash2 size={13} /> {t("Remove")}</Button>{/if}</div>
      {/if}
  {:else if group}
    <div class="stack">
      <h2>{group.name}</h2>
      <p>{count(groupComponents(group, diagram.groups).filter((id) => topology.nodes.some((node) => node.id === id)).length,
        'component', 'components', ['компонент', 'компонента', 'компонентов'])}</p>
      <Button onclick={() => toggleGroup(group.id)}>{group.collapsed ? t("Expand group") : t("Collapse group")}</Button>
      <Button onclick={() => groupDialog(true)}>{t("Edit group")}</Button>
      <Button onclick={disband}>{t("Ungroup")}</Button>
    </div>
  {:else if edge}
    {@const from = topology.nodes.find((node) => node.id === edge?.source)}
    {@const to = topology.nodes.find((node) => node.id === edge?.target)}
    {@const kind = connectionKind(catalog, from?.kind, to?.kind)}
    <div class="stack"><h2>{t("Connection")}</h2><p>{t(from?.name ?? '')} → {t(to?.name ?? '')}</p>
    <p class="muted">{t(connectionLabels[kind])}</p>
    {#if kind === 'cache'}<p>{t("Keep a direct API connection to the primary database or shard router for writes.")}</p>
    {:else if kind === 'telemetry'}<p>{t("This link sends metrics to the collector and uses one collection slot.")}</p>
    {:else if kind === 'replication'}<p>{t("The read replica subscribes to its primary using this link.")}</p>{/if}
    <div class="row wrap">
      <Button disabled={layout !== 'canvas' || (diagram.routes[selectedEdge]?.length ?? 0) >= 24} onclick={addWaypoint}>{t("Add waypoint")}</Button>
      {#if diagram.routes[selectedEdge]?.length}
        <Button onclick={() => updateRoute(selectedEdge, [], true)}>{t("Reset route")}</Button>
        {#if compact}
          <Button onclick={() => updateRoute(selectedEdge, diagram.routes[selectedEdge].slice(0, -1), true)}>{t('Remove last waypoint')}</Button>
        {/if}
      {/if}
      <Button disabled={busy} onclick={openConnect}>{t("Reconnect")}</Button>
      <Button variant="danger" disabled={busy} onclick={remove}>{t("Remove connection")}</Button>
    </div>
    </div>
  {:else if selection.length > 1}
    <p class="muted">{t('{0} components selected', [num(selection.length)])}</p>
  {:else}<p class="muted">{t("Select a component or connection to inspect it.")}</p>{/if}
{/snippet}

<section class="architecture">
  <header class="topology-header">
    <div><p class="eyebrow">{t("Production /")} {game.name}</p><h1><span class="desktop-heading">{t("Infrastructure topology")}</span><span class="mobile-heading">{t("Topology")}</span></h1><p class="mobile-sub muted">{viewingDraft ? t("Draft") : t("Production")} · {count(topology.nodes.length, 'component', 'components', ['компонент', 'компонента', 'компонентов'])}</p></div>
    <div class="service-metrics">
      {#each summary as item}<div><span class="eyebrow">{t(item.label)}</span><strong>{item.value}</strong></div>{/each}
    </div>
  </header>
  <div class="workspace">
    <div class="drawing">
      <div class="canvas-bar row spread wrap" data-tutorial={guideTarget.canvasTools} class:editing={viewingDraft}>
        <div class="row wrap">
          <Badge tone="success"><i class="dot"></i>{viewingDraft ? t("Editing draft / {0} changes", [pendingChanges.length]) : t("Production")}</Badge>
        </div>
        <div class="row wrap">
          {#if layoutFailed}<Button variant="danger" onclick={retryDiagram}>{t("Retry saving layout")}</Button>{/if}
          <Button aria-pressed={touchSelect} onclick={() => touchSelect = !touchSelect}>{t("Select multiple")}</Button>
          {#if selection.length > 1}<Button onclick={() => { groupSelected = ''; groupDialog(false); }}>{t("Create group")}</Button>{/if}
          {#if layout === 'canvas'}
            <Button iconOnly aria-label={t('Fit view')} title={t('Fit view')} disabled={!placement} onclick={() => placement?.fit()}><Scan size={16} /></Button>
          {/if}
          <Button data-tutorial={guideTarget.add} disabled={busy} onclick={() => { search = ''; dialog = 'catalog'; }}><Plus size={14} /> {t("Add node")}</Button>
          <Button data-tutorial={active?.id === guideApi ? guideTarget.openInspector : undefined}
            disabled={!active && !edge && !group && selection.length < 2} onclick={() => dialog = 'inspector'}>
            {active ? t('Open component') : t('Inspect selection')}
          </Button>
          <Button aria-label={t('Map settings')} onclick={() => { helpKind = active?.kind ?? 'api'; dialog = 'map-settings'; }}>
            <SlidersHorizontal size={16} /> {t('Map settings')}
          </Button>
        </div>
      </div>
      {#if layout === 'canvas'}
        <div class="canvas" data-tutorial={guideTarget.canvas} bind:this={canvas}>
          {#if canvas}
          {#key compact}
            <TopologyGraph {guideApi} {tutorialLink} {topology} {diagram} {game} {catalog} {requestType} {hiddenConnections} {alignment} {selected} {selection} {groupSelected} edgeSelected={selectedEdge} editable={viewingDraft}
              {compact} {removed} {touchSelect} {select} inspect={inspectComponent} {selectEdge} selectGroup={chooseGroup} {selectMany} {connect} {move} {toggleGroup} {updateRoute}
              {cluster} container={canvas} {bindPlacement} {saveViewport} menu={openMenu} clear={() => select('')} />
          {/key}
          {/if}
          <p class="canvas-hint mono">{compact ? t("Pinch to zoom · Drag to pan") : t("Scroll to pan · Ctrl + wheel to zoom")}</p>
        </div>
      {:else}
        <div class="component-list stack">
          {#each visibleGroups as item (item.id)}
            <Button aria-pressed={groupSelected === item.id} onclick={() => chooseGroup(item.id)}>
              {item.name} <span class="muted">{item.collapsed ? t('Collapsed') : t('Expanded')}</span>
            </Button>
          {/each}
          {#each [...topology.nodes, ...removed] as node (node.id)}
            {@const Icon = componentIcon[node.kind]}
            <Button class="row spread" data-tutorial={node.id === guideApi ? guideTarget.api : undefined} aria-pressed={selection.includes(node.id)} disabled={removed.includes(node)} onclick={() => select(node.id)} ondblclick={() => inspectComponent(node.id)}>
              <span class="row"><Icon size={17} /> {t(node.name)}</span><span class="muted">{removed.includes(node) ? t("Pending removal") : t(catalog.components[node.kind].name)}</span>
            </Button>
          {/each}
          {#if visibleConnections.length}<p class="eyebrow">{t("Connections")}</p>{/if}
          {#each visibleConnections as item (edgeKey(item))}
            <Button aria-pressed={selectedEdge === edgeKey(item)} onclick={() => selectEdge(edgeKey(item))}>{t(topology.nodes.find((n) => n.id === item.source)?.name ?? '')} → {t(topology.nodes.find((n) => n.id === item.target)?.name ?? '')}</Button>
          {/each}
        </div>
      {/if}
      <div class="edit-bar row wrap">
        {#if viewingDraft}
          <Button data-tutorial={guideTarget.viewProduction} onclick={() => showProduction = true}>{t('View production')}</Button>
          <Button iconOnly aria-label={t("Undo draft edit")} title={t("Undo")} disabled={busy || !history.length} onclick={() => undo()}><Undo2 size={16} /></Button>
          <Button iconOnly aria-label={t("Redo draft edit")} title={t("Redo")} disabled={busy || !future.length} onclick={() => undo(true)}><Redo2 size={16} /></Button>
          <Button data-tutorial={guideTarget.connect} disabled={busy} onclick={openConnect}>{t("Connect")}</Button>
          <Button disabled={busy} onclick={() => { review = undefined; dialog = 'discard'; }}>{t("Discard")}</Button>
          <Button variant="primary" data-tutorial={guideTarget.review} disabled={busy} onclick={inspectReview}>{t("Review deployment")} <ArrowRight size={14} /></Button>
        {:else if game.draft}<Button data-tutorial={guideTarget.returnDraft} onclick={() => showProduction = false}>{t('Return to draft')}</Button>
        {:else}<Button data-tutorial={guideTarget.createDraft} disabled={busy} onclick={draft}><GitBranch size={15} /> {t("Create draft")}</Button>{/if}
      </div>
    </div>
  </div>
</section>

{#if context}
  <div class="context panel stack" role="group" aria-label={t(context.kind === 'component' ? 'Component actions' : context.kind === 'edge' ? 'Connection actions' : 'Canvas actions')}
    bind:this={contextPanel} style:left={`${context.x}px`} style:top={`${context.y}px`}>
    {#if context.kind === 'component' && active}
      {@const component = active}
      <Button onclick={() => { closeMenu(true); inspectComponent(component.id); }}><Info size={14} />{t('Component info')}</Button>
      {#if component.kind !== 'source'}
        <Button disabled={busy} onclick={() => copyComponent(component)}><Copy size={14} />{t('Copy component')}</Button>
        <Button disabled={busy} onclick={() => { closeMenu(true); void configure(); }}><SlidersHorizontal size={14} />{t('Edit configuration')}</Button>
        {#if viewingDraft}<Button variant="danger" disabled={busy} onclick={() => { closeMenu(true); void remove(); }}><Trash2 size={14} />{t('Remove selected')}</Button>{/if}
      {/if}
    {:else if context.kind === 'edge' && edge}
      <Button onclick={() => { addWaypoint(); context = undefined; }}>{t("Add waypoint")}</Button>
      {#if diagram.routes[selectedEdge]?.length}<Button onclick={() => { updateRoute(selectedEdge, [], true); context = undefined; }}>{t("Reset route")}</Button>{/if}
      {#if viewingDraft}<Button variant="danger" disabled={busy} onclick={() => { closeMenu(); void remove(); }}>{t("Remove selected")}</Button>{/if}
    {:else if context.kind === 'canvas'}
      <Button disabled={busy} onclick={() => { search = ''; dialog = 'catalog'; closeMenu(); }}><Plus size={14} />{t("Add node")}</Button>
    {/if}
    <Button variant="ghost" onclick={() => closeMenu(true)}><X size={14} /> {t("Close menu")}</Button>
  </div>
{/if}

{#if dialog === 'deployed' && deployed?.comparison}
  <Modal title={t("Deployment complete")} close={() => dialog = undefined}>
    <div data-tutorial={guideTarget.compare}><DeploymentComparison comparison={deployed.comparison} /></div>
    {#snippet footer()}<Button variant="primary" data-tutorial={guideTarget.done} onclick={() => dialog = undefined}>{t("Done")}</Button>{/snippet}
  </Modal>
{:else if dialog === 'map-settings'}
  <Modal bind:this={drawer} title={t('Map settings')} side="end" close={() => dialog = undefined}>
    <div class="map-settings stack">
      <section class="stack">
        <h3>{t('Map view')}</h3>
        <Button block data-tutorial={guideTarget.list} onclick={() => { layout = layout === 'canvas' ? 'list' : 'canvas'; changeDialog(); }}>
          {#if layout === 'canvas'}<List size={16} />{t('Show component list')}{:else}<MousePointer2 size={16} />{t('Show topology canvas')}{/if}
        </Button>
        <Switch label={t('Alignment guides')} checked={alignment}
          onchange={({ currentTarget }) => setMapPreferences(hiddenConnections, currentTarget.checked)} />
        <small>{t('Snap cards to the edges and centers of nearby components while dragging.')}</small>
      </section>
      <section class="stack">
        <h3>{t('Visible connections')}</h3>
        <ul class="edge-legend" aria-label={t('Connection types')}>
          {#each Object.entries(connectionStyles) as [category, style] (category)}
            <li class:dashed={style.dashed} style:--edge-color={style.color}>
              <Switch label={t(style.label)} checked={!hiddenConnections.includes(category as ConnectionCategory)}
                onchange={({ currentTarget }) => toggleConnection(category as ConnectionCategory, currentTarget.checked)} />
            </li>
          {/each}
        </ul>
        <div class="field">
          <span>{t('Trace request type')}</span>
          <Select label={t('Trace request type')} bind:value={requestType}
            options={[{ value: '', label: t('All traffic') }, ...Object.keys(game.snapshot.demand).map((operation) => ({ value: operation, label: t(catalog.operations[operation]) }))]} />
        </div>
      </section>
      <Disclosure label={t('Connection reference')} variant="panel">
        {@render connectionReference()}
      </Disclosure>
      <Button href={guideArticleHref(guideHref, 'topology-editing')}>{t('Topology guide')}</Button>
    </div>
  </Modal>
{:else if dialog === 'reference'}
  <Modal title={t("Connection reference")} close={() => dialog = referenceReturn}>
    {@render connectionReference()}
  </Modal>
{:else if dialog === 'group'}
  <Modal title={group ? t("Edit group") : t("Create group")} close={() => dialog = undefined}>
    <Form id="diagram-group" class="stack" onsubmit={(event) => { event.preventDefault(); saveGroup(); }}>
      <label class="field"><span>{t("Group name")}</span><TextInput bind:value={groupName} maxlength={60} required /></label>
      {#if diagram.groups.length > (group ? 1 : 0)}
        <div class="field"><span>{t('Parent group')}</span><Select label={t('Parent group')} bind:value={groupParent}
          options={[{ value: '', label: t('None') }, ...diagram.groups.filter((item) => item.id !== group?.id && !(group && nestedGroups(group, diagram.groups).has(item.id))).map((item) => ({ value: item.id, label: item.name }))]} /></div>
      {/if}
      <fieldset class="stack"><legend>{t("Components")}</legend>
        {#each topology.nodes as node (node.id)}
          <Checkbox label={t(node.name)} checked={groupMembers.includes(node.id)} onchange={({ currentTarget }) => groupMembers = currentTarget.checked ? [...groupMembers, node.id] : groupMembers.filter((id) => id !== node.id)} />
        {/each}
      </fieldset>
    </Form>
    {#snippet footer()}<Button variant="primary" form="diagram-group" type="submit" disabled={!groupMembers.length}>{t("Save group")}</Button>{/snippet}
  </Modal>
{:else if dialog === 'catalog'}
  <Modal bind:this={drawer} title={t("Component library")} side="start" subtitle={t("Add a component to the architecture draft.")} close={() => dialog = undefined}>
    {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    {@render catalogList()}
  </Modal>
{:else if dialog === 'inspector'}
  <Modal bind:this={drawer} title={t("Component inspector")} side="end" width={inspectorWidth} resize={saveInspectorWidth} footer={compact ? undefined : inspectorFooter} close={() => dialog = undefined}>
    <div class="stack">
      {@render inspect()}
      {#if viewingDraft}
        <section class="draft-summary stack">
          <div><p class="eyebrow accent">{t("Draft summary")}</p><h2>{pendingChanges.length} {t("pending changes")}</h2></div>
          {#each pendingChanges.slice(0, 3) as item}
            <div class="panel draft-item"><strong class={item.tone === 'good' ? 'accent' : item.tone === 'bad' ? 'danger' : item.tone === 'warn' ? 'warning' : ''}>{t(item.label)}</strong><small>{t(item.note)}</small></div>
          {/each}
          {#if pendingChanges.length > 3}<small>+{pendingChanges.length - 3} {t("more in review")}</small>{/if}
          <div class="row spread"><span class="eyebrow">{t("Daily cost change")}</span><strong>{delta >= 0 ? '+' : ''}{preciseMoney(delta)}</strong></div>
        </section>
      {/if}
    </div>
  </Modal>
{:else if dialog === 'configuration' && active}
  <Configuration serviceRoles={catalog.service_roles} operationNames={catalog.operations} workloads={game.snapshot.demand} engineering={game.engineering} component={active} daily={(viewingDraft ? game.draft_costs : game.component_costs)[active.id] ?? 0} storage={catalog.database_storage} {guideHref} definition={catalog.components[active.kind]} {busy} error={error || editError}
    close={() => dialog = configurationReturn} apply={updateConfig} onEdited={(changed) => changedConfig = changed}
    preview={(name, config) => api<Review>(`/${game.id}/draft/review`, 'POST', { revision: game.revision, topology:
      { ...topology, nodes: topology.nodes.map((node) => node.id === selected ? { ...node, name, config } : node) } })} />
{:else if dialog === 'connect'}
  <Modal title={replacedEdge ? t("Reconnect components") : t("Connect components")} close={() => { dialog = undefined; editError = ''; }}>
    <Form id="connect-components" class="stack" onsubmit={(event) => { event.preventDefault(); if (target) void connect({ source, target }, replacedEdge); }}>
      {#if error || editError}<p class="notice error" role="alert">{message(error || editError)}</p>{/if}
      <div class="field"><span>{t("Source component")}</span><Select data-tutorial={guideTarget.source} label={t("Source component")}
        bind:value={source} onchange={() => target = ''} searchable
        options={topology.nodes.filter((node) => catalog.connections[node.kind].length).map((node) => ({ value: node.id, label: t(node.name) }))} /></div>
      <div class="field"><span>{t("Target component")}</span><Select data-tutorial={guideTarget.destination} label={t("Target component")}
        bind:value={target} searchable options={targets.map((node) => ({ value: node.id, label: t(node.name) }))} /></div>
      {#if target}
        {@const kind = connectionKind(catalog, origin?.kind, targets.find((node) => node.id === target)?.kind)}
        <p class="muted">{t(connectionLabels[kind])}</p>
        {#if kind === 'cache'}<p>{t("Keep a direct API-to-primary connection for writes. Add API-to-cache for read lookups.")}</p>{/if}
      {/if}
      {#if !targets.length}<p class="muted">{t("There are no new compatible connections from this component.")}</p>{/if}
    </Form>
    {#snippet footer()}<Button variant="primary" block type="submit" form="connect-components" data-tutorial={guideTarget.saveLink} disabled={busy || !target}>{t("Connect components")}</Button>{/snippet}
  </Modal>
{:else if dialog === 'discard'}
  <Modal title={t("Discard draft")} close={() => dialog = undefined}>
    <p>{t("Remove all edits in the current draft?")}</p>
    {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    {#snippet footer()}<div class="row spread"><Button onclick={() => dialog = undefined}>{t("Cancel")}</Button><Button variant="danger" disabled={busy} onclick={() => finish(false)}>{t("Discard draft")}</Button></div>{/snippet}
  </Modal>
{:else if dialog === 'review'}
  <Modal title={t("Deployment review")} subtitle={t("Validate the draft and check its impact before deploying.")} wide close={() => dialog = undefined}>
    <div class="stack">
      {#if reviewing}<p aria-live="polite">{t("Checking topology…")}</p>{/if}
      {#if error || reviewError}<p class="notice error" role="alert">{message(error || reviewError)}</p>{/if}
      {#if review}
        {@const dailyChange = review.daily_after - review.daily_before}
        {#each review.errors as issue}<p class="notice error" role="alert">{message(issue)}</p>{/each}
        <div class="panel inset pad stack" data-tutorial={guideTarget.forecast}>
          <h3>{t("Change summary")}</h3>
          {#each Object.entries(review.changes) as [key, changes]}
            {#if changes.length && key !== 'modified'}
              <div class="review-item"><p class="eyebrow">{t(changeLabels[key])} · {changes.length}</p><p>{changes.map((name) => name.split(' → ').map((part) => t(part)).join(' → ')).join(', ')}</p></div>
            {/if}
          {/each}
          {#each review.details as item}
            <div class="review-item"><p class="eyebrow">{t(item.component)} / {t(item.field)}</p><p class="mono">{t(String(item.before))} → {t(String(item.after))}</p></div>
          {/each}
          {#if !Object.values(review.changes).some((items) => items.length)}<p class="muted">{t("No changes to deploy.")}</p>{/if}
          <div class="row spread wrap"><span>{t("Daily infrastructure")}</span><strong>{preciseMoney(review.daily_before)} → {preciseMoney(review.daily_after)} ({dailyChange > 0 ? '+' : ''}{preciseMoney(dailyChange)})</strong></div>
          <div class="row spread"><span>{t("One-time deployment cost")}</span><strong>{preciseMoney(review.install)}</strong></div>
        </div>
        {#if review.migration_ticks}<p class="notice warn">{t('Migration preparation: {0} ticks. Included transfer cost: {1}. Production stays live until completion.', [review.migration_ticks, preciseMoney(review.migration_cost ?? 0)])} <a href={guideArticleHref(guideHref, 'architecture-migration')}>{t('Architecture Migration')}</a></p>{/if}
      {#each review.warnings as warning}<p class="notice warn">{message(warning)}</p>{/each}
        {#if review.forecast}
          <div data-tutorial={guideTarget.capacityForecast}><Forecast forecast={review.forecast} /></div>
          {#each Object.entries(review.forecast.databases ?? {}) as [id, database] (id)}
            <DatabaseForecast {database} {guideHref} name={topology.nodes.find((node) => node.id === id)?.name} />
          {/each}
        {/if}
      {/if}
    </div>
    {#snippet footer()}
      <div class="row spread wrap"><Button onclick={() => dialog = undefined}>{t("Back to draft")}</Button>
        <Button variant="primary" data-tutorial={guideTarget.deploy} disabled={busy || !review || review.errors.length > 0 || !Object.values(review.changes).some((items) => items.length)}
          onclick={() => finish(true)}>{t(review?.migration_ticks ? "Start migration" : "Deploy changes")} <ArrowRight size={15} /></Button>
      </div>
    {/snippet}
  </Modal>
{/if}

<style>
  .map-settings { gap: 18px; }
  .map-settings section { gap: 9px; }
  .map-settings small { color: var(--muted); }
  .edge-legend { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
  .edge-legend li { display: flex; align-items: center; gap: 9px; }
  .edge-legend li::before { content: ''; display: block; width: 18px; flex: none; border-top: 2px solid var(--edge-color); }
  .edge-legend li.dashed::before { border-top-style: dashed; }
  .architecture { min-width: 0; display: grid; grid-template-rows: auto minmax(550px, 1fr); min-height: calc(100dvh - 65px); }
  .topology-header { display: grid; grid-template-columns: .95fr 1.1fr; align-items: center; gap: 12px; min-height: 91px; background: var(--background); padding: 12px 26px; }
  .topology-header h1 { font-size: 26px; margin-top: 5px; }
  .service-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; }
  .service-metrics strong { display: block; font-size: clamp(15px, 1.7vw, 25px); overflow-wrap: anywhere; margin-top: 4px; }
  .service-metrics span { font-size: 10px; }
  .workspace { min-width: 0; display: grid; border-block: 1px solid var(--border); }
  .inspector-help { color: var(--primary); text-decoration: underline; width: fit-content; font-size: 13px; }
  .inspector-section { gap: 9px; }
  .resource-list { display: grid; gap: 0; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
  .resource-meter { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; align-items: center; padding: 10px 12px; }
  .resource-meter + .resource-meter { border-top: 1px solid var(--border); }
  .resource-meter :global(.meter label) { min-width: 0; overflow-wrap: anywhere; }
  .resource-meter :global(.meter span) { font: 600 13px var(--mono); font-variant-numeric: tabular-nums; }
  .catalog-group { display: grid; gap: 5px; margin: 17px 0 0; }
  .catalog-group h3 { margin-bottom: 2px; }
  .catalog-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px; align-items: center; }
  .stack > :global(.dependency) { display: grid; justify-content: start; text-align: left; overflow-wrap: anywhere; }
  .stack > :global(.dependency small) { color: var(--muted); }
  .catalog-row :global(.catalog-item) { min-height: 40px; padding-inline: 8px; gap: 7px; justify-content: flex-start; text-align: left; }
  .catalog-row :global(.catalog-item svg) { color: var(--primary); flex: 0 0 auto; }
  .catalog-row :global(.catalog-item span) { min-width: 0; overflow-wrap: anywhere; }
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
  .canvas-hint { position: absolute; bottom: 10px; left: 52px; font-size: 10px; color: var(--muted); pointer-events: none; }
  .edit-bar { z-index: 1; justify-content: flex-end; padding: 10px 15px; border-top: 1px solid var(--border); }
  .component-list { padding: 16px; align-content: start; overflow: auto; }
  .component-list :global(button) { justify-content: space-between; text-align: left; }
  .identity { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: start; padding-block: 2px 5px; }
  .identity h2 { overflow-wrap: anywhere; font-size: 22px; line-height: 1.15; margin-block: 3px 8px; }
  .identity p { color: var(--muted); font-size: 12px; }
  .identity-meta { gap: 6px 10px; }
  .component-symbol { display: grid; place-items: center; flex: 0 0 40px; width: 40px; height: 40px; border-radius: 10px; background: var(--tint); color: var(--primary); }
  .switch { display: grid; grid-template-columns: 1fr 1fr; border-radius: 8px; background: var(--surface); }
  .switch :global(button) { border-radius: 8px; min-height: 36px; color: var(--muted); border: 0; background: transparent; font-size: 12px; }
  .switch :global(button[aria-pressed="true"]) { color: var(--text); background: var(--tint); font-weight: 600; }
  .stack :global(.instance) { margin-top: 5px; justify-content: space-between; }
  .counter { gap: 7px; padding-inline: 1px; }
  .counter :global(button) { min-height: 32px; }
  .cost { padding-top: 13px; border-top: 1px solid var(--border); }
  .cost strong { font-size: 22px; }
  .metric-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 92px), 1fr)); gap: 6px; margin: 0; }
  .metric-overview > div { display: grid; align-content: space-between; gap: 5px; min-width: 0; padding: 9px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
  .metric-overview dt, .metric-details dt { color: var(--muted); font-size: 12px; line-height: 1.35; }
  .metric-overview dd, .metric-details dd { min-width: 0; overflow-wrap: anywhere; font: 600 13px var(--mono); }
  .metric-details { margin: 0; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
  .metric-details > div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, auto); gap: 6px 14px; align-items: baseline; padding: 8px 11px; }
  .metric-details > div + div { border-top: 1px solid var(--border); }
  .metric-details > div > dd { text-align: end; max-inline-size: 14ch; }
  .context { position: fixed; z-index: var(--sui-layer-popover); width: max-content; min-width: 175px; max-width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px); padding: 8px; gap: 5px; overflow: auto; }
  .context :global(.sui-button) { justify-content: flex-start; white-space: normal; text-align: start; min-height: 36px; }
  .mobile-sub, .mobile-heading { display: none; }
  @media (min-width: 851px) and (max-width: 1200px) {
    .topology-header { padding-inline: 18px; }
  }
  @media (max-width: 850px) {
    .architecture { display: block; padding: 14px 17px 20px; min-height: 0; }
    .topology-header { display: block; padding: 0; background: none; min-height: 0; }
    .topology-header h1 { margin: 0; }
    .desktop-heading { display: none; }
    .mobile-heading { display: inline; }
    .topology-header .eyebrow, .service-metrics { display: none; }
    .mobile-sub { display: block; font-size: 12px; }
    .workspace { display: flex; flex-direction: column; gap: 13px; border: 0; }
    .drawing { min-height: 0; background: none; display: flex; flex-direction: column; }
    .canvas-hint { top: 12px; bottom: auto; }
    .canvas { height: clamp(310px, 45dvh, 490px); border: 1px solid var(--border); border-radius: 10px; }
    .canvas-bar, .edit-bar { padding: 8px 0; border: 0; }
    .canvas-bar { min-height: 58px; }
    .canvas-bar.editing { background: transparent; }
    .edit-bar { padding-bottom: 0; }
    .component-list { border: 1px solid var(--border); border-radius: 10px; background: var(--background); }
  }
</style>
