<script lang="ts">
  import type { Tone } from './types';

  let { label, value, detail, tone = 'neutral', compact = false }: {
    label?: string; value: string | number; detail?: string; tone?: Tone; compact?: boolean;
  } = $props();
</script>

<div class:compact data-sui-tone={tone}>
  {#if label}<span class="label">{label}</span>{/if}
  <strong>{value}</strong>
  {#if detail}<span class="detail">{detail}</span>{/if}
</div>

<style>
  div { display: grid; justify-items: start; align-content: start; gap: var(--sui-space-1); min-inline-size: 0; overflow-wrap: anywhere; }
  strong { color: var(--sui-tone-text); font: 600 clamp(1.125rem, 3vw, 1.875rem)/1.15 var(--sui-mono); font-variant-numeric: tabular-nums; }
  .label { color: var(--sui-muted); font: var(--sui-caption); }
  .detail { color: var(--sui-muted); font: var(--sui-body); font-size: 0.8125rem; }
  .compact strong { font-size: 1.125rem; }
</style>
