<script lang="ts">
  import { Chart, type ChartSeries } from '@service-unavailable/ui';
  import { t } from '../i18n.svelte';
  import { clock, num } from '../format';

  let { title, values, ticks, secondary = [], secondaryTitle, primaryTitle = title, emptyText, format = num, time = clock, sampleTime = time }: {
    title: string; values: (number | null)[]; ticks: number[]; secondary?: number[]; secondaryTitle?: string; primaryTitle?: string;
    emptyText?: string; format?: (value: number) => string; time?: (tick: number) => string; sampleTime?: (tick: number) => string;
  } = $props();
  const series = $derived<ChartSeries[]>([
    { id: 'primary', label: primaryTitle, values },
    ...(secondary.length && secondaryTitle ? [{ id: 'secondary', label: secondaryTitle, values: secondary }] : [])
  ]);
</script>

<Chart {title} {series} {format} labels={ticks.map(time)} sampleLabels={ticks.map(sampleTime)}
  emptyLabel={emptyText ?? t('Install Monitoring with Service history to view this chart.')}
  missingLabel={t('No sample recorded')} sampleLabel={t('Inspect chart samples for {0}', [title])} />
