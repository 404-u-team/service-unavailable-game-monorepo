<script lang="ts">
  import { t } from '../i18n.svelte';
  import { clock, num, pct, preciseMoney } from '../format';
  import type { Catalog, Game, OperatingCosts, RevenueSources } from '../types';
  import { target } from './onboarding';
  import Chart from './Chart.svelte';

  let { game, catalog }: { game: Game; catalog: Catalog } = $props();
  const economy = $derived(game.economy);
  const time = (tick: number) => clock(tick, game.start_minute, catalog.minutes_per_tick);
  const revenues: [keyof RevenueSources, string][] = [
    ['advertising', 'Advertising'],
    ['subscriptions', 'Premium subscriptions'],
    ['legacy', 'Revenue from earlier versions'],
  ];
  const expenses: [keyof OperatingCosts, string][] = [
    ['infrastructure', 'Infrastructure'],
    ['traffic', 'Traffic processing'],
    ['payments', 'Payment fees'],
    ['legacy', 'Operating costs from earlier versions'],
  ];
  const period = $derived(t('Daily rates use the last {0} of {1} game steps.', [economy.recorded_ticks, 1440 / catalog.minutes_per_tick]));
  const emptyText = $derived(t('Run the simulation to record financial activity.'));
  const currency = (value: number) => preciseMoney(value);
  const display = (value: number | null, format: (value: number) => string) => value === null ? '—' : format(value);
  const totalRevenue = $derived(economy.history.map(({ revenue }) => revenue.advertising + revenue.subscriptions));
  const totalCosts = $derived(economy.history.map(({ expenses }) => expenses.infrastructure + expenses.traffic + expenses.payments));
  const ticks = $derived(economy.history.map(({ tick }) => tick));
  let source = $state<keyof RevenueSources | 'total'>('total');
</script>

<div class="finance-cards">
  {#each [
    { label: 'Balance', value: currency(economy.balance), detail: t('{0} net to date', [currency(economy.profit)]), loss: economy.balance < 0 },
    { label: 'Revenue / day', value: currency(economy.daily_revenue), detail: t('{0} recognized to date', [currency(economy.revenue)]) },
    { label: 'Expenses / day', value: currency(economy.daily_total_expenses), detail: t('{0} operating costs', [currency(economy.daily_operating)]) },
    { label: 'Net profit / day', value: currency(economy.daily_net_profit), detail: t('Operating margin {0}', [display(economy.operating_margin, (value) => pct(value, 1))]), loss: economy.daily_net_profit < 0 },
    { label: 'Daily active users (DAU)', value: num(Math.round(economy.daily_active_users)), detail: t('{0} registered users', [num(game.audience)]) },
    { label: 'Revenue per DAU', value: display(economy.arpdau, (value) => preciseMoney(value, 4)), detail: t('ARPDAU') },
    { label: 'Operating cost per DAU', value: display(economy.cost_per_dau, (value) => preciseMoney(value, 4)), detail: t('Per game day') },
    ...(game.features.some((item) => item.id === 'premium' && item.state === 'released')
      ? [{ label: 'Paying subscribers', value: num(economy.subscribers), detail: t('{0} of registered users', [pct(economy.conversion, 1)]) }] : [])
  ] as item (item.label)}
    <section class="panel pad"><p class="eyebrow">{t(item.label)}</p><strong class="stat" class:danger={item.loss}>{item.value}</strong><small>{item.detail}</small></section>
  {/each}
</div>
<p class="muted">{t('DAU estimates how many registered users use Messenger in a game day.')} {economy.recorded_ticks ? period : emptyText} {t('One-time purchases show actual charges over that window.')}</p>

<div class="finance-split">
  <section class="panel pad stack">
    <h2 data-tutorial={target.finance}>{t('Revenue breakdown')}</h2>
    <div class="ledger">
      <table>
        <thead><tr><th scope="col">{t('Source')}</th><th scope="col">{t('Per game day')}</th><th scope="col">{t('To date')}</th></tr></thead>
        <tbody>
          {#each revenues as [key, label] (key)}
            {#if key !== 'legacy' || economy.revenue_sources.legacy > 0.005}
              <tr><th scope="row">{t(label)}</th><td>{currency(economy.daily_sources[key])}</td><td>{currency(economy.revenue_sources[key])}</td></tr>
            {/if}
          {/each}
        </tbody>
        <tfoot><tr><th scope="row">{t('Recognized revenue')}</th><td>{currency(economy.daily_revenue)}</td><td>{currency(economy.revenue)}</td></tr></tfoot>
      </table>
    </div>
    <p class="muted">{t('{0} served ad impressions per game day', [num(Math.round(economy.daily_ad_impressions))])}</p>
    {#if economy.daily_ad_impressions > 0}
      <p class="muted">{t('Average value per 1,000 served impressions {0}', [currency(economy.daily_sources.advertising * 1000 / economy.daily_ad_impressions)])}</p>
    {/if}
    <p class="muted">{t('Ads earn revenue when served. Subscriptions are paid up front and recognized over the paid term.')}</p>
    <label class="field"><span>{t('Revenue history')}</span>
      <select bind:value={source}>
        <option value="total">{t('Recognized revenue')}</option>
        {#each revenues.slice(0, 2) as [key, label]}<option value={key}>{t(label)}</option>{/each}
      </select>
    </label>
    <Chart title={t('Revenue per simulation step')} values={source === 'total' ? totalRevenue : economy.history.map((point) => point.revenue[source as keyof RevenueSources])} {ticks} {time} {emptyText} format={(value) => preciseMoney(value, 4)} />
  </section>

  <section class="panel pad stack">
    <h2 data-tutorial={target.expenses}>{t('Expense breakdown')}</h2>
    <div class="ledger">
      <table>
        <thead><tr><th scope="col">{t('Expense')}</th><th scope="col">{t('Per game day')}</th><th scope="col">{t('To date')}</th></tr></thead>
        <tbody>
          {#each expenses as [key, label] (key)}
            {#if key !== 'legacy' || economy.operating_costs.legacy > 0.005}
              <tr><th scope="row">{t(label)}</th><td>{currency(economy.daily_costs[key])}</td><td>{currency(economy.operating_costs[key])}</td></tr>
            {/if}
          {/each}
          <tr class="subtotal"><th scope="row">{t('Operating costs')}</th><td>{currency(economy.daily_operating)}</td><td>{currency(economy.operating)}</td></tr>
          <tr><th scope="row">{t('Development')}</th><td>{currency(economy.recent_purchases.development)}</td><td>{currency(economy.development)}</td></tr>
          <tr><th scope="row">{t('Marketing')}</th><td>{currency(economy.recent_purchases.marketing)}</td><td>{currency(economy.marketing)}</td></tr>
          <tr><th scope="row">{t('Deployments')}</th><td>{currency(economy.recent_purchases.deployment)}</td><td>{currency(economy.deployment)}</td></tr>
        </tbody>
        <tfoot><tr><th scope="row">{t('Total expenses')}</th><td>{currency(economy.daily_total_expenses)}</td><td>{currency(economy.operating + economy.development + economy.marketing + economy.deployment)}</td></tr></tfoot>
      </table>
    </div>
    <Chart title={t('Operating costs per simulation step')} values={totalCosts} {ticks} {time} {emptyText} format={(value) => preciseMoney(value, 4)} />
  </section>

  <section class="panel pad stack">
    <h2>{t('Cash flow')}</h2>
    <dl>
      <div><dt>{t('Starting capital')}</dt><dd>{currency(economy.starting_capital)}</dd></div>
      <div><dt>{t('Cash received to date')}</dt><dd>{currency(economy.cash_received)}</dd></div>
      <div><dt>{t('Prepaid subscription revenue remaining')}</dt><dd>{currency(economy.deferred_subscription_revenue)}</dd></div>
    </dl>
    <Chart title={t('Game balance')} values={game.business_history.map((point) => point.balance)} ticks={game.business_history.map((point) => point.tick)} {time} />
  </section>

  <section class="panel pad stack">
    <h2>{t('Production infrastructure')}</h2>
    <p class="muted">{t('Recurring prices use a {0}-day game month. Deployed components cost money even when idle.', [catalog.days_per_month])}</p>
    <div class="ledger">
      <table>
        <thead><tr><th scope="col">{t('Component')}</th><th scope="col">{t('Per game day')}</th><th scope="col">{t('Per game month')}</th></tr></thead>
        <tbody>
          {#each game.production.nodes as node (node.id)}
            {@const daily = game.component_costs[node.id] ?? 0}
            <tr><th scope="row">{t(node.name)}</th><td>{currency(daily)}</td><td>{currency(daily * catalog.days_per_month)}</td></tr>
          {/each}
        </tbody>
        <tfoot><tr><th scope="row">{t('Total')}</th><td>{currency(economy.daily_infrastructure)}</td><td>{currency(economy.daily_infrastructure * catalog.days_per_month)}</td></tr></tfoot>
      </table>
    </div>
  </section>
</div>

<style>
  .finance-cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
  .stat { display: block; font: 600 clamp(20px, 3vw, 29px) var(--mono); margin-block: 4px; overflow-wrap: anywhere; }
  .finance-split { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
  section { min-width: 0; align-content: start; }
  .ledger { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border-bottom: 1px solid var(--border); padding: 8px 5px; text-align: left; }
  th[scope="row"] { font-weight: normal; }
  th:not(:first-child), td { text-align: right; }
  td, dd { font-family: var(--mono); white-space: nowrap; }
  tfoot th[scope="row"], .subtotal th[scope="row"] { font-weight: 600; }
  dl { margin: 0; }
  dl div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 12px; padding: 8px 0; border-bottom: 1px solid var(--border); }
  dd { margin: 0; }
  @media (max-width: 1000px) { .finance-split { grid-template-columns: 1fr; } }
  @media (max-width: 740px) { .finance-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 340px) { .finance-cards { grid-template-columns: 1fr; } }
</style>
