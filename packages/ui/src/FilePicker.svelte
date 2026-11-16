<script lang="ts">
  import type { Snippet } from 'svelte';

  let { label, accept, disabled = false, variant = 'secondary', onchange, children }: {
    label: string;
    accept?: string;
    disabled?: boolean;
    variant?: 'primary' | 'secondary';
    onchange: (file: File) => void;
    children: Snippet;
  } = $props();

  function select(event: Event & { currentTarget: HTMLInputElement }) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (file) onchange(file);
  }
</script>

<label class="sui-button" data-variant={variant}>
  {@render children()}
  <input type="file" aria-label={label} {accept} {disabled} onchange={select} />
</label>

<style>
  label { position: relative; }
  label:has(input:focus-visible) { outline: 2px solid var(--sui-primary); outline-offset: 3px; }
  label:has(input:disabled) { opacity: .6; cursor: default; }
  input { position: absolute; inset: 0; inline-size: 100%; block-size: 100%; opacity: 0; cursor: inherit; }
</style>
