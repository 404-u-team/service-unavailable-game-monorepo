<script lang="ts">
  import { Tabs } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { TabItem } from './types';

  let { label, items, value = $bindable(''), activation = 'automatic', children }: {
    label: string;
    items: readonly TabItem[];
    value?: string;
    activation?: 'automatic' | 'manual';
    children: Snippet<[TabItem]>;
  } = $props();

  const active = $derived(items.find((item) => item.value === value && !item.disabled)?.value
    ?? items.find((item) => !item.disabled)?.value ?? '');
</script>

<Tabs.Root value={active} onValueChange={(next) => value = next} activationMode={activation} loop>
  <Tabs.List aria-label={label} class="sui-tabs">
    {#each items as item (item.value)}
      <Tabs.Trigger class="sui-focus sui-tab" value={item.value} disabled={item.disabled}>{item.label}</Tabs.Trigger>
    {/each}
  </Tabs.List>
  {#each items as item (item.value)}
    <Tabs.Content class="sui-focus sui-tab-panel" value={item.value}>
      {@render children(item)}
    </Tabs.Content>
  {/each}
</Tabs.Root>

<style>
  :global(.sui-tabs) { display: flex; flex-wrap: wrap; gap: var(--sui-space-1); border-block-end: 1px solid var(--sui-border); }
  :global(.sui-tab) { min-block-size: var(--sui-target); border: 0; border-block-end: 2px solid transparent; padding: var(--sui-space-2) var(--sui-space-3); background: transparent; color: var(--sui-muted); font: var(--sui-body); font-weight: 600; cursor: pointer; }
  :global(.sui-tab:hover:enabled), :global(.sui-tab[data-state='active']) { color: var(--sui-text); border-color: var(--sui-primary); }
  :global(.sui-tab:disabled) { opacity: 0.55; cursor: default; }
  :global(.sui-tab-panel) { padding-block: var(--sui-space-4); color: var(--sui-text); font: var(--sui-body); }
</style>
