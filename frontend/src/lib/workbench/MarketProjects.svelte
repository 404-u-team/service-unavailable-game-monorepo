<script lang="ts">
  import { t } from '../i18n.svelte';
  import { duration, money, num, pct } from '../format';
  import Meter from '../Meter.svelte';
  import type { Game, Market } from '../types';

  let { game, busy, act, localization = false }: {
    game: Game; busy: boolean; localization?: boolean;
    act: (path: string, body?: object, method?: string) => Promise<Game | null>;
  } = $props();

  const stages: Record<Market['stage'], string> = {
    planned: 'Available', developing: 'Preparing', ready: 'Ready to launch', active: 'Active'
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
          <small class="muted">{game.markets.filter((market) => market.language_weights?.[language.name]).map((market) => t(market.name)).join(', ')}</small>
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
    <div class="projects markets">
      {#each game.markets as market (market.id)}
        <article class="stack panel inset">
          <div class="row spread market-heading"><h3>{t(market.name)}</h3><span class="badge {market.stage === 'active' ? 'good' : 'dim'}">{t(stages[market.stage])}</span></div>
          <small>{t('Market potential: {0} users', [num(market.potential)])}</small>
          <details>
            <summary>{t('Product languages')}</summary>
            <dl>
              {#each Object.entries(market.language_weights ?? {}) as [language, weight] (language)}
                <div class="row spread"><dt>{t(language)} · {language === 'English' ? pct(weight) : t('{0} of audience · +{1} acquisition', [pct(weight), pct(market.language_benefits?.[language] ?? 0, 1)])}</dt><dd>{game.languages.find((item) => item.name === language)?.ready ? t('Available') : t('Can develop')}</dd></div>
              {/each}
            </dl>
          </details>
          {#if market.stage === 'planned'}
            <div class="row spread wrap"><small class="muted">{money(market.cost)} · {duration(market.duration)}</small>
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
  .projects { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); gap: 10px; align-items: start; }
  article { padding: 12px; gap: 7px; align-content: start; min-width: 0; }
  .market-heading h3 { min-width: 0; overflow-wrap: anywhere; }
  .market-heading .badge { flex: none; }
  @media (min-width: 1100px) { .markets { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  summary { cursor: pointer; font-size: 12px; }
  dl { margin: 5px 0; font-size: 11px; }
  dd { margin: 0; color: var(--muted); }
  article button { justify-self: start; }
</style>
