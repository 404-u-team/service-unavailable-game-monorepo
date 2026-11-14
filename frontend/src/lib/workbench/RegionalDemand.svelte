<script lang="ts">
  import { t } from '../i18n.svelte';
  import { minuteClock, num, pct, preciseMoney, rps } from '../format';
  import type { DemandOverview } from '../types';
  import Chart from './Chart.svelte';

  let { demand }: { demand: DemandOverview } = $props();
  const utc = (minutes: number) => `UTC${minutes < 0 ? '−' : '+'}${minuteClock(Math.abs(minutes))}`;
</script>

<div class="regional-demand">
  <section class="panel pad stack">
    <div>
      <h2>{t('Expected daily demand')}</h2>
      <p class="muted">{t('Baseline requests per second by UTC hour. Campaigns and events can lift live demand.')}</p>
    </div>
    <Chart title={t('Expected daily demand')} values={demand.expected} ticks={Array.from({ length: demand.expected.length }, (_, hour) => hour * 60)}
      time={(minute) => minute === 1440 ? '24:00' : minuteClock(minute)} />
  </section>
  <section class="panel inset pad stack">
    <div class="row spread wrap"><h2>{t('Regional traffic')}</h2><span class="mono" data-testid="game-utc-time">{t('Day {0} / {1}', [demand.day, minuteClock(demand.utc_minute)])} UTC</span></div>
    {#each demand.regions as region (region.id)}
      <div class="region">
        <div class="row spread wrap"><h3>{t(region.name)}</h3><strong class="mono">{rps(region.requests)}</strong></div>
        <p>{minuteClock(region.local_minute)} <span class="muted">({utc(region.utc_offset)})</span></p>
        <p class="muted">{t('{0} registered users', [num(region.audience)])} · {t('{0} DAU', [num(Math.round(region.daily_active_users))])}</p>
        {#if region.earned_ad_revenue}<p class="muted">{t('Ad revenue in the last game day: {0}', [preciseMoney(region.earned_ad_revenue)])}</p>{/if}
        {#if region.daily_ad_revenue}<p class="muted">{t('Potential ad revenue: {0}/day', [preciseMoney(region.daily_ad_revenue)])}</p>{/if}
      </div>
    {/each}
    {#if demand.campaign_lift}<p class="muted">{t('Campaign lift {0}', [pct(demand.campaign_lift, 1)])}</p>{/if}
    {#if demand.event_lift}<p class="notice warn">{t('Activity spike {0}', [pct(demand.event_lift, 1)])}</p>{/if}
  </section>
</div>

<style>
  .regional-demand { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; }
  .regional-demand section { min-width: 0; align-content: start; }
  .region { border-top: 1px solid var(--border); padding-top: 8px; }
  .region p { font-size: 13px; margin-top: 4px; }
  @media (max-width: 1000px) { .regional-demand { grid-template-columns: 1fr; } }
</style>
