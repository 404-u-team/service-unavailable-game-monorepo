<script lang="ts">
  import { Minus, Plus } from '@lucide/svelte';
  import type { NumberStepLabels } from './types';

  let { id, label, value = $bindable(), min = -Infinity, max = Infinity, step = 1, precision = 0,
    unit, locale, parse, invalidMessage, stepLabels, onchange, required = false, disabled = false }: {
    id?: string; label: string; value?: number; min?: number; max?: number; step?: number; precision?: number;
    unit?: string; locale: string; parse: (text: string) => number | undefined; invalidMessage: string;
    stepLabels: NumberStepLabels; onchange?: (value: number | undefined) => void; required?: boolean; disabled?: boolean;
  } = $props();
  const uid = $props.id();
  let input: HTMLInputElement;
  let editing = $state(false);
  let invalid = $state(false);
  let draft = $state('');
  const display = (number?: number) => number == null || !Number.isFinite(number) ? '' :
    new Intl.NumberFormat(locale, { maximumFractionDigits: precision, useGrouping: !editing }).format(number);


  $effect(() => {
    if (value != null && Number.isFinite(value)) {
      invalid = false;
      input.setCustomValidity('');
    }
  });

  function update(next: number | undefined) {
    invalid = next === undefined || next < min || next > max || Number(next.toFixed(precision)) !== next;
    input.setCustomValidity(invalid && (required || !!draft.trim()) ? invalidMessage : '');
    value = invalid ? undefined : next;
    onchange?.(value);
  }

  function increment(direction: number) {
    const base = value ?? (Number.isFinite(min) ? min : 0);
    const next = Math.min(max, Math.max(min, Number((base + direction * step).toFixed(precision))));
    draft = display(next);
    update(next);
  }
</script>

<div class="number sui-control">
  <button class="sui-focus" type="button" aria-label={stepLabels.decrease} disabled={disabled || (value ?? Infinity) <= min} onclick={() => increment(-1)}><Minus size={13} /></button>
  <input class="sui-focus" bind:this={input} id={id ?? uid} aria-label={label} aria-invalid={invalid && (required || !!draft.trim())}
    aria-describedby={invalid && (required || !!draft.trim()) ? `${uid}-error` : undefined}
    type="text" role="spinbutton" aria-valuemin={Number.isFinite(min) ? min : undefined} aria-valuemax={Number.isFinite(max) ? max : undefined}
    aria-valuenow={Number.isFinite(value) ? value : undefined} inputmode={precision ? 'decimal' : 'numeric'} {required} {disabled} value={editing || invalid ? draft : display(value)}
    onfocus={() => { if (!invalid) draft = display(value); editing = true; }}
    onblur={() => { editing = false; }}
    oninput={(event) => { draft = event.currentTarget.value; update(parse(draft)); }}
    onkeydown={(event) => {
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); increment(event.key === 'ArrowUp' ? 1 : -1); }
    }} />
  {#if unit}<span>{unit}</span>{/if}
  <button class="sui-focus" type="button" aria-label={stepLabels.increase} disabled={disabled || (value ?? -Infinity) >= max} onclick={() => increment(1)}><Plus size={13} /></button>
</div>
{#if invalid && (required || !!draft.trim())}<small class="error" id={`${uid}-error`}>{invalidMessage}</small>{/if}

<style>
  .number { display: flex; align-items: stretch; gap: var(--sui-space-1); padding: 0; }
  .number:has(input[aria-invalid="true"]) { border-color: var(--sui-danger); }
  input { border: 0; border-radius: var(--sui-radius); padding: 0 var(--sui-space-2); color: inherit; background: transparent; min-inline-size: 0; flex: 1; font: var(--sui-caption); font-size: 0.875rem; }
  button { flex: 0 0 min(25%, var(--sui-target)); display: grid; place-items: center; border: 0; border-radius: var(--sui-radius); color: var(--sui-text); background: var(--sui-raised); }
  button:enabled { cursor: pointer; }
  button:hover:enabled { background: var(--sui-tint); }
  button:disabled, input:disabled { opacity: 0.55; }
  input:focus-visible, button:focus-visible { outline-offset: -2px; }
  span { align-self: center; color: var(--sui-muted); font: var(--sui-caption); }
  .error { display: block; color: var(--sui-danger); }
</style>
