<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Activity, Layers3, SlidersHorizontal } from '@lucide/svelte';
  import { Badge, Button, Chart, Form, FormField, Meter, PageColumns, Panel, Slider, Slideover, Switch, Toaster, createToasts } from '@service-unavailable/ui';
  import { formatNumber, stepLabels, t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Patterns/Workbench' });
</script>

<script lang="ts">
  let settingsOpen = $state(false);
  let allocation = $state(65);
  let monitoring = $state(true);
  const toasts = createToasts();
</script>

<Story name="Capacity overview">
  <main>
    <header>
      <div class="identity">
        <div class="mark" aria-hidden="true"><Layers3 size={24} strokeWidth={1.8} /></div>
        <div><p>Messenger</p><h1>{t('Service overview')}</h1></div>
      </div>
      <Button onclick={() => settingsOpen = true}><SlidersHorizontal size={16} aria-hidden="true" />{t('Service settings')}</Button>
    </header>

    <PageColumns minWidth="12rem">
      <Panel><span class="metric-label">{t('Incoming traffic')}</span><span class="metric">{formatNumber(246)} <small>{t('req/s')}</small></span></Panel>
      <Panel><span class="metric-label">{t('Provisioned capacity')}</span><span class="metric">{formatNumber(265)} <small>{t('req/s')}</small></span></Panel>
      <Panel><span class="metric-label">{t('Availability')}</span><span class="metric">{formatNumber(99.8)}<small>%</small></span></Panel>
    </PageColumns>

    <div class="content">
      <Panel>
        {#snippet header()}
          <div class="panel-header">
            <Activity size={17} aria-hidden="true" /><h2>{t('Service telemetry')}</h2><Badge tone="success">{t('Monitored')}</Badge>
          </div>
        {/snippet}
        <Chart title={t('Request volume')} labels={['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00']}
          series={[
            { id: 'demand', label: t('Demand'), values: [92, 125, 171, null, 183, 229, 246] },
            { id: 'capacity', label: t('Capacity'), values: [165, 165, 180, 210, 210, 235, 265] }
          ]}
          emptyLabel={t('No measurements available.')}
          missingLabel={t('No sample recorded')} sampleLabel={t('Inspect samples')} format={formatNumber} />
      </Panel>
      <Panel inset>
        {#snippet header()}<h2>{t('Server utilization')}</h2>{/snippet}
        <div class="meters">
          <Meter label={t('CPU usage')} value={72} valueText="72%" />
          <Meter label={t('Memory usage')} value={54} valueText="54%" />
          <Meter label={t('Queue occupancy')} value={81} valueText="81%" tone="warning" />
        </div>
      </Panel>
    </div>
  </main>

  <Slideover bind:open={settingsOpen} title={t('Service settings')} closeLabel={t('Close dialog')} resizeLabel={t('Resize side panel')}>
    <Form ondata={() => {
      settingsOpen = false;
      toasts.add({ title: t('Settings saved'), tone: 'success' });
    }}>
      <FormField label={t('Traffic allocation')}>
        {#snippet children(control)}
          <Slider {...control} name="traffic" bind:value={allocation} min={0} max={100} step={5} manualLabel={t('Exact traffic allocation')} manualStepLabels={stepLabels(t('Traffic allocation'))} unit="%" />
        {/snippet}
      </FormField>
      <Switch name="monitoring" label={t('Enable monitoring')} bind:checked={monitoring} />
      <Button variant="primary" type="submit">{t('Save settings')}</Button>
    </Form>
  </Slideover>
  <Toaster {toasts} label={t('Notifications')} dismissLabel={(title) => t('Dismiss {0}', [title])} />
</Story>

<style>
  main { max-inline-size: 74rem; margin-inline: auto; display: grid; gap: var(--sui-space-5); }
  header, .identity, .panel-header { display: flex; align-items: center; gap: var(--sui-space-3); }
  header { justify-content: space-between; flex-wrap: wrap; padding-block: var(--sui-space-3); }
  .mark { display: grid; place-items: center; flex: none; inline-size: 3rem; block-size: 3rem; border-radius: var(--sui-radius); background: var(--sui-primary); color: var(--sui-on-primary); }
  h1 { margin: 0; font: var(--sui-display); }
  h2 { margin: 0; font: 700 1rem/1.35 var(--sui-heading); }
  p, .metric-label { margin: 0; color: var(--sui-muted); font: var(--sui-caption); }
  .metric-label, .metric { display: block; }
  .metric { margin-block-start: var(--sui-space-2); font: var(--sui-title); font-variant-numeric: tabular-nums; }
  small { color: var(--sui-muted); font: var(--sui-caption); }
  .content { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(0, 1fr); gap: var(--sui-space-4); align-items: start; }
  .panel-header { flex-wrap: wrap; }
  .panel-header :global(.badge) { margin-inline-start: auto; }
  .meters { display: grid; gap: var(--sui-space-5); }
  @media (max-width: 680px) { .content { grid-template-columns: minmax(0, 1fr); } }
</style>
