<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Tone } from './types';

  let { title, children, tone = 'info', announce }: {
    title?: string;
    children: Snippet;
    tone?: Tone;
    announce?: 'polite' | 'assertive';
  } = $props();
</script>

<div class="alert" data-sui-tone={tone} role={announce === 'assertive' ? 'alert' : announce === 'polite' ? 'status' : undefined}>
  {#if title}<strong>{title}</strong>{/if}
  <div>{@render children()}</div>
</div>

<style>
  .alert { display: grid; gap: var(--sui-space-1); padding: var(--sui-space-3); border-inline-start: 3px solid var(--sui-tone-text); border-radius: var(--sui-radius); background: var(--sui-tone-surface); color: var(--sui-text); font: var(--sui-body); overflow-wrap: anywhere; }
  strong { color: var(--sui-tone-text); }
</style>
