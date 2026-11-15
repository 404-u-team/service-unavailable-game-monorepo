<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { Chart, Meter } from '@service-unavailable/ui';
  import { formatNumber, t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Data/Visualization' });
</script>

<script lang="ts">
  const copy = $derived({
    emptyLabel: t('No measurements available.'),
    missingLabel: t('No sample recorded'),
    sampleLabel: t('Inspect samples'),
    format: formatNumber
  });
</script>

<Story name="Line chart">
  <div class="chart">
    <Chart {...copy} title={t('Request volume')} labels={['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00']} series={[
      { id: 'demand', label: t('Demand'), values: [92, 125, 171, null, 183, 229, 246] },
      { id: 'capacity', label: t('Capacity'), values: [165, 165, 180, 210, 210, 235, 265] }
    ]} />
  </div>
</Story>

<Story name="Bar chart">
  <div class="chart">
    <Chart {...copy} kind="bar" title={t('Daily cash flow')} labels={[t('Monday'), t('Tuesday'), t('Wednesday'), t('Thursday')]} series={[
      { id: 'receipts', label: t('Receipts'), values: [108, 141, 156, 184] },
      { id: 'expenses', label: t('Expenses'), values: [-65, -78, -92, -97] }
    ]} />
  </div>
</Story>

<Story name="Empty chart">
  <div class="chart"><Chart {...copy} title={t('Request volume')} labels={[]} series={[]} /></div>
</Story>

<Story name="Meter">
  <div class="meters">
    <Meter label={t('CPU usage')} value={42} valueText="42%" />
    <Meter label={t('Queue occupancy')} value={79} valueText="79%" tone="warning" />
    <Meter label={t('Memory usage')} value={96} valueText="96%" tone="danger" />
  </div>
</Story>

<style>
  .chart { max-inline-size: 52rem; }
  .meters { display: grid; gap: var(--sui-space-5); max-inline-size: 30rem; }
</style>
