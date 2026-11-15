<script lang="ts">
  import { Check, Minus } from '@lucide/svelte';
  import type { CheckProps } from './types';

  let { label, description, checked = $bindable(false), switchStyle = false, indeterminate = $bindable(false), ...attrs }:
    CheckProps & { switchStyle?: boolean; indeterminate?: boolean } = $props();

  const uid = $props.id();
  const labelId = `${uid}-label`;
  const descriptionId = `${uid}-description`;
  const describedBy = $derived([attrs['aria-describedby'], description && descriptionId].filter(Boolean).join(' ') || undefined);
</script>

<label class="check" class:switchStyle>
  <input {...attrs} type="checkbox" role={switchStyle ? 'switch' : undefined} class={['sui-focus', attrs.class]}
    bind:checked bind:indeterminate aria-labelledby={attrs['aria-labelledby'] ?? labelId} aria-describedby={describedBy} />
  {#if !switchStyle}
    <span class="mark" aria-hidden="true">
      {#if indeterminate}<Minus size={13} strokeWidth={3} />{:else if checked}<Check size={13} strokeWidth={3} />{/if}
    </span>
  {/if}
  <span class="copy">
    <span id={labelId}>{label}</span>
    {#if description}<small id={descriptionId}>{description}</small>{/if}
  </span>
</label>

<style>
  .check { position: relative; display: flex; align-items: center; gap: var(--sui-space-3); min-block-size: var(--sui-target); width: fit-content; color: var(--sui-text); font: var(--sui-body); }
  .check:has(input:enabled) { cursor: pointer; }
  .check:has(input:disabled) { opacity: 0.55; }
  .copy { display: grid; padding-block: var(--sui-space-2); }
  small { color: var(--sui-muted); font-size: 0.8125rem; }
  input { inline-size: 1.125rem; block-size: 1.125rem; flex: none; margin: 0; accent-color: var(--sui-primary); color-scheme: dark; }
  .switchStyle input {
    appearance: none; box-sizing: border-box; display: grid; align-items: center; inline-size: 2.375rem; block-size: 1.375rem;
    border: 1px solid var(--sui-control-border); border-radius: 999px; padding-inline: 3px; background: var(--sui-raised);
  }
  .switchStyle input::before { content: ''; inline-size: 0.875rem; block-size: 0.875rem; border-radius: 50%; background: var(--sui-muted); }
  .switchStyle input:checked { background: var(--sui-primary); border-color: var(--sui-primary); }
  .switchStyle input:checked::before { justify-self: end; background: var(--sui-on-primary); }
  .check:not(.switchStyle) input { position: absolute; opacity: 0; }
  .mark {
    box-sizing: border-box; display: grid; place-items: center; inline-size: 1.125rem; block-size: 1.125rem; flex: none;
    border: 1px solid var(--sui-control-border); border-radius: 0.25rem; background: var(--sui-inset); color: var(--sui-on-primary);
  }
  input:is(:checked, :indeterminate) + .mark { background: var(--sui-primary); border-color: var(--sui-primary); }
  input:focus-visible + .mark { outline: var(--sui-focus); outline-offset: 3px; }
  .check:hover:has(input:enabled) .mark { border-color: var(--sui-primary); }
  @media (forced-colors: active) {
    .check:not(.switchStyle) input { position: static; opacity: 1; }
    .mark { display: none; }
    .switchStyle input { appearance: auto; display: revert; }
    .switchStyle input::before { content: none; }
  }
</style>
