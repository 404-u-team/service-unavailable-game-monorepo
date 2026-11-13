<script lang="ts">
  import { Background, BackgroundVariant, Controls, MarkerType, MiniMap, Position, SvelteFlow,
    type Connection as FlowConnection, type Edge, type IsValidConnection } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { untrack } from 'svelte';
  import FitOnResize from './FitOnResize.svelte';
  import FlowNode, { type WorkbenchNode } from './FlowNode.svelte';
  import { rps } from '../format';
  import { statusLabel } from '../labels';
  import type { Catalog, Component, Connection, Game, Point, Topology } from '../types';

  let { topology, game, catalog, selected, edgeSelected, editable, compact, removed,
    select, selectEdge, connect, move, menu, clear, cluster, container }: {
    topology: Topology; game: Game; catalog: Catalog; selected: string;
    edgeSelected: string; editable: boolean; compact: boolean; removed: Component[];
    select: (id: string) => void; selectEdge: (id: string) => void;
    connect: (edge: Connection) => void; move: (id: string, position: Point) => void;
    menu: (event: MouseEvent, id?: string) => void; clear: () => void; cluster: boolean; container: HTMLElement;
  } = $props();

  export const edgeKey = (edge: Connection) => `${edge.source}:${edge.target}`;
  const nodeTypes = { workbench: FlowNode };
  let nodes = $state.raw<WorkbenchNode[]>([]);
  let edges = $state.raw<Edge[]>([]);
  const actual = $derived(Object.fromEntries(game.production.nodes.map((node) => [node.id, node])));

  const mobilePositions: Record<string, { original: Point; display: Point }> = {
    traffic: { original: { x: 45, y: 185 }, display: { x: 0, y: 0 } },
    edge: { original: { x: 275, y: 185 }, display: { x: 188, y: 0 } },
    api: { original: { x: 505, y: 185 }, display: { x: 94, y: 117 } },
    db: { original: { x: 735, y: 185 }, display: { x: 94, y: 239 } }
  };

  function project(p: Point, id: string, inverse = false): Point {
    if (!compact) return p;
    const anchor = mobilePositions[id] ?? { original: { x: 505, y: 365 }, display: { x: 282, y: 117 } };
    const from = inverse ? anchor.display : anchor.original;
    const to = inverse ? anchor.original : anchor.display;
    return { x: to.x + p.y - from.y, y: to.y + p.x - from.x };
  }

  $effect(() => {
    const current = untrack(() => nodes);
    const stable = new Map(current.map((node) => [node.id, node]));
    const next = [...topology.nodes, ...removed].flatMap((node): WorkbenchNode[] => {
      const live = actual[node.id];
      const definition = catalog.components[node.kind];
      const metric = game.snapshot.components[node.id];
      const pending = removed.includes(node);
      const settings = Object.fromEntries(Object.entries(definition.fields).map(([key, field]) => [key, node.config[key] ?? field.default]));
      const configured = live && Object.keys(definition.fields).some((key) => (live.config[key] ?? definition.fields[key].default) !== settings[key]);
      const change = pending ? 'Pending removal' : !live ? 'Added in draft' : configured || live.name !== node.name ? 'Modified in draft' : '';
      const status = metric?.status;
      const use = metric && Object.keys(metric.utilization).length ? Math.max(...Object.values(metric.utilization)) : undefined;
      const tone = status === 'failed' || status === 'overloaded' ? 'bad' : status === 'warning' ? 'warn' : status === 'healthy' || node.kind === 'source' ? 'good' : 'dim';
      const instances = Number(settings.instances ?? 1);
      const meta = node.kind === 'source' ? rps(game.snapshot.metrics.rps)
        : node.kind === 'api' ? `${instances > 1 ? `${instances}× · ` : ''}${settings.cpu} vCPU · ${settings.memory} GB`
        : node.kind === 'worker' ? `${instances}× · ${settings.cpu} vCPU`
        : node.kind === 'balancer' ? String(settings.algorithm)
        : definition.name;
      const base: WorkbenchNode = {
        ...stable.get(node.id), id: node.id, type: 'workbench', position: project(node.position, node.id),
        data: { name: node.name, kind: node.kind, meta, tone, health: status ? statusLabel[status] : node.kind === 'source' ? 'Traffic input' : 'No telemetry', change, use, editable: editable && !pending, vertical: compact,
          input: compact ? node.id === 'edge' ? Position.Left : Position.Top : Position.Left,
          output: compact ? node.id === 'traffic' ? Position.Right : Position.Bottom : Position.Right }, 
        selected: node.id === selected, draggable: editable && !pending, deletable: false,
        selectable: !pending, connectable: editable && !pending, ariaLabel: node.name
      };
      const previous = stable.get(node.id);
      if (previous?.dragging || previous?.position.x === base.position.x && previous.position.y === base.position.y) base.position = previous.position;
      const related = [base];
      if (cluster && !pending && node.id === selected && instances > 1 && (node.kind === 'api' || node.kind === 'worker')) {
        for (let i = 0; i < instances; i++) {
          const p = base.position;
          related.push({
            id: `${node.id}~${i + 1}`, type: 'workbench',
            position: { x: p.x + (compact ? 170 : 0) + (i % 3) * 175, y: p.y + (compact ? 0 : 115) + Math.floor(i / 3) * 106 },
            data: { ...base.data, name: `Instance ${i + 1}`, meta: `${settings.cpu} vCPU`, health: 'Cluster member', change: '', use: undefined, editable: false },
            selectable: false, focusable: false, draggable: false, deletable: false, connectable: false
          });
        }
      }
      return related.map((item) => {
        const prev = stable.get(item.id);
        if (prev && prev.position.x === item.position.x && prev.position.y === item.position.y &&
            prev.selected === item.selected && prev.draggable === item.draggable &&
            JSON.stringify(prev.data) === JSON.stringify(item.data)) return prev;
        return item;
      });
    });
    if (next.length !== current.length || next.some((node, index) => node !== current[index])) nodes = next;
  });

  $effect(() => {
    const traffic = new Map(game.snapshot.traffic.map((item) => [edgeKey(item), item.rps]));
    const liveEdges = new Set(game.production.edges.map(edgeKey));
    const current = untrack(() => edges);
    const previous = new Map(current.map((edge) => [edge.id, edge]));
    const next = topology.edges.map((item) => {
      const key = edgeKey(item);
      const flow = traffic.get(key);
      const color = key === edgeSelected || !liveEdges.has(key) ? '#ffb35c' : '#c7f46c';
      const width = flow === undefined ? 2 : Math.min(3.8, 1.6 + flow / 120);
      const edge: Edge = {
        ...item, id: key, type: 'step', selected: key === edgeSelected, deletable: false,
        label: flow === undefined ? undefined : `${Math.round(flow)}/s`,
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color },
        style: `stroke: ${color}; stroke-width: ${width};${liveEdges.has(key) ? '' : 'stroke-dasharray: 5 3;'}`,
        labelStyle: 'fill: #c7f46c; font-family: IBM Plex Mono, monospace; font-size: 11px;',
        interactionWidth: 20
      };
      const old = previous.get(key);
      return old && old.label === edge.label && old.style === edge.style && old.selected === edge.selected ? old : edge;
    });
    if (next.length !== current.length || next.some((edge, index) => edge !== current[index])) edges = next;
  });

  const valid: IsValidConnection = (candidate) => {
    if (!editable) return false;
    const source = topology.nodes.find((node) => node.id === candidate.source);
    const target = topology.nodes.find((node) => node.id === candidate.target);
    return Boolean(source && target && catalog.connections[source.kind].includes(target.kind)
      && !topology.edges.some((edge) => edge.source === source.id && edge.target === target.id));
  };

  function onConnect(connection: FlowConnection) {
    if (valid(connection)) connect({ source: connection.source, target: connection.target });
  }
</script>

<SvelteFlow bind:nodes bind:edges {nodeTypes} fitView fitViewOptions={{ padding: compact ? 0.12 : 0.12, maxZoom: compact ? 1 : 1.13 }}
  minZoom={0.15} maxZoom={2.5} colorMode="dark" attributionPosition="bottom-right"
  nodesDraggable={editable} nodesConnectable={editable} deleteKey={null} isValidConnection={valid} onconnect={onConnect}
  onnodeclick={({ node }) => select(node.id)}
  onedgeclick={({ edge }) => selectEdge(edge.id)}
  onnodedragstop={({ targetNode }) => { if (editable && targetNode) move(targetNode.id, project(targetNode.position, targetNode.id, true)); }}
  onpaneclick={clear} onnodecontextmenu={({ event, node }) => menu(event, node.id)}
  onpanecontextmenu={({ event }) => menu(event)}
  onedgecontextmenu={({ event, edge }) => { selectEdge(edge.id); menu(event); }}
  panOnDrag zoomOnPinch>
  <FitOnResize {container} {compact} nodeIds={nodes.map((node) => node.id)} />
  <Background variant={BackgroundVariant.Lines} gap={compact ? 24 : 32} patternColor="#202a30" bgColor="#0c1013" />
  <Controls position="bottom-left" showLock={false} />
  {#if !compact}<MiniMap position="bottom-right" width={119} height={74} pannable zoomable maskColor="#0c1013a0" nodeColor="#30494c" />{/if}
</SvelteFlow>

<style>
  :global(.svelte-flow) {
    --xy-background-color: var(--background);
    --xy-controls-button-background-color: var(--surface);
    --xy-controls-button-background-color-hover: var(--tint);
    --xy-controls-button-color: var(--text);
    --xy-controls-button-color-hover: var(--primary);
    --xy-controls-button-border-color: var(--border);
    --xy-minimap-background-color: var(--surface);
  }
  :global(.svelte-flow__controls) { border: 1px solid var(--border); overflow: hidden; border-radius: 8px; }
  :global(.svelte-flow__minimap) { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  :global(.svelte-flow__attribution) { background: var(--surface); }
  :global(.svelte-flow__attribution a) { color: var(--muted); }
  :global(.svelte-flow__node-workbench:focus-visible) { outline: 2px solid var(--primary); outline-offset: 4px; border-radius: 11px; }
</style>
