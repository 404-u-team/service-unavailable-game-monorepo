<script lang="ts">
  import Modal from '../Modal.svelte';
  import type { Component, Definition, Setting } from '../types';

  let { component, definition, busy, error, close, apply }: {
    component: Component; definition: Definition; busy: boolean; error: string;
    close: () => void; apply: (name: string, settings: Record<string, Setting>) => void;
  } = $props();
  let name = $state('');
  let values = $state<Record<string, Setting>>({});
  const initial = $derived({ name: component.name, values: Object.fromEntries(Object.entries(definition.fields).map(([key, field]) => [key, component.config[key] ?? field.default])) });
  function initialize() { name = initial.name; values = initial.values; }
  initialize();
  const presets = [
    { name: 'Small S1 · 1 vCPU / 2 GB', cpu: 1, memory: 2 },
    { name: 'Standard S2 · 2 vCPU / 4 GB', cpu: 2, memory: 4 },
    { name: 'Performance P4 · 4 vCPU / 8 GB', cpu: 4, memory: 8 },
    { name: 'Performance P8 · 8 vCPU / 16 GB', cpu: 8, memory: 16 }
  ];
</script>

<Modal title="Component configuration" subtitle={component.name} {close}>
  <form id="configure-component" class="stack" onsubmit={(event) => { event.preventDefault(); apply(name, { ...values }); }}>
    {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    <label class="field"><span>Component name</span><input bind:value={name} maxlength="60" required /></label>
    {#if component.kind === 'api'}
      <label class="field"><span>Instance size</span>
        <select value={presets.findIndex((preset) => preset.cpu === values.cpu && preset.memory === values.memory)} onchange={(event) => {
          const preset = presets[Number(event.currentTarget.value)];
          if (preset) { values.cpu = preset.cpu; values.memory = preset.memory; }
        }}>
          <option value={-1}>Custom</option>
          {#each presets as preset, index}<option value={index}>{preset.name}</option>{/each}
        </select>
      </label>
    {/if}
    <div class="form-grid">
      {#each Object.entries(definition.fields) as [key, field]}
        <label class="field"><span>{field.label}</span>
          {#if field.options}
            <select bind:value={values[key]}>
              {#each field.options as option}<option value={option}>{option}</option>{/each}
            </select>
          {:else}
            <input type="number" min={field.min ?? undefined} max={field.max ?? undefined} step={key === 'instances' ? 1 : 'any'}
              value={values[key]} oninput={(event) => { values[key] = event.currentTarget.valueAsNumber; }} required />
          {/if}
        </label>
      {/each}
    </div>
    <p class="muted">{definition.description}</p>
  </form>
  {#snippet footer()}
    <div class="row spread">
      <button class="btn" onclick={close}>Cancel</button>
      <button type="submit" form="configure-component" class="btn primary" disabled={busy}>Save to draft</button>
    </div>
  {/snippet}
</Modal>

<style>
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 420px) { .form-grid { grid-template-columns: 1fr; } }
</style>
