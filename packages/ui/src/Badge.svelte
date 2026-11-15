<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Tone } from './types';

  let { children, tone = 'neutral' }: { children: Snippet; tone?: Tone } = $props();
</script>

<span class="badge" data-sui-tone={tone}>{@render children()}</span>

<style>
  .badge { display: inline-block; max-inline-size: 100%; box-sizing: border-box; padding: var(--sui-space-1) var(--sui-space-2); border-radius: var(--sui-radius-sm); color: var(--sui-tone-text); background: var(--sui-tone-surface); font: var(--sui-caption); overflow-wrap: anywhere; }
</style>
