<script lang="ts">
  import NumberInput from '#lib/controls/NumberInput.svelte';
  import { Button, Checkbox, FilePicker, Form, FormField, Switch, TextInput, Toaster, createToasts } from '@service-unavailable/ui';
  import { apiMessage, locale, message, t } from '#lib/i18n.svelte.ts';
  import { onMount, tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { Activity, ArrowLeft, ArrowRight, BookOpen, ChevronRight, Database, Diamond, Download, GitFork, Radio, Server, Trash2, Upload } from '@lucide/svelte';
  import Language from '#lib/Language.svelte';
  import Brand from '#lib/Brand.svelte';
  import Guide from '#lib/Guide.svelte';
  import DashboardLayouts from '#lib/workbench/DashboardLayouts.svelte';
  import { applyDefaultDashboardLayout } from '#lib/workbench/dashboard-layouts.ts';
  import Modal from '#lib/Modal.svelte';
  import { ApiError, createGame, deleteSave, downloadSave, importSave, loadCatalog, previewSave, saves as listSaves } from '#lib/api.ts';
  import { money, num, preciseMoney } from '#lib/format.ts';
  import type { Catalog, Difficulty, Save, SavePreview, Settings } from '#lib/types.ts';

  let saves = $state<Save[]>([]);
  let catalog = $state<Catalog>();
  let loading = $state(true);
  let busy = $state(false);
  let error = $state('');
  let transferError = $state<unknown>();
  let exportId = $state('');
  let importFile = $state<File>();
  let preview = $state<SavePreview>();
  let importing = $state(false);
  let saveToDelete = $state<Save>();
  let deleting = $state(false);
  let deleteError = $state<unknown>();
  let savesHeading = $state<HTMLHeadingElement>();
  const toasts = createToasts();
  let name = $state('Pulse Messenger');
  let difficulty = $state<Difficulty>('beginner');
  let seed = $state<number>();
  let showSeed = $state(false);
  let createId = '';
  let preferences = $state<Settings>({ show_tutorial: true, reduced_motion: false });
  const screens = { menu: 'Main menu', new: 'New game', saves: 'Saved games', guide: 'Guide', settings: 'Settings' };
  const options = [
    { id: 'new', description: 'Create a new service' },
    { id: 'saves', description: 'Open an existing save' },
    { id: 'guide', description: 'Components and mechanics' },
    { id: 'settings', description: 'Preferences for new games' }
  ] as const;
  const current = $derived((page.url.searchParams.get('view') || 'menu') as keyof typeof screens);
  const latest = $derived(saves[0]);
  const starting = $derived(catalog?.difficulties?.[difficulty]);
  const scenarioIcons = { messenger: Radio, social: Diamond, multiplayer: Activity, education: BookOpen };

  onMount(() => {
    const stored = localStorage.getItem('workbench-preferences');
    if (stored) {
      try { preferences = JSON.parse(stored); } catch { localStorage.removeItem('workbench-preferences'); }
    }
    void load();
  });

  async function load() {
    error = '';
    loading = true;
    catalog = undefined;
    try { [saves, catalog] = await Promise.all([listSaves(), loadCatalog()]); }
    catch (reason) { error = apiMessage(reason); }
    finally { loading = false; }
  }

  async function exportGame(id: string) {
    exportId = id;
    transferError = undefined;
    try { await downloadSave(id); }
    catch (reason) { transferError = reason; }
    finally { exportId = ''; }
  }

  function closeDelete() {
    if (deleting) return;
    saveToDelete = undefined;
    deleteError = undefined;
  }

  async function confirmDelete() {
    if (!saveToDelete || deleting) return;
    const { id } = saveToDelete;
    deleting = true;
    deleteError = undefined;
    try { await deleteSave(id); }
    catch (reason) {
      deleteError = reason;
      return;
    } finally { deleting = false; }
    saves = saves.filter((save) => save.id !== id);
    closeDelete();
    await tick();
    savesHeading?.focus({ preventScroll: true });
  }

  async function selectSaveFile(selected: File) {
    importing = true;
    transferError = undefined;
    try {
      preview = await previewSave(selected);
      importFile = selected;
    } catch (reason) { transferError = reason; }
    finally { importing = false; }
  }

  function closeImport() {
    if (importing) return;
    preview = undefined;
    importFile = undefined;
    transferError = undefined;
  }

  async function confirmImport() {
    if (!importFile || importing) return;
    importing = true;
    transferError = undefined;
    try {
      const imported = await importSave(importFile);
      initializeDashboards(imported.id);
      saves = [imported, ...saves];
      toasts.add({
        title: t('Save imported successfully.'), tone: 'success', duration: 0,
        action: { label: t('Open imported save'), href: `/game/${imported.id}?view=build` }
      });
      preview = undefined;
      importFile = undefined;
    } catch (reason) { transferError = reason; }
    finally { importing = false; }
  }

  function remember() {
    localStorage.setItem('workbench-preferences', JSON.stringify(preferences));
  }

  function initializeDashboards(id: string) {
    try { applyDefaultDashboardLayout(id); } catch { /* The game still opens when browser storage is unavailable. */ }
  }

  async function start(event: SubmitEvent) {
    event.preventDefault();
    if (loading || busy || !starting) return;
    busy = true;
    error = '';
    createId ||= crypto.randomUUID();
    try {
      const game = await createGame({ id: createId, name, scenario: 'messenger', difficulty, seed: showSeed ? seed ?? null : null, settings: preferences });
      initializeDashboards(game.id);
      await goto(`/game/${game.id}?view=build`);
      createId = '';
    } catch (reason) { error = apiMessage(reason); }
    finally { busy = false; }
  }
</script>

<div class="menu" data-reduced-motion={preferences.reduced_motion}>
  <header class="menu-header">
    {#if current === 'menu'}<Brand />
    {:else}<a class="row menu-back eyebrow" href="/"><ArrowLeft size={15} /> {t("Main menu")}</a>{/if}
    <span class="eyebrow">{t(screens[current] ?? screens.menu)}</span>
  </header>
  <Toaster {toasts} placement="top-end" label={t('Notifications')} dismissLabel={(title) => t('Dismiss {0}', [title])} />
  <main>
    {#if error}<div class="notice error row spread" role="alert">{message(error)}<Button onclick={load}>{t("Retry connection")}</Button></div>{/if}
    {#if current === 'new'}
      <div class="intro setup-title"><h1>{t("New game")}</h1><p class="muted">{t("Choose a product and its starting configuration.")}</p></div>
      <Form class="stack setup" onsubmit={start}>
        <fieldset class="scenario-grid">
          <legend class="eyebrow">{t("Product scenario")}</legend>
          {#each Object.entries(catalog?.scenarios ?? {}) as [id, scenario]}
            {@const Icon = scenarioIcons[id as keyof typeof scenarioIcons]}
            <label class="scenario" class:available={scenario.available}>
              <span class="scenario-icon"><Icon size={23} /></span>
              <span><strong>{t(scenario.name)}</strong><small>{t(scenario.description)}</small><span class="scenario-status mono">{scenario.available ? t("Available") : t("Unavailable")}</span></span>
              <input type="radio" name="scenario" value={id} checked={id === 'messenger'} disabled={!scenario.available} aria-label={t(scenario.name)} />
            </label>
          {/each}
        </fieldset>
        <div class="setup-grid">
          <FormField label={t('Service name')}>
            {#snippet children(field)}<TextInput {...field} bind:value={name} maxlength={60} required />{/snippet}
          </FormField>
          <fieldset class="difficulty">
            <legend class="eyebrow">{t("Difficulty")}</legend>
            {#each Object.entries(catalog?.difficulties ?? {}) as [id, option]}
              <label class="sui-button"><input type="radio" name="difficulty" value={id} bind:group={difficulty} /> {t(option.name)}</label>
            {/each}
          </fieldset>
        </div>
        {#if starting}
          <section class="panel pad starting"><p class="eyebrow">{t("Starting conditions")}</p>
            <div class="row wrap"><span>{money(starting.balance)} {t("budget")}</span><span>{t("{0} registered users", [num(starting.audience)])}</span><span>{t("1 API server")}</span><span>{t("1 database")}</span></div>
          </section>
        {/if}
        <div class="row wrap seed">
          <Checkbox label={t("Specify a simulation seed")} bind:checked={showSeed} />
          {#if showSeed}<div class="field seed-field"><span>{t("Simulation seed")}</span><NumberInput label={t("Simulation seed")} min={0} max={4294967295} bind:value={seed} /></div>{/if}
        </div>
        <div class="row setup-actions"><Button href="/" class="large">{t("Cancel")}</Button><Button type="submit" variant="primary" class="large" disabled={busy || loading || !starting}>{busy ? t("Creating game…") : t("Create game")} <ArrowRight size={15} /></Button></div>
      </Form>
    {:else if current === 'saves'}
      <div class="intro row spread wrap">
        <div><h1 bind:this={savesHeading} tabindex="-1">{t("Saved games")}</h1><p class="muted">{t("Use save files to move a game between browsers or devices.")}</p></div>
        <FilePicker variant="primary" accept=".json,application/json" label={t('Select a save file')}
          disabled={loading || importing} onchange={selectSaveFile}>
          <Upload size={15} /> {importing && !preview ? t('Checking save…') : t('Import save')}
        </FilePicker>
      </div>
      {#if transferError && !preview}<p class="notice error" role="alert">{apiMessage(transferError)}</p>{/if}

      <section class="panel pad stack">
        {#if loading}<p class="muted">{t("Loading saved games…")}</p>
        {:else if !saves.length}<p class="muted">{t("No saved games.")}</p><Button href="/?view=new" variant="primary">{t("New game")}</Button>
        {:else}
          {#each saves as save (save.id)}
            <div class="save-row">
              <a href={`/game/${save.id}?view=build`} class="row spread">
                <div><strong>{save.name}</strong><small>{t(catalog?.scenarios[save.scenario]?.name ?? save.scenario)} {t("· Day")} {save.day}</small></div>
                <ChevronRight size={17} />
              </a>
              <div><span class="mono">{num(save.audience)} {t("users")}</span><small>{money(save.balance)} {t("balance")}</small></div>
              <div class="row wrap save-actions">
                <Button type="button" disabled={Boolean(exportId)} onclick={() => exportGame(save.id)}
                  aria-label={t('Export {0}', [save.name])}>
                  <Download size={15} /> {exportId === save.id ? t('Exporting…') : t('Export')}
                </Button>
                <Button type="button" disabled={importing} onclick={() => saveToDelete = save} aria-label={t('Delete {0}', [save.name])}>
                  <Trash2 size={15} /> {t('Delete')}
                </Button>
              </div>
            </div>
          {/each}
        {/if}
      </section>
      {#if saveToDelete}
        <Modal title={t('Delete save')} close={closeDelete}>
          <p class="delete-confirmation">{t('Permanently delete the save “{0}”?', [saveToDelete.name])}</p>
          {#if deleteError}<p class="notice error" role="alert">{deleteError instanceof ApiError ? apiMessage(deleteError) : t('Could not delete the save. Try again.')}</p>{/if}
          {#snippet footer()}
            <div class="row spread wrap">
              <Button disabled={deleting} onclick={closeDelete}>{t('Cancel')}</Button>
              <Button variant="danger" disabled={deleting} onclick={confirmDelete}>{deleting ? t('Deleting…') : t('Delete save')}</Button>
            </div>
          {/snippet}
        </Modal>
      {/if}
      {#if preview}
        <Modal title={t('Import preview')} close={closeImport}>
          <div class="stack">
            <dl class="import-preview">
              <div><dt>{t('Service name')}</dt><dd>{preview.name}</dd></div>
              <div><dt>{t('Product scenario')}</dt><dd>{t(catalog?.scenarios[preview.scenario]?.name ?? preview.scenario)}</dd></div>
              <div><dt>{t('Game day')}</dt><dd>{num(preview.day)}</dd></div>
              <div><dt>{t('Registered users')}</dt><dd>{num(preview.audience)}</dd></div>
              <div><dt>{t('Balance')}</dt><dd>{preciseMoney(preview.balance)}</dd></div>
              <div><dt>{t('Save version')}</dt><dd>{preview.version}</dd></div>
              {#if preview.exported_at}
                <div><dt>{t('Export date')}</dt><dd>{new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(preview.exported_at))}</dd></div>
              {/if}
            </dl>
            <p class="muted">{t('Importing this file creates a new save in this browser.')}</p>
            {#if transferError}<p class="notice error" role="alert">{apiMessage(transferError)}</p>{/if}
          </div>
          {#snippet footer()}
            <div class="row spread wrap">
              <Button disabled={importing} onclick={closeImport}>{t('Cancel')}</Button>
              <Button variant="primary" disabled={importing} onclick={confirmImport}>{t('Import as new save')}</Button>
            </div>
          {/snippet}
        </Modal>
      {/if}
    {:else if current === 'guide'}
      <div class="intro"><h1>{t("Guide")}</h1></div>
      {#if catalog}<Guide {catalog} />{:else if loading}<p class="muted">{t("Loading guide…")}</p>{/if}
    {:else if current === 'settings'}
      <div class="intro"><h1>{t("Settings")}</h1><p class="muted">{t("Defaults for new games on this browser.")}</p></div>
      <div class="stack settings">
        <div class="panel pad stack form">
          <Switch label={t("Show onboarding prompts")} bind:checked={preferences.show_tutorial} onchange={remember} />
          <Switch label={t("Reduce motion")} bind:checked={preferences.reduced_motion} onchange={remember} />
          <Language />
        </div>
        <DashboardLayouts {toasts} />
      </div>
    {:else}
      <div class="intro menu-title"><h1>Service Unavailable</h1><p class="muted">{t("Infrastructure simulator")}</p></div>
      <div class="menu-grid">
        <section class="panel continue">
          <div><h2>{latest ? t("Continue game") : t("Start a service")}</h2><p class="eyebrow">{latest ? t("Most recent save / {0}", [latest.name]) : t("Messenger / Starting topology")}</p></div>
          <div class="preview grid-bg" aria-label={t("Starting topology from incoming traffic through a balancer and API server to a database")}>
            <div class="preview-node"><Radio size={17} /><strong>{t("Ingress")}</strong></div><span class="wire"></span>
            <div class="preview-node emphasis"><GitFork size={17} /><strong>{t("Balancer")}</strong></div><span class="wire"></span>
            <div class="preview-node"><Server size={17} /><strong>{t("API server")}</strong></div><span class="wire"></span>
            <div class="preview-node"><Database size={17} /><strong>{t("Database")}</strong></div>
          </div>
          {#if latest}
            <dl class="summary">
              <div><dt class="eyebrow">{t("Day")}</dt><dd>{latest.day}</dd></div>
              <div><dt class="eyebrow">{t("Registered users")}</dt><dd>{num(latest.audience)}</dd></div>
              <div><dt class="eyebrow">{t("Balance")}</dt><dd>{money(latest.balance)}</dd></div>
            </dl>
          {:else}<p class="muted">{loading ? t("Checking for saved games…") : t("Build and operate a messenger service. Track request load, manage expenses and deploy infrastructure changes.")}</p>{/if}
          <Button variant="primary" block class="large" href={latest ? `/game/${latest.id}?view=build` : '/?view=new'}>{latest ? t("Continue") : t("Create a service")} <ArrowRight size={15} /></Button>
        </section>
        <section class="panel options">
          <h2>{t("Game options")}</h2>
          {#each options as option}
            <a href={`/?view=${option.id}`} class="row spread"><span><strong>{t(screens[option.id])}</strong><small>{t(option.description)}</small></span><ArrowRight size={15} class="accent" /></a>
          {/each}
        </section>
      </div>
    {/if}
  </main>
</div>

<style>
  .menu { --sui-toast-top: 74px; min-height: 100dvh; }
  .menu-header { min-height: 88px; padding: 20px clamp(18px, 4vw, 58px); display: flex; align-items: center; justify-content: space-between; background: var(--background); border-bottom: 1px solid var(--border); }
  .menu-header :global(.brand) { font-size: 22px; }
  .menu-header :global(.brand-mark) { width: 44px; height: 44px; font-size: 29px; border-radius: 12px; }
  main { max-width: 1660px; margin: auto; padding: clamp(24px, 4vw, 60px); }
  .intro { margin-bottom: 30px; }
  .intro p { margin-top: 6px; }
  .menu-title { margin-bottom: 48px; }
  .menu-title h1 { font-size: clamp(35px, 4vw, 54px); }
  .menu-title p { font-size: 16px; }
  .menu-grid { display: grid; align-items: start; grid-template-columns: 1.95fr 1fr; gap: 26px; }
  .continue, .options { display: grid; align-content: start; padding: 16px 19px 22px; gap: 19px; }
  .continue { grid-template-rows: auto auto minmax(65px, 1fr) auto; min-height: 465px; }
  h2 { font-size: 18px; }
  .continue .eyebrow { margin-top: 4px; }
  .preview { display: flex; align-items: center; justify-content: center; min-height: 210px; border: 1px solid var(--border); border-radius: 11px; margin-top: 10px; padding: 16px; }
  .preview-node { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border); border-radius: 9px; background: var(--raised); padding: 14px 12px; font-size: 15px; }
  .preview-node :global(svg) { color: var(--primary); }
  .preview-node.emphasis { border-color: var(--primary); }
  .wire { flex: 0 1 66px; min-width: 10px; height: 2px; background: var(--primary); }
  .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 0 10px; }
  .summary dd { font: 700 25px var(--head); margin-top: 6px; }
  .options h2 { margin-bottom: 17px; }
  .options a, .save-row, .scenario { min-height: 68px; padding: 12px 16px; border: 1px solid var(--border); background: var(--rail); border-radius: 10px; }
  .options a:hover, .save-row:hover { border-color: var(--primary); }
  .options strong { text-transform: uppercase; }
  small { display: block; margin-top: 3px; }
  .form { max-width: 710px; }
  .settings { max-width: 980px; }
  .menu-back:hover { color: var(--primary); }
  .setup-title h1 { font-size: clamp(33px, 4vw, 45px); }
  .menu :global(form.setup) { gap: 28px; }
  .scenario-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 24px; }
  .scenario-grid legend { margin-bottom: 12px; }
  .scenario-grid .scenario { min-height: 115px; padding: 15px; background: var(--surface); gap: 15px; }
  .scenario-grid .scenario.available { background: var(--tint); }
  .scenario strong { text-transform: uppercase; font-size: 17px; }
  .scenario-icon { display: grid; place-items: center; background: var(--rail); color: var(--muted); width: 53px; height: 53px; border-radius: 10px; }
  .available .scenario-icon, .available .scenario-status { color: var(--primary); }
  .scenario-status { display: block; font-size: 11px; margin-top: 7px; color: var(--muted); }
  .scenario:not(.available) input { visibility: hidden; }
  .setup-grid { display: grid; grid-template-columns: 1fr 1fr; align-items: end; gap: 24px; }
  .difficulty { grid-template-columns: repeat(3, 1fr); }
  .difficulty .sui-button { position: relative; min-height: 40px; cursor: pointer; }
  .difficulty .sui-button:has(input:checked) { border-color: var(--primary); background: var(--tint); color: var(--primary); }
  .difficulty input { position: absolute; inset: 0; opacity: 0; width: 100%; height: 100%; margin: 0; cursor: pointer; }
  .difficulty .sui-button:has(:focus-visible) { outline: 2px solid var(--primary); outline-offset: 3px; }
  .starting .row { gap: 10px 22px; margin-top: 7px; }
  .setup-actions { justify-content: flex-end; }
  .setup-actions :global(.sui-button) { min-width: 170px; text-transform: uppercase; }
  .seed { font-size: 12px; }
  .seed-field { max-width: 155px; }
  .notice { margin-bottom: 16px; }
  .save-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 15px; align-items: center; }
  .save-row > a { min-width: 0; overflow-wrap: anywhere; }
  .save-row > a:hover { color: var(--primary); }
  .save-row > a :global(svg) { flex-shrink: 0; margin-left: 8px; }
  .save-actions { justify-content: flex-end; }
  .delete-confirmation { overflow-wrap: anywhere; }
  .import-preview { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
  .import-preview dt { color: var(--muted); font-size: 13px; }
  .import-preview dd { overflow-wrap: anywhere; }
  @media (max-width: 530px) {
    .save-row { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  }
  fieldset { min-width: 0; display: grid; gap: 8px; border: 0; margin: 0; padding: 0; }
  legend { margin-bottom: 6px; }
  .scenario { display: grid; grid-template-columns: auto 1fr auto; gap: 9px; align-items: center; }
  .scenario.available { border-color: var(--primary); cursor: pointer; }
  .scenario input { accent-color: var(--primary); }
  @media (max-width: 850px) {
    .menu-header { min-height: 67px; padding: 13px 17px; }
    .menu-header :global(.brand) { font-size: 14px; }
    .menu-header :global(.brand-mark) { width: 31px; height: 31px; font-size: 23px; border-radius: 9px; }
    main { padding: 20px 17px 32px; }
    .menu-title { margin-bottom: 23px; }
    .menu-grid { grid-template-columns: 1fr; gap: 15px; }
    .continue, .options { padding: 15px; gap: 12px; }
    .continue { min-height: auto; grid-template-rows: auto; }
    .preview { min-height: 144px; padding: 8px; margin-top: 0; }
    .preview-node { font-size: 11px; padding: 10px 6px; }
    .preview-node :global(svg) { display: none; }
    .options { border: 0; background: none; padding: 5px 0 0; }
    .options h2, .options small, .options a :global(svg) { display: none; }
    .options a { min-height: 50px; justify-content: center; }
    .menu :global(form.setup), .setup-grid { gap: 16px; }
    .scenario-grid, .setup-grid { grid-template-columns: 1fr; }
    .scenario-grid .scenario { min-height: 76px; padding: 10px 13px; gap: 10px; }
    .scenario-icon { width: 43px; height: 43px; }
    .scenario strong { font-size: 14px; }
    .scenario-status { margin-top: 3px; }
    .setup-actions { display: grid; grid-template-columns: 1fr 1.5fr; }
    .setup-actions :global(.sui-button) { min-width: 0; }
  }
</style>
