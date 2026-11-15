<script lang="ts">
  import { goto } from '$app/navigation';
  import { t } from '../i18n.svelte';
  import { duration, money } from '../format';
  import { guideArticleHref } from '../guide';
  import Meter from '../Meter.svelte';
  import type { Catalog, Game } from '../types';
  import type { Section } from '../labels';
  let { game, catalog, act, busy, link }: { game: Game; catalog: Catalog; busy: boolean;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    link: (section: Section, focus?: string) => string } = $props();
  const states = { unavailable: 'Unavailable', available: 'Available', developing: 'In development', completed: 'Completed' };
</script>

<section class="panel pad stack" aria-label={t('Engineering')}>
  <div class="row spread wrap"><div><h2>{t('Engineering')}</h2><p class="muted">{t('Research unlocks capabilities. Design and deploy the infrastructure yourself; its costs are separate.')}</p></div>
    <button class="btn" disabled={busy} onclick={async () => { if (game.engineering_lesson === 6) await act('/engineering-lesson', { step: 0 }, 'PUT'); await goto(`${link('product')}&engineering=1`); }}>{t('Engineering walkthrough')}</button></div>
  <div class="research-grid">
    {#each game.engineering ?? [] as project (project.id)}
      {@const definition = catalog.engineering[project.id]}
      <article class="research stack" data-tutorial={project.id === 'decomposition' ? 'engineering.research' : undefined}>
        <div class="row spread wrap"><h3>{t(definition.name)}</h3><span class="badge" class:good={project.state === 'completed'}>{t(states[project.state])}</span></div>
        <p>{t(definition.description)}</p>
        <p><strong>{t('Unlocks')}</strong> · {t(definition.unlocks)}</p>
        <p class="muted">{t(definition.advantages)}</p><p class="notice">{t(definition.tradeoffs)}</p>
        <dl><div><dt>{t('Research cost')}</dt><dd>{money(definition.cost)}</dd></div><div><dt>{t('Development time')}</dt><dd>{duration(definition.duration)}</dd></div></dl>
        <p>{t('Prerequisites')}: {definition.prereq.length ? definition.prereq.map((key) => t(catalog.engineering[key].name)).join(', ') : t('None')}</p>
        {#if project.state === 'developing'}<Meter value={1 - project.remaining / definition.duration} label={t('{0} remaining', [duration(project.remaining)])} />{/if}
        <div class="row wrap"><a class="btn" href={guideArticleHref(link('guide'), definition.guide)}>{t('Engineering Guide')}</a>
          {#if project.state === 'available'}<button class="btn primary" disabled={busy || game.balance < definition.cost} onclick={() => act(`/engineering/${project.id}`, { action: 'develop' })}>{t('Start research')}</button>{/if}</div>
      </article>
    {/each}
  </div>
</section>

<style>
  .research-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 310px), 1fr)); gap: 14px; }
  .research { border: 1px solid var(--border); border-radius: 8px; padding: 15px; min-width: 0; }
  .research h3 { font-size: 15px; }
  dl { margin: 0; } dl div { display: flex; justify-content: space-between; gap: 12px; } dd { margin: 0; }
</style>
