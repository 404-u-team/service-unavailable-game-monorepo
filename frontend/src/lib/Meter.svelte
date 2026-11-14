<script lang="ts">
  import { pct } from './format';
  let { value, label, show = true, tone }: { value: number; label: string; show?: boolean; tone?: string } = $props();
  const fill = $derived(Number.isFinite(value) ? Math.min(100, Math.max(0, value * 100)) : 0);
  const color = $derived(tone ?? (value >= 1 ? 'bad' : value >= 0.78 ? 'warn' : 'good'));
</script>

{#if show}<div class="row spread meter-label"><span>{label}</span><strong>{pct(value)}</strong></div>{/if}
<span class="meter {color}" role="meter" aria-label={label} aria-valuenow={fill} aria-valuetext={pct(value)} aria-valuemin={0} aria-valuemax={100}>
  <span style:width={`${fill}%`}></span>
</span>

<style>
  .meter-label { font: 400 12px var(--mono); margin-bottom: 6px; }
  .meter-label strong { font-family: inherit; }
</style>
