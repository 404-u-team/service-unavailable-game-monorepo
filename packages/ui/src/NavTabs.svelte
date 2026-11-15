<script lang="ts">
  import type { NavItem } from './types';

  let { label, items }: { label: string; items: readonly NavItem[] } = $props();
</script>

<nav aria-label={label}>
  {#each items as item (item.href)}
    <a href={item.href} class="sui-focus" aria-current={item.current ? 'page' : undefined}>{item.label}</a>
  {/each}
</nav>

<style>
  nav { display: flex; flex-wrap: wrap; gap: var(--sui-space-1); border-block-end: 1px solid var(--sui-border); }
  a { box-sizing: border-box; display: flex; align-items: center; min-block-size: var(--sui-target); padding: var(--sui-space-2) var(--sui-space-3); border-block-end: 2px solid transparent; color: var(--sui-muted); font: var(--sui-body); font-weight: 600; text-decoration: none; }
  a:hover, a[aria-current] { border-color: var(--sui-primary); color: var(--sui-text); }
</style>
