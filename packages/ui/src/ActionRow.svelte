<script lang="ts">
  import { ChevronRight } from '@lucide/svelte';
  import type { Snippet } from 'svelte';
  import Button from './Button.svelte';

  let { title, description, href, onclick, icon, status, attributes }: {
    title: string;
    description?: string;
    href?: string;
    onclick?: () => void;
    icon?: Snippet;
    status?: Snippet;
    attributes?: Record<`data-${string}`, string | undefined>;
  } = $props();
</script>

<div class="frame">
  <Button {...attributes} {href} {onclick} variant="ghost" block class="sui-action-row">
    {#if icon}<span class="icon" aria-hidden="true">{@render icon()}</span>{/if}
    <span class="copy">
      <strong>{title}</strong>
      {#if description}<span>{description}</span>{/if}
    </span>
    {#if status}<span class="status">{@render status()}</span>{/if}
    <ChevronRight class="arrow" size={16} aria-hidden="true" />
  </Button>
</div>

<style>
  .frame > :global(.sui-action-row) {
    justify-content: start; text-align: start; padding: var(--sui-space-3);
    border: 1px solid var(--sui-border); background: var(--sui-inset);
  }
  .frame > :global(.sui-action-row:hover) { border-color: var(--sui-control-border); background: var(--sui-raised); }
  .copy { display: grid; flex: 1; min-inline-size: 0; gap: var(--sui-space-1); }
  strong { font: 700 1rem/1.25 var(--sui-heading); }
  .copy > span { color: var(--sui-muted); font: var(--sui-body); font-size: 0.8125rem; }
  .status { max-inline-size: 38%; }
  .icon { display: grid; place-items: center; flex: none; color: var(--sui-primary); }
  .frame :global(.arrow) { flex: none; color: var(--sui-muted); }
</style>
