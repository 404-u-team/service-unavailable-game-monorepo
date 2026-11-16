<script lang="ts">
  import { Button } from '@service-unavailable/ui';
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
  let destination = $state.raw<ReturnType<typeof visibleTarget>>();
  let bounds = $state.raw({ left: 0, right: 0, top: 0, bottom: 0 });
  let position = $state.raw({ x: 10, y: 10, maxHeight: 360 });
  let tooltipWidth = $state(330);
  let modal = $state<HTMLElement>();
  let modalTarget = $state(false);
  let visible = $state(false);
  let menuOpen = $state(false);
  let menuCovered = $state(false);
  const needsAction = $derived(Boolean(view.open || (modal && !modalTarget) || (!view.allowed && !replay)));
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
    let lastDialog: HTMLElement | undefined;
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
      // A slide changes the panel's position without resizing it.
      if (dialog?.getAnimations().some((animation) => animation.pending || animation.playState === 'running')) schedule();
      const viewBox = viewport();
      if (root.parentElement !== (dialog ?? document.body)) {
        const focused = document.activeElement;
        (dialog ?? document.body).append(root);
        root.showPopover();
        if (focused instanceof HTMLElement && root.contains(focused)) focused.focus({ preventScroll: true });
      }
      modal = dialog;
      const currentKey = view.target;
      const desired = findTarget(currentKey, dialog);
      modalTarget = !dialog || !currentKey || Boolean(desired);
      const key = dialog && !modalTarget ? target.close : currentKey;
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
      const menu = document.querySelector<HTMLElement>('.sui-menu[data-state="open"]');
      if (menu) watch.add(menu);
      for (let element: HTMLElement | null | undefined = node; element && element !== document.body; element = element.parentElement) watch.add(element);
      for (const element of observed) if (!watch.has(element)) resize.unobserve(element);
      for (const element of watch) if (!observed.has(element)) resize.observe(element);
      observed = watch;
      if (scroll && node) revealTarget(node, dialog);
      const highlight = node && visibleTarget(node, dialog);
      const linkedPort = key === target.linkOrigin ? findTarget(target.linkDestination) : undefined;
      const highlightedPort = linkedPort && visibleTarget(linkedPort);
      const connectButton = key === target.linkOrigin ? findTarget(target.connect) : undefined;
      const connectBounds = connectButton && visibleTarget(connectButton);
      if (scroll && !dialog && !attemptedReveal && ((!highlight && key === target.api) ||
        (key === target.linkOrigin && (!highlight || !highlightedPort)))) {
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
      destination = highlightedPort;
      const dialogBox = dialog?.getBoundingClientRect();
      bounds = dialogBox ? intersection(viewBox, dialogBox) : viewBox;
      const width = Math.min(360, Math.max(0, viewBox.right - viewBox.left - 20));
      tooltipWidth = width;
      const height = inner.scrollHeight + popover.offsetHeight - popover.clientHeight + 22;
      const menuBox = menu?.getBoundingClientRect();
      const avoid = [highlight, highlightedPort, connectBounds, menuBox].reduce<typeof highlight>((area, next) => area && next ? {
        left: Math.min(area.left, next.left), right: Math.max(area.right, next.right),
        top: Math.min(area.top, next.top), bottom: Math.max(area.bottom, next.bottom)
      } : area ?? next, undefined);
      position = placeTooltip(viewBox, avoid, width, height, dialogBox);
      menuOpen = Boolean(menu);
      const overlap = menuBox && intersection(menuBox, {
        left: position.x, right: position.x + width, top: position.y, bottom: position.y + Math.min(height, position.maxHeight)
      });
      menuCovered = Boolean(overlap && overlap.right > overlap.left && overlap.bottom > overlap.top);

      if (focusedControlStep && focusedControlStep !== currentStep && (document.activeElement === document.body || root.contains(document.activeElement))) {
        focusedControlStep = currentStep;
        popover.focus({ preventScroll: true });
      }
    }

    const observer = new MutationObserver((records) => {
      if (records.some(({ target: element }) => element instanceof Element && !root.contains(element))) schedule();
    });
    observer.observe(document.body, { subtree: true, childList: true, attributes: true,
      attributeFilter: ['data-state', 'class', 'style', 'data-starting-style', 'data-tutorial', 'data-tutorial-obstruction'] });
    document.addEventListener('transitionend', schedule, true);
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
      document.removeEventListener('transitionend', schedule, true);
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

<!-- Keep the guide in the dialog's focus scope while displaying it above the dialog's clipping and animation. -->
<div class="tutorial-layer" popover="manual" data-spotlight-ui bind:this={layer}>
  {#if hole}
    <div class="mask" aria-hidden="true"
      style:left="{bounds.left}px" style:top="{bounds.top}px" style:width="{bounds.right - bounds.left}px" style:height="{bounds.bottom - bounds.top}px">
      <div class="spotlight" class:port={view.target === target.linkOrigin} class:menu-open={menuOpen} data-tutorial-highlight={modal && !modalTarget ? target.close : view.target}
        style:left="{hole.left - bounds.left}px" style:top="{hole.top - bounds.top}px"
        style:width="{hole.right - hole.left}px" style:height="{hole.bottom - hole.top}px"></div>
      {#if destination}
        <div class="spotlight port" data-tutorial-highlight={target.linkDestination}
          style:left="{destination.left - bounds.left}px" style:top="{destination.top - bounds.top}px"
          style:width="{destination.right - destination.left}px" style:height="{destination.bottom - destination.top}px"></div>
      {/if}
    </div>
  {/if}
  <aside class="panel tutorial" class:menu-covered={menuCovered} bind:this={tooltip} tabindex="-1" aria-label={t('Guided onboarding')}
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
          <small class="step-type" class:action={needsAction}>{t(needsAction ? 'Action required' : 'Review and continue')}</small>
          <h2>{t(step.title)}</h2>
          {#if modal && !modalTarget && view.target}
            <p>{t('Close this dialog to continue the tutorial.')}</p>
          {:else}
            <p>{view.instruction ? t(view.instruction, view.args?.map((arg) => t(arg))) : t(step.text)}</p>
          {/if}
          {#if waiting}<p class="status">{t('Waiting for the server…')}</p>
          {:else if view.target && !visible && !modal}<p class="status">{t('The highlighted control is out of view. Try showing it again, or skip this step.')}</p>
          {/if}
        </div>
        <div class="row wrap tutorial-actions">
          {#if index > 0}<Button disabled={busy} onclick={() => act('back')}>{t('Back')}</Button>{/if}
          {#if view.open && !modal && !visible}
            <Button variant="primary" href={link(view.open)}>{t('Open {0}', [t(sections[view.open].name)])}</Button>
          {:else if view.retry}
            <Button variant="primary" disabled={busy} onclick={showTarget}>{t('Retry')}</Button>
          {:else if (replay || (view.allowed && visible) || (view.allowed && !view.target)) && (!modal || modalTarget)}
            <Button variant="primary" disabled={busy} onclick={() => act('next')}>
              {t(index === onboarding.length - 1 ? 'Finish' : firstInChapter ? 'Continue chapter' : 'Next')}
            </Button>
          {:else if (view.target || modal) && !waiting}
            <Button disabled={busy} onclick={focusTarget}><Focus size={14} />{t(visible ? 'Focus target' : 'Show target')}</Button>
          {/if}
          <Button variant="ghost" disabled={busy} onclick={() => act('skip-step')}>{t('Skip step')}</Button>
          <Button variant="ghost" disabled={busy} onclick={() => act('skip')}>{t(firstInChapter ? 'Pause tutorial' : 'Skip tutorial')}</Button>
        </div>
      {:else}
        <h2>{t('Tutorial complete')}</h2>
        <p>{t('You can revisit the chapters from the Guide or restart the tutorial in Settings.')}</p>
        <Button variant="primary" onclick={complete}>{t('Done')}</Button>
      {/if}
    </div>
  </aside>
</div>

<style>
  .tutorial-layer { position: fixed; inset: 0; width: auto; height: auto; max-width: none; max-height: none;
    margin: 0; padding: 0; border: 0; background: transparent; color: var(--text); pointer-events: none; overflow: clip; }
  .mask { position: absolute; overflow: hidden; pointer-events: none; }
  .spotlight { position: absolute; border-radius: 8px; color: #d9ff8c; box-shadow: inset 0 0 0 2px currentColor, 0 0 0 2px #11190e, 0 0 0 160vmax #06090bbf; }
  .spotlight.menu-open { box-shadow: inset 0 0 0 2px currentColor; }
  .spotlight.port { border-radius: 50%; box-shadow: inset 0 0 0 2px currentColor, 0 0 10px 2px #c7f46c88; }
  .tutorial { position: absolute; pointer-events: auto; background: var(--raised); border-color: #839d59; padding: 10px; overflow: auto;
    overscroll-behavior: contain; scrollbar-width: thin; box-shadow: 0 10px 35px #000c; }
  .tutorial.menu-covered { visibility: hidden; pointer-events: none; }
  .tutorial-content { display: grid; gap: 7px; overflow-wrap: anywhere; }
  header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1px 8px; color: var(--muted); }
  header small { font-size: 11px; }
  .progress { display: flex; gap: 3px; }
  .progress span { height: 2px; flex: 1; background: var(--border); }
  .progress .past { background: #77944d; }
  .progress .current { background: var(--primary); }
  .copy { display: grid; gap: 4px; }
  .step-type { color: var(--muted); font-weight: 650; font-size: 11px; }
  .step-type.action { color: var(--primary); }
  h2 { font-size: 16px; }
  p { font-size: 13px; }
  .status { color: var(--primary); font-size: 11px; }
  .tutorial-actions { gap: 1px 4px; }
  .tutorial :global(.sui-button) { min-height: 32px; padding-inline: 7px; font-size: 12px; }
  .tutorial :global([data-variant='ghost']) { color: var(--muted); }
</style>
