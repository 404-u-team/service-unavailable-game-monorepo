<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';

  let { anchor, element = $bindable<HTMLDivElement>(), children, ontoggle, ...attributes }: HTMLAttributes<HTMLDivElement> & {
    anchor: HTMLButtonElement | undefined; element?: HTMLDivElement; children: Snippet;
  } = $props();
  let open = $state(false);

  function position() {
    if (!anchor || !element) return;
    const bounds = anchor.getBoundingClientRect();
    const width = Math.min(window.innerWidth - 16, Math.max(bounds.width, 216));
    const below = window.innerHeight - bounds.bottom - 8;
    const above = bounds.top - 8;
    const showAbove = below < 220 && above > below;
    element.style.width = `${width}px`;
    element.style.left = `${Math.max(8, Math.min(bounds.left, window.innerWidth - width - 8))}px`;
    element.style.maxHeight = `${Math.max(40, Math.min(330, showAbove ? above : below))}px`;
    element.style.top = showAbove ? 'auto' : `${bounds.bottom + 4}px`;
    element.style.bottom = showAbove ? `${window.innerHeight - bounds.top + 4}px` : 'auto';
  }
</script>

<svelte:window onresize={() => { if (open) position(); }} onscrollcapture={() => { if (open) position(); }} />

<div {...attributes} popover="auto" bind:this={element} class="popover" role="presentation" tabindex="-1"
  onbeforetoggle={(event) => { if (event.newState === 'open') position(); }}
  ontoggle={(event) => { open = event.newState === 'open'; ontoggle?.(event); }}>
  {@render children()}
</div>

<style>
  .popover { position: fixed; margin: 0; padding: 5px; border: 1px solid var(--sui-border); border-radius: 9px; background: var(--sui-surface); color: var(--sui-text); box-shadow: var(--sui-shadow); overflow: auto; }
</style>
