<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Activity, ArrowDownToLine, ArrowUpFromLine, Cpu, Layers3, Radio, Timer } from '@lucide/svelte';
  import {
    Alert, Button, Chart, Dashboard, Disclosure, FormField, Meter, Switch, Textarea, parseDashboardState,
    type DashboardState, type DashboardWidgetDefinition, type DashboardWidgetState
  } from '@service-unavailable/ui';
  import { formatNumber, t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Patterns/Dashboard' });
</script>

<script lang="ts">
  import { onMount } from 'svelte';

  const key = 'sui-storybook-infrastructure-dashboard';
  let imported = $state.raw<DashboardState | null>();
  let dashboard: ReturnType<typeof Dashboard> | undefined = $state();
  let json = $state('');
  let importError = $state(false);
  let status = $state('');

  onMount(() => {
    const restored = parseDashboardState(localStorage.getItem(key));
    if (restored) imported = restored;
  });

  const labels = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00'];
  const demand = [92, 125, 171, null, 183, 229, 246];
  const capacity = [165, 165, 180, 210, 210, 235, 265];
  const chartCopy = $derived({
    emptyLabel: t('No measurements available.'),
    missingLabel: t('No sample recorded'),
    sampleLabel: t('Inspect samples'),
    format: formatNumber
  });

  const widgets: DashboardWidgetDefinition[] = $derived([
    { id: 'traffic', title: t('Incoming traffic'), placement: { x: 0, y: 0, width: 4, height: 2 }, minHeight: 2, content: traffic },
    { id: 'availability', title: t('Availability'), placement: { x: 4, y: 0, width: 4, height: 2 }, minHeight: 2, content: availability },
    { id: 'latency', title: t('Response time'), placement: { x: 8, y: 0, width: 4, height: 2 }, minHeight: 2, content: latency },
    {
      id: 'history', title: t('Request history'), content: history, settings: historySettings,
      defaultSettings: { compareCapacity: true }, placement: { x: 0, y: 2, width: 8, height: 7 }, minWidth: 6, minHeight: 4
    },
    {
      id: 'utilization', title: t('Server utilization'), content: utilization,
      placement: { x: 8, y: 2, width: 4, height: 7 }, minWidth: 3, minHeight: 3
    },
    {
      id: 'cash', title: t('Daily cash flow'), content: cash, initiallyHidden: true,
      placement: { x: 0, y: 9, width: 8, height: 7 }, minWidth: 6, minHeight: 4
    }
  ]);

  function store(state: DashboardState) {
    localStorage.setItem(key, JSON.stringify(state));
  }

  function restore() {
    const parsed = parseDashboardState(json);
    importError = !parsed;
    status = parsed ? 'Dashboard restored.' : '';
    if (parsed) {
      imported = parsed;
      store(parsed);
    }
  }
</script>

{#snippet traffic(_widget: DashboardWidgetState)}
  <div class="reading">
    <Activity size={20} aria-hidden="true" /><span>{formatNumber(246)} <small>{t('req/s')}</small></span>
  </div>
{/snippet}

{#snippet availability(_widget: DashboardWidgetState)}
  <div class="reading">
    <Radio size={20} aria-hidden="true" /><span>{formatNumber(99.8)}<small>%</small></span>
  </div>
{/snippet}

{#snippet latency(_widget: DashboardWidgetState)}
  <div class="reading">
    <Timer size={20} aria-hidden="true" /><span>{formatNumber(42)} <small>{t('ms')}</small></span>
  </div>
{/snippet}

{#snippet history(widget: DashboardWidgetState)}
  <Chart {...chartCopy} title={t('Request volume')} {labels} series={[
    { id: 'demand', label: t('Demand'), values: demand },
    ...(widget.settings.compareCapacity === true ? [{ id: 'capacity', label: t('Capacity'), values: capacity }] : [])
  ]} />
{/snippet}

{#snippet historySettings(widget: DashboardWidgetState, patch: (values: { compareCapacity: boolean }) => void)}
  <Switch label={t('Compare with provisioned capacity')} checked={widget.settings.compareCapacity === true}
    onchange={(event) => patch({ compareCapacity: event.currentTarget.checked })} />
{/snippet}

{#snippet utilization(_widget: DashboardWidgetState)}
  <div class="meters">
    <div class="pool"><Cpu size={16} aria-hidden="true" /> API · EU-01</div>
    <Meter label={t('CPU usage')} value={72} valueText="72%" />
    <Meter label={t('Memory usage')} value={54} valueText="54%" />
    <Meter label={t('Queue occupancy')} value={81} valueText="81%" tone="warning" />
  </div>
{/snippet}

{#snippet cash(_widget: DashboardWidgetState)}
  <Chart {...chartCopy} kind="bar" title={t('Cash receipts and expenses')}
    labels={[t('Monday'), t('Tuesday'), t('Wednesday'), t('Thursday')]} series={[
      { id: 'receipts', label: t('Receipts'), values: [108, 141, 156, 184] },
      { id: 'expenses', label: t('Expenses'), values: [-65, -78, -92, -97] }
    ]} />
{/snippet}

<Story name="Editable dashboard">
  <main>
    <div class="service"><span class="logo"><Layers3 size={20} aria-hidden="true" /></span> Messenger</div>
    <Dashboard bind:this={dashboard} title={t('Infrastructure dashboard')} {widgets} snapshot={imported} onchange={store} {t} />
    <div class="exchange">
      <Disclosure label={t('Dashboard snapshot')}>
        <div class="snapshot">
          <FormField label={t('Dashboard JSON')} hint={t('Copy a saved snapshot or paste one to restore the entire dashboard.')}>
            {#snippet children(control)}
              <Textarea {...control} rows={5} bind:value={json} spellcheck={false} />
            {/snippet}
          </FormField>
          <div class="actions">
            <Button disabled={!dashboard} onclick={() => { json = JSON.stringify(dashboard?.getSnapshot(), null, 2); importError = false; status = ''; }}>
              <ArrowUpFromLine size={16} aria-hidden="true" />{t('Export JSON')}
            </Button>
            <Button disabled={!json.trim()} onclick={restore}>
              <ArrowDownToLine size={16} aria-hidden="true" />{t('Import JSON')}
            </Button>
          </div>
          {#if importError}<Alert tone="danger" announce="assertive">{t('This dashboard snapshot is invalid or uses an unsupported version.')}</Alert>{/if}
          <output>{status ? t(status) : ''}</output>
        </div>
      </Disclosure>
    </div>
  </main>
</Story>

<style>
  main { display: grid; gap: var(--sui-space-4); margin-inline: auto; max-inline-size: 76rem; }
  .service { display: flex; align-items: center; gap: var(--sui-space-2); color: var(--sui-muted); font: var(--sui-caption); }
  .logo { display: grid; place-items: center; inline-size: 2rem; block-size: 2rem; border-radius: var(--sui-radius); background: var(--sui-primary); color: var(--sui-on-primary); }
  .reading { display: flex; align-items: center; gap: var(--sui-space-3); min-block-size: 2rem; font: var(--sui-title); font-variant-numeric: tabular-nums; }
  .reading :global(svg), .pool :global(svg) { flex: none; color: var(--sui-primary); }
  small, .pool { color: var(--sui-muted); font: var(--sui-caption); }
  .meters, .snapshot { display: grid; gap: var(--sui-space-4); }
  .pool, .actions { display: flex; align-items: center; gap: var(--sui-space-2); }
  .actions { flex-wrap: wrap; }
  .exchange { border-block-start: 1px solid var(--sui-border); max-inline-size: 44rem; }
  .snapshot { padding-block-end: var(--sui-space-3); }
  .snapshot :global(textarea) { font: var(--sui-caption); }
  output:empty { display: none; }
</style>
