<script lang="ts">
  import { goto } from '$app/navigation';
  import { Badge, Button, Panel } from '@service-unavailable/ui';
  import { ChevronRight } from '@lucide/svelte';
  import { message, t } from '../i18n.svelte';
  import { duration, money } from '../format';
  import { guideArticleHref } from '../guide';
  import Meter from '../Meter.svelte';
  import Modal from '../Modal.svelte';
  import type { Catalog, Game } from '../types';
  import type { Section } from '../labels';

  let { game, catalog, act, busy, link, error }: {
    game: Game; catalog: Catalog; busy: boolean; error: string;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
    link: (section: Section, focus?: string) => string;
  } = $props();
  const states = { unavailable: 'Unavailable', available: 'Available', developing: 'In development', completed: 'Completed' } as const;
  let selected = $state('');
  const project = $derived(game.engineering?.find((item) => item.id === selected));

  async function walkthrough() {
    if (game.engineering_lesson === 6 && !await act('/engineering-lesson', { step: 0 }, 'PUT')) return;
    await goto(`${link('product')}&engineering=1`);
  }

  function start(id: string) {
    return act(`/engineering/${id}`, { action: 'develop' });
  }
</script>

<section class="stack" aria-label={t('Engineering')}>
  <div class="row spread wrap">
    <p class="muted">{t('Research unlocks capabilities. Design and deploy the infrastructure yourself; its costs are separate.')}</p>
    <Button disabled={busy} onclick={walkthrough}>{t('Engineering walkthrough')}</Button>
  </div>
  <ul class="list">
    {#each game.engineering ?? [] as item (item.id)}
      {@const definition = catalog.engineering[item.id]}
      <li data-tutorial={item.id === 'decomposition' ? 'engineering.research' : undefined}>
        <Panel>
          <div class="research">
            <div class="stack">
              <div class="row wrap">
                <h3>{t(definition.name)}</h3>
                <Badge tone={item.state === 'completed' ? 'success' : item.state === 'developing' ? 'info' : 'neutral'}>{t(states[item.state])}</Badge>
              </div>
              <p>{t(definition.unlocks)}</p>
              {#if item.state === 'developing'}
                <Meter value={1 - item.remaining / definition.duration} label={t('{0} remaining', [duration(item.remaining)])} />
              {:else if item.state === 'available'}
                <small>{money(definition.cost)} · {duration(definition.duration)}</small>
              {/if}
            </div>
            <div class="row wrap actions">
              {#if item.state === 'available'}
                <Button variant="primary" disabled={busy || game.balance < definition.cost} onclick={() => start(item.id)}>{t('Start research')}</Button>
              {/if}
              <Button aria-label={t('Research details for {0}', [t(definition.name)])} onclick={() => selected = item.id}>{t('Details')} <ChevronRight size={16} /></Button>
            </div>
          </div>
        </Panel>
      </li>
    {/each}
  </ul>
</section>

{#if project}
  {@const definition = catalog.engineering[project.id]}
  <Modal side="end" title={t(definition.name)} subtitle={t(states[project.state])} close={() => selected = ''}>
    <div class="stack">
      <p>{t(definition.description)}</p>
      <div><h3>{t('Unlocks')}</h3><p>{t(definition.unlocks)}</p></div>
      <div><h3>{t('Advantages')}</h3><p>{t(definition.advantages)}</p></div>
      <div><h3>{t('Trade-offs')}</h3><p>{t(definition.tradeoffs)}</p></div>
      <dl>
        <div><dt>{t('Research cost')}</dt><dd>{money(definition.cost)}</dd></div>
        <div><dt>{t('Development time')}</dt><dd>{duration(definition.duration)}</dd></div>
      </dl>
      <div class="stack">
        <h3>{t('Prerequisites')}</h3>
        {#if definition.prereq.length}
          <ul class="list">
            {#each definition.prereq as id (id)}
              {@const complete = game.engineering?.some((item) => item.id === id && item.state === 'completed')}
              <li class="row spread"><span>{t(catalog.engineering[id].name)}</span><Badge tone={complete ? 'success' : 'warning'}>{t(complete ? 'Met' : 'Missing')}</Badge></li>
            {/each}
          </ul>
        {:else}<p>{t('None')}</p>{/if}
      </div>
      {#if project.state === 'developing'}<Meter value={1 - project.remaining / definition.duration} label={t('{0} remaining', [duration(project.remaining)])} />{/if}
      {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    </div>
    {#snippet footer()}
      <div class="row spread wrap">
        <Button href={guideArticleHref(link('guide'), definition.guide)}>{t('Engineering Guide')}</Button>
        {#if project.state === 'available'}
          <Button variant="primary" disabled={busy || game.balance < definition.cost} onclick={() => start(project.id)}>{t('Start research')}</Button>
        {/if}
      </div>
    {/snippet}
  </Modal>
{/if}

<style>
  .research { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px 20px; }
  .research .stack { gap: 6px; flex: 1 1 22rem; }
  .actions { justify-content: flex-start; }
  dl { margin: 0; }
  dl div { display: flex; justify-content: space-between; gap: 12px; padding-block: 6px; border-bottom: 1px solid var(--border); }
</style>
