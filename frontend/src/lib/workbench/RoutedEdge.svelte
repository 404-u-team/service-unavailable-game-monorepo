<script lang="ts" module>
  import type { Edge } from '@xyflow/svelte';
  import type { Point } from '../types';

  export type RoutedEdge = Edge<{
    points: Point[];
    waypoints: Point[];
    labelAt?: Point;
    label?: string;
    color: string;
    width: number;
    dashed: boolean;
    moving: boolean;
    reconnectable: boolean;
    update?: (points: Point[], save: boolean) => void;
  }, 'routed'>;
</script>

<script lang="ts">
  import { t } from '../i18n.svelte';
  import { BaseEdge, EdgeLabel, EdgeReconnectAnchor, useSvelteFlow, useStore, type EdgeProps } from '@xyflow/svelte';
  let { data, selected, markerEnd, sourceX, sourceY, targetX, targetY }: EdgeProps<RoutedEdge> = $props();
  const store = useStore();
  const { screenToFlowPosition } = useSvelteFlow();
  const points = $derived(data?.points.length ? data.points : [{ x: sourceX, y: sourceY }, { x: targetX, y: targetY }]);
  const path = $derived(points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' '));
  const endpoint = $derived(points.at(-1));
  function dragWaypoint(event: PointerEvent, index: number) {
    if (event.button !== 0 || !data?.update) return;
    event.preventDefault();
    event.stopPropagation();
    (event.currentTarget as HTMLButtonElement).focus({ preventScroll: true });
    const original = [...data.waypoints];
    const update = data.update;
    const pointerId = event.pointerId;
    const controller = new AbortController();
    const options = { signal: controller.signal, capture: true };
    let moved = false;

    function move(next: PointerEvent, save: boolean) {
      if (next.pointerId !== pointerId) return;
      if (save) controller.abort();
      if (!moved && Math.hypot(next.clientX - event.clientX, next.clientY - event.clientY) < 2) return;
      moved = true;
      next.preventDefault();
      const points = original.map((point, i) => i === index
        ? screenToFlowPosition({ x: next.clientX, y: next.clientY }, { snapToGrid: false })
        : point);
      update(points, save);
    }

    window.addEventListener('pointermove', (next) => move(next, false), options);
    window.addEventListener('pointerup', (next) => move(next, true), options);
    window.addEventListener('pointercancel', (next) => {
      if (next.pointerId !== pointerId) return;
      controller.abort();
      if (moved) update(original, false);
    }, options);
  }

</script>

{#if data && endpoint}
  <path d={path} stroke="#0c1013" stroke-width={data.width + 5} fill="none" pointer-events="none" />
  <BaseEdge {path} {markerEnd} interactionWidth={20}
    style={`stroke:${data.color};stroke-width:${data.width};${data.dashed ? 'stroke-dasharray:5 4;' : ''}`} />
  {#if data.moving}
    <path d={path} class="traffic" stroke={data.color} fill="none" pointer-events="none" />
  {/if}
  {#if data.labelAt && data.label && store.viewport.zoom >= .42}
    <EdgeLabel transparent selectEdgeOnClick x={data.labelAt.x} y={data.labelAt.y}>
      <span class="rate mono" style:color={data.color}>{data.label}</span>
    </EdgeLabel>
  {/if}
  {#if selected && data.update}
    {#each data.waypoints as point, index (index)}
      <EdgeLabel transparent class="waypoint-layer nopan" x={point.x} y={point.y}>
        <button class="waypoint nodrag nopan" type="button" aria-label={t("Waypoint {0}", [index + 1])}
          title={t("Drag to move. Delete to remove.")}
          onpointerdown={(event) => dragWaypoint(event, index)}
          onkeydown={(event) => {
            const delta = { ArrowLeft: [-8, 0], ArrowRight: [8, 0], ArrowUp: [0, -8], ArrowDown: [0, 8] }[event.key];
            if (!delta && !['Delete', 'Backspace'].includes(event.key)) return;
            event.preventDefault();
            event.stopPropagation();
            if (delta) data?.update?.(data.waypoints.map((p, i) => i === index ? { x: p.x + delta[0], y: p.y + delta[1] } : p), true);
            else data?.update?.(data.waypoints.filter((_, i) => i !== index), true);
          }}
          oncontextmenu={(event) => {
            event.preventDefault();
            event.stopPropagation();
            data?.update?.(data.waypoints.filter((_, i) => i !== index), true);
          }}></button>
      </EdgeLabel>
    {/each}
    {#if data.reconnectable}
      <EdgeReconnectAnchor type="source" position={{ x: sourceX + 15, y: sourceY }} size={14} style="background: var(--warning); border: 2px solid var(--background);" />
      <EdgeReconnectAnchor type="target" position={{ x: targetX - 15, y: targetY }} size={14} style="background: var(--warning); border: 2px solid var(--background);" />
    {/if}
  {/if}
{/if}

<style>
  .rate { font-size: 11px; white-space: nowrap; padding: 1px 4px; border-radius: 4px; background: var(--background); }
  :global(.svelte-flow__edge-label.waypoint-layer) { z-index: 10 !important; }
  .waypoint { pointer-events: auto; touch-action: none; cursor: grab; display: block; border-radius: 50%; width: 19px; height: 19px;
    padding: 0; border: 3px solid var(--background); background: var(--warning); outline-offset: 2px; }
  .waypoint:active { cursor: grabbing; }
  .traffic { stroke-width: 2; stroke-dasharray: 3 14; animation: flow 1s linear infinite; opacity: .8; }
  @keyframes flow { to { stroke-dashoffset: -17; } }
  @media (prefers-reduced-motion: reduce) { .traffic { display: none; } }
  :global([data-reduced-motion="true"]) .traffic { display: none; }
</style>
