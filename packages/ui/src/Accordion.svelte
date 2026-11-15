<script lang="ts">
  import type { Snippet } from 'svelte';
  import Disclosure from './Disclosure.svelte';
  import type { AccordionItem } from './types';

  let { items, multiple = false, initialOpen, children }: {
    items: readonly AccordionItem[];
    multiple?: boolean;
    initialOpen?: string;
    children: Snippet<[AccordionItem]>;
  } = $props();

  const group = $props.id();
</script>

<div class="accordion">
  {#each items as item (item.id)}
    <Disclosure label={item.title} name={multiple ? undefined : group} open={item.id === initialOpen} variant="panel">
      {@render children(item)}
    </Disclosure>
  {/each}
</div>

<style>
  .accordion { display: grid; gap: var(--sui-space-2); color: var(--sui-text); font: var(--sui-body); }
</style>
