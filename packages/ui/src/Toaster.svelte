<script lang="ts">
  import { tick } from 'svelte';
  import { X } from '@lucide/svelte';
  import type { ToastItem, Toasts } from './toasts.svelte';

  let { toasts, label, dismissLabel }: { toasts: Toasts; label: string; dismissLabel: (title: string) => string } = $props();

  const buttons = new Map<number, HTMLButtonElement>();
  let visibility = $state<DocumentVisibilityState>('visible');
  let priorFocus: HTMLElement | undefined;

  function register(node: HTMLButtonElement, id: number) {
    buttons.set(id, node);
    return { destroy: () => { buttons.delete(id); } };
  }

  function rememberFocus(event: FocusEvent & { currentTarget: HTMLElement }) {
    const from = event.relatedTarget;
    if (from instanceof HTMLElement && !event.currentTarget.contains(from)) priorFocus = from;
  }

  async function dismiss(item: ToastItem) {
    const index = toasts.items.indexOf(item);
    const focused = buttons.get(item.id) === document.activeElement;
    toasts.dismiss(item.id);
    if (!focused) return;
    await tick();
    const neighbor = toasts.items[Math.min(index, toasts.items.length - 1)];
    (neighbor ? buttons.get(neighbor.id) : priorFocus)?.focus({ preventScroll: true });
  }
</script>

<svelte:document bind:visibilityState={visibility} />

<div class="sui-sr-only" aria-live="polite" aria-relevant="additions" aria-atomic="false">
  {#each toasts.items.filter((item) => item.announce !== 'assertive') as item (item.id)}
    <div>{item.title}{item.description ? '. ' + item.description : ''}</div>
  {/each}
</div>
<div class="sui-sr-only" aria-live="assertive" aria-relevant="additions" aria-atomic="false">
  {#each toasts.items.filter((item) => item.announce === 'assertive') as item (item.id)}
    <div>{item.title}{item.description ? '. ' + item.description : ''}</div>
  {/each}
</div>

{#if toasts.items.length}
  <section class="toasts" class:paused={visibility === 'hidden'} aria-label={label} onfocusin={rememberFocus}>
    <ul>
      {#each toasts.items as item (item.id)}
        {@const duration = item.duration ?? 6000}
        <li data-sui-tone={item.tone ?? 'info'}>
          <div>
            <strong>{item.title}</strong>
            {#if item.description}<p>{item.description}</p>{/if}
          </div>
          <button type="button" class="sui-button" data-variant="ghost" data-icon-only use:register={item.id}
            aria-label={dismissLabel(item.title)} onclick={() => void dismiss(item)}>
            <X size={17} aria-hidden="true" />
          </button>
          {#if duration > 0 && Number.isFinite(duration)}
            <span class="timer" aria-hidden="true" style:--duration={`${duration}ms`} onanimationend={() => void dismiss(item)}></span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .toasts {
    position: fixed; z-index: var(--sui-layer-toast); inset-block-end: max(var(--sui-space-4), env(safe-area-inset-bottom));
    inset-inline-end: var(--sui-space-4); inline-size: min(22rem, calc(100% - 2 * var(--sui-space-4))); max-block-size: 55dvh;
    overflow: auto; overscroll-behavior: contain; padding: 5px; box-sizing: border-box;
  }
  ul { display: grid; gap: var(--sui-space-2); padding: 0; margin: 0; list-style: none; }
  li {
    position: relative; overflow: hidden; display: flex; align-items: start; justify-content: space-between; gap: var(--sui-space-2);
    border: 1px solid var(--sui-border);
    border-radius: var(--sui-radius); background: var(--sui-tone-surface); color: var(--sui-text);
    font: var(--sui-body); padding: var(--sui-space-2) var(--sui-space-3); overflow-wrap: anywhere;
  }
  .timer {
    position: absolute; inset: auto 0 0; block-size: 2px; pointer-events: none; background: var(--sui-tone-text);
    transform-origin: left; animation: countdown var(--duration) linear forwards;
  }
  .timer:dir(rtl) { transform-origin: right; }
  @keyframes countdown { to { transform: scaleX(0); } }
  li:focus-within .timer, .paused .timer { animation-play-state: paused; }
  @media (hover: hover) { li:hover .timer { animation-play-state: paused; } }
  @media (prefers-reduced-motion: reduce) { .timer { animation-timing-function: step-end; } }
  strong { color: var(--sui-tone-text); }
  p { margin: var(--sui-space-1) 0 0; }
</style>
