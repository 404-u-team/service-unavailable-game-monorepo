<script lang="ts">
  import type { Forecast } from '../types';
  import { ms, num, pct } from '../format';
  let { forecast }: { forecast: Forecast } = $props();
</script>
<section class="panel inset pad stack">
  <div class="row spread wrap"><h3>Capacity forecast</h3><span class="badge {forecast.confidence === 'low' ? 'warn' : 'good'}">{forecast.confidence} confidence</span></div>
  <dl>
    <div><dt>Incoming requests</dt><dd>{num(forecast.rps.low)}–{num(forecast.rps.high)} RPS</dd></div>
    <div><dt>Average latency</dt><dd>{ms(forecast.latency.low)}–{ms(forecast.latency.high)}</dd></div>
    <div><dt>Availability</dt><dd>{pct(forecast.availability.low, 1)}–{pct(forecast.availability.high, 1)}</dd></div>
    <div><dt>Active audience</dt><dd>{num(Math.round(forecast.audience.low))}–{num(Math.round(forecast.audience.high))}</dd></div>
  </dl>
</section>
<style>
  dl { margin: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; }
  dd { font-family: var(--mono); font-size: 12px; margin-top: 2px; }
  dt { font-size: 12px; }
</style>
