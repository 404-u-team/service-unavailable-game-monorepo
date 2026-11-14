<script lang="ts">
  import { t } from '../i18n.svelte';
  import { duration, money, num } from '../format';
  import Meter from '../Meter.svelte';
  import type { Game, Market } from '../types';

  let { game, busy, act, localization = false }: {
    game: Game; busy: boolean; localization?: boolean;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
  } = $props();

  const stages: Record<Market['stage'], string> = {
    planned: 'Planned', developing: 'In development', ready: 'Ready to launch', active: 'Active'
  };
</script>

<section class="panel pad stack">
  {#if localization}
    <h2>{t('Messenger languages')}</h2>
    <p class="muted">{t('Localization improves organic adoption and paid acquisition in markets that use the language.')}</p>
    <div class="projects">
      {#each game.languages as language (language.name)}
        <article class="stack panel inset">
          <h3>{t(language.name)}</h3>
          {#if language.ready}<span class="badge good">{t('Available')}</span>
          {:else if language.remaining}
            <Meter value={1 - language.remaining / language.duration} label={t('{0} remaining', [duration(language.remaining)])} />
          {:else}
            <span class="muted">{money(language.cost)} · {duration(language.duration)}</span>
            <button class="btn" disabled={busy || game.balance < language.cost}
              onclick={() => act(`/languages/${encodeURIComponent(language.name)}`)}>{t('Develop language')}</button>
          {/if}
        </article>
      {/each}
    </div>
  {:else}
    <h2>{t('Market expansion')}</h2>
    <p class="muted">{t('Fund market research and launch preparation. Active markets attract organic users and can run targeted campaigns.')}</p>
    <div class="projects">
      {#each game.markets as market (market.id)}
        <article class="stack panel inset">
          <div class="row spread wrap"><h3>{t(market.name)}</h3><span class="badge {market.stage === 'active' ? 'good' : 'dim'}">{t(stages[market.stage])}</span></div>
          <small>{t('Market potential: {0} users', [num(market.potential)])} · {t(market.language)}</small>
          {#if market.stage === 'planned'}
            <div class="row spread wrap"><span>{money(market.cost)} · {duration(market.duration)}</span>
              <button class="btn" disabled={busy || game.balance < market.cost}
                onclick={() => act(`/markets/${market.id}`, { action: 'develop' })}>{t('Start preparation')}</button></div>
          {:else if market.stage === 'developing'}
            <Meter value={1 - market.remaining / market.duration} label={t('{0} remaining', [duration(market.remaining)])} />
          {:else if market.stage === 'ready'}
            <p class="muted">{t('Launch requires at least 65% service satisfaction.')}</p>
            <button class="btn primary" disabled={busy || game.satisfaction < .65}
              onclick={() => act(`/markets/${market.id}`, { action: 'launch' })}>{t('Launch market')}</button>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .projects { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 10px; }
  article { padding: 12px; gap: 9px; align-content: start; }
</style>
