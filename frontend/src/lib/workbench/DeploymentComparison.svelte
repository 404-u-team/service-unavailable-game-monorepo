<script lang="ts">
  import { t } from '../i18n.svelte';
  import type { Deployment } from '../types';
  import { ms, pct, preciseMoney, rps } from '../format';
  let { comparison }: { comparison: NonNullable<Deployment['comparison']> } = $props();
  const before = $derived(comparison.before);
  const after = $derived(comparison.after);
  const metrics = $derived([
    ['Successful requests', rps(before.throughput), rps(after.throughput)],
    ['Average latency', ms(before.latency), ms(after.latency)],
    ['Error rate', pct(before.errors / (before.rps || 1), 2), pct(after.errors / (after.rps || 1), 2)],
    ['Daily infrastructure', preciseMoney(comparison.daily_before), preciseMoney(comparison.daily_after)]
  ]);
</script>

<div class="stack">
  <h3>{t("Deployment results")}</h3>
  <table>
    <thead><tr><th scope="col">{t("Metric")}</th><th scope="col">{t("Before")}</th><th scope="col">{t("After")}</th></tr></thead>
    <tbody>{#each metrics as [label, previous, current]}
      <tr><th scope="row">{label}</th><td class="mono">{previous}</td><td class="mono">{current}</td></tr>
    {/each}</tbody>
  </table>
  {#if after.availability < .95 && after.throughput <= before.throughput + 1}
    <p class="muted">{t("Successful throughput barely changed and availability remains low. Open Telemetry to inspect the remaining symptoms.")}</p>
  {/if}
</div>

<style>
  table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12px; }
  th, td { border-bottom: 1px solid var(--border); padding: 5px; overflow-wrap: anywhere; text-align: start; }
  th:first-child { width: 42%; }
</style>
