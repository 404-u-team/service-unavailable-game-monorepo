<script lang="ts">
  import { apiMessage, message, t } from '../i18n.svelte';
  import Modal from '../Modal.svelte';
  import Forecast from './Forecast.svelte';
  import Help from './Help.svelte';
  import { fieldNotes } from './details';
  import { preciseMoney } from '../format';
  import type { Component, Definition, Review, Setting } from '../types';

  let { component, definition, busy, error, close, apply, preview }: {
    component: Component; definition: Definition; busy: boolean; error: string;
    close: () => void; preview: (name: string, settings: Record<string, Setting>) => Promise<Review>; apply: (name: string, settings: Record<string, Setting>) => void;
  } = $props();
  let name = $state('');
  let estimate = $state<Review>();
  let previewError = $state('');
  let estimating = $state(false);
  let previewVersion = 0;
  let includeLegacy = $state(true);
  let values = $state<Record<string, Setting>>({});
  const initial = $derived({ name: component.name, values: Object.fromEntries(Object.entries(definition.fields).map(([key, field]) => [key, component.config[key] ?? field.default])) });
  function initialize() { name = initial.name; values = initial.values; }
  initialize();
  const legacy = $derived(Object.fromEntries(Object.entries(component.config).filter(([key]) => !definition.fields[key])));
  function nextValues() {
    return { ...(includeLegacy ? legacy : {}), ...values };
  }

  function resetPreview() {
    previewVersion++;
    estimate = undefined;
    previewError = '';
    estimating = false;
  }

  async function getPreview() {
    const version = ++previewVersion;
    estimating = true;
    previewError = '';
    try {
      const result = await preview(name, nextValues());
      if (version === previewVersion) estimate = result;
    } catch (reason) {
      if (version === previewVersion) previewError = apiMessage(reason);
    } finally {
      if (version === previewVersion) estimating = false;
    }
  }
  const presets = [
    { name: 'Small S1 · 1 vCPU / 2 GB', cpu: 1, memory: 2 },
    { name: 'Standard S2 · 2 vCPU / 4 GB', cpu: 2, memory: 4 },
    { name: 'Performance P4 · 4 vCPU / 8 GB', cpu: 4, memory: 8 },
    { name: 'Performance P8 · 8 vCPU / 16 GB', cpu: 8, memory: 16 }
  ];
</script>

<Modal title={t("Component configuration")} subtitle={t(component.name)} {close}>
  <form id="configure-component" class="stack" oninput={resetPreview} onchange={resetPreview}
    onsubmit={(event) => { event.preventDefault(); apply(name, nextValues()); }}>
    {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    <label class="field"><span>{t("Component name")}</span><input bind:value={name} maxlength="60" required /></label>
    {#if component.kind === 'api'}
      <label class="field"><span>{t("Instance size")}</span>
        <select value={presets.findIndex((preset) => preset.cpu === values.cpu && preset.memory === values.memory)} onchange={(event) => {
          const preset = presets[Number(event.currentTarget.value)];
          if (preset) { values.cpu = preset.cpu; values.memory = preset.memory; }
        }}>
          <option value={-1}>{t("Custom")}</option>
          {#each presets as preset, index}<option value={index}>{t(preset.name)}</option>{/each}
        </select>
      </label>
    {/if}
    <div class="form-grid">
      {#each Object.entries(definition.fields) as [key, field]}
        <div class="field">
          <div class="row spread"><label for={`config-${key}`}>{t(field.label)}</label><Help label={t("Help with {0}", [t(field.label)])} text={t(fieldNotes[key])} /></div>
          {#if field.options}
            <select id={`config-${key}`} bind:value={values[key]}>
              {#each field.options as option}<option value={option}>{t(option)}</option>{/each}
            </select>
          {:else}
            <input id={`config-${key}`} type="number" min={field.min ?? undefined} max={field.max ?? undefined} step={['instances', 'cpu', 'slots'].includes(key) ? 1 : 'any'}
              value={values[key]} oninput={(event) => { values[key] = event.currentTarget.valueAsNumber; }} required />
          {/if}
          <small class="muted">{field.options ? '' : `${field.min}–${field.max} · `}{t("Default")} {t(String(field.default))}{#if values[key] !== initial.values[key]} {t("· Current")} {initial.values[key]}{/if}</small>
        </div>
      {/each}
    </div>
    {#if Object.keys(legacy).length}<label class="row"><input type="checkbox" bind:checked={includeLegacy} /> {t("Keep throughput throttles from this save")}</label>{/if}
    <p class="muted">{t(definition.description)}</p>
    <p class="muted">{t("Settings take effect after deployment.")}</p>
    <button type="button" class="btn" disabled={estimating || busy || !name.trim() || Object.values(values).some((value) => typeof value === 'number' && !Number.isFinite(value))} onclick={getPreview}>
      {estimating ? t("Estimating…") : t("Preview cost and capacity")}
    </button>
    {#if previewError}<p class="notice error" role="alert">{message(previewError)}</p>{/if}
    {#if estimate}
      <p>{t("Daily infrastructure ·")} {preciseMoney(estimate.daily_before)} → {preciseMoney(estimate.daily_after)}</p>
      <p>{t("Deployment cost ·")} {preciseMoney(estimate.install)}</p>
      {#each estimate.errors as issue}<p class="notice error">{message(issue)}</p>{/each}
      {#each estimate.warnings as issue}<p class="notice warn">{message(issue)}</p>{/each}
      {#if estimate.forecast}<Forecast forecast={estimate.forecast} />{/if}
    {/if}
  </form>
  {#snippet footer()}
    <div class="row spread">
      <button class="btn" onclick={close}>{t("Cancel")}</button>
      <button type="submit" form="configure-component" class="btn primary" disabled={busy}>{t("Save to draft")}</button>
    </div>
  {/snippet}
</Modal>

<style>
  .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  @media (max-width: 420px) { .form-grid { grid-template-columns: 1fr; } }
</style>
