<script lang="ts">
  import { t } from '../i18n.svelte';
  import { num, pct } from '../format';
  import { guideArticleHref, resourceArticle } from '../guide';
  import type { DatabaseForecast } from '../types';

  let { database, guideHref, name }: { database: DatabaseForecast; guideHref: string; name?: string } = $props();
  const resources = $derived(Object.entries(database.projected_utilization)
    .filter(([resource]) => !['Reads', 'Writes', 'Replication'].includes(resource)));
</script>

<section class="panel inset pad stack">
  <h3>{name ? t('Database forecast for {0}', [t(name)]) : t('Database upgrade forecast')}</h3>
  <p class="muted">{t('Projected ranges vary audience and assume no active incidents.')}</p>
  <table>
    <thead><tr><th scope="col">{t('Metric')}</th><th scope="col">{t('Current')}</th><th scope="col">{t('Projected')}</th></tr></thead>
    <tbody>
      {#each resources as [resource, range] (resource)}
        <tr class:warning={range.high >= 1}>
          <th scope="row"><a href={guideArticleHref(guideHref, resourceArticle(resource))} target="_blank" rel="noopener">{t(resource)}</a></th>
          <td>{pct(database.current_utilization[resource] ?? 0)}</td>
          <td>{pct(range.low)}–{pct(range.high)}</td>
        </tr>
      {/each}
      {#if database.projected_write_capacity && database.current_write_capacity != null}
        <tr>
          <th scope="row">{t('Sustainable writes (units/s)')}</th>
          <td>{num(database.current_write_capacity)}</td>
          <td>{num(database.projected_write_capacity.low)}–{num(database.projected_write_capacity.high)}</td>
        </tr>
      {/if}
      {#if database.projected_write_demand}
        <tr><th scope="row">{t('Write demand (units/s)')}</th><td>{database.current_write_demand == null ? '—' : num(database.current_write_demand)}</td>
          <td>{num(database.projected_write_demand.low)}–{num(database.projected_write_demand.high)}</td></tr>
      {/if}
    </tbody>
  </table>
  {#if resources.some(([, range]) => range.high >= 1)}
    <p class="warning">{t('Projected overload is highlighted. Check the remaining bottlenecks before deploying.')}</p>
  {/if}
</section>

<style>
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: start; padding: 6px 4px; border-bottom: 1px solid var(--border); }
  td { font: 12px var(--mono); }
  a { text-decoration: underline; text-underline-offset: 2px; }
  p { font-size: 12px; }
</style>
