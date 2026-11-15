<script lang="ts">
  import type { Tone } from './types';

  let { label, value, min = 0, max = 100, valueText, tone = 'success' }: {
    label: string; value: number; min?: number; max?: number; valueText?: string; tone?: Tone;
  } = $props();
  const id = $props.id();
  const bounded = $derived(Math.min(max, Math.max(min, value)));
  const displayed = $derived(valueText ?? String(bounded));
</script>

<div class="meter" data-sui-tone={tone}>
  <div><label for={id}>{label}</label><span aria-hidden="true">{displayed}</span></div>
  <meter {id} {min} {max} value={bounded} aria-valuetext={valueText}></meter>
</div>

<style>
  .meter { display: grid; gap: var(--sui-space-2); color: var(--sui-text); font: var(--sui-body); }
  .meter > div { display: flex; justify-content: space-between; flex-wrap: wrap; gap: var(--sui-space-2); }
  span { color: var(--sui-tone-text); font: var(--sui-caption); }
  meter { appearance: none; display: block; inline-size: 100%; block-size: 0.5rem; border-radius: 99px; background: var(--sui-border); }
  meter::-webkit-meter-bar { background: var(--sui-border); border: 0; block-size: 100%; }
  meter::-webkit-meter-optimum-value { background: var(--sui-tone-text); }
  meter::-moz-meter-bar { border-radius: inherit; background: var(--sui-tone-text); }
  @media (forced-colors: active) { meter { appearance: auto; } }
</style>
