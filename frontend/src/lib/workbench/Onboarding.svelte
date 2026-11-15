<script lang="ts">
  import { untrack } from 'svelte';
  import { Focus } from '@lucide/svelte';
  import { t } from '../i18n.svelte';
  import { sections, type Section } from '../labels';
  import { chapters, onboarding, stepId, target, type Target, type TutorialAction, type TutorialProgress } from './onboarding';
  import { findTarget, intersection, openDialog, placeTooltip, revealTarget, viewport, visibleTarget } from './spotlight';

  let { progress, view, busy, waiting, link, change, recover, complete, lesson }: {
    lesson?: { title: string; text: string; index: number };
    progress: TutorialProgress;
    view: { target?: Target; instruction?: string; args?: string[]; open?: Section; allowed?: boolean; retry?: boolean };
    busy: boolean; waiting: boolean; link: (section: Section) => string;
    change: (action: TutorialAction) => void; recover: (key?: Target) => void; complete?: () => void;
  } = $props();

  const index = $derived(lesson ? lesson.index : onboarding.findIndex((item) => item.id === stepId(progress)));
  const step = $derived(lesson ? { id: `engineering-${lesson.index}`, chapter: 0, title: lesson.title, text: lesson.text } : onboarding[index]);
  const chapterSteps = $derived(onboarding.filter((item) => item.chapter === step?.chapter));
  const chapterIndex = $derived(chapterSteps.findIndex((item) => item.id === step?.id));
  const firstInChapter = $derived(chapterIndex === 0 && index > 0);
  const replay = $derived(index >= 0 && (progress.furthest_id === 'complete' ||
    index < onboarding.findIndex((item) => item.id === progress.furthest_id)));

  let layer = $state<HTMLDivElement>();
  let tooltip = $state<HTMLElement>();
  let content = $state<HTMLDivElement>();
  let hole = $state.raw<ReturnType<typeof visibleTarget>>();
  let bounds = $state.raw({ left: 0, right: 0, top: 0, bottom: 0 });
  let position = $state.raw({ x: 10, y: 10, maxHeight: 360 });
  let tooltipWidth = $state(330);
  let modal = $state<HTMLDialogElement>();
  let modalTarget = $state(false);
  let visible = $state(false);
  let reposition: (() => void) | undefined;
  let focusedControlStep = '';
  const explanationId = 'tutorial-explanation';
  let description: HTMLElement | undefined;

  function clearDescription() {
    if (!description) return;
    const remaining = description.getAttribute('aria-describedby')?.split(/\s+/).filter((id) => id !== explanationId);
    if (remaining?.length) description.setAttribute('aria-describedby', remaining.join(' '));
    else description.removeAttribute('aria-describedby');
    description = undefined;
  }

  function showTarget() {
    recover(view.target);
    reposition?.();
  }

  function focusTarget() {
    const key = modal && !modalTarget ? target.close : view.target;
    const element = findTarget(key, modal);
    if (element) {
      if (!element.matches('a, button, input, select, summary, [tabindex]')) element.tabIndex = -1;
      element.focus({ preventScroll: true });
    }
    showTarget();
  }

  $effect(() => {
    if (!layer || !tooltip || !content) return;
    const root = layer;
    const popover = tooltip;
    const inner = content;
    let frame = 0;
    let lastKey: Target | undefined;
    let lastNode: HTMLElement | undefined;
    let lastStep = '';
    let lastDialog: HTMLDialogElement | undefined;
    let scroll = true;
    let lastViewport = '';
    let attemptedReveal = false;
    let observed = new Set<Element>();
    const resize = new ResizeObserver(schedule);
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update);
    }

    function update() {
      frame = 0;
      const dialog = openDialog();
      const viewBox = viewport();
      if (root.parentElement !== (dialog ?? document.body)) {
        const focused = document.activeElement;
        (dialog ?? document.body).append(root);
        if (focused instanceof HTMLElement && root.contains(focused)) focused.focus({ preventScroll: true });
      }
      modal = dialog;
      const currentKey = view.target;
      const desired = findTarget(currentKey, dialog);
      modalTarget = !dialog || Boolean(desired);
      const key = dialog && !desired ? target.close : currentKey;
      const node = desired ?? findTarget(key, dialog);
      const currentStep = step?.id ?? '';
      const viewKey = JSON.stringify(viewBox);
      if (node !== lastNode || key !== lastKey || dialog !== lastDialog || currentStep !== lastStep || viewKey !== lastViewport) {
        scroll = true;
        attemptedReveal = false;
        lastNode = node;
        lastKey = key;
        lastStep = currentStep;
        lastDialog = dialog;
        lastViewport = viewKey;
      }
      const watch = new Set<Element>([inner, document.documentElement]);
      if (dialog) watch.add(dialog);
      for (let element: HTMLElement | null | undefined = node; element && element !== document.body; element = element.parentElement) watch.add(element);
      for (const element of observed) if (!watch.has(element)) resize.unobserve(element);
      for (const element of watch) if (!observed.has(element)) resize.observe(element);
      observed = watch;
      if (scroll && node) revealTarget(node, dialog);
      const highlight = node && visibleTarget(node, dialog);
      if (!highlight && scroll && key === target.api && !dialog && !attemptedReveal) {
        attemptedReveal = true;
        recover(key);
      }
      scroll = false;
      visible = Boolean(highlight) && (!dialog || modalTarget);
      if (description !== node || !highlight) {
        clearDescription();
        if (node && highlight && (node.matches('a, button, input, select, summary, [tabindex]'))) {
          const previous = node.getAttribute('aria-describedby');
          node.setAttribute('aria-describedby', previous ? `${previous} ${explanationId}` : explanationId);
          description = node;
        }
      }
      hole = highlight;
      bounds = dialog ? intersection(viewBox, dialog.getBoundingClientRect()) : viewBox;
      const preferred = dialog && bounds.right - bounds.left >= 280 && bounds.bottom - bounds.top >= 250 ? bounds : viewBox;
      const width = Math.min(360, Math.max(0, preferred.right - preferred.left - 20));
      tooltipWidth = width;
      const footer = dialog?.querySelector(':scope > footer')?.getBoundingClientRect();
      const aboveFooter = footer && footer.top - preferred.top > 190 && (!highlight || highlight.bottom < footer.top);
      const chrome = popover.offsetHeight - popover.clientHeight + 22;
      position = placeTooltip(preferred, highlight, width, inner.scrollHeight + chrome, aboveFooter ? footer : undefined);

      if (focusedControlStep && focusedControlStep !== currentStep && (document.activeElement === document.body || root.contains(document.activeElement))) {
        focusedControlStep = currentStep;
        popover.focus({ preventScroll: true });
      }
    }

    const observer = new MutationObserver((records) => {
      if (records.some(({ target: element }) => element instanceof Element && !root.contains(element))) schedule();
    });
    observer.observe(document.body, { subtree: true, childList: true, attributes: true,
      attributeFilter: ['open', 'class', 'style', 'data-tutorial', 'data-tutorial-obstruction'] });
    window.addEventListener('scroll', schedule, true);
    window.addEventListener('resize', schedule);
    window.visualViewport?.addEventListener('scroll', schedule);
    window.visualViewport?.addEventListener('resize', schedule);
    reposition = () => { scroll = true; schedule(); };
    schedule();
    return () => {
      window.removeEventListener('scroll', schedule, true);
      window.removeEventListener('resize', schedule);
      window.visualViewport?.removeEventListener('scroll', schedule);
      window.visualViewport?.removeEventListener('resize', schedule);
      cancelAnimationFrame(frame);
      observer.disconnect();
      resize.disconnect();
      clearDescription();
      reposition = undefined;
      root.remove();
    };
  });

  $effect(() => {
    if (step && view.target !== target.close) untrack(() => reposition?.());
  });

  function act(action: TutorialAction) {
    if (step) focusedControlStep = step.id;
    change(action);
  }
</script>

<div class="tutorial-layer" data-spotlight-ui bind:this={layer}>
  {#if hole}
    <div class="mask" aria-hidden="true"
      style:left="{bounds.left}px" style:top="{bounds.top}px" style:width="{bounds.right - bounds.left}px" style:height="{bounds.bottom - bounds.top}px">
      <div class="spotlight" data-tutorial-highlight={modal && !modalTarget ? target.close : view.target}
        style:left="{hole.left - bounds.left}px" style:top="{hole.top - bounds.top}px"
        style:width="{hole.right - hole.left}px" style:height="{hole.bottom - hole.top}px"></div>
    </div>
  {/if}
  <aside class="panel tutorial" bind:this={tooltip} tabindex="-1" aria-label={t('Guided onboarding')}
    style:left="{position.x}px" style:top="{position.y}px" style:max-height="{position.maxHeight}px" style:width="{tooltipWidth}px">
    <div class="tutorial-content" bind:this={content}>
      {#if step}
        <header>
          <small>{lesson ? t('Engineering walkthrough') : t('Chapter {0} of {1} · {2}', [step.chapter + 1, chapters.length, t(chapters[step.chapter])])}</small>
          <small>{t('Step {0} of {1}', [lesson ? lesson.index + 1 : chapterIndex + 1, lesson ? 6 : chapterSteps.length])}</small>
        </header>
        <div class="progress" aria-hidden="true">
          {#each chapters as chapter, i (chapter)}<span class:past={i < step.chapter} class:current={i === step.chapter}></span>{/each}
        </div>
        <div class="copy" id={explanationId} aria-live="polite" aria-atomic="true">
          <h2>{t(step.title)}</h2>
          {#if modal && !modalTarget && view.target}
            <p>{t('Close this dialog to continue the tutorial.')}</p>
          {:else}
            <p>{view.instruction ? t(view.instruction, view.args?.map((arg) => t(arg))) : t(step.text)}</p>
          {/if}
          {#if waiting}<p class="status">{t('Waiting for the server…')}</p>
          {:else if view.target && !visible && !modal}<p class="status">{t('The highlighted control is out of view. Try showing it again, or skip this step.')}</p>
          {:else if ('mode' in step || view.instruction) && !view.allowed && !replay && visible && !view.open}
            <p class="status">{t('Use the highlighted control to continue.')}</p>
          {/if}
        </div>
        <div class="row wrap tutorial-actions">
          {#if index > 0}<button class="btn" disabled={busy} onclick={() => act('back')}>{t('Back')}</button>{/if}
          {#if view.open && !modal && !visible}
            <a class="btn primary" href={link(view.open)}>{t('Open {0}', [t(sections[view.open].name)])}</a>
          {:else if view.retry}
            <button class="btn primary" disabled={busy} onclick={showTarget}>{t('Retry')}</button>
          {:else if (replay || (view.allowed && visible) || (view.allowed && !view.target)) && (!modal || modalTarget)}
            <button class="btn primary" disabled={busy} onclick={() => act('next')}>
              {t(index === onboarding.length - 1 ? 'Finish' : firstInChapter ? 'Continue chapter' : 'Next')}
            </button>
          {:else if (view.target || modal) && !waiting}
            <button class="btn" disabled={busy} onclick={focusTarget}><Focus size={14} />{t(visible ? 'Focus target' : 'Show target')}</button>
          {/if}
          <button class="btn ghost" disabled={busy} onclick={() => act('skip-step')}>{t('Skip step')}</button>
          <button class="btn ghost" disabled={busy} onclick={() => act('skip')}>{t(firstInChapter ? 'Pause tutorial' : 'Skip tutorial')}</button>
        </div>
      {:else}
        <h2>{t('Tutorial complete')}</h2>
        <p>{t('You can revisit the chapters from the Guide or restart the tutorial in Settings.')}</p>
        <button class="btn primary" onclick={complete}>{t('Done')}</button>
      {/if}
    </div>
  </aside>
</div>

<style>
  .tutorial-layer { position: fixed; inset: 0; z-index: var(--layer-tutorial); pointer-events: none; }
  .mask { position: fixed; overflow: hidden; pointer-events: none; }
  .spotlight { position: absolute; border-radius: 8px; color: #d9ff8c; box-shadow: inset 0 0 0 2px currentColor, 0 0 0 2px #11190e, 0 0 0 160vmax #06090bbf; }
  .tutorial { position: fixed; pointer-events: auto; background: var(--raised); border-color: #839d59; padding: 10px; overflow: auto;
    overscroll-behavior: contain; scrollbar-width: thin; box-shadow: 0 10px 35px #000c; }
  .tutorial-content { display: grid; gap: 7px; overflow-wrap: anywhere; }
  header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1px 8px; color: var(--muted); }
  header small { font-size: 11px; }
  .progress { display: flex; gap: 3px; }
  .progress span { height: 2px; flex: 1; background: var(--border); }
  .progress .past { background: #77944d; }
  .progress .current { background: var(--primary); }
  .copy { display: grid; gap: 4px; }
  h2 { font-size: 16px; }
  p { font-size: 13px; }
  .status { color: var(--primary); font-size: 11px; }
  .tutorial-actions { gap: 1px 4px; }
  .tutorial .btn { min-height: 32px; padding-inline: 7px; font-size: 12px; }
  .tutorial .ghost { color: var(--muted); }
</style>
