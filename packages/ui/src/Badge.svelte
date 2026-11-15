<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Tone } from './types';

  let { children, tone = 'neutral', class: className }: { children: Snippet; tone?: Tone; class?: string } = $props();
</script>

<span class={['sui-badge', className]} data-sui-tone={tone}>{@render children()}</span>

<style>
  .sui-badge { display: inline-flex; align-items: center; gap: var(--sui-space-1); inline-size: fit-content; max-inline-size: 100%; box-sizing: border-box; padding: var(--sui-space-1) var(--sui-space-2); border-radius: var(--sui-radius-sm); color: var(--sui-tone-text); background: var(--sui-tone-surface); font: var(--sui-caption); overflow-wrap: anywhere; }
</style>
