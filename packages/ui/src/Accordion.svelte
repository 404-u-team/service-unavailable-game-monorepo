<script lang="ts" generics="Item extends AccordionItem">
  import type { Snippet } from 'svelte';
  import Disclosure from './Disclosure.svelte';
  import type { AccordionItem } from './types';

  let { items, multiple = false, initialOpen, summary: itemSummary, children }: {
    items: readonly Item[];
    multiple?: boolean;
    initialOpen?: string;
    summary?: Snippet<[Item]>;
    children: Snippet<[Item]>;
  } = $props();

  const group = $props.id();
</script>

<div class="accordion">
  {#each items as item (item.id)}
    <Disclosure label={item.title} name={multiple ? undefined : group} open={item.id === initialOpen} variant="panel">
      {#snippet summary()}{@render itemSummary?.(item)}{/snippet}
      {@render children(item)}
    </Disclosure>
  {/each}
</div>

<style>
  .accordion { display: grid; gap: var(--sui-space-2); color: var(--sui-text); font: var(--sui-body); }
</style>
