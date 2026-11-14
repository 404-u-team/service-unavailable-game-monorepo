<script lang="ts">
  import { t } from '../i18n.svelte';
  import { clock, num } from '../format';
  let { title, values, ticks, secondary = [], secondaryTitle, primaryTitle = title, emptyText, format = num, time = clock, sampleTime = time }: {
    title: string; values: (number | null)[]; ticks: number[]; secondary?: number[]; secondaryTitle?: string; primaryTitle?: string;
    emptyText?: string; format?: (value: number) => string; time?: (tick: number) => string; sampleTime?: (tick: number) => string;
  } = $props();
  const data = $derived([...values.filter((value) => value !== null), ...secondary]);
  const low = $derived(data.length ? Math.min(...data) : 0);
  const high = $derived(data.length ? Math.max(...data) : 0);
  const padding = $derived(Math.max((high - low) * .08, Math.abs(high) * .004, data.length && high > low ? 0.0001 : 0.1));
  const minimum = $derived(low < 0 ? low - padding : Math.max(0, low - padding));
  const maximum = $derived(high + padding);
  const x = (index: number) => ticks.length === 1 ? 320 : 60 + index / Math.max(1, ticks.length - 1) * 575;
  const y = (value: number) => 170 - (value - minimum) / (maximum - minimum) * 151;
  const point = (value: number, index: number) => `${x(index)},${y(value)}`;
  let activeTick = $state<number>();
  const activeIndex = $derived(activeTick === undefined ? -1 : ticks.indexOf(activeTick));
  const primaryValue = $derived(values[activeIndex]);
  const secondaryValue = $derived(secondary[activeIndex]);

  function inspectPointer(event: PointerEvent) {
    const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    activeTick = ticks[Math.round(fraction * (ticks.length - 1))];
  }

  function inspectKey(event: KeyboardEvent) {
    const index = activeIndex < 0 ? ticks.length - 1 : activeIndex;
    const next = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: ticks.length - 1 }[event.key];
    if (event.key === 'Escape') activeTick = undefined;
    if (next === undefined) return;
    event.preventDefault();
    activeTick = ticks[Math.max(0, Math.min(ticks.length - 1, next))];
  }
  const series = $derived.by(() => {
    const spans: string[][] = [];
    let contiguous = false;
    values.forEach((value, index) => {
      if (value === null) { contiguous = false; return; }
      if (!contiguous) spans.push([]);
      spans[spans.length - 1].push(point(value, index));
      contiguous = true;
    });
    return spans;
  });
</script>

{#if data.length}
  {@const recorded = values.filter((value) => value !== null)}
  <figure class="chart">
  <svg viewBox="0 0 650 205" role="img" aria-label={t("{0}, {1} samples. Latest value {2}.", [title, recorded.length, format(recorded.at(-1) ?? 0)])}>
    {#each [0, .25, .5, .75, 1] as item}
      <line x1="60" x2="635" y1={170 - item * 151} y2={170 - item * 151} />
      <text x="51" y={174 - item * 151} text-anchor="end">{format(minimum + item * (maximum - minimum))}</text>
    {/each}
    {#each [0, .25, .5, .75, 1] as item}
      <line x1={60 + item * 575} x2={60 + item * 575} y1="19" y2="170" />
      {#if ticks.length >= 5 || item === 0}
        <text x={60 + item * 575} y="192" text-anchor={item === 1 ? 'end' : 'middle'}>{time(ticks[Math.floor(item * (ticks.length - 1))] ?? 0)}</text>
      {/if}
    {/each}
    {#if secondary.length}<polyline class="secondary" points={secondary.map(point).join(' ')} />{/if}
    {#each series as span}
      {#if span.length === 1}
        {@const [x, y] = span[0].split(',')}
        <circle cx={x} cy={y} r="4" />
      {:else}<polyline points={span.join(' ')} />{/if}
    {/each}
    {#if activeIndex >= 0}
      <line class="crosshair" x1={x(activeIndex)} x2={x(activeIndex)} y1="19" y2="170" />
      {#if primaryValue != null}<circle cx={x(activeIndex)} cy={y(primaryValue)} r="4" />{/if}
      {#if secondaryValue != null}<circle class="secondary-point" cx={x(activeIndex)} cy={y(secondaryValue)} r="4" />{/if}
    {/if}
  </svg>
  <button type="button" class="inspect" aria-label={t('Inspect chart samples for {0}', [title])}
    onfocus={() => activeTick ??= ticks.at(-1)} onblur={() => activeTick = undefined}
    onpointermove={inspectPointer} onpointerdown={inspectPointer}
    onpointerleave={(event) => { if (event.pointerType === 'mouse') activeTick = undefined; }} onkeydown={inspectKey}></button>
  {#if activeIndex >= 0}
    <output class="sample" style:left={`clamp(6px, ${x(activeIndex) / 6.5}% - 76px, 100% - min(208px, 100%))`}>
      <strong>{sampleTime(ticks[activeIndex])}</strong>
      {#if primaryValue != null}<span>{primaryTitle} · {format(primaryValue)}</span>{/if}
      {#if secondaryValue != null && secondaryTitle}<span>{secondaryTitle} · {format(secondaryValue)}</span>{/if}
      {#if primaryValue == null && secondaryValue == null}<span>{t('No sample recorded')}</span>{/if}
    </output>
  {/if}
  </figure>
{:else}
  <div class="chart-empty grid-bg"><p class="muted">{emptyText ?? t("Install Monitoring with Service history to view this chart.")}</p></div>
{/if}

<style>
  .chart { position: relative; margin: 0; min-width: 0; }
  .inspect { position: absolute; top: 9%; bottom: 17%; left: 9.23%; right: 2.31%; border: 0; background: transparent; cursor: crosshair; touch-action: pan-y; }
  .inspect:focus-visible { outline: 1px solid var(--primary); }
  .crosshair { stroke: var(--muted); stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; }
  .secondary-point { fill: #77b9ba; }
  .sample { display: grid; gap: 3px; position: absolute; z-index: 2; top: 0; max-width: min(202px, 100%); padding: 6px 9px; border: 1px solid var(--border); border-radius: 7px; background: var(--raised); box-shadow: 0 3px 12px #0006; font-size: 11px; pointer-events: none; }
  svg { display: block; width: 100%; overflow: visible; }
  line { stroke: var(--border); opacity: .62; }
  text { fill: var(--muted); font: 10px var(--mono); }
  polyline { fill: none; stroke: var(--primary); stroke-width: 2.5; vector-effect: non-scaling-stroke; }
  polyline.secondary { stroke: #77b9ba; stroke-dasharray: 5 4; }
  circle { fill: var(--primary); }
  .chart-empty { min-height: 155px; border: 1px solid var(--border); border-radius: 8px; display: grid; place-items: center; padding: 18px; text-align: center; }
  @media (max-width: 600px) {
    text { font-size: 17px; }
  }
</style>
