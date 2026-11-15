<script lang="ts">
  import { t } from '../i18n.svelte';
  import { minuteClock, num, pct, preciseMoney, rps } from '../format';
  import type { DemandOverview, Market } from '../types';
  import Chart from './Chart.svelte';
  import Select from '../controls/Select.svelte';

  let { demand, markets }: { demand: DemandOverview; markets: Market[] } = $props();
  const utc = (minutes: number) => `UTC${minutes < 0 ? '−' : '+'}${minuteClock(Math.abs(minutes))}`;
  let sort = $state('requests');
  const regions = $derived([...demand.regions].sort((a, b) => sort === 'name' ? t(a.name).localeCompare(t(b.name))
    : sort === 'audience' ? b.audience - a.audience : b.requests - a.requests));
</script>

<div class="regional-demand">
  <section class="stack">
    <div>
      <h2>{t('Expected daily demand')}</h2>
      <p class="muted">{t('Baseline requests per second by UTC hour. Campaigns and events can lift live demand.')}</p>
    </div>
    <Chart title={t('Expected daily demand')} values={demand.expected} ticks={Array.from({ length: demand.expected.length }, (_, hour) => hour * 60)}
      format={rps} time={minuteClock}
      sampleTime={(minute) => `${t('Day {0} / {1}', [demand.day + Math.floor(minute / 1440), minuteClock(minute % 1440)])} UTC`} />
    {#if demand.campaign_lift}<p class="muted">{t('Campaign lift {0}', [pct(demand.campaign_lift, 1)])}</p>{/if}
    {#if demand.event_lift}<p class="notice warn">{t('Activity spike {0}', [pct(demand.event_lift, 1)])}</p>{/if}
  </section>
  <section class="stack">
    <div class="row spread wrap"><h2>{t('Regional traffic')}</h2><span class="mono" data-testid="game-utc-time">{t('Day {0} / {1}', [demand.day, minuteClock(demand.utc_minute)])} UTC</span></div>
    <div class="sort"><Select label={t('Sort regions')} bind:value={sort} options={[
      { value: 'requests', label: t('Request rate') }, { value: 'audience', label: t('Registered users') }, { value: 'name', label: t('Region name') }
    ]} /></div>
    <div class="regions">
      {#each regions as region (region.id)}
        <details>
          <summary>
            <strong>{t(region.name)}</strong><span class="muted mono">{minuteClock(region.local_minute)}</span><strong class="mono">{rps(region.requests)}</strong>
          </summary>
          <dl>
            <div><dt>{t('Market status')}</dt><dd>{t(markets.find((market) => market.id === region.id)?.stage === 'active' ? 'Active' : 'Inactive')}</dd></div>
            <div><dt>{t('Local time')}</dt><dd>{minuteClock(region.local_minute)} ({utc(region.utc_offset)})</dd></div>
            <div><dt>{t('Registered users')}</dt><dd>{num(region.audience)}</dd></div>
            <div><dt>{t('Daily active users (DAU)')}</dt><dd>{num(Math.round(region.daily_active_users))}</dd></div>
            {#if region.earned_ad_revenue}<div><dt>{t('Ad revenue in the last game day')}</dt><dd>{preciseMoney(region.earned_ad_revenue)}</dd></div>{/if}
          </dl>
        </details>
      {/each}
    </div>
  </section>
</div>

<style>
  .regional-demand { container-type: inline-size; }
  .regional-demand { display: flex; flex-wrap: wrap; gap: 20px; align-items: start; }
  .regional-demand section { min-width: 0; flex: 1 1 17rem; align-content: start; }
  .sort { max-width: 190px; }
  .regions { max-height: 280px; overflow-y: auto; overscroll-behavior: contain; }
  details { border-top: 1px solid var(--border); padding: 8px 3px; font-size: 13px; }
  summary { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 8px; align-items: center; cursor: pointer; }
  summary strong:first-child::before { content: '▸ '; color: var(--muted); }
  details[open] summary strong:first-child::before { content: '▾ '; }
  dl { margin: 6px 0 2px 8px; }
  dl div { display: flex; justify-content: space-between; gap: 10px; padding: 4px 1px; }
  dd { margin: 0; text-align: end; font-family: var(--mono); }
</style>
