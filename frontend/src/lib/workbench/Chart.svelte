<script lang="ts">
  import { clock, num } from '../format';
  let { title, values, ticks, secondary = [] }: { title: string; values: number[]; ticks: number[]; secondary?: number[] } = $props();
  const data = $derived([...values, ...secondary]);
  const low = $derived(data.length ? Math.min(...data) : 0);
  const high = $derived(data.length ? Math.max(...data) : 0);
  const padding = $derived(Math.max((high - low) * .08, Math.abs(high) * .004, 0.1));
  const minimum = $derived(low < 0 ? low - padding : Math.max(0, low - padding));
  const maximum = $derived(high + padding);
  const point = (value: number, index: number) => `${values.length === 1 ? 320 : 60 + index / Math.max(1, values.length - 1) * 575},${170 - (value - minimum) / (maximum - minimum) * 151}`;
</script>

{#if values.length}
  <svg viewBox="0 0 650 205" role="img" aria-label={`${title}, ${values.length} samples. Latest value ${num(values.at(-1) ?? 0)}.`}>
    {#each [0, .25, .5, .75, 1] as item}
      <line x1="60" x2="635" y1={170 - item * 151} y2={170 - item * 151} />
      <text x="51" y={174 - item * 151} text-anchor="end">{num(minimum + item * (maximum - minimum))}</text>
    {/each}
    {#each [0, .25, .5, .75, 1] as item}
      <line x1={60 + item * 575} x2={60 + item * 575} y1="19" y2="170" />
      {#if ticks.length >= 5 || item === 0}
        <text x={60 + item * 575} y="192" text-anchor={item === 1 ? 'end' : 'middle'}>{clock(ticks[Math.floor(item * (ticks.length - 1))] ?? 0)}</text>
      {/if}
    {/each}
    {#if values.length === 1}<circle cx={point(values[0], 0).split(',')[0]} cy={point(values[0], 0).split(',')[1]} r="4" />{/if}
    {#if secondary.length}<polyline class="secondary" points={secondary.map(point).join(' ')} />{/if}
    <polyline points={values.map(point).join(' ')} />
  </svg>
{:else}
  <div class="chart-empty grid-bg"><p class="muted">Install Monitoring with Service history to view this chart.</p></div>
{/if}

<style>
  svg { display: block; width: 100%; overflow: visible; }
  line { stroke: var(--border); opacity: .62; }
  text { fill: var(--muted); font: 10px var(--mono); }
  polyline { fill: none; stroke: var(--primary); stroke-width: 2.5; vector-effect: non-scaling-stroke; }
  polyline.secondary { stroke: #77b9ba; stroke-dasharray: 5 4; }
  circle { fill: var(--primary); }
  .chart-empty { min-height: 155px; border: 1px solid var(--border); border-radius: 8px; display: grid; place-items: center; padding: 18px; text-align: center; }
</style>
