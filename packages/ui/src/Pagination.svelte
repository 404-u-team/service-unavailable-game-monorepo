<script lang="ts">
  import { ChevronLeft, ChevronRight } from '@lucide/svelte';
  import Button from './Button.svelte';

  let { page, pages, label, previousLabel, nextLabel, pageLabel, onchange }: {
    page: number; pages: number; label: string; previousLabel: string; nextLabel: string;
    pageLabel: (page: number, pages: number) => string; onchange: (page: number) => void;
  } = $props();
  const total = $derived(Math.max(1, Math.trunc(pages) || 1));
  const current = $derived(Math.min(total, Math.max(1, Math.trunc(page) || 1)));
</script>

{#if total > 1}
  <nav aria-label={label}>
    <Button aria-label={previousLabel} iconOnly disabled={current <= 1} onclick={() => onchange(current - 1)}>
      <ChevronLeft size={18} aria-hidden="true" />
    </Button>
    <output aria-live="polite">{pageLabel(current, total)}</output>
    <Button aria-label={nextLabel} iconOnly disabled={current >= total} onclick={() => onchange(current + 1)}>
      <ChevronRight size={18} aria-hidden="true" />
    </Button>
  </nav>
{/if}

<style>
  nav { display: flex; align-items: center; justify-content: center; gap: var(--sui-space-3); }
  output { color: var(--sui-muted); font: var(--sui-caption); text-align: center; }
  nav:dir(rtl) :global(svg) { transform: scaleX(-1); }
</style>
