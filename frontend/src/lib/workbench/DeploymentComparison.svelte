<script lang="ts">
  import { t } from '../i18n.svelte';
  import type { Deployment, ResourcePressure } from '../types';
  import { ms, pct, preciseMoney, rps } from '../format';
  let { comparison }: { comparison: NonNullable<Deployment['comparison']> } = $props();
  const before = $derived(comparison.before);
  const after = $derived(comparison.after);
  const pressure = $derived(comparison.pressure_after);
  const formatPressure = (value: ResourcePressure) =>
    `${t(value.component)} · ${t(value.resource)} · ${pct(value.utilization)}`;
  const metrics = $derived([
    ['Incoming requests', rps(before.rps), rps(after.rps)],
    ['Successful requests', rps(before.throughput), rps(after.throughput)],
    ['Failed requests', rps(before.errors), rps(after.errors)],
    ['Rejected requests', rps(before.rejected), rps(after.rejected)],
    ['Average latency', ...(before.throughput && after.throughput ? [ms(before.latency), ms(after.latency)] : [])],
    ['Estimated p95 latency', ...(before.p95_latency != null && after.p95_latency != null ? [ms(before.p95_latency), ms(after.p95_latency)] : [])],
    ['Error rate', pct(before.errors / (before.rps || 1), 2), pct(after.errors / (after.rps || 1), 2)],
    ['Estimated capacity', ...(comparison.capacity_before != null && comparison.capacity_after != null
      ? [rps(comparison.capacity_before), rps(comparison.capacity_after)] : [])],
    ['Capacity headroom', ...(comparison.capacity_before != null && comparison.capacity_after != null
      ? [rps(comparison.capacity_before - before.rps), rps(comparison.capacity_after - after.rps)] : [])],
    ['Daily infrastructure', preciseMoney(comparison.daily_before), preciseMoney(comparison.daily_after)]
  ]);
  const displayed = $derived(metrics.filter((row) => row.length === 3).sort((a, b) => Number(a[1] === a[2]) - Number(b[1] === b[2])));
</script>

<div class="stack">
  <h3>{t("Deployment results")}</h3>
  <p class="muted">{t('Both configurations use the workload at deployment time.')}</p>
  <table>
    <thead><tr><th scope="col">{t("Metric")}</th><th scope="col">{t("Before")}</th><th scope="col">{t("After")}</th></tr></thead>
    <tbody>{#each displayed as [label, previous, current] (label)}
      <tr class:unchanged={previous === current}><th scope="row">{t(label)}</th><td class="mono">{previous}</td><td class="mono">{current}</td></tr>
    {/each}</tbody>
  </table>
  {#if comparison.pressure_before && pressure}
    <p class="muted">{t('Highest monitored load')} · {formatPressure(comparison.pressure_before)} → {formatPressure(pressure)}</p>
  {:else if pressure}
    <p class="muted">{t('Highest monitored load after deployment')} · {formatPressure(pressure)}</p>
  {/if}
  {#if comparison.capacity_before == null || comparison.capacity_after == null}
    <p class="muted">{t('A capacity comparison needs service history and measurable traffic in both configurations.')}</p>
  {:else}
    <p class="muted">{t('Estimated capacity is the request rate that can sustain 99% successful processing with the current workload mix.')}</p>
  {/if}
  {#if before.throughput <= 0 || after.throughput <= 0}
    <p class="muted">{t('Latency comparisons require successful requests in both configurations.')}</p>
  {/if}
  {#if rps(before.throughput) === rps(after.throughput)}
    {#if before.availability >= .99 && after.availability >= .99}
      <p class="muted">{t(comparison.capacity_before != null && comparison.capacity_after != null && comparison.capacity_after - comparison.capacity_before > 1
        ? 'Both configurations handled current demand. The new configuration has more room for future traffic.'
        : 'Both configurations handled current demand, so successful throughput stayed the same.')}</p>
    {:else if pressure && pressure.utilization >= 1}
      <p class="notice warn">{t('Successful throughput barely changed. {0} is at {1} load on {2}.',
        [t(pressure.component), pct(pressure.utilization), t(pressure.resource)])}</p>
    {:else}
      <p class="muted">{t("Successful throughput barely changed and availability remains low. Open Telemetry to inspect the remaining symptoms.")}</p>
    {/if}
  {/if}
</div>

<style>
  table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12px; }
  th, td { border-bottom: 1px solid var(--border); padding: 6px; overflow-wrap: anywhere; text-align: start; }
  th:first-child { width: 42%; }
  .unchanged { color: var(--muted); }
  tbody tr:not(.unchanged) td:last-child { font-weight: 700; }
</style>
