<script lang="ts">
  import { t } from '../i18n.svelte';
  import { ms, num, pct, preciseMoney, rps } from '../format';
  import { guideArticleHref } from '../guide';
  import type { Catalog, Game } from '../types';
  import type { Section } from '../labels';
  let { game, catalog, link }: { game: Game; catalog: Catalog; link: (section: Section, focus?: string) => string } = $props();
  const services = $derived(game.production.nodes.filter((n) => n.kind === 'api' && game.snapshot.components[n.id]));
  const databases = $derived(game.production.nodes.filter((n) => n.kind === 'database' && game.snapshot.components[n.id]?.database));
  const domains = $derived([...new Set(databases.filter((n) => game.snapshot.components[n.id].partition_share != null).map((n) => String(n.config.domain ?? 'Shared')))]);
</script>

{#if services.length || databases.length}
  <section class="panel pad stack">
    <div class="row spread wrap"><h2>{t('Service responsibilities')}</h2><a class="btn" href={guideArticleHref(link('guide'), 'service-routing')}>{t('Engineering Guide')}</a></div>
    <p class="muted">{t('These readings include only components covered by monitoring.')}</p>
    <div class="service-grid">
      {#each services as node (node.id)}
        {@const metric = game.snapshot.components[node.id]}
        <article class="stack service"><a href={link('build', node.id)}><strong>{t(node.name)} · {t(metric.service_role ?? 'Universal')}</strong></a>
          <p>{rps(metric.rps)} · {t('Service latency')}: {ms(metric.service_latency ?? metric.latency)} · {t('Service errors')}: {rps(metric.service_errors ?? 0)}</p>
          <p>{t('Active instances')}: {metric.active_instances} · {preciseMoney(game.component_costs[node.id])} {t('per day')}</p>
          {#each Object.entries(metric.operations ?? {}) as [op, rate]}<small>{t(catalog.operations[op] ?? op)} · {rps(rate)}</small>{/each}
        </article>
      {/each}
      {#each databases as node (node.id)}
        {@const metric = game.snapshot.components[node.id]}
        <article class="stack service"><a href={link('build', node.id)}><strong>{t(node.name)} · {t(metric.data_domain ?? 'Shared')}</strong></a>
          <p>{t('Read demand')}: {t('{0} units/s', [num(metric.database!.read_demand)])} · {t('Write demand')}: {t('{0} units/s', [num(metric.database!.write_demand)])}</p>
          {#if metric.partition_share != null}<p>{t('Partition traffic share')}: {pct(metric.partition_share, 1)}</p>{/if}
        </article>
      {/each}
    </div>
    {#each domains as domain}
      {@const shares = databases.filter((n) => n.config.domain === domain).map((n) => game.snapshot.components[n.id].partition_share ?? 0)}
      <p>{t('Observed shard imbalance')}: {t(domain)} · {pct(Math.max(...shares) / (shares.reduce((a, b) => a + b, 0) / shares.length) - 1, 1)} {t('above observed mean')}</p>
    {/each}
  </section>
{/if}

<style>
  .service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 12px; }
  .service { padding: 12px; border: 1px solid var(--border); border-radius: 8px; min-width: 0; overflow-wrap: anywhere; }
</style>
