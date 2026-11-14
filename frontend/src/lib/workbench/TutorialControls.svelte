<script lang="ts">
  import { t } from '../i18n.svelte';
  import type { Game } from '../types';
  import { chapters, onboarding, stepId, type TutorialAction } from './onboarding';

  let { game, busy = false, change }: { game: Game; busy?: boolean; change: (action: TutorialAction) => void } = $props();
  const current = $derived(stepId(game.onboarding));
  const step = $derived(onboarding.find((item) => item.id === current));
</script>

{#if game.scenario === 'messenger'}
  <section class="panel pad stack" aria-label={t('Guided onboarding')}>
    <div>
      <h3>{t('Guided onboarding')}</h3>
      <p class="muted">{step ? t('Chapter {0} of {1} · {2}', [step.chapter + 1, chapters.length, t(chapters[step.chapter])]) : t('Tutorial complete')}</p>
    </div>
    <div class="row wrap">
      {#if current !== 'complete'}
        <button class="btn primary" disabled={busy} onclick={() => change('resume')}>{t('Resume tutorial')}</button>
      {/if}
      {#if current !== 'clock' || game.onboarding.skipped || !game.settings.show_tutorial}
        <button class="btn" disabled={busy} onclick={() => change('restart')}>{t('Restart tutorial')}</button>
      {/if}
    </div>
  </section>
{/if}
