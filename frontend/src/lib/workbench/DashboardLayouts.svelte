<script lang="ts">
  import { Badge, Button, Dropdown, FilePicker, Form, FormField, Panel, TextInput, type Toasts } from '@service-unavailable/ui';
  import { Download, Upload } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import { downloadFile } from '../download';
  import { t } from '../i18n.svelte';
  import {
    applyDashboardLayout, dashboardLayoutNameLength, isDashboardLibraryChange, maxDashboardLayoutBytes,
    parseDashboardLayoutFile, readDashboardLibrary, readGameDashboardLayout, serializeDashboardLayout,
    writeDashboardLibrary, type DashboardLayout, type DashboardLayoutLibrary
  } from './dashboard-layouts';

  let { gameId, toasts }: { gameId?: string; toasts: Toasts } = $props();
  let library = $state.raw<DashboardLayoutLibrary>({ defaultId: null, presets: [] });
  let ready = $state(false);
  let name = $state('');
  let importing = $state(false);
  const json = '.json,application/json';

  function notify(message: string, tone: 'success' | 'danger') {
    toasts.add({ title: t(message), tone });
  }

  function refresh() {
    try {
      library = readDashboardLibrary();
      ready = true;
    }
    catch { notify('Dashboard layout storage is unavailable in this browser.', 'danger'); }
  }

  onMount(() => {
    refresh();
    const update = (event: StorageEvent) => {
      if (isDashboardLibraryChange(event.key)) refresh();
    };
    window.addEventListener('storage', update);
    return () => window.removeEventListener('storage', update);
  });

  function updateLibrary(change: (current: DashboardLayoutLibrary) => DashboardLayoutLibrary) {
    const next = change(readDashboardLibrary());
    writeDashboardLibrary(next);
    library = next;
  }

  function storePreset(name: string, layout: DashboardLayout) {
    const preset = { id: crypto.randomUUID(), name, layout };
    updateLibrary((current) => ({ ...current, presets: [...current.presets, preset] }));
  }

  function saveCurrent(event: SubmitEvent & { currentTarget: HTMLFormElement }) {
    event.preventDefault();
    const title = name.trim();
    if (!gameId || !title) return;
    try {
      storePreset(title, readGameDashboardLayout(gameId));
      event.currentTarget.reset();
      name = '';
      notify('Dashboard layout saved.', 'success');
    } catch { notify('Could not save the dashboard layout in this browser.', 'danger'); }
  }

  function exportLayout(name: string, layout?: DashboardLayout) {
    try {
      if (!layout && gameId) layout = readGameDashboardLayout(gameId);
      if (!layout) return;
      downloadFile(new Blob([serializeDashboardLayout({ name, layout })], { type: 'application/json' }), 'service-unavailable-dashboard-layout.json');
    } catch { notify('Could not export the dashboard layout.', 'danger'); }
  }

  function apply(layout: DashboardLayout) {
    if (!gameId) return;
    try {
      applyDashboardLayout(gameId, layout);
      notify('Layout applied to this game.', 'success');
    } catch { notify('Could not save the dashboard layout in this browser.', 'danger'); }
  }

  async function importLayout(file: File) {
    if (importing) return;
    if (file.size > maxDashboardLayoutBytes) {
      notify('The dashboard layout file is larger than 512 KB.', 'danger');
      return;
    }
    importing = true;
    try {
      const imported = parseDashboardLayoutFile(await file.text());
      if (!imported) notify('Choose a valid dashboard layout JSON file.', 'danger');
      else if (gameId) apply(imported.layout);
      else {
        storePreset(imported.name, imported.layout);
        notify('Dashboard layout imported.', 'success');
      }
    } catch { notify('Could not import the dashboard layout.', 'danger'); }
    finally { importing = false; }
  }

  function setDefault(id: string | null) {
    try {
      updateLibrary((current) => ({
        ...current, defaultId: current.presets.some((preset) => preset.id === id) ? id : null
      }));
      notify(library.defaultId ? 'Default layout for new games updated.' : 'New games will use the built-in layout.', 'success');
    } catch { notify('Could not save the dashboard layout in this browser.', 'danger'); }
  }

  function remove(id: string) {
    try {
      updateLibrary((current) => ({
        defaultId: current.defaultId === id ? null : current.defaultId,
        presets: current.presets.filter((preset) => preset.id !== id)
      }));
      notify('Saved dashboard layout deleted.', 'success');
    } catch { notify('Could not save the dashboard layout in this browser.', 'danger'); }
  }
</script>

<div class="stack layouts">
  {#if gameId}
    <Panel inset>
      <div class="stack">
        <div><h2>{t('Current game dashboards')}</h2>
          <p class="muted">{t('Save or export the layouts for Monitoring, Growth, and Finance. Importing a layout replaces the arrangement for all three dashboards in this game.')}</p>
        </div>
        <Form class="save-layout" onsubmit={saveCurrent}>
          <FormField label={t('Layout name')}>
            {#snippet children(field)}<TextInput {...field} bind:value={name} maxlength={dashboardLayoutNameLength} required />{/snippet}
          </FormField>
          <Button type="submit" variant="primary" disabled={!ready || !name.trim()}>{t('Save layout')}</Button>
        </Form>
        <div class="row wrap">
          <Button disabled={!ready} onclick={() => exportLayout(t('Current dashboard layout'))}><Download size={16} /> {t('Export current layout')}</Button>
          <FilePicker accept={json} label={t('Import layout into current game')} disabled={!ready || importing} onchange={importLayout}>
            <Upload size={16} /> {t('Import layout into current game')}
          </FilePicker>
        </div>
      </div>
    </Panel>
  {/if}

  <Panel inset>
    <div class="stack">
      <div class="row spread wrap">
        <div><h2>{t('Saved dashboard layouts')}</h2>
          <p class="muted">{t('Layout presets are stored in this browser. New games copy the selected default when they are created.')}</p>
        </div>
        {#if !gameId}
          <FilePicker accept={json} label={t('Import layout preset')} disabled={!ready || importing} onchange={importLayout}>
            <Upload size={16} /> {t('Import layout preset')}
          </FilePicker>
        {/if}
      </div>
      {#if ready && library.defaultId === null}<p class="muted">{t('New games use the built-in layout.')}</p>{/if}
      {#if library.presets.length}
        <ul class="list">
          {#each library.presets as preset (preset.id)}
            <li class="row spread wrap preset">
              <div class="row wrap">
                <strong>{preset.name}</strong>
                {#if library.defaultId === preset.id}<Badge tone="success">{t('Default for new games')}</Badge>{/if}
              </div>
              <div class="row wrap">
                {#if gameId}<Button aria-label={t('Apply {0} to this game', [preset.name])} onclick={() => apply(preset.layout)}>{t('Apply to this game')}</Button>{/if}
                <Button aria-label={library.defaultId === preset.id ? t('Use built-in default') : t('Set {0} as default for new games', [preset.name])}
                  onclick={() => setDefault(library.defaultId === preset.id ? null : preset.id)}>
                  {t(library.defaultId === preset.id ? 'Use built-in default' : 'Set as default')}
                </Button>
                <Dropdown label={t('Actions for {0}', [preset.name])} items={[
                  { id: 'export', label: t('Export layout'), onSelect: () => exportLayout(preset.name, preset.layout) },
                  { id: 'delete', label: t('Delete layout'), tone: 'danger', onSelect: () => remove(preset.id) }
                ]} />
              </div>
            </li>
          {/each}
        </ul>
      {:else if ready}
        <p class="muted">{t('No dashboard layouts saved yet.')}</p>
      {/if}
    </div>
  </Panel>
</div>

<style>
  .layouts { min-inline-size: 0; }
  .layouts :global(.save-layout) { grid-template-columns: minmax(0, 20rem) auto; align-items: end; justify-content: start; }
  .preset { border-block-start: 1px solid var(--sui-border); padding-block-start: var(--sui-space-3); }
  @media (max-width: 530px) { .layouts :global(.save-layout) { grid-template-columns: minmax(0, 1fr); } }
</style>
