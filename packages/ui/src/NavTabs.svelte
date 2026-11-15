<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';
  import type { NavItem } from './types';

  let { label, items, icon, variant = 'bar', class: className, ...attrs }:
    HTMLAttributes<HTMLElement> & {
      label: string; items: readonly NavItem[]; icon?: Snippet<[NavItem]>;
      variant?: 'bar' | 'rail' | 'dock';
    } = $props();
</script>

<nav {...attrs} class={['sui-nav', className]} data-variant={variant} aria-label={label}>
  {#each items as item (item.href)}
    <a {...item.attributes} href={item.href} class="sui-focus" aria-current={item.current ? 'page' : undefined}>
      {#if icon}<span class="icon" aria-hidden="true">{@render icon(item)}</span>{/if}
      <span>{item.label}</span>
    </a>
  {/each}
</nav>

<style>
  nav { display: flex; gap: var(--sui-space-1); min-inline-size: 0; }
  nav[data-variant='bar'] { flex-wrap: wrap; border-block-end: 1px solid var(--sui-border); }
  a {
    box-sizing: border-box; display: flex; align-items: center; gap: var(--sui-space-1); min-block-size: var(--sui-target);
    padding: var(--sui-space-2) var(--sui-space-3); border-block-end: 2px solid transparent; color: var(--sui-muted);
    font: var(--sui-body); font-weight: 600; text-decoration: none;
  }
  nav[data-variant='bar'] a:is(:hover, [aria-current]) { border-color: var(--sui-primary); color: var(--sui-text); }
  nav[data-variant='rail'] { flex-direction: column; }
  nav[data-variant='dock'] { justify-content: space-between; }
  nav:not([data-variant='bar']) a {
    display: flex; flex-direction: column; justify-content: center; padding: var(--sui-space-1); border: 0;
    min-inline-size: 0; text-align: center; font-size: 0.6875rem; line-height: 1.2; overflow-wrap: anywhere;
  }
  nav[data-variant='dock'] a { flex: 1; }
  nav:not([data-variant='bar']) a:is(:hover, [aria-current]) { color: var(--sui-text); }
  nav:not([data-variant='bar']) a:is(:hover, [aria-current]) .icon { background: var(--sui-tint); color: var(--sui-primary); }
  .icon { display: grid; place-items: center; flex: none; }
  nav:not([data-variant='bar']) .icon { border-radius: var(--sui-radius); inline-size: 2.75rem; block-size: 2rem; }
</style>
