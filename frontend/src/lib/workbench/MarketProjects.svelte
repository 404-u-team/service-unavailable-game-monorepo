<script lang="ts">
  import { Badge, Button, Disclosure, Panel } from '@service-unavailable/ui';
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

<section class="stack">
  {#if localization}
    <p class="muted">{t('Localization improves organic adoption and paid acquisition in markets that use the language.')}</p>
    <ul class="list projects">
      {#each game.languages as language (language.name)}
        <li>
          <Panel inset padding="compact">
            <article class="project">
              <div class="project-summary">
                <h3>{t(language.name)}</h3>
                <small class="muted">{game.markets.filter((market) => market.language_weights?.[language.name]).map((market) => t(market.name)).join(', ')}</small>
              </div>
              <div class="project-action">
                {#if language.ready}<Badge tone="success">{t('Available')}</Badge>
                {:else if language.remaining}
                  <Meter value={1 - language.remaining / language.duration} label={t('{0} remaining', [duration(language.remaining)])} />
                {:else}
                  <small class="muted">{money(language.cost)} · {duration(language.duration)}</small>
                  <Button disabled={busy || game.balance < language.cost}
                    onclick={() => act(`/languages/${encodeURIComponent(language.name)}`)}>{t('Develop language')}</Button>
                {/if}
              </div>
            </article>
          </Panel>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted">{t('Fund market research and launch preparation. Active markets attract organic users and can run targeted campaigns.')}</p>
    <ul class="list projects">
      {#each game.markets as market (market.id)}
        <li>
          <Panel inset padding="compact">
            <article class="project">
              <div class="project-summary">
                <div class="row wrap"><h3>{t(market.name)}</h3><Badge tone={market.stage === 'active' ? 'success' : 'neutral'}>{t(stages[market.stage])}</Badge></div>
                <small>{t('Market potential: {0} users', [num(market.potential)])}</small>
              </div>
              {#if market.stage !== 'active'}
                <div class="project-action">
                  {#if market.stage === 'planned'}
                    <small class="muted">{money(market.cost)} · {duration(market.duration)}</small>
                    <Button disabled={busy || game.balance < market.cost}
                      onclick={() => act(`/markets/${market.id}`, { action: 'develop' })}>{t('Start preparation')}</Button>
                  {:else if market.stage === 'developing'}
                    <Meter value={1 - market.remaining / market.duration} label={t('{0} remaining', [duration(market.remaining)])} />
                  {:else if market.stage === 'ready'}
                    <small class="muted">{t('Launch requires at least 65% service satisfaction.')}</small>
                    <Button variant="primary" disabled={busy || game.satisfaction < .65}
                      onclick={() => act(`/markets/${market.id}`, { action: 'launch' })}>{t('Launch market')}</Button>
                  {/if}
                </div>
              {/if}
              <div class="project-details">
                <Disclosure label={t('Product languages')}>
                  <dl>
                    {#each Object.entries(market.language_weights ?? {}) as [language, weight] (language)}
                      <div class="row spread"><dt>{t(language)} · {language === 'English' ? pct(weight) : t('{0} of audience · +{1} acquisition', [pct(weight), pct(market.language_benefits?.[language] ?? 0, 1)])}</dt><dd>{game.languages.find((item) => item.name === language)?.ready ? t('Available') : t('Can develop')}</dd></div>
                    {/each}
                  </dl>
                </Disclosure>
              </div>
            </article>
          </Panel>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .projects { container-type: inline-size; }
  .project { display: grid; align-items: start; gap: 6px 12px; }
  .project-summary, .project-action { display: grid; gap: 5px; min-width: 0; }
  .project-action { justify-items: start; }
  .project-details { grid-column: 1 / -1; border-top: 1px solid var(--sui-border); }
  dl { margin: 0; font-size: 12px; }
  dd { color: var(--muted); text-align: end; }
  @container (min-width: 27rem) {
    .project { grid-template-columns: minmax(0, 1fr) minmax(9rem, 42%); }
    .project-action { justify-items: end; text-align: end; align-self: center; }
  }
</style>
