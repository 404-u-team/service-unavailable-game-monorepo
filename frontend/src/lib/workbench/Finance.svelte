<script lang="ts">
  import type { Snippet } from 'svelte';
  import { Disclosure, PageColumns, Stat } from '@service-unavailable/ui';
  import GameDashboard from './GameDashboard.svelte';
  import { t } from '../i18n.svelte';
  import { clock, num, pct, preciseMoney, when } from '../format';
  import type { Catalog, Game, OperatingCosts, RevenueSources } from '../types';
  import { target } from './onboarding';
  import Select from '../controls/Select.svelte';
  import Chart from './Chart.svelte';

  let { game, catalog, tools }: { game: Game; catalog: Catalog; tools: Snippet } = $props();
  const economy = $derived(game.economy);
  let board = $state<{ showWidget: (id: string) => void }>();

  export function showWidget(id: string) {
    board?.showWidget(id);
  }
  const time = (tick: number) => clock(tick, game.start_minute, catalog.minutes_per_tick);
  const sampleTime = (tick: number) => when(tick, game.start_minute, catalog.minutes_per_tick);
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
  const totalRevenue = $derived(economy.history.map(({ revenue }) => revenue.advertising + revenue.subscriptions + revenue.legacy));
  const totalCosts = $derived(economy.history.map(({ expenses }) => expenses.infrastructure + expenses.traffic + expenses.payments + expenses.legacy));
  const ticks = $derived(economy.history.map(({ tick }) => tick));
  let source = $state<keyof RevenueSources | 'total'>('total');
  const metrics = $derived([
    { label: 'Balance', value: currency(economy.balance), detail: t('{0} net to date', [currency(economy.profit)]), loss: economy.balance < 0 },
    { label: 'Revenue / day', value: currency(economy.daily_revenue), detail: t('{0} recognized to date', [currency(economy.revenue)]) },
    { label: 'Operating costs / day', value: currency(economy.daily_operating), detail: t('{0} operating costs to date', [currency(economy.operating)]) },
    { label: 'Operating profit / day', value: currency(economy.daily_profit), detail: t('Operating margin {0}', [display(economy.operating_margin, (value) => pct(value, 1))]), loss: economy.daily_profit < 0 },
    { label: 'Daily active users (DAU)', value: num(Math.round(economy.daily_active_users)), detail: t('{0} registered users', [num(game.audience)]) },
    { label: 'Revenue per DAU', value: display(economy.arpdau, (value) => preciseMoney(value, 4)), detail: t('ARPDAU') },
    { label: 'Operating cost per DAU', value: display(economy.cost_per_dau, (value) => preciseMoney(value, 4)), detail: t('Per game day') },
    ...(game.features.some((item) => item.id === 'premium' && item.state === 'released')
      ? [{ label: 'Paying subscribers', value: num(economy.subscribers), detail: t('{0} of registered users', [pct(economy.conversion, 1)]) }] : [])
  ]);
</script>

{#snippet stats(start: number, end: number)}
  <PageColumns columns={2} minWidth="6rem" gap="12px">
    {#each metrics.slice(start, end) as item (item.label)}
      <Stat label={t(item.label)} value={item.value} detail={item.detail} tone={item.loss ? 'danger' : 'neutral'} compact />
    {/each}
  </PageColumns>
{/snippet}

{#snippet position()}{@render stats(0, 2)}{/snippet}
{#snippet costs()}{@render stats(2, 4)}{/snippet}
{#snippet users()}{@render stats(4, 8)}{/snippet}
{#snippet receipts()}<Stat value={currency(economy.cash_received)} compact />{/snippet}
{#snippet purchases()}<Stat value={currency(economy.daily_total_expenses - economy.daily_operating)} compact />{/snippet}

{#snippet revenue()}
  <div class="stack" data-tutorial={target.finance}>
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
    <div class="field"><span>{t('Revenue history')}</span>
      <Select label={t('Revenue history')} value={source} onchange={(value) => source = value as typeof source}
        options={[{ value: 'total', label: t('Recognized revenue') }, ...revenues.slice(0, 2).map(([value, label]) => ({ value, label: t(label) }))]} />
    </div>
    <Chart title={t('Revenue per simulation step')} values={source === 'total' ? totalRevenue : economy.history.map((point) => point.revenue[source as keyof RevenueSources])} {ticks} {time} {sampleTime} {emptyText} format={(value) => preciseMoney(value, 4)} />
  </div>
{/snippet}

{#snippet expensesWidget()}
  <div class="stack" data-tutorial={target.expenses}>
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
        </tbody>
      </table>
    </div>
    <Chart title={t('Operating costs per simulation step')} values={totalCosts} {ticks} {time} {sampleTime} {emptyText} format={(value) => preciseMoney(value, 4)} />
  </div>
{/snippet}

{#snippet cash()}
  <div class="stack">
    <dl>
      <div><dt>{t('Starting capital')}</dt><dd>{currency(economy.starting_capital)}</dd></div>
      <div><dt>{t('Cash received to date')}</dt><dd>{currency(economy.cash_received)}</dd></div>
      <div><dt>{t('Subscription cash receipts')}</dt><dd>{currency(economy.subscription_cash)}</dd></div>
      <div><dt>{t('Operating costs paid')}</dt><dd>−{currency(economy.operating)}</dd></div>
      {#each [['Development', economy.development], ['Marketing', economy.marketing], ['Deployments', economy.deployment]] as [label, amount] (label)}
        <div><dt>{t(String(label))}</dt><dd>−{currency(Number(amount))}</dd></div>
      {/each}
      <div><dt>{t('Prepaid subscription revenue remaining')}</dt><dd>{currency(economy.deferred_subscription_revenue)}</dd></div>
    </dl>
    {#if economy.purchases?.length}
      <Disclosure label={t('Recent purchases')}>
        <dl>
          {#each economy.purchases as [tick, costs] (tick)}
            {#each [['Development', costs.development], ['Marketing', costs.marketing], ['Deployments', costs.deployment]] as [label, amount] (label)}
              {#if Number(amount) > 0}<div><dt>{sampleTime(tick)} · {t(String(label))}</dt><dd>−{currency(Number(amount))}</dd></div>{/if}
            {/each}
          {/each}
        </dl>
      </Disclosure>
    {/if}
    <Chart title={t('Game balance')} values={game.business_history.map((point) => point.balance)} ticks={game.business_history.map((point) => point.tick)} {time} {sampleTime} {emptyText} format={currency} />
  </div>
{/snippet}

{#snippet profit()}
  <div class="stack">
    <Chart title={t('Operating profit per simulation step')} values={totalRevenue.map((revenue, index) => revenue - totalCosts[index])} {ticks} {time} {sampleTime} {emptyText} format={(value) => preciseMoney(value, 4)} />
  </div>
{/snippet}

{#snippet infrastructure()}
  <div class="stack">
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
  </div>
{/snippet}

<GameDashboard bind:this={board} gameId={game.id} section="finance" title={t('Finance')} {tools} widgets={[
  { id: 'balance', title: t('Cash and revenue'), placement: { x: 0, y: 0, width: 4, height: 3 }, content: position },
  { id: 'daily-operations', title: t('Daily operations'), placement: { x: 4, y: 0, width: 4, height: 3 }, content: costs },
  { id: 'unit-economics', title: t('Unit economics'), placement: { x: 8, y: 0, width: 4, height: 5 }, content: users },
  { id: 'receipts', title: t('Cash received to date'), placement: { x: 0, y: 3, width: 4, height: 2 }, content: receipts },
  { id: 'one-time', title: t('One-time purchases'), placement: { x: 4, y: 3, width: 4, height: 2 }, content: purchases },
  { id: 'revenue', title: t('Revenue breakdown'), placement: { x: 0, y: 5, width: 6, height: 11 }, content: revenue },
  { id: 'expenses', title: t('Expense breakdown'), placement: { x: 6, y: 5, width: 6, height: 8 }, content: expensesWidget },
  { id: 'profit', title: t('Operating profit'), placement: { x: 6, y: 13, width: 6, height: 6 }, content: profit },
  { id: 'cash-flow', title: t('Cash flow'), placement: { x: 0, y: 16, width: 6, height: 11 }, content: cash },
  { id: 'infrastructure', title: t('Production infrastructure'), placement: { x: 6, y: 19, width: 6, height: 8 }, content: infrastructure }
]} />
<p class="muted">{t('DAU estimates how many registered users use Messenger in a game day.')} {economy.recorded_ticks ? period : emptyText} {t('One-time purchases show actual charges over that window.')}</p>


<style>
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
</style>
