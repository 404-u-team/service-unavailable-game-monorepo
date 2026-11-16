<script lang="ts">
  import { ChevronDown } from '@lucide/svelte';
  import type { Snippet } from 'svelte';

  let { label, open = $bindable(false), name, variant = 'inline', summaryAttributes, summary, children }: {
    label: string;
    open?: boolean;
    name?: string;
    variant?: 'inline' | 'panel';
    summaryAttributes?: Record<`data-${string}`, string | undefined>;
    summary?: Snippet;
    children: Snippet;
  } = $props();
</script>

<details {name} bind:open class:panel={variant === 'panel'}>
  <summary {...summaryAttributes} class="sui-focus">
    <ChevronDown size={16} aria-hidden="true" />
    <span class="label">
      <span>{label}</span>
      {@render summary?.()}
    </span>
  </summary>
  <div class="body">{@render children()}</div>
</details>

<style>
  details { min-inline-size: 0; color: var(--sui-text); font: var(--sui-body); }
  summary {
    box-sizing: border-box; display: flex; align-items: center; gap: var(--sui-space-2);
    min-block-size: var(--sui-target); padding-block: var(--sui-space-2);
    list-style: none; border-radius: var(--sui-radius); color: var(--sui-info); cursor: pointer; font-weight: 600;
  }
  summary::-webkit-details-marker { display: none; }
  .label { display: flex; flex: 1; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--sui-space-1) var(--sui-space-3); min-inline-size: 0; }
  summary > :global(svg) { flex: none; transform: rotate(-90deg); transition: transform var(--sui-motion); }
  summary:dir(rtl) > :global(svg) { transform: rotate(90deg); }
  details[open] summary > :global(svg) { transform: none; }
  .panel { border: 1px solid var(--sui-border); border-radius: var(--sui-radius); background: var(--sui-surface); }
  .panel summary { flex-direction: row-reverse; justify-content: space-between; padding-inline: var(--sui-space-3); color: var(--sui-text); }
  .panel .body { border-block-start: 1px solid var(--sui-border); padding: var(--sui-space-3); }
</style>
