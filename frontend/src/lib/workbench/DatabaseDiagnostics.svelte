<script lang="ts">
  import { Button, Tooltip } from '@service-unavailable/ui';
  import { guideArticleHref, resourceArticle } from '../guide';
  import { t } from '../i18n.svelte';
  import { num, pct } from '../format';
  import type { ComponentMetrics, DatabaseUpgrade } from '../types';

  let { metric, guide, configureHref, configure, busy = false, showHealthy = false }: {
    metric: ComponentMetrics;
    guide: string;
    configureHref?: string;
    configure?: () => void;
    busy?: boolean;
    showHealthy?: boolean;
  } = $props();
  const data = $derived(metric.database);
  const hasDisk = $derived(data?.disk_read_iops != null && data.disk_write_iops != null && data.disk_capacity_iops != null);
  const diagnostic = $derived(data?.diagnostic);
  const limiting = $derived(diagnostic?.limiting ?? []);
  const near = $derived(diagnostic?.resources.filter((resource) => !limiting.includes(resource)) ?? []);
  const titles = {
    write_exceeded: 'Database write capacity exceeded',
    write_pressure: 'Database writes near capacity',
    resource_pressure: 'Database resources under pressure'
  };
  const actions: Record<DatabaseUpgrade, string> = {
    cpu: 'Increase vCPU to raise read and write processing capacity.',
    memory: 'Increase RAM to relieve memory pressure and improve read processing.',
    connections: 'Raise the connection pool limit to admit more reads and writes.',
    storage: 'Increase storage space to keep accepting writes.',
    nvme: 'Switch to NVMe to raise the shared disk I/O budget.',
    nvme_array: 'Switch to NVMe array for a higher shared disk I/O budget.',
    legacy: 'Clear the legacy throughput throttles to let hardware set the limit.'
  };
</script>

{#if data && (diagnostic || showHealthy)}
  <div class="stack database-details" class:notice={Boolean(diagnostic)} class:warn={Boolean(diagnostic)}>
    {#if diagnostic}<strong>{t(titles[diagnostic.level])}</strong>{/if}
    <dl>
      <div><dt>{t('Read demand')}</dt><dd>{t('{0} units/s', [num(data.read_demand)])}</dd></div>
      <div><dt class="row">{t('Disk I/O')} <Tooltip label={t('Help with {0}', [t('Disk I/O')])}
        text={t('Open the relevant guide article.')} href={guideArticleHref(guide, 'database-io', 'io')} /></dt><dd>{pct(metric.utilization['Disk I/O'])}</dd></div>
      {#if hasDisk}
        <div><dt>{t('Modeled read IOPS')}</dt><dd>{num(data.disk_read_iops ?? 0)}</dd></div>
        <div><dt>{t('Modeled write IOPS')}</dt><dd>{num(data.disk_write_iops ?? 0)}</dd></div>
        <div><dt>{t('Modeled IOPS demand / capacity')}</dt><dd>{num((data.disk_read_iops ?? 0) + (data.disk_write_iops ?? 0))} / {num(data.disk_capacity_iops ?? 0)}</dd></div>
      {/if}
      {#if data.write_capacity !== null}
        <div><dt>{t('Write demand')}</dt><dd>{t('{0} units/s', [num(data.write_demand)])}</dd></div>
        <div><dt>{t('Sustainable writes at current read load')}</dt><dd>{t('{0} units/s', [num(data.write_capacity)])}</dd></div>
      {:else}
        <div><dt>{t('Replication replay demand')}</dt><dd>{t('{0} units/s', [num(data.replication_demand)])}</dd></div>
        <div><dt>{t('Replication replay throughput')}</dt><dd>{t('{0} units/s', [num(data.replication_throughput)])}</dd></div>
        {#if data.replication_backlog > 0}
          <div><dt>{t('Pending replication work')}</dt><dd>{t('{0} units', [num(data.replication_backlog)])}</dd></div>
          {#if metric.replication_lag == null}<div><dt>{t('Replication lag')}</dt><dd>{t('Replay stalled')}</dd></div>{/if}
        {/if}
      {/if}
    </dl>
    {#if hasDisk}<p class="muted">{t('Modeled IOPS use one read unit as the reference. Writes add weighted disk work for the workload, index and replica links.')}</p>{/if}
    {#if diagnostic}
      {#if limiting.length}
        <div><strong>{t('Capacity limits')}</strong>
          {#each limiting as resource}
            <a class="resource" href={guideArticleHref(guide, resourceArticle(resource))}>{t(resource)} · {pct(metric.utilization[resource] ?? 0)}</a>
          {/each}
        </div>
      {/if}
      {#if near.length}
        <p>{t('Resources under pressure')}{#each near as resource}<span class="resource">{t(resource)} · {pct(metric.utilization[resource] ?? 0)}</span>{/each}</p>
      {/if}
      {#if limiting.includes('CPU') || limiting.includes('Disk I/O')}
        <p>{t('A larger connection pool only raises admission capacity. CPU and disk limits still apply.')}</p>
      {/if}
      {#if limiting.includes('Disk I/O') && !limiting.includes('Storage')}
        <p>{t('Adding storage space in GB does not increase disk speed.')}</p>
      {/if}
      {#if diagnostic.level === 'write_exceeded' || diagnostic.level === 'write_pressure'}
        <p>{t('Application writes stay on the primary. A read replica cannot reduce that write workload.')}</p>
        {#if diagnostic.level === 'write_exceeded'}
          <p>{t('If hardware upgrades are exhausted, reduce write demand. A write limiter protects other traffic by rejecting excess writes.')}</p>
        {/if}
      {/if}
      {#if diagnostic.upgrades.length}
        <ul>{#each diagnostic.upgrades as upgrade}<li>{t(actions[upgrade])}</li>{/each}</ul>
        {#if configureHref}<Button href={configureHref}>{t('Edit configuration')}</Button>
        {:else if configure}<Button disabled={busy} onclick={configure}>{t('Edit configuration')}</Button>{/if}
      {/if}
      {#if diagnostic.read_options}
        <p>{t('Offloading eligible reads can free shared capacity. Caches remove repeated reads. Replicas also add disk work on the primary.')}</p>
        <div class="row wrap">
          <a href={guideArticleHref(guide, 'cache')}>{t('Cache')}</a>
          <a href={guideArticleHref(guide, 'replica')}>{t('Read replica')}</a>
        </div>
      {/if}
    {/if}
    <a href={guideArticleHref(guide, data.write_capacity === null ? 'replication' : 'database-scaling')}>{t('Database Guide')}</a>
  </div>
{/if}

<style>
  .database-details { font-size: 13px; overflow-wrap: anywhere; }
  .database-details dl { margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .database-details dt { min-height: 34px; align-content: center; color: var(--muted); }
  .database-details dd { font: 600 13px var(--mono); margin: 0; }
  .database-details ul { margin: 0; padding-inline-start: 18px; }
  .resource { display: block; }
  .database-details a:not(.sui-button) { color: var(--primary); text-decoration: underline; }
</style>
