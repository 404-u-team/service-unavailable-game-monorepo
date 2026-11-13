<script lang="ts">
  import { t } from '../i18n.svelte';
  import type { Forecast } from '../types';
  import { ms, num, pct } from '../format';
  let { forecast }: { forecast: Forecast } = $props();
</script>
<section class="panel inset pad stack">
  <div class="row spread wrap"><h3>{t("Capacity forecast")}</h3><span class="badge {forecast.confidence === 'low' ? 'warn' : 'good'}">{t(forecast.confidence)} {t("confidence")}</span></div>
  <dl>
    <div><dt>{t("Incoming requests")}</dt><dd>{t('{0}–{1} RPS', [num(forecast.rps.low), num(forecast.rps.high)])}</dd></div>
    <div><dt>{t("Average latency")}</dt><dd>{ms(forecast.latency.low)}–{ms(forecast.latency.high)}</dd></div>
    <div><dt>{t("Availability")}</dt><dd>{pct(forecast.availability.low, 1)}–{pct(forecast.availability.high, 1)}</dd></div>
    <div><dt>{t("Active audience")}</dt><dd>{num(Math.round(forecast.audience.low))}–{num(Math.round(forecast.audience.high))}</dd></div>
  </dl>
</section>
<style>
  dl { margin: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; }
  dd { font-family: var(--mono); font-size: 12px; margin-top: 2px; }
  dt { font-size: 12px; }
</style>
