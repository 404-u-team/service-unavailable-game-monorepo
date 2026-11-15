<script lang="ts">
  import NumberInput from './NumberInput.svelte';
  import type { NumberStepLabels } from './types';

  let { value = $bindable(), min, max, step = 1, id, name, disabled = false, unit, manualLabel, manualStepLabels, ...a11y }: {
    value: number;
    min: number;
    max: number;
    step?: number;
    id?: string;
    name?: string;
    disabled?: boolean;
    unit?: string;
    'aria-label'?: string;
    'aria-describedby'?: string;
    'aria-invalid'?: boolean | 'true' | 'false' | 'grammar' | 'spelling';
  } & ({ manualLabel?: undefined; manualStepLabels?: never } | { manualLabel: string; manualStepLabels: NumberStepLabels }) = $props();

  const filled = $derived(max > min ? Math.max(0, Math.min(100, (value - min) * 100 / (max - min))) : 0);
  let manual = $state<number>();

  $effect(() => { manual = value; });

  function updateManual(event: Event & { currentTarget: HTMLInputElement }) {
    if (event.currentTarget.validity.valid) value = event.currentTarget.valueAsNumber;
  }
</script>

<div class="slider">
  <input {...a11y} class="sui-focus" type="range" {id} name={manualLabel ? undefined : name} {min} {max} {step}
    {disabled} {value} style:--filled={`${filled}%`} oninput={(event) => {
      value = event.currentTarget.valueAsNumber;
      manual = value;
    }} />
  {#if manualLabel && manualStepLabels}
    <NumberInput bind:value={manual} {min} {max} {step} {name} {disabled} {unit} stepLabels={manualStepLabels} required
      aria-label={manualLabel} aria-describedby={a11y['aria-describedby']} oninput={updateManual} />
  {/if}
</div>

<style>
  .slider { display: flex; align-items: center; flex-wrap: wrap; gap: var(--sui-space-3); }
  .slider > :global(.sui-number) { flex: 0 1 11rem; }
  input {
    --track-direction: to right;
    --track: linear-gradient(var(--track-direction), var(--sui-primary) var(--filled), var(--sui-control-border) var(--filled));
    flex: 1 1 8rem; min-inline-size: 0; block-size: var(--sui-target); margin: 0; appearance: none; background: transparent;
  }
  input:dir(rtl) { --track-direction: to left; }
  input:enabled { cursor: pointer; }
  input:disabled { opacity: 0.55; }
  input::-webkit-slider-runnable-track { block-size: 0.375rem; border-radius: 999px; background: var(--track); }
  input::-moz-range-track { block-size: 0.375rem; border-radius: 999px; background: var(--track); }
  input::-webkit-slider-thumb {
    appearance: none; inline-size: 1rem; block-size: 1rem; margin-block-start: -0.3125rem;
    border: 2px solid var(--sui-on-primary); border-radius: 50%; background: var(--sui-primary);
  }
  input::-moz-range-thumb { box-sizing: border-box; inline-size: 1rem; block-size: 1rem; border: 2px solid var(--sui-on-primary); border-radius: 50%; background: var(--sui-primary); }
  @media (forced-colors: active) { input { appearance: auto; } }
</style>
