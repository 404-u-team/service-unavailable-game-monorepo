<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';

  let { children, columns = 3, minWidth = '15rem', gap = 'var(--sui-space-4)', class: className, ...attrs }:
    HTMLAttributes<HTMLDivElement> & { children: Snippet; columns?: 2 | 3 | 4; minWidth?: string; gap?: string } = $props();
</script>

<div {...attrs} class={['columns', className]} style:--columns={columns} style:--min-width={minWidth} style:--gap={gap}>
  {@render children()}
</div>

<style>
  .columns {
    display: grid; gap: var(--gap); align-items: start; min-inline-size: 0;
    --column-width: calc((100% - (var(--columns) - 1) * var(--gap)) / var(--columns));
    grid-template-columns: repeat(auto-fit, minmax(min(100%, max(var(--min-width), var(--column-width))), 1fr));
  }
  .columns > :global(*) { min-inline-size: 0; }
</style>
