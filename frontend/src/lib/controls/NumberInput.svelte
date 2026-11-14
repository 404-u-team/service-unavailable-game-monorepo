<script lang="ts">
  import { Minus, Plus } from '@lucide/svelte';
  import { locale, t } from '../i18n.svelte';
  import { parseNumber } from './numeric';

  let { id, label, value = $bindable(), min = -Infinity, max = Infinity, step = 1, precision = 0,
    unit, onchange, required = false, disabled = false }: {
    id?: string; label: string; value?: number; min?: number; max?: number; step?: number; precision?: number;
    unit?: string; onchange?: (value: number | undefined) => void; required?: boolean; disabled?: boolean;
  } = $props();
  const uid = $props.id();
  let input: HTMLInputElement;
  let editing = $state(false);
  let invalid = $state(false);
  let draft = $state('');
  const display = (number?: number) => number == null || !Number.isFinite(number) ? '' :
    new Intl.NumberFormat(locale(), { maximumFractionDigits: precision, useGrouping: !editing }).format(number);
  const error = $derived(t('Enter a number between {0} and {1}.', [min, max]));

  $effect(() => {
    if (value != null && Number.isFinite(value)) {
      invalid = false;
      input.setCustomValidity('');
    }
  });

  function update(next: number | undefined) {
    invalid = next === undefined || next < min || next > max || Number(next.toFixed(precision)) !== next;
    input.setCustomValidity(invalid && (required || !!draft.trim()) ? error : '');
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

<div class="number">
  <button type="button" aria-label={t('Decrease {0}', [label])} disabled={disabled || (value ?? Infinity) <= min} onclick={() => increment(-1)}><Minus size={13} /></button>
  <input bind:this={input} id={id ?? uid} aria-label={label} aria-invalid={invalid && (required || !!draft.trim())}
    aria-describedby={invalid && (required || !!draft.trim()) ? `${uid}-error` : undefined}
    type="text" role="spinbutton" aria-valuemin={Number.isFinite(min) ? min : undefined} aria-valuemax={Number.isFinite(max) ? max : undefined}
    aria-valuenow={Number.isFinite(value) ? value : undefined} inputmode={precision ? 'decimal' : 'numeric'} {required} {disabled} value={editing || invalid ? draft : display(value)}
    onfocus={() => { if (!invalid) draft = display(value); editing = true; }}
    onblur={() => { editing = false; }}
    oninput={(event) => { draft = event.currentTarget.value; update(parseNumber(draft, locale())); }}
    onkeydown={(event) => {
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); increment(event.key === 'ArrowUp' ? 1 : -1); }
    }} />
  {#if unit}<span class="muted">{unit}</span>{/if}
  <button type="button" aria-label={t('Increase {0}', [label])} disabled={disabled || (value ?? -Infinity) >= max} onclick={() => increment(1)}><Plus size={13} /></button>
</div>
{#if invalid && (required || !!draft.trim())}<small class="danger" id={`${uid}-error`}>{error}</small>{/if}

<style>
  .number { min-width: 0; display: flex; align-items: center; border: 1px solid var(--border); border-radius: 7px; background: var(--raised); }
  .number input { text-align: center; border: 0; background: transparent; min-width: 0; flex: 1; padding-inline: 3px; font-family: var(--mono); }
  .number button { flex: 0 0 28px; display: grid; place-items: center; border: 0; align-self: stretch; color: var(--text); background: transparent; }
  .number button:disabled { opacity: .45; }
  .number span { font-size: 11px; }
</style>
