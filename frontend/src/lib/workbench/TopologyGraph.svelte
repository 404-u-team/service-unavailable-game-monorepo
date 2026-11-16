<script lang="ts">
  import { locale, message, t } from '../i18n.svelte';
  import { Background, BackgroundVariant, Controls, MarkerType, MiniMap, Position, SvelteFlow,
    type Connection as FlowConnection, type IsValidConnection, type OnConnectEnd, type OnConnectStart, type Viewport } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { onDestroy, untrack } from 'svelte';
  import { target } from './onboarding';
  import type { CanvasTools } from './placement';
  import CanvasViewport from './CanvasViewport.svelte';
  import FlowNode, { type WorkbenchNode } from './FlowNode.svelte';
  import GroupNode, { type GroupFlowNode } from './GroupNode.svelte';
  import RoutedEdge, { type RoutedEdge as DiagramEdge } from './RoutedEdge.svelte';
  import { labelPosition, routeConnection, segments, type Rect } from './routing';
  import { num, rps } from '../format';
  import { statusLabel } from '../labels';
  import { groupComponents, nestedGroups } from './groups';
  import { connectionError, connectionKind, connectionLabels } from './connections';
  import type { Catalog, Component, Connection, Diagram, DiagramGroup, Game, Point, Topology } from '../types';

  let { guideApi, topology, diagram, game, catalog, requestType, selected, edgeSelected, groupSelected, selection, editable, compact, removed, touchSelect,
    select, inspect, selectEdge, selectGroup, selectMany, connect, move, toggleGroup, updateRoute, menu, clear, cluster, container, bindPlacement, saveViewport }: {
    guideApi?: string; topology: Topology; diagram: Diagram; game: Game; catalog: Catalog; requestType: string; selected: string;
    edgeSelected: string; groupSelected: string; selection: string[]; editable: boolean; compact: boolean; removed: Component[]; touchSelect: boolean;
    select: (id: string) => void; inspect: (id: string) => void; selectEdge: (id: string) => void; selectGroup: (id: string) => void;
    selectMany: (ids: string[]) => void; connect: (edge: Connection, replaces?: string) => void;
    move: (positions: Record<string, Point>) => void; toggleGroup: (id: string) => void;
    updateRoute: (key: string, waypoints: Point[], save: boolean) => void;
    menu: (event: MouseEvent, id?: string) => void; clear: () => void; cluster: boolean; container: HTMLElement;
    bindPlacement: (tools?: CanvasTools) => void;
    saveViewport: (viewport: Viewport) => void;
  } = $props();

  const edgeKey = (edge: Connection) => `${edge.source}:${edge.target}`;
  const nodeTypes = { workbench: FlowNode, groupCard: GroupNode };
  const edgeTypes = { routed: RoutedEdge };
  type CanvasNode = WorkbenchNode | GroupFlowNode;
  let nodes = $state.raw<CanvasNode[]>([]);
  let edges = $state.raw<DiagramEdge[]>([]);
  let linkStart = $state<{ id: string; isTarget: boolean }>();
  let reconnectKey = $state('');
  let dragPositions = $state.raw<Record<string, Point>>({});
  let routeFrame: ReturnType<typeof setTimeout> | undefined;
  let queuedDrag: Record<string, Point> = {};
  let dragging = $state(false);

  function previewPositions(next: Record<string, Point>) {
    dragging = true;
    queuedDrag = next;
    if (routeFrame !== undefined) return;
    routeFrame = setTimeout(() => {
      routeFrame = undefined;
      dragPositions = queuedDrag;
    }, topology.edges.length < 80 ? 16 : 75);
  }

  function finishMove(next: Record<string, Point>) {
    clearTimeout(routeFrame);
    routeFrame = undefined;
    move(next);
    dragPositions = {};
    dragging = false;
  }

  onDestroy(() => clearTimeout(routeFrame));
  let linkFeedback = $state('');
  function viewportKey() { return `workbench-viewport:${game.id}:${compact ? 'compact' : 'wide'}`; }
  function restoreViewport(): Viewport | undefined {
    const saved = diagram.viewports?.[compact ? 'compact' : 'wide'];
    if (saved) return saved;
    try {
      const stored = JSON.parse(localStorage.getItem(viewportKey()) ?? 'null');
      if (stored && [stored.x, stored.y, stored.zoom].every(Number.isFinite)) return stored;
    } catch { /* The diagram still fits when browser preferences are unavailable. */ }
  }
  const initialViewport = untrack(restoreViewport);
  let viewportReady = false;
  let transientMove = false;
  const card = $derived({ width: compact ? 156 : 167, height: compact ? 86 : 101 });
  let graphSnapshot = $state.raw(untrack(() => game.snapshot));
  $effect(() => { if (!dragging) graphSnapshot = game.snapshot; });
  const actual = $derived(Object.fromEntries(game.production.nodes.map((node) => [node.id, node])));
  const components = $derived(Object.fromEntries(topology.nodes.map((node) => [node.id, node])));
  const groups = $derived(diagram.groups);
  const savedPositions = $derived(diagram.positions);
  const routes = $derived(diagram.routes);
  const hiddenGroups = $derived(new Set(groups.filter((group) => group.collapsed)
    .flatMap((group) => [...nestedGroups(group, groups)])));
  const collapsedMembers = $derived(new Map(groups.filter((group) => group.collapsed && !hiddenGroups.has(group.id))
    .flatMap((group) => groupComponents(group, groups).map((member) => [member, group.id] as const))));
  const allGroups = $derived(new Map(groups.map((group) => [group.id, group])));


  const compactOffsets: Record<string, Point> = {
    traffic: { x: 0, y: -112 },
    edge: { x: -45, y: -112 },
    api: { x: -275, y: 10 },
    db: { x: -505, y: 134 }
  };

  function project(point: Point, id: string, inverse = false): Point {
    const offset = compact ? compactOffsets[id] : undefined;
    const direction = inverse ? -1 : 1;
    return offset ? { x: point.x + offset.x * direction, y: point.y + offset.y * direction } : point;
  }

  function position(node: Component) {
    return project(dragPositions[node.id] ?? savedPositions[node.id] ?? node.position, node.id);
  }

  function projectWaypoint(point: Point, edge: Connection, inverse = false) {
    const a = project(point, edge.source, inverse);
    const b = project(point, edge.target, inverse);
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }
  const groupBoxes = $derived.by(() => {
    const boxes = new Map<string, Rect>();
    function measure(group: DiagramGroup): Rect | undefined {
      const found = boxes.get(group.id);
      if (found) return found;
      const items: Rect[] = [];
      for (const id of group.collapsed ? groupComponents(group, groups) : group.members) {
        const node = components[id];
        const child = allGroups.get(id);
        const rect = node ? { ...position(node), ...card } : child && measure(child);
        if (rect) items.push(rect);
      }
      if (!items.length) return;
      const x = Math.min(...items.map((r) => r.x));
      const y = Math.min(...items.map((r) => r.y));
      const box = group.collapsed ? { x, y, width: 180, height: 83 } : {
        x: x - 16, y: y - 43, width: Math.max(...items.map((r) => r.x + r.width)) - x + 32,
        height: Math.max(...items.map((r) => r.y + r.height)) - y + 59
      };
      boxes.set(group.id, box);
      return box;
    }
    for (const group of groups) if (!hiddenGroups.has(group.id)) measure(group);
    return boxes;
  });

  $effect(() => {
    const current = untrack(() => nodes);
    const stable = new Map(current.map((node) => [node.id, node]));
    const next: CanvasNode[] = [];
    for (const group of groups) {
      const bounds = groupBoxes.get(group.id);
      if (!bounds || hiddenGroups.has(group.id)) continue;
      const members = groupComponents(group, groups).filter((id) => components[id]);
      const stats = members.flatMap((id) => graphSnapshot.components[id] ? [graphSnapshot.components[id]] : []);
      const warnings = stats.filter((metric) => !['idle', 'healthy'].includes(metric.status)).length;
      const priority = ['failed', 'overloaded', 'warning', 'healthy', 'idle'] as const;
      const status = priority.find((state) => stats.some((metric) => metric.status === state));
      next.push({
        id: group.id, type: 'groupCard', position: { x: bounds.x, y: bounds.y }, width: bounds.width, height: bounds.height,
        data: { name: group.name, count: members.length, warnings,
          status: status ? statusLabel[status] : 'Metrics unavailable', collapsed: group.collapsed,
          throughput: stats.length ? stats.reduce((sum, metric) => sum + metric.throughput, 0) : undefined,
          toggle: stable.get(group.id)?.type === 'groupCard' ? (stable.get(group.id) as GroupFlowNode).data.toggle : () => toggleGroup(group.id) },
        selected: group.id === groupSelected, draggable: true, dragHandle: '.drag-group',
        selectable: true, connectable: false, deletable: false, ariaLabel: group.name, zIndex: group.collapsed ? 0 : -1 - nestedGroups(group, groups).size
      });
    }
    for (const node of [...topology.nodes, ...removed]) {
      if (collapsedMembers.has(node.id)) continue;
      const live = actual[node.id];
      const definition = catalog.components[node.kind];
      const metric = graphSnapshot.components[node.id];
      const pending = removed.includes(node);
      const settings = Object.fromEntries(Object.entries(definition.fields).map(([key, field]) => [key, node.config[key] ?? field.default]));
      const configured = live && Object.keys(definition.fields).some((key) => (live.config[key] ?? definition.fields[key].default) !== settings[key]);
      const change = pending ? t('Pending removal') : !live ? t('Added in draft') : configured || live.name !== node.name ? t('Modified in draft') : '';
      const monitor = graphSnapshot.monitors?.[node.id];
      const status = metric?.status ?? (monitor ? monitor.failed ? 'failed' : monitor.dropped.length ? 'warning' : monitor.covered.length ? 'healthy' : 'idle' : undefined);
      const use = metric && Object.keys(metric.utilization).length ? Math.max(...Object.values(metric.utilization)) : undefined;
      const tone = status === 'failed' || status === 'overloaded' ? 'bad' : status === 'warning' ? 'warn' : status === 'healthy' || node.kind === 'source' ? 'good' : 'dim';
      const instances = Number(settings.instances ?? 1);
      const meta = node.kind === 'source' ? rps(graphSnapshot.metrics.rps)
        : node.kind === 'api' ? `${instances > 1 ? `${instances}× · ` : ''}${t('{0} vCPU · {1} GB', [num(Number(settings.cpu)), num(Number(settings.memory))])}`
        : node.kind === 'worker' ? `${instances}× · ${t('{0} vCPU', [num(Number(settings.cpu))])}`
        : node.kind === 'balancer' ? t(String(settings.algorithm)) : t(definition.name);
      const compatible = linkStart && linkStart.id !== node.id ? !connectionError(topology, catalog, linkStart.isTarget
        ? { source: node.id, target: linkStart.id } : { source: linkStart.id, target: node.id }, reconnectKey) : undefined;
      const base: WorkbenchNode = {
        id: node.id, type: 'workbench', position: position(node), ...card,
        data: { name: t(node.name), kind: node.kind, meta: node.kind === 'api' ? `${t(String(settings.role ?? 'Universal'))} · ${meta}` : node.kind === 'database' ? `${t(String(settings.domain ?? 'Shared'))} · ${t(String(settings.partition ?? 'Independent'))}` : meta, tone,
          health: status ? t(statusLabel[status]) : node.kind === 'source' ? t('Traffic input') : t('Metrics unavailable'),
          change, use, editable: editable && !pending, vertical: compact, compatible,
          input: Position.Left, output: Position.Right },
        domAttributes: node.id === guideApi && !pending ? { 'data-tutorial': target.api } : undefined,
        selected: selection.includes(node.id), draggable: !pending, deletable: false,
        selectable: !pending, connectable: editable && !pending, ariaLabel: t(node.name), zIndex: 1
      };
      next.push(base);
      if (cluster && !pending && node.id === selected && instances > 1 && (node.kind === 'api' || node.kind === 'worker')) {
        for (let i = 0; i < instances; i++) {
          const p = base.position;
          next.push({
            id: `${node.id}~${i + 1}`, type: 'workbench', ...card,
            position: { x: p.x + (i % 3) * (card.width + 18), y: p.y + 124 + Math.floor(i / 3) * (card.height + 14) },
            data: { ...base.data, name: t('Instance {0}', [i + 1]), meta: t('{0} vCPU', [num(Number(settings.cpu))]), health: t('Cluster member'), change: '', use: undefined, editable: false },
            selectable: false, focusable: false, draggable: false, deletable: false, connectable: false, zIndex: 1
          });
        }
      }
    }
    const resolved = next.map((node) => {
      const previous = stable.get(node.id);
      if (!previous) return node;
      if (previous.dragging) return { ...previous, data: node.data } as CanvasNode;
      if (previous.position.x === node.position.x && previous.position.y === node.position.y &&
          previous.domAttributes?.['data-tutorial'] === node.domAttributes?.['data-tutorial'] && previous.width === node.width && previous.height === node.height && previous.selected === node.selected &&
          JSON.stringify(previous.data) === JSON.stringify(node.data)) return previous;
      return node;
    });
    if (resolved.length !== current.length || resolved.some((node, index) => node !== current[index])) nodes = resolved;
  });

  const edgeSpecs = $derived.by(() => {
    const bundles = new Map<string, { key: string; source: string; target: string; originals: Connection[]; kind: ReturnType<typeof connectionKind>; aggregated: boolean }>();
    for (const edge of topology.edges) {
      const source = collapsedMembers.get(edge.source) ?? edge.source;
      const target = collapsedMembers.get(edge.target) ?? edge.target;
      if (source === target) continue;
      const aggregated = source !== edge.source || target !== edge.target;
      const kind = connectionKind(catalog, components[edge.source]?.kind, components[edge.target]?.kind);
      const key = aggregated ? `bundle:${source}:${target}:${kind}` : edgeKey(edge);
      const bundle = bundles.get(key);
      if (bundle) bundle.originals.push(edge);
      else bundles.set(key, { key, source, target, kind, originals: [edge], aggregated });
    }
    return [...bundles.values()];
  });

  const geometry = $derived.by(() => {
    const boxes: Record<string, Rect> = {};
    for (const node of [...topology.nodes, ...removed]) {
      if (!collapsedMembers.has(node.id)) boxes[node.id] = { ...position(node), ...card };
    }
    for (const group of groups) {
      const box = groupBoxes.get(group.id);
      if (group.collapsed && box) boxes[group.id] = box;
    }
    return { boxes, obstacles: Object.values(boxes) };
  });

  const paths = $derived.by(() => {
    const { boxes, obstacles } = geometry;
    const occupied: [Point, Point][] = [];
    const paths = edgeSpecs.flatMap((item, index) => {
      const from = boxes[item.source];
      const to = boxes[item.target];
      if (!from || !to) return [];
      const waypoints = item.aggregated ? [] : (routes[item.key] ?? []).map((point) => projectWaypoint(point, item.originals[0]));
      const start = { x: from.x + from.width, y: from.y + from.height / 2 };
      const end = { x: to.x, y: to.y + to.height / 2 };
      const preview = dragging && topology.edges.length >= 40;
      const stops = preview ? [start, ...waypoints, end] : [];
      const points = preview
        ? [start, ...segments(stops).flatMap(([a, b]) => [{ x: (a.x + b.x) / 2, y: a.y }, { x: (a.x + b.x) / 2, y: b.y }, b])]
        : routeConnection(start, end, obstacles, waypoints, occupied, (index % 7 - 3) * 9);
      occupied.push(...segments(points));
      return [{ ...item, waypoints, points }];
    });
    return { paths, obstacles };
  });

  $effect(() => {
    const traffic = new Map(graphSnapshot.traffic.map((item) => [edgeKey(item), requestType ? item.operations?.[requestType] ?? 0 : item.rps]));
    const liveEdges = new Set(game.production.edges.map(edgeKey));
    const current = untrack(() => edges);
    const previous = new Map(current.map((edge) => [edge.id, edge]));
    const labels: Rect[] = [];
    const next = paths.paths.map((item): DiagramEdge => {
      const known = item.originals.flatMap((edge) => traffic.has(edgeKey(edge)) ? [traffic.get(edgeKey(edge))!] : []);
      const flow = known.length ? known.reduce((sum, value) => sum + value, 0) : undefined;
      const live = item.originals.every((edge) => liveEdges.has(edgeKey(edge)));
      const selected = item.key === edgeSelected;
      const diagnostic = item.kind === 'telemetry' || item.kind === 'replication';
      const dim = requestType && !diagnostic && (!flow || flow <= 0) && !selected;
      const color = dim ? '#53636b' : item.kind === 'telemetry' ? '#8cbdf3' : item.kind === 'replication' ? '#d7aeed'
        : selected || !live ? '#ffb35c' : ['queries', 'reads', 'cache'].includes(item.kind) ? '#5ed5c6'
        : ['enqueue', 'jobs'].includes(item.kind) ? '#ffd587' : '#c7f46c';
      const label = flow === undefined || (requestType && !flow) ? (item.aggregated ? `${item.originals.length}×` : undefined) : t('{0}/s', [num(Math.round(flow))]);
      const width = flow === undefined ? 1.7 : Math.min(3.8, 1.6 + flow / 120);
      const old = previous.get(item.key);
      const value: DiagramEdge = {
        id: item.key, source: item.source, target: item.target, type: 'routed', selected, deletable: false, zIndex: 0,
        ariaLabel: `${t(components[item.originals[0].source]?.name ?? '')} → ${t(components[item.originals[0].target]?.name ?? '')} · ${t(connectionLabels[item.kind])}`,
        markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color },
        data: { points: item.points, waypoints: item.waypoints, label, color, width,
          labelAt: label ? labelPosition(item.points, label.length * 7 + 8, paths.obstacles, labels) : undefined,
          dashed: !live || item.kind === 'telemetry' || item.kind === 'replication',
          moving: game.speed > 0 && Boolean(flow && flow > 0) && !game.settings.reduced_motion,
          reconnectable: !item.aggregated && editable,
          update: item.aggregated ? undefined : old?.data?.update ?? ((waypoints, save) => updateRoute(item.key, waypoints.map((point) => projectWaypoint(point, item.originals[0], true)), save)) }
      };
      return old && old.ariaLabel === value.ariaLabel && old.selected === value.selected && JSON.stringify(old.data) === JSON.stringify(value.data) ? old : value;
    });
    if (next.length !== current.length || next.some((edge, index) => edge !== current[index])) edges = next;
  });

  const valid: IsValidConnection = (candidate) => editable && !connectionError(topology, catalog, candidate, reconnectKey);

  function trackDrag(dragged: CanvasNode[]) {
    const positions: Record<string, Point> = {};
    for (const item of dragged) {
      if (item.type === 'workbench' && components[item.id]) positions[item.id] = project(item.position, item.id, true);
      else if (item.type === 'groupCard') {
        const group = groups.find((group) => group.id === item.id);
        if (!group) continue;
        const bounds = groupBoxes.get(group.id);
        if (!bounds) continue;
        const current = dragPositions;
        // The group's bounds follow its children as the drag progresses.
        const dx = item.position.x - bounds.x;
        const dy = item.position.y - bounds.y;
        for (const id of groupComponents(group, groups)) {
          if (!components[id]) continue;
          const start = current[id] ?? diagram.positions[id] ?? components[id].position;
          positions[id] = { x: start.x + dx, y: start.y + dy };
        }
      }
    }
    return positions;
  }
  function nudge(event: KeyboardEvent) {
    const delta = { ArrowLeft: [-5, 0], ArrowRight: [5, 0], ArrowUp: [0, -5], ArrowDown: [0, 5] }[event.key];
    const element = event.target;
    if (!(element instanceof HTMLElement) || !element.classList.contains('svelte-flow__node')) return;
    if ((event.key === 'Enter' || event.key === ' ') && element.dataset.id === guideApi && guideApi) {
      event.preventDefault();
      event.stopPropagation();
      select(guideApi);
      return;
    }
    if (!delta) return;
    const dragged = nodes.filter((node) => node.selected && node.draggable);
    if (!dragged.some((node) => node.id === element.dataset.id)) return;
    event.preventDefault();
    event.stopPropagation();
    const scale = event.shiftKey ? 4 : 1;
    finishMove(trackDrag(dragged.map((node) => ({
      ...node, position: { x: node.position.x + delta[0] * scale, y: node.position.y + delta[1] * scale }
    }))));
  }
  const startConnection: OnConnectStart = (_, params) => {
    linkFeedback = '';
    if (params.nodeId) linkStart = { id: params.nodeId, isTarget: params.handleType === 'target' };
  };

  const finishConnection: OnConnectEnd = (event, state) => {
    if (linkStart && !state.isValid) {
      const contact = 'changedTouches' in event ? event.changedTouches[0] : event;
      const underPointer = contact ? document.elementsFromPoint(contact.clientX, contact.clientY) : [];
      const hoverNode = underPointer.flatMap((element) => {
        const node = element.closest<HTMLElement>('.svelte-flow__node-workbench');
        return node ? [node] : [];
      })[0];
      const closePort = contact && [...container.querySelectorAll<HTMLElement>(linkStart.isTarget ? '.svelte-flow__handle.source' : '.svelte-flow__handle.target')]
        .find((port) => {
          const bounds = port.getBoundingClientRect();
          return Math.hypot(contact.clientX - (bounds.x + bounds.width / 2), contact.clientY - (bounds.y + bounds.height / 2)) <= 13;
        });
      const target = state.toNode?.id ?? hoverNode?.dataset.id ?? (closePort ? closePort.dataset.nodeid : undefined);
      const candidate = linkStart.isTarget ? { source: target ?? '', target: linkStart.id } : { source: linkStart.id, target: target ?? '' };
      linkFeedback = target ? connectionError(topology, catalog, candidate, reconnectKey) ?? '' : t('Drop on a highlighted port to connect.');
    }
    linkStart = undefined;
    reconnectKey = '';
  };
  const localizedLabels = $derived({
    'controls.ariaLabel': t('Canvas controls'),
    'controls.zoomIn.ariaLabel': t('Zoom in'),
    'controls.zoomOut.ariaLabel': t('Zoom out'),
    'minimap.ariaLabel': t('Minimap'),
    'handle.ariaLabel': t('Connection port'),
    'node.a11yDescription.default': t('Use arrow keys to move the selected node.'),
    'node.a11yDescription.keyboardDisabled': t('Use Enter to select a component.'),
    'node.a11yDescription.ariaLiveMessage': ({ x, y }: Point) => t('Moved to {0}, {1}.', [Math.round(x), Math.round(y)]),
    'edge.a11yDescription.default': t('Use Enter to select a connection.')
  });

  function inspectNode(event: MouseEvent) {
    if (touchSelect || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !(event.target instanceof Element)
      || event.target.closest('button, .svelte-flow__handle')) return;
    const element = event.target.closest<HTMLElement>('.svelte-flow__node-workbench');
    const id = element?.dataset.id;
    if (!id || !topology.nodes.some((node) => node.id === id)) return;
    event.stopPropagation();
    element?.focus({ preventScroll: true });
    inspect(id);
  }
</script>

{#key locale()}
<div class="flow-shell" role="presentation" onkeydowncapture={nudge} ondblclickcapture={inspectNode}>
<SvelteFlow bind:nodes bind:edges {nodeTypes} {edgeTypes} fitView={!initialViewport} {initialViewport} fitViewOptions={{ padding: .12, maxZoom: compact ? 1 : 1.13 }}
  minZoom={0.15} maxZoom={2.5} colorMode="dark" attributionPosition="bottom-right"
  ariaLabelConfig={localizedLabels} elevateNodesOnSelect={false}
  autoPanOnConnect={false} nodesConnectable={editable} deleteKey={null} multiSelectionKey={['Control', 'Meta', 'Shift']}
  isValidConnection={valid}
  onbeforeconnect={(connection: FlowConnection) => { if (valid(connection)) connect({ source: connection.source, target: connection.target }); return false; }}
  onbeforereconnect={(next, old) => {
    if (valid(next)) connect({ source: next.source, target: next.target }, old.id);
    return null;
  }}
  onreconnectstart={(_, edge) => { reconnectKey = edge.id; }}
  onconnectstart={startConnection} onconnectend={finishConnection}
  onclickconnectstart={startConnection} onclickconnectend={finishConnection}
  onreconnectend={() => { linkStart = undefined; reconnectKey = ''; }}
  onnodeclick={({ node, event }) => {
    if (node.type === 'groupCard') selectGroup(node.id);
    else if (!('ctrlKey' in event) || !(event.ctrlKey || event.metaKey || event.shiftKey)) select(node.id);
  }}
  onselectionchange={({ nodes: items, edges: chosen }) => {
    const next = items.filter((item) => item.type === 'workbench').map((item) => item.id);
    if (!touchSelect) selectMany(next);
    if (chosen.length === 1 && chosen[0].id !== edgeSelected && !next.length) selectEdge(chosen[0].id);
  }}
  onedgeclick={({ edge }) => selectEdge(edge.id)}
  onnodedrag={({ nodes: dragged }) => previewPositions(trackDrag(dragged))}
  onnodedragstop={({ nodes: dragged }) => finishMove(trackDrag(dragged))}
  onselectiondrag={(_, dragged) => previewPositions(trackDrag(dragged))}
  onselectiondragstop={(_, dragged) => finishMove(trackDrag(dragged))}
  oninit={() => { viewportReady = true; }}
  onmoveend={(event, viewport) => {
    if (event || (viewportReady && !transientMove)) saveViewport(viewport);
  }}
  onpaneclick={() => { linkFeedback = ''; clear(); }}
  onnodecontextmenu={({ event, node }) => { if (node.type === 'groupCard') { selectGroup(node.id); menu(event); } else menu(event, node.id); }}
  onpanecontextmenu={({ event }) => menu(event)}
  onedgecontextmenu={({ event, edge }) => { selectEdge(edge.id); menu(event); }}
  panOnDrag={[0, 1]} panOnScroll zoomOnScroll={false} zoomActivationKey="Control" zoomOnPinch>
  <CanvasViewport nodePosition={(id) => nodes.find((node) => node.id === id)?.position} transientMove={(moving) => transientMove = moving} {container} size={card} obstacles={geometry.obstacles} {bindPlacement} />
  <Background variant={BackgroundVariant.Lines} gap={compact ? 24 : 32} patternColor="#202a30" bgColor="#0c1013" />
  <Controls position={compact ? "top-left" : "bottom-left"} showFitView={false} showLock={false} />
  {#if !compact}<MiniMap position="bottom-right" width={119} height={74} pannable zoomable maskColor="#0c1013a0" nodeColor="#30494c" />{/if}
</SvelteFlow>
</div>
{/key}
{#if linkStart || linkFeedback}
  <p class="link-feedback notice" role="status">{linkStart ? t("Highlighted ports accept this connection.") : message(linkFeedback)}</p>
{/if}

<style>
  .flow-shell { position: absolute; inset: 0; }
  .link-feedback { position: absolute; top: 9px; left: 9px; right: 9px; width: fit-content; max-width: calc(100% - 18px); pointer-events: none; background: var(--surface); }
  :global(.svelte-flow) {
    --xy-background-color: var(--background);
    --xy-controls-button-background-color: var(--surface);
    --xy-controls-button-background-color-hover: var(--tint);
    --xy-controls-button-color: var(--text);
    --xy-controls-button-color-hover: var(--primary);
    --xy-controls-button-border-color: var(--border);
    --xy-minimap-background-color: var(--surface);
  }
  :global(.svelte-flow__node-workbench:has(.connectable)) { z-index: 1003 !important; }
  :global(.svelte-flow__edge-labels) { z-index: 1002; pointer-events: none; }
  :global(.svelte-flow__controls) { border: 1px solid var(--border); overflow: hidden; border-radius: 8px; }
  :global(.svelte-flow__minimap) { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  :global(.svelte-flow__attribution) { background: var(--surface); }
  :global(.svelte-flow__attribution a) { color: var(--muted); }
  :global(.svelte-flow__node-workbench:focus-visible) { outline: 2px solid var(--primary); outline-offset: 4px; border-radius: 11px; }
</style>
