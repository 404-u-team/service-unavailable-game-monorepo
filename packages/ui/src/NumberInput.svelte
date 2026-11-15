<script lang="ts">
  import { Minus, Plus } from '@lucide/svelte';
  import type { HTMLInputAttributes } from 'svelte/elements';
  import type { NumberStepLabels } from './types';

  let { value = $bindable<number>(), unit, stepLabels, disabled, readonly, step, min, max, class: className, ...attrs }:
    Omit<HTMLInputAttributes, 'type' | 'value'> & { value?: number; unit?: string; stepLabels: NumberStepLabels } = $props();

  const unitId = $props.id();
  const description = $derived([attrs['aria-describedby'], unit ? unitId : undefined].filter(Boolean).join(' ') || undefined);
  let input: HTMLInputElement;

  function adjust(direction: -1 | 1) {
    const previous = input.value;
    if (direction > 0) input.stepUp();
    else input.stepDown();
    if (previous === input.value) return;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
</script>

<div class="sui-number sui-control" data-disabled={disabled || undefined}>
  {#if step !== 'any'}
    <button class="sui-focus" type="button" aria-label={stepLabels.decrease}
      disabled={disabled || readonly || (min != null && value != null && value <= Number(min))} onclick={() => adjust(-1)}>
      <Minus size={15} aria-hidden="true" />
    </button>
  {/if}
  <input {...attrs} {disabled} {readonly} {step} {min} {max} type="number" bind:this={input} bind:value
    aria-describedby={description} class={['sui-focus', className]} />
  {#if unit}<span id={unitId}>{unit}</span>{/if}
  {#if step !== 'any'}
    <button class="sui-focus" type="button" aria-label={stepLabels.increase}
      disabled={disabled || readonly || (max != null && value != null && value >= Number(max))} onclick={() => adjust(1)}>
      <Plus size={15} aria-hidden="true" />
    </button>
  {/if}
</div>

<style>
  .sui-number { display: flex; align-items: center; gap: var(--sui-space-2); padding: 0; }
  .sui-number:has(:enabled):hover { border-color: var(--sui-muted); }
  .sui-number:has(input[aria-invalid='true'], input:user-invalid) { border-color: var(--sui-danger); }
  .sui-number[data-disabled] { opacity: 0.55; }
  input {
    flex: 1; align-self: stretch; box-sizing: border-box; min-inline-size: 0; inline-size: 0; padding: 0 var(--sui-space-2);
    border: 0; border-radius: var(--sui-radius); appearance: textfield;
    background: transparent; color: inherit; font: var(--sui-caption); font-size: 0.875rem; font-variant-numeric: tabular-nums;
  }
  input:focus-visible, button:focus-visible { outline-offset: -2px; }
  input::placeholder { color: var(--sui-muted); }
  input::-webkit-inner-spin-button, input::-webkit-outer-spin-button { appearance: none; margin: 0; }
  span { color: var(--sui-muted); font: var(--sui-caption); overflow-wrap: anywhere; max-inline-size: 30%; }
  button {
    flex: none; align-self: stretch; display: grid; place-items: center; min-inline-size: var(--sui-target);
    padding: 0; border: 0; border-radius: calc(var(--sui-radius) - 1px); background: var(--sui-raised); color: var(--sui-text);
  }
  button:enabled { cursor: pointer; }
  button:hover:enabled { background: var(--sui-tint); }
  button:disabled { color: var(--sui-muted); }
  .sui-number:not(:has(button)) span { padding-inline-end: var(--sui-space-3); }
</style>
