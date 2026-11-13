<script lang="ts">
  import { t } from '../i18n.svelte';
  import type { Deployment, ResourcePressure } from '../types';
  import { ms, pct, preciseMoney, rps } from '../format';
  let { comparison }: { comparison: NonNullable<Deployment['comparison']> } = $props();
  const before = $derived(comparison.before);
  const after = $derived(comparison.after);
  const pressure = $derived(comparison.pressure_after);
  const formatPressure = (value?: ResourcePressure | null) => value
    ? `${t(value.component)} · ${t(value.resource)} · ${pct(value.utilization)}`
    : '—';
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
  {#if comparison.pressure_before || pressure}
    <p class="muted">{t('Highest monitored load')} · {formatPressure(comparison.pressure_before)} → {formatPressure(pressure)}</p>
  {/if}
  {#if after.availability < .95 && after.throughput <= before.throughput + 1}
    {#if pressure && pressure.utilization >= 1}
      <p class="notice warn">{t('Successful throughput barely changed. {0} is at {1} load on {2}.',
        [t(pressure.component), pct(pressure.utilization), t(pressure.resource)])}</p>
    {:else}
      <p class="muted">{t("Successful throughput barely changed and availability remains low. Open Telemetry to inspect the remaining symptoms.")}</p>
    {/if}
  {/if}
</div>

<style>
  table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12px; }
  th, td { border-bottom: 1px solid var(--border); padding: 5px; overflow-wrap: anywhere; text-align: start; }
  th:first-child { width: 42%; }
</style>
