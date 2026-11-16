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
    rate: number;
    endpoints: [boolean, boolean];
    breakdown: { label: string; color: string; count: number; rate?: number }[];
    operations: { label: string; rate: number }[];
    reconnectable: boolean;
    update?: (points: Point[], save: boolean) => void;
  }, 'routed'>;
</script>

<script lang="ts">
  import { Tooltip } from '@service-unavailable/ui';
  import { num } from '../format';
  import { t } from '../i18n.svelte';
  import { BaseEdge, EdgeLabel, EdgeReconnectAnchor, useSvelteFlow, useStore, type EdgeProps } from '@xyflow/svelte';
  let { data, selected, sourceX, sourceY, targetX, targetY }: EdgeProps<RoutedEdge> = $props();
  const store = useStore();
  const { screenToFlowPosition } = useSvelteFlow();
  const points = $derived(data?.points.length ? data.points : [{ x: sourceX, y: sourceY }, { x: targetX, y: targetY }]);
  const path = $derived(points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' '));
  const start = $derived(points[0]);
  const end = $derived(points.at(-1));
  const packetGap = $derived((data?.rate ?? 0) >= 300 ? 12 : (data?.rate ?? 0) >= 60 ? 21 : 36);
  const packetDuration = $derived((data?.rate ?? 0) >= 300 ? '.43s' : (data?.rate ?? 0) >= 60 ? '.85s' : '1.6s');
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

{#if data && end}
  <path d={path} stroke="#0c1013" stroke-width={data.width + 5} fill="none" pointer-events="none" />
  <BaseEdge {path} interactionWidth={20}
    style={`stroke:${data.color};stroke-width:${data.width};stroke-opacity:${data.rate > 0 ? '.72' : '1'};${data.dashed ? 'stroke-dasharray:5 4;' : ''}`} />
  {#if data.rate > 0}
    <path d={path} class="traffic" stroke={data.color} fill="none" pointer-events="none"
      style:--gap={packetGap} style:--duration={packetDuration} />
  {/if}
  {#if data.endpoints[0]}
    <circle data-port="source" cx={start.x + 5} cy={start.y} r="2.8" fill={data.color} pointer-events="none" />
  {/if}
  {#if data.endpoints[1]}
    <circle data-port="target" cx={end.x - 5} cy={end.y} r="2.8" fill={data.color} pointer-events="none" />
  {/if}
  {#if data.labelAt && data.label && store.viewport.zoom >= .42}
    <EdgeLabel transparent selectEdgeOnClick class="nopan rate-layer" x={data.labelAt.x} y={data.labelAt.y}>
      <Tooltip class="topology-rate" label={t('Connection breakdown for {0}', [data.label])} delay={150}>
        {#snippet trigger()}<span class="rate mono" style:color={data.color}>{data.label}</span>{/snippet}
        {#snippet content()}
          <strong>{t('Connection breakdown')}</strong>
          <dl class="breakdown">
            {#each data.breakdown as row (row.label)}
              <div>
                <dt><i style:background={row.color}></i>{row.label}</dt>
                <dd>{num(row.count)}×{#if row.rate !== undefined} · {t('{0}/s', [num(row.rate)])}{/if}</dd>
              </div>
            {/each}
          </dl>
          {#if data.operations.length}
            <strong>{t('Request types')}</strong>
            <dl class="breakdown operations">
              {#each data.operations as row (row.label)}
                <div><dt>{row.label}</dt><dd>{t('{0}/s', [num(row.rate)])}</dd></div>
              {/each}
            </dl>
          {/if}
        {/snippet}
      </Tooltip>
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
      <EdgeReconnectAnchor type="source" position={{ x: start.x + 15, y: start.y }} size={14} style="background: var(--warning); border: 2px solid var(--background);" />
      <EdgeReconnectAnchor type="target" position={{ x: end.x - 15, y: end.y }} size={14} style="background: var(--warning); border: 2px solid var(--background);" />
    {/if}
  {/if}
{/if}

<style>
  :global(.topology-rate) { display: block; border: 0; padding: 1px 4px; border-radius: 4px; background: var(--background); cursor: help; }
  :global(.topology-rate:focus-visible) { outline: 2px solid var(--primary); }
  .rate { font-size: 11px; white-space: nowrap; }
  .breakdown { display: grid; gap: 5px; margin: 5px 0 0; font-size: 12px; }
  .breakdown + strong { display: block; margin-top: 10px; }
  .breakdown div { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 9px; align-items: baseline; }
  .breakdown dt { min-width: 0; }
  .breakdown dd { white-space: nowrap; font-family: var(--mono); }
  .breakdown i { display: inline-block; margin-inline-end: 5px; width: 6px; height: 6px; border-radius: 50%; }
  .operations { color: var(--muted); }
  :global(.svelte-flow__edge-label.waypoint-layer) { z-index: 10 !important; }
  .waypoint { pointer-events: auto; touch-action: none; cursor: grab; display: block; border-radius: 50%; width: 19px; height: 19px;
    padding: 0; border: 3px solid var(--background); background: var(--warning); outline-offset: 2px; }
  .waypoint:active { cursor: grabbing; }
  .traffic { stroke-width: 4; stroke-linecap: round; stroke-dasharray: .1 var(--gap);
    animation: flow var(--duration) linear infinite; filter: brightness(1.45); }
  @keyframes flow { to { stroke-dashoffset: calc(-1 * (.1 + var(--gap))); } }
  @media (prefers-reduced-motion: reduce) { .traffic { display: none; } }
</style>
