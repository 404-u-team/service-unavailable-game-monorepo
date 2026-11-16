<script lang="ts">
  import { apiMessage, message, t } from '../i18n.svelte';
  import Modal from '../Modal.svelte';
  import NumberInput from '../controls/NumberInput.svelte';
  import Select from '../controls/Select.svelte';
  import Slider from '../controls/Slider.svelte';
  import { Alert, Badge, Button, Checkbox, Form, FormField, Panel, Stat, TextInput, Tooltip } from '@service-unavailable/ui';
  import { tick } from 'svelte';
  import { target } from './onboarding';
  import Forecast from './Forecast.svelte';
  import DatabaseForecast from './DatabaseForecast.svelte';
  import { fieldArticle, guideArticleHref } from '../guide';
  import { fieldNotes } from './details';
  import { num, pct, preciseMoney, rps } from '../format';
  import type { Catalog, Component, Definition, Review, Setting } from '../types';

  let { component, definition, busy, error, close, apply, preview, guideHref, onEdited, daily, storage, engineering = [], serviceRoles = {}, operationNames = {}, workloads = {} }: {
    serviceRoles?: Record<string, string[]>; operationNames?: Record<string, string>; workloads?: Record<string, number>;
    engineering?: import('../types').Research[];
    component: Component; definition: Definition; daily: number; storage: Catalog["database_storage"]; guideHref: string; busy: boolean; error: string;
    onEdited?: (changed: boolean) => void; close: () => void; preview: (name: string, settings: Record<string, Setting>) => Promise<Review>; apply: (name: string, settings: Record<string, Setting>) => void;
  } = $props();
  let name = $state('');
  let estimate = $state<Review>();
  let previewError = $state('');
  let estimating = $state(false);
  let summary = $state<HTMLElement>();
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
      if (version === previewVersion) {
        estimate = result;
        await tick();
        if (version === previewVersion) summary?.scrollIntoView({ block: 'nearest' });
      }
    } catch (reason) {
      if (version === previewVersion) previewError = apiMessage(reason);
    } finally {
      if (version === previewVersion) estimating = false;
    }
  }
  const unlocks: Record<string, string> = { role: 'decomposition', domain: 'domains', partition: 'sharding', query_plan: 'queries', autoscale: 'autoscaling', min_instances: 'autoscaling', max_instances: 'autoscaling', target_utilization: 'autoscaling' };
  const engineeringArticles: Record<string, string> = { decomposition: 'service-decomposition', domains: 'data-domains', sharding: 'database-sharding', queries: 'query-optimization', autoscaling: 'api-autoscaling' };
  const unlocked = (key: string) => !unlocks[key] || engineering.some((r) => r.id === unlocks[key] && r.state === 'completed');
  const supported = $derived(serviceRoles[String(values.role ?? 'Universal')] ?? []);
  const eligibleDemand = $derived(supported.reduce((sum, op) => sum + (workloads[op] ?? 0), 0));
  const presets = $derived(Object.entries(definition.presets ?? {}));
  const activePreset = $derived(presets.findIndex(([, entries]) => Object.entries(entries).every(([key, value]) => values[key] === value)));
  const sliderFields = new Set(['cpu', 'memory', 'connections', 'network', 'concurrency', 'slots', 'capacity', 'limit', 'routing_capacity']);
  const storageTier = $derived(storage?.[String(values.disk)]);
  const valid = $derived(!!name.trim() && Object.values(values).every((value) => typeof value !== 'number' || Number.isFinite(value)));
  const fields = $derived(Object.entries(definition.fields).filter(([key]) =>
    !['min_instances', 'max_instances', 'target_utilization'].includes(key) || values.autoscale === 'Enabled'));
  const resources = $derived(fields.filter(([key, field]) => key === 'disk' || (field.min != null && !unlocks[key])));
  const behavior = $derived(fields.filter(([key, field]) => key !== 'disk' && (field.min == null || unlocks[key])));
  let forecastSection = $state<HTMLElement>();

  function setValue(key: string, next: Setting) {
    values[key] = next;
    resetPreview();
  }
</script>

<Modal title={t("Component configuration")} subtitle={t(component.name)} {close} wide>
  <div class="configuration-grid">
    <Form id="configure-component" oninput={resetPreview}
      onsubmit={(event) => { event.preventDefault(); if (!busy && valid) apply(name, nextValues()); }}>
      {#if error}<Alert tone="danger" announce="assertive">{message(error)}</Alert>{/if}

      <Panel aria-label={t('Component settings')}>
        {#snippet header()}<h3>{t('Component settings')}</h3>{/snippet}
        <div class="form-grid">
          <FormField label={t('Component name')}>
            {#snippet children(field)}<TextInput {...field} bind:value={name} maxlength={60} required />{/snippet}
          </FormField>
          {#if presets.length}
            {@const label = t(component.kind === 'api' ? 'Instance size' : 'Preset')}
            <FormField {label}>
              {#snippet children(field)}
                <Select {...field} data-tutorial={component.kind === 'api' ? target.instance : undefined} {label} value={String(activePreset)}
                  options={[{ value: '-1', label: t('Custom'), disabled: true }, ...presets.map(([preset], index) => ({ value: String(index), label: t(preset) }))]}
                  onchange={(value) => {
                    const preset = presets[Number(value)];
                    if (preset) { values = { ...values, ...preset[1] }; resetPreview(); }
                  }} />
              {/snippet}
            </FormField>
          {/if}
        </div>
      </Panel>

      {#if resources.length}
        <Panel aria-label={t('Resources and capacity')}>
          {#snippet header()}<h3>{t('Resources and capacity')}</h3>{/snippet}
          <div class="form-grid">
            {#each resources as [key, field] (key)}{@render setting(key, field)}{/each}
          </div>
        </Panel>
      {/if}
      {#if behavior.length}
        <Panel aria-label={t('Component behavior')}>
          {#snippet header()}<h3>{t('Component behavior')}</h3>{/snippet}
          <div class="stack">
            <div class="form-grid">
              {#each behavior as [key, field] (key)}{@render setting(key, field)}{/each}
            </div>
            {#if component.kind === 'api'}
              <div class="routing stack">
                <dl>
                  <div><dt>{t('Supported operations')}</dt><dd>{supported.map((op) => t(operationNames[op] ?? op)).join(', ')}</dd></div>
                  <div><dt>{t('Eligible demand before routing')}</dt><dd>{rps(eligibleDemand)}</dd></div>
                </dl>
                <p class="muted">{t('Instances share one role and all dependencies. Separate API nodes can have different roles, resources and routes.')}</p>
                {#if values.role === 'Media'}<p>{t('Media needs released image, voice or file features to receive their traffic.')}</p>{/if}
                {#if values.role === 'Search'}<p>{t('Search needs the Message search feature and an indexed primary.')}</p>{/if}
                {#if !['Universal', 'Accounts'].includes(String(values.role ?? 'Universal'))}
                  <Alert tone="warning">{t('Connect this service to an Accounts API for identity checks and to its data domain.')}</Alert>
                {/if}
                <a href={guideArticleHref(guideHref, 'service-routing')} target="_blank" rel="noreferrer">{t('Routing and dependencies')}</a>
              </div>
            {/if}
          </div>
        </Panel>
      {/if}
      {#if Object.keys(legacy).length}
        <Panel padding="compact"><Checkbox bind:checked={includeLegacy} onchange={resetPreview} label={t("Keep throughput throttles from this save")} /></Panel>
      {/if}
    </Form>

    <aside class="preview" aria-label={t('Cost and capacity')} bind:this={summary}>
      <Panel inset>
        {#snippet header()}<h3>{t('Cost and capacity')}</h3>{/snippet}
        <div class="stack">
          <Stat label={t('Configured daily cost')} value={preciseMoney(daily)} />
          <p class="muted">{t("Settings take effect after deployment.")}</p>
          {#if previewError}<Alert tone="danger" announce="assertive">{message(previewError)}</Alert>{/if}
          {#if estimate}
            {@const dailyChange = estimate.daily_after - estimate.daily_before}
            <dl class="costs" aria-live="polite">
              <div>
                <dt>{t('Daily infrastructure ·')}</dt>
                <dd>{preciseMoney(estimate.daily_before)} → {preciseMoney(estimate.daily_after)}</dd>
                <dd><Badge tone={dailyChange > 0 ? 'warning' : dailyChange < 0 ? 'success' : 'neutral'}>{dailyChange > 0 ? '+' : ''}{preciseMoney(dailyChange)}</Badge></dd>
              </div>
              <div><dt>{t('One-time deployment cost')}</dt><dd>{preciseMoney(estimate.install)}</dd></div>
            </dl>
            {#if estimate.forecast || estimate.errors.length || estimate.warnings.length}
              <Button variant="ghost" block onclick={() => { forecastSection?.focus({ preventScroll: true }); forecastSection?.scrollIntoView({ block: 'start' }); }}>
                {t('View forecast details')}
              </Button>
            {/if}
          {/if}
        </div>
      </Panel>
    </aside>

    {#if estimate && (estimate.forecast || estimate.errors.length || estimate.warnings.length)}
      <section class="forecast" tabindex="-1" bind:this={forecastSection} aria-label={t('Forecast details')}>
        <Panel>
          {#snippet header()}<h3>{t('Forecast details')}</h3>{/snippet}
          <div class="stack">
            {#each estimate.errors as issue}<Alert tone="danger">{message(issue)}</Alert>{/each}
            {#each estimate.warnings as issue}<Alert tone="warning">{message(issue)}</Alert>{/each}
            {#if estimate.forecast}
              {@const database = estimate.forecast.databases?.[component.id]}
              <Forecast forecast={estimate.forecast} />
              {#if database}
                <DatabaseForecast {database} {guideHref} />
              {:else if ['database', 'replica'].includes(component.kind)}
                <p class="muted">{t('Database forecasts require current and draft monitoring coverage.')}</p>
              {/if}
            {/if}
          </div>
        </Panel>
      </section>
    {/if}
  </div>

  {#snippet footer()}
    <div class="row spread wrap">
      <Button onclick={close}>{t("Cancel")}</Button>
      <Button aria-label={t("Preview cost and capacity")} disabled={estimating || busy || !valid} onclick={getPreview}>
        {estimating ? t("Estimating…") : t("Preview")}
      </Button>
      <Button type="submit" form="configure-component" data-tutorial={target.save} variant="primary" disabled={busy || !valid}>{t("Save to draft")}</Button>
    </div>
  {/snippet}
</Modal>

{#snippet setting(key: string, field: Definition['fields'][string])}
  {@const label = t(field.label)}
  {@const note = fieldNotes[key]}
  {@const changed = values[key] !== initial.values[key] && (typeof values[key] !== 'number' || Number.isFinite(values[key]))}
  {@const range = field.min != null && field.max != null ? t('Range {0}–{1}', [num(field.min), num(field.max)]) : undefined}
  {@const hint = !unlocked(key) ? undefined : [range, changed ? t('Saved value {0}', [t(String(initial.values[key]))]) : undefined].filter(Boolean).join(' · ') || undefined}
  {#if unlocked(key)}
    <FormField id={'config-' + key} {label} {hint}>
      {#snippet help()}
        {#if note}<Tooltip label={t("Help with {0}", [label])} text={t(note)} href={guideArticleHref(guideHref, fieldArticle(component.kind, key))} newTab />{/if}
      {/snippet}
      {#snippet children(control)}
        {#if field.options}
          <Select {...control} {label} value={String(values[key])}
            options={field.options.map((option) => ({ value: option, label: t(option) }))} onchange={(value) => setValue(key, value)} />
        {:else if field.min != null && field.max != null}
          <NumberInput id={control.id} aria-describedby={control['aria-describedby']} {label} min={field.min} max={field.max} step={field.step ?? 1}
            precision={['instances', 'slots'].includes(key) ? 0 : 4} value={Number(values[key])}
            onchange={(value) => setValue(key, value ?? NaN)} required />
          {#if sliderFields.has(key)}
            <Slider label={t('Adjust {0}', [label])} min={field.min} max={field.max} step={field.step ?? 1}
              value={Number.isFinite(values[key]) ? Number(values[key]) : Number(field.default)} onchange={(value) => setValue(key, value)} />
          {/if}
        {/if}
        {#if key === 'disk' && storageTier}
          <small class="muted">{t('{0} modeled IOPS · {1} of base cost', [num(storageTier.read_capacity), pct(1 + storageTier.base_cost_surcharge)])}</small>
        {/if}
      {/snippet}
    </FormField>
  {:else}
    <div class="locked">
      <strong>{label}</strong>
      <p>{t('Unlock this setting through Engineering in Product.')}</p>
      <a href={guideArticleHref(guideHref, engineeringArticles[unlocks[key]])} target="_blank" rel="noreferrer">{t('Engineering Guide')}</a>
    </div>
  {/if}
{/snippet}

<style>
  .configuration-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: var(--sui-space-4); align-items: start; }
  .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sui-space-4); align-items: start; }
  .preview { position: sticky; top: 0; min-width: 0; }
  .forecast { grid-column: 1 / -1; scroll-margin-block: var(--sui-space-3); }
  .routing { padding-block-start: var(--sui-space-4); border-block-start: 1px solid var(--sui-border); }
  .routing dl, .costs { display: grid; gap: var(--sui-space-3); margin: 0; }
  dt { color: var(--sui-muted); }
  dd { margin: 0; }
  .costs dd { font-family: var(--sui-mono); }
  .locked { display: grid; gap: var(--sui-space-1); padding: var(--sui-space-3); border-radius: var(--sui-radius); background: var(--sui-inset); }
  .locked p { color: var(--sui-muted); font-size: 0.8125rem; }
  @media (max-width: 740px), (max-height: 520px) {
    .configuration-grid { grid-template-columns: minmax(0, 1fr); }
    .preview { position: static; }
  }
  @media (max-width: 520px) { .form-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
