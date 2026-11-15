<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';

  let { children, header, footer, inset = false, class: className, ...attrs }: HTMLAttributes<HTMLDivElement> & {
    children: Snippet;
    header?: Snippet;
    footer?: Snippet;
    inset?: boolean;
  } = $props();
</script>

<div {...attrs} class={['panel', className]} class:inset>
  {#if header}<div class="header">{@render header()}</div>{/if}
  <div class="body">{@render children()}</div>
  {#if footer}<div class="footer">{@render footer()}</div>{/if}
</div>

<style>
  .panel { box-sizing: border-box; min-inline-size: 0; border: 1px solid var(--sui-border); border-radius: var(--sui-radius-panel); background: var(--sui-surface); color: var(--sui-text); font: var(--sui-body); overflow-wrap: anywhere; }
  .inset { background: var(--sui-inset); }
  .header, .body, .footer { padding: var(--sui-space-4); }
  .header { border-block-end: 1px solid var(--sui-border); }
  .footer { border-block-start: 1px solid var(--sui-border); }
</style>
