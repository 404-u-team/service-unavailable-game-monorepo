<script lang="ts">
  import type { Snippet } from 'svelte';

  let { title, children, actions, handle, resize }: {
    title: string;
    children: Snippet;
    actions?: Snippet;
    handle?: Snippet;
    resize?: Snippet;
  } = $props();

  const heading = $props.id();
</script>

<article aria-labelledby={heading} class:resizable={!!resize}>
  <header>
    {@render handle?.()}
    <h3 id={heading}>{title}</h3>
    {@render actions?.()}
  </header>
  <div class="body">{@render children()}</div>
  {@render resize?.()}
</article>

<style>
  article {
    box-sizing: border-box; position: relative; display: flex; flex-direction: column;
    min-inline-size: 0; block-size: 100%; min-block-size: 0;
    background: var(--sui-surface); color: var(--sui-text); border: 1px solid var(--sui-border);
    border-radius: var(--sui-radius-panel); font: var(--sui-body);
  }
  header {
    display: flex; align-items: center; gap: var(--sui-space-2); min-block-size: 2.75rem;
    border-block-end: 1px solid var(--sui-border); padding-inline: var(--sui-space-3);
  }
  h3 { flex: 1; min-inline-size: 0; margin: 0; padding-block: var(--sui-space-2); font: 700 1rem/1.3 var(--sui-heading); overflow-wrap: anywhere; }
  .body { min-block-size: 0; min-inline-size: 0; overflow: auto; padding: var(--sui-space-3); overscroll-behavior: contain; }
  .resizable .body { margin-block-end: 1.5rem; }
</style>
