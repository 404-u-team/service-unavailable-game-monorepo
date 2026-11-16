<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { FieldControl } from './types';

  let { label, id, hint, error, help, children }: {
    label: string;
    id?: string;
    hint?: string;
    error?: string;
    help?: Snippet;
    children: Snippet<[FieldControl]>;
  } = $props();

  const uid = $props.id();
  const controlId = $derived(id ?? uid);
  const hintId = `${uid}-hint`;
  const errorId = `${uid}-error`;
  const control = $derived({
    id: controlId,
    'aria-describedby': [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined,
    'aria-invalid': error ? true : undefined
  });
</script>

<div class="field">
  <div class="caption">
    <label for={controlId}>{label}</label>
    {@render help?.()}
  </div>
  {@render children(control)}
  {#if hint}<small id={hintId}>{hint}</small>{/if}
  {#if error}<small id={errorId} class="error">{error}</small>{/if}
</div>

<style>
  .field { display: grid; gap: var(--sui-space-1); min-inline-size: 0; color: var(--sui-text); font: var(--sui-body); }
  .caption { display: flex; justify-content: space-between; align-items: center; gap: var(--sui-space-2); }
  label { font-weight: 600; }
  small { color: var(--sui-muted); font-size: 0.8125rem; overflow-wrap: anywhere; }
  .error { color: var(--sui-danger); }
</style>
