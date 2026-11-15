<script lang="ts">
  import { chartDomain, chartValue, lineSegments, type ChartSeries } from './chart';

  let { title, labels, sampleLabels, series, kind = 'line', emptyLabel, missingLabel, sampleLabel, format = String }: {
    title: string;
    labels: readonly string[];
    sampleLabels?: readonly string[];
    series: readonly ChartSeries[];
    kind?: 'line' | 'bar';
    emptyLabel: string;
    missingLabel: string;
    sampleLabel: string;
    format?: (value: number) => string;
  } = $props();

  const uid = $props.id();
  const tooltipId = `${uid}-sample`;
  const color = (index: number) => `var(--sui-chart-${index % 4 + 1})`;
  const dash = (index: number) => ['', '6 4', '2 4', '10 4 2 4'][index % 4];
  const domain = $derived(chartDomain(series, labels.length, kind === 'bar'));
  const x = (index: number) => kind === 'bar'
    ? (index + 0.5) * 1000 / labels.length
    : labels.length === 1 ? 500 : index * 980 / (labels.length - 1) + 10;
  const y = (value: number) => domain ? 188 - (value - domain.min) / (domain.max - domain.min) * 176 : 188;
  const barWidth = $derived(Math.min(72, 750 / Math.max(1, labels.length * series.length)));
  let active = $state(-1);
  let keyboardSample = $state(-1);
  const activeIndex = $derived(active < labels.length ? active : -1);

  function inspect(event: PointerEvent & { currentTarget: HTMLElement }) {
    const box = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - box.left) / box.width));
    active = kind === 'bar'
      ? Math.min(labels.length - 1, Math.floor(ratio * labels.length))
      : Math.max(0, Math.min(labels.length - 1, Math.round((ratio * 1000 - 10) * (labels.length - 1) / 980)));
  }

  function inspectKeys(event: KeyboardEvent) {
    const last = labels.length - 1;
    const index = activeIndex < 0 ? last : activeIndex;
    const next = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: last }[event.key];
    if (event.key === 'Escape') active = keyboardSample = -1;
    if (next === undefined) return;
    event.preventDefault();
    active = keyboardSample = Math.max(0, Math.min(last, next));
  }

  function display(value: number | null | undefined) {
    const numeric = chartValue(value);
    return numeric === null ? missingLabel : format(numeric);
  }
</script>

<figure aria-labelledby={uid}>
  <figcaption id={uid}>{title}</figcaption>
  {#if domain}
    <div class="plot">
      <div class="scale" aria-hidden="true">
        {#each [1, 0.5, 0] as fraction}
          <span>{format(domain.min + (domain.max - domain.min) * fraction)}</span>
        {/each}
      </div>
      <div class="canvas">
        <svg class="graphic" viewBox="0 0 1000 200" preserveAspectRatio="none" aria-hidden="true">
          {#each [12, 56, 100, 144, 188] as row}
            <line class="grid-line" x1="0" x2="1000" y1={row} y2={row} />
          {/each}
          {#if kind === 'bar' && domain.min < 0 && domain.max > 0}
            <line class="zero-line" x1="0" x2="1000" y1={y(0)} y2={y(0)} />
          {/if}
          {#if activeIndex >= 0}
            <line class="crosshair" x1={x(activeIndex)} x2={x(activeIndex)} y1="12" y2="188" />
          {/if}
          {#each series as item, index (item.id)}
            {#if kind === 'line'}
              {#each lineSegments(item.values, labels.length, x, y) as segment}
                {#if segment.length > 1}
                  <polyline fill="none" stroke={color(index)} stroke-dasharray={dash(index)}
                    points={segment.map((point) => `${point.x},${point.y}`).join(' ')} />
                {:else}
                  <path stroke={color(index)} d={`M${segment[0].x},${segment[0].y}h0.01`} />
                {/if}
              {/each}
            {:else}
              {#each item.values.slice(0, labels.length) as value, bin}
                {@const sample = chartValue(value)}
                {#if sample !== null}
                  <rect x={x(bin) + (index - series.length / 2) * barWidth} y={Math.min(y(0), y(sample))}
                    width={barWidth * 0.88} height={Math.abs(y(sample) - y(0))} fill={color(index)} />
                {/if}
              {/each}
            {/if}
          {/each}
        </svg>
        <button class="sui-focus inspect" type="button" aria-label={sampleLabel} aria-describedby={activeIndex >= 0 ? tooltipId : undefined}
          onfocus={() => { if (activeIndex < 0) active = keyboardSample = labels.length - 1; }}
          onblur={() => active = keyboardSample = -1} onkeydown={inspectKeys}
          onpointermove={(event) => { if (event.pointerType !== 'touch') inspect(event); }}
          onpointerdown={inspect}
          onpointerleave={(event) => { if (event.pointerType === 'mouse' && document.activeElement !== event.currentTarget) active = -1; }}></button>
        {#if activeIndex >= 0}
          <div id={tooltipId} class="sui-tooltip sample" role="tooltip"
            style:--point={`${x(activeIndex) / 10}%`} class:before={x(activeIndex) > 500}>
            <strong>{sampleLabels?.[activeIndex] ?? labels[activeIndex]}</strong>
            <dl>
              {#each series as item, index (item.id)}
                <div><dt><span style:background={color(index)} aria-hidden="true"></span>{item.label}</dt><dd>{display(item.values[activeIndex])}</dd></div>
              {/each}
            </dl>
          </div>
        {/if}
      </div>
      <div class="axis" aria-hidden="true"><span>{labels[0]}</span>{#if labels.length > 1}<span>{labels.at(-1)}</span>{/if}</div>
    </div>
    <ul class="legend">
      {#each series as item, index (item.id)}
        <li><svg viewBox="0 0 22 8" width="22" height="8" aria-hidden="true">
          {#if kind === 'line'}<line x1="0" x2="22" y1="4" y2="4" stroke={color(index)} stroke-width="2" stroke-dasharray={dash(index)} />
          {:else}<rect x="3" width="16" height="8" fill={color(index)} />{/if}
        </svg>{item.label}</li>
      {/each}
    </ul>
    <div class="sui-sr-only" aria-live="polite">
      {#if keyboardSample >= 0 && keyboardSample < labels.length}
        {labels[keyboardSample]}.
        {#each series as item (item.id)}{item.label} · {display(item.values[keyboardSample])}. {/each}
      {/if}
    </div>
  {:else}
    <p class="empty">{emptyLabel}</p>
  {/if}
</figure>

<style>
  figure { display: grid; gap: var(--sui-space-2); margin: 0; min-inline-size: 0; color: var(--sui-text); font: var(--sui-body); }
  figcaption { font: 700 1rem/1.35 var(--sui-heading); overflow-wrap: anywhere; }
  ul { display: flex; flex-wrap: wrap; gap: var(--sui-space-1) var(--sui-space-4); list-style: none; padding: 0; margin: 0; }
  li { display: inline-flex; align-items: center; gap: var(--sui-space-2); color: var(--sui-muted); overflow-wrap: anywhere; }
  li svg { flex: none; }
  .plot { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--sui-space-1) var(--sui-space-2); }
  .scale, .axis { color: var(--sui-muted); font: var(--sui-caption); overflow-wrap: anywhere; }
  .scale { display: flex; flex-direction: column; justify-content: space-between; text-align: end; max-inline-size: min(6rem, 26vw); padding-block: 0.375rem; }
  .axis { display: flex; justify-content: space-between; grid-column: 2; gap: var(--sui-space-2); }
  .axis span:last-child { text-align: end; }
  .canvas { position: relative; background: var(--sui-inset); border-radius: var(--sui-radius); }
  .graphic { display: block; inline-size: 100%; block-size: clamp(8rem, 26vw, 13rem); overflow: visible; }
  .grid-line { stroke: var(--sui-border); }
  .zero-line { stroke: var(--sui-control-border); }
  .crosshair { stroke: var(--sui-muted); stroke-dasharray: 4 3; }
  line, polyline, path { vector-effect: non-scaling-stroke; }
  polyline { stroke-width: 2; }
  path { stroke-width: 5; stroke-linecap: round; }
  .inspect { position: absolute; inset: 0; padding: 0; border: 0; border-radius: var(--sui-radius); background: transparent; cursor: crosshair; touch-action: pan-y; }
  .sample {
    --sample-width: min(13rem, calc(100% - 8px));
    --sample-left: calc(var(--point) + 8px);
    position: absolute; inset-block-start: var(--sui-space-2);
    left: clamp(4px, var(--sample-left), calc(100% - var(--sample-width) - 4px));
    inline-size: var(--sample-width); pointer-events: none;
    z-index: 1; font: var(--sui-caption); padding: var(--sui-space-2);
  }
  .sample.before { --sample-left: calc(var(--point) - var(--sample-width) - 8px); }
  dl { display: grid; gap: var(--sui-space-1); margin: var(--sui-space-1) 0 0; }
  dl div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0 var(--sui-space-2); }
  dt { color: var(--sui-muted); }
  dt span { display: inline-block; inline-size: 0.5rem; block-size: 0.5rem; margin-inline-end: var(--sui-space-1); border-radius: 50%; }
  dd { margin: 0; }
  .empty { margin: 0; padding: var(--sui-space-6); border: 1px dashed var(--sui-control-border); border-radius: var(--sui-radius); color: var(--sui-muted); text-align: center; }
</style>
