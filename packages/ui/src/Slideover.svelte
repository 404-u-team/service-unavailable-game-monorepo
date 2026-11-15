<script lang="ts">
  import Overlay from './Overlay.svelte';
  import type { OverlayProps } from './types';

  let { open = $bindable(false), width = $bindable(448), side = 'end',
    minWidth = 320, maxWidth = 800, resizeLabel, ...props }: OverlayProps & {
    side?: 'start' | 'end';
    width?: number;
    minWidth?: number;
    maxWidth?: number;
    resizeLabel?: string;
  } = $props();

  const panelId = $props.id();
  let viewport = $state(0);
  let dragging: { pointer: number; x: number; width: number; direction: number } | undefined;
  const compact = $derived(viewport > 0 && viewport < minWidth + 72);
  const min = $derived(Math.min(minWidth, viewport || minWidth));
  const max = $derived(Math.max(min, Math.min(maxWidth, viewport ? viewport - 24 : maxWidth)));
  const panelWidth = $derived(Math.round(Math.min(max, Math.max(min, width))));

  function resize(next: number) {
    width = Math.round(Math.min(max, Math.max(min, next)));
  }

  function direction(handle: HTMLElement) {
    const rtl = getComputedStyle(handle).direction === 'rtl';
    return (side === 'start') !== rtl ? 1 : -1;
  }

  function startDrag(event: PointerEvent & { currentTarget: HTMLElement }) {
    if (!event.isPrimary || event.button !== 0) return;
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    handle.focus({ preventScroll: true });
    dragging = { pointer: event.pointerId, x: event.clientX, width: panelWidth, direction: direction(handle) };
    event.preventDefault();
  }

  function moveDrag(event: PointerEvent) {
    if (dragging?.pointer === event.pointerId) resize(dragging.width + (event.clientX - dragging.x) * dragging.direction);
  }

  function endDrag(event: PointerEvent) {
    if (dragging?.pointer === event.pointerId) dragging = undefined;
  }

  function resizeKey(event: KeyboardEvent & { currentTarget: HTMLElement }) {
    const step = (event.shiftKey ? 64 : 16) * direction(event.currentTarget);
    const next = { ArrowLeft: panelWidth - step, ArrowRight: panelWidth + step, Home: min, End: max }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    resize(next);
  }
</script>

<svelte:window bind:innerWidth={viewport} />

<Overlay {...props} bind:open {side} {panelId} width={compact ? viewport : panelWidth}>
  {#snippet handle()}
    {#if resizeLabel && !compact && max > min}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (A focusable separator is an interactive window splitter.) -->
      <div class="grip sui-focus" class:start={side === 'start'} role="separator" tabindex="0"
        aria-label={resizeLabel} aria-orientation="vertical" aria-controls={panelId}
        aria-valuemin={min} aria-valuemax={max} aria-valuenow={panelWidth}
        onpointerdown={startDrag} onpointermove={moveDrag} onpointerup={endDrag}
        onpointercancel={endDrag} onlostpointercapture={endDrag} onkeydown={resizeKey}></div>
    {/if}
  {/snippet}
</Overlay>

<style>
  .grip {
    box-sizing: border-box; position: absolute; z-index: 1; inset-block: 0; inset-inline-start: 0;
    display: grid; place-items: center; inline-size: 1.5rem; border-inline-start: 1px solid transparent;
    cursor: ew-resize; touch-action: none;
  }
  .grip.start { inset-inline: auto 0; border-inline: 0 1px solid transparent; }
  .grip::before { content: ''; inline-size: 0.25rem; block-size: 2rem; border-radius: 999px; background: var(--sui-control-border); }
  .grip:is(:hover, :focus-visible)::before { background: var(--sui-primary); }
  .grip:focus-visible { outline-offset: -3px; }
</style>
