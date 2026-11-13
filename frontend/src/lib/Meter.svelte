<script lang="ts">
  import { pct } from './format';
  let { value, label, show = true, tone }: { value: number; label: string; show?: boolean; tone?: string } = $props();
  const color = $derived(tone ?? (value >= 1 ? 'bad' : value >= 0.78 ? 'warn' : 'good'));
</script>

{#if show}<div class="row spread meter-label"><span>{label}</span><strong>{pct(value)}</strong></div>{/if}
<span class="meter {color}" role="meter" aria-label={label} aria-valuenow={Math.min(100, Math.max(0, Math.round(value * 100)))} aria-valuetext={pct(value)} aria-valuemin={0} aria-valuemax={100}>
  <span style:width={pct(Math.min(1, Math.max(0, value)), 2)}></span>
</span>

<style>
  .meter-label { font: 400 12px var(--mono); margin-bottom: 6px; }
  .meter-label strong { font-family: inherit; }
</style>
