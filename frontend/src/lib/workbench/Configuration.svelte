<script lang="ts">
  import { apiMessage, message, t } from '../i18n.svelte';
  import Modal from '../Modal.svelte';
  import NumberInput from '../controls/NumberInput.svelte';
  import Select from '../controls/Select.svelte';
  import Slider from '../controls/Slider.svelte';
  import TextInput from '../controls/TextInput.svelte';
  import Toggle from '../controls/Toggle.svelte';
  import { target } from './onboarding';
  import Forecast from './Forecast.svelte';
  import DatabaseForecast from './DatabaseForecast.svelte';
  import { fieldArticle, guideArticleHref } from '../guide';
  import Help from './Help.svelte';
  import { fieldNotes } from './details';
  import { num, pct, preciseMoney } from '../format';
  import type { Catalog, Component, Definition, Review, Setting } from '../types';

  let { component, definition, busy, error, close, apply, preview, guideHref, onEdited, daily, storage }: {
    component: Component; definition: Definition; daily: number; storage: Catalog["database_storage"]; guideHref: string; busy: boolean; error: string;
    onEdited?: (changed: boolean) => void; close: () => void; preview: (name: string, settings: Record<string, Setting>) => Promise<Review>; apply: (name: string, settings: Record<string, Setting>) => void;
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

  $effect(() => {
    onEdited?.(Object.entries(initial.values).some(([key, value]) => values[key] !== value));
  });

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
  const presets = $derived(Object.entries(definition.presets ?? {}));
  const activePreset = $derived(presets.findIndex(([, entries]) => Object.entries(entries).every(([key, value]) => values[key] === value)));
  const sliderFields = new Set(['cpu', 'memory', 'connections', 'network', 'concurrency', 'slots', 'capacity', 'limit']);
  const storageTier = $derived(storage?.[String(values.disk)]);
  const valid = $derived(!!name.trim() && Object.values(values).every((value) => typeof value !== 'number' || Number.isFinite(value)));

  function setValue(key: string, next: Setting) {
    values[key] = next;
    resetPreview();
  }
</script>

<Modal title={t("Component configuration")} subtitle={t(component.name)} {close} wide>
  <div class="configuration-grid">
  <form id="configure-component" class="stack" oninput={resetPreview}
    onsubmit={(event) => { event.preventDefault(); if (valid) apply(name, nextValues()); }}>
    {#if error}<p class="notice error" role="alert">{message(error)}</p>{/if}
    <label class="field"><span>{t("Component name")}</span><TextInput bind:value={name} maxlength={60} required /></label>
    {#if presets.length}
      {@const label = t(component.kind === 'api' ? 'Instance size' : 'Preset')}
      <div class="field"><span>{label}</span>
        <Select data-tutorial={component.kind === 'api' ? target.instance : undefined} {label} value={String(activePreset)}
          options={[{ value: '-1', label: t('Custom') }, ...presets.map(([preset], index) => ({ value: String(index), label: t(preset) }))]}
          onchange={(value) => {
            const preset = presets[Number(value)];
            if (preset) { values = { ...values, ...preset[1] }; resetPreview(); }
          }} />
      </div>
    {/if}
    <div class="form-grid">
      {#each Object.entries(definition.fields) as [key, field] (key)}
        <div class="field">
          <div class="row spread"><label for={`config-${key}`}>{t(field.label)}</label>{#if fieldNotes[key]}<Help label={t("Help with {0}", [t(field.label)])} text={t(fieldNotes[key])} href={guideArticleHref(guideHref, fieldArticle(component.kind, key))} newTab />{/if}</div>
          {#if field.options}
            <Select id={`config-${key}`} label={t(field.label)} value={String(values[key])}
              options={field.options.map((option) => ({ value: option, label: t(option) }))} onchange={(value) => setValue(key, value)} />
          {:else if field.min != null && field.max != null}
            <NumberInput id={`config-${key}`} label={t(field.label)} min={field.min} max={field.max} step={field.step ?? 1}
              precision={['instances', 'slots'].includes(key) ? 0 : 4} value={Number(values[key])}
              onchange={(value) => setValue(key, value ?? NaN)} required />
            {#if sliderFields.has(key)}
              <Slider label={t('Adjust {0}', [t(field.label)])} min={field.min} max={field.max} step={field.step ?? 1}
                value={Number.isFinite(values[key]) ? Number(values[key]) : Number(field.default)} onchange={(value) => setValue(key, value)} />
            {/if}
          {/if}
          {#if key === 'disk' && storageTier}
            <small>{t('{0} modeled IOPS · +{1} base cost', [num(storageTier.read_capacity), pct(storageTier.base_cost_surcharge)])}</small>
          {/if}
          <small class="muted">{field.options ? '' : `${num(field.min ?? 0)}–${num(field.max ?? 0)} · `}{t("Default")} {t(String(field.default))}{#if values[key] !== initial.values[key]} {t("· Current")} {t(String(initial.values[key]))}{/if}</small>
        </div>
      {/each}
    </div>
    {#if Object.keys(legacy).length}<label class="row"><Toggle bind:checked={includeLegacy} onchange={resetPreview} /> {t("Keep throughput throttles from this save")}</label>{/if}
  </form>
  <aside class="preview stack">
    <h3>{t('Cost and capacity')}</h3>
    <p class="muted">{t("Settings take effect after deployment.")}</p>
    <p>{t('Configured daily cost: {0}', [preciseMoney(daily)])}</p>
    <button type="button" class="btn" disabled={estimating || busy || !valid} onclick={getPreview}>
      {estimating ? t("Estimating…") : t("Preview cost and capacity")}
    </button>
    {#if previewError}<p class="notice error" role="alert">{message(previewError)}</p>{/if}
    {#if estimate}
      {@const dailyChange = estimate.daily_after - estimate.daily_before}
      <p>{t('Daily infrastructure ·')} {preciseMoney(estimate.daily_before)} → {preciseMoney(estimate.daily_after)}
        ({dailyChange > 0 ? '+' : ''}{preciseMoney(dailyChange)})</p>
      <p>{t("Deployment cost ·")} {preciseMoney(estimate.install)}</p>
      {#each estimate.errors as issue}<p class="notice error">{message(issue)}</p>{/each}
      {#each estimate.warnings as issue}<p class="notice warn">{message(issue)}</p>{/each}
      {#if estimate.forecast}
        {@const database = estimate.forecast.databases?.[component.id]}
        <Forecast forecast={estimate.forecast} />
        {#if database}
          <DatabaseForecast {database} {guideHref} />
        {:else if ['database', 'replica'].includes(component.kind)}
          <p class="muted">{t('Database forecasts require current and draft monitoring coverage.')}</p>
        {/if}
      {/if}
    {/if}
  </aside>
  </div>
  {#snippet footer()}
    <div class="row spread">
      <button class="btn" onclick={close}>{t("Cancel")}</button>
      <button type="submit" form="configure-component" data-tutorial={target.save} class="btn primary" disabled={busy || !valid}>{t("Save to draft")}</button>
    </div>
  {/snippet}
</Modal>

<style>
  .configuration-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 22px; align-items: start; }
  .preview { min-width: 0; background: var(--raised); border-radius: 8px; border: 1px solid var(--border); padding: 14px; }
  .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  @media (max-width: 670px) { .configuration-grid { grid-template-columns: 1fr; } }
  @media (max-width: 420px) { .form-grid { grid-template-columns: 1fr; } }
</style>
