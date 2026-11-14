<script lang="ts">
  import { t } from '../i18n.svelte';
  import { onboarding } from './onboarding';
  import { spotlightBounds } from './spotlight';
  import type { Section } from '../labels';
  import type { Game } from '../types';

  let { progress, section, link, change, busy }: {
    progress: Game['onboarding']; section: Section; link: (section: Section) => string;
    change: (action: 'back' | 'next' | 'skip' | 'resume') => void; busy: boolean;
  } = $props();
  const step = $derived(onboarding[progress.step]);
  let highlight = $state<ReturnType<typeof spotlightBounds>>();
  let modalOpen = $state(false);
  let positionAbove = $state(false);

  $effect(() => {
    if (!step || progress.skipped) return;
    const selector = step.target;
    const currentSection = section;
    let frame = 0;
    let target: Element | undefined;
    const resize = new ResizeObserver(update);
    function update() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const modal = document.querySelector('dialog[open]');
        modalOpen = Boolean(modal);
        const next = [...document.querySelectorAll(selector)].find((item) =>
          item.getClientRects().length && (!modal || modal.contains(item)));
        if (target !== next) {
          if (target) resize.unobserve(target);
          if (next) resize.observe(next);
          target = next;
        }
        highlight = target ? spotlightBounds(target.getBoundingClientRect(), innerWidth, innerHeight) : undefined;
        positionAbove = Boolean(highlight && highlight.top > innerHeight / 2);
      });
    }
    const observer = new MutationObserver((records) => {
      if (records.some((item) => !(item.target instanceof Element) || !item.target.closest('[data-spotlight-ui]'))) update();
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['open', 'class', 'style'] });
    if (currentSection) update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      observer.disconnect();
      resize.disconnect();
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  });
</script>

{#if step && !progress.skipped && !modalOpen}
  {#if highlight}<div class="spotlight" data-spotlight-ui aria-hidden="true"
    style:left="{highlight.left}px" style:top="{highlight.top}px" style:width="{highlight.width}px" style:height="{highlight.height}px"></div>{/if}
  <aside class="panel tutorial stack" class:top={positionAbove} data-spotlight-ui aria-label={t('Guided onboarding')}>
    <small aria-live="polite">{t('Step {0} of {1}', [progress.step + 1, onboarding.length])}</small>
    <h2>{t(step.title)}</h2>
    <p>{t(step.text)}</p>
    <div class="row wrap">
      {#if progress.step > 0}<button class="btn" disabled={busy} onclick={() => change('back')}>{t('Back')}</button>{/if}
      {#if 'section' in step && step.section && step.section !== section}<a class="btn primary" href={link(step.section)}>{t('Open {0}', [t(step.section === 'build' ? 'Topology' : 'Telemetry')])}</a>
      {:else if !('action' in step) || progress.step < progress.furthest}<button class="btn primary" disabled={busy} onclick={() => change('next')}>{t(progress.step === onboarding.length - 1 ? 'Finish' : 'Next')}</button>{/if}
      <button class="btn ghost" disabled={busy} onclick={() => change('skip')}>{t('Skip tutorial')}</button>
    </div>
  </aside>
{/if}

<style>
  .spotlight { position: fixed; z-index: 13; pointer-events: none; border: 2px solid var(--primary);
    border-radius: 8px; box-shadow: 0 0 0 160vmax #06090b3d; }
  .tutorial { position: fixed; z-index: 14; bottom: 15px; left: 88px; padding: 13px; pointer-events: none;
    width: min(330px, calc(100vw - 30px)); gap: 6px; box-shadow: 0 10px 30px #0009; }
  .tutorial.top { top: 75px; bottom: auto; }
  .tutorial p { font-size: 13px; }
  .tutorial .btn { min-height: 32px; pointer-events: auto; }
  @media (max-width: 850px) {
    .tutorial { bottom: calc(72px + env(safe-area-inset-bottom)); left: 10px; padding: 10px; max-width: calc(100vw - 20px); }
    .tutorial.top { top: 72px; bottom: auto; }
  }
</style>
