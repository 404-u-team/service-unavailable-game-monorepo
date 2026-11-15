<script lang="ts">
  import { apiMessage, message, t } from '#lib/i18n.svelte.ts';
  import { onMount, untrack } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/state';
  import { ArrowDownRight, ArrowUpRight, Pause, X, Save as SaveIcon } from '@lucide/svelte';
  import Brand from '#lib/Brand.svelte';
  import Architecture from '#lib/workbench/Architecture.svelte';
  import Onboarding from '#lib/workbench/Onboarding.svelte';
  import { engineeringLessons } from '#lib/workbench/engineering-lesson.ts';
  import Dashboard from '#lib/workbench/Dashboard.svelte';
  import { ApiError, gameAction, loadCatalog, loadGame } from '#lib/api.ts';
  import { desktop, mobile, sections, type Section } from '#lib/labels.ts';
  import { subscribeGame } from '#lib/live.ts';
  import { nav, onboarding, stepId, target, tutorialView, type StepId, type Target,
    type TutorialAction, type TutorialArchitecture, type TutorialEvent } from '#lib/workbench/onboarding.ts';
  import { openDialog } from '#lib/workbench/spotlight.ts';
  import { syncLayout } from '#lib/workbench/layout-sync.ts';
  import { money, minuteClock, preciseMoney, when } from '#lib/format.ts';
  import type { Catalog, Diagram, Game, Speed } from '#lib/types.ts';

  let game = $state.raw<Game>();
  let engineeringWalkthrough = $state(false);
  $effect(() => { if (page.url.searchParams.get('engineering') === '1') engineeringWalkthrough = true; });
  const engineeringStep = $derived(game ? engineeringLessons[game.engineering_lesson ?? 0] : undefined);
  async function changeEngineering(action: TutorialAction) {
    if (!game) return;
    if (action === 'skip') { engineeringWalkthrough = false; return; }
    const next = Math.min(6, Math.max(0, (game.engineering_lesson ?? 0) + (action === 'back' ? -1 : 1)));
    await act('/engineering-lesson', { step: next }, 'PUT');
    if (next === 6) engineeringWalkthrough = false;
  }

  let pendingDiagram = $state.raw<Diagram>();
  let layout: ReturnType<typeof syncLayout> | undefined;
  let live: ReturnType<typeof subscribeGame> | undefined;
  let layoutFailed = $state(false);
  let viewedEvent = '';
  let recentEvent = $state<Game['incidents'][number]>();
  const latestIncident = $derived(game?.incidents[0]);
  $effect(() => {
    if (!latestIncident || latestIncident.id === viewedEvent) return;
    viewedEvent = latestIncident.id;
    if (latestIncident.severity === 'info' && !latestIncident.id.startsWith('campaign-complete-') &&
        !latestIncident.id.startsWith('release-')) return;
    if (game && game.tick - latestIncident.start < 3) recentEvent = latestIncident;
  });

  let catalog = $state<Catalog>();
  let error = $state('');
  let connection = $state('');
  let loading = $state(true);
  let busy = $state(false);
  let saved = $state(false);
  let lastSpeed: Exclude<Speed, 0> = 1;
  let currentId = '';
  let mounted = $state(false);
  let compact = $state(false);
  let architecture = $state<{ revealTutorialApi: () => void }>();
  let tutorialUi = $state.raw<TutorialArchitecture>();
  let tutorialEvent = $state<{ step: StepId; name: TutorialEvent }>();
  let completion = $state(false);
  let pendingAction = $state('');
  let pendingTutorial = $state(false);
  let rejected = $state<StepId>();
  let generation = 0;
  let feedback: ReturnType<typeof setTimeout>;
  let actionRequest: { gameId: string; path: string; method: string; key: string; body: string } | undefined;
  const id = $derived(page.params.id ?? '');
  const section = $derived.by((): Section => {
    const key = page.url.searchParams.get('view') || 'build';
    return Object.hasOwn(sections, key) && key !== 'saves' ? key as Section : 'build';
  });
  const link = (target: Section, focus?: string) => `/game/${id}?view=${target}${focus ? `&component=${encodeURIComponent(focus)}` : ''}`;
  const tutorialStep = $derived(game ? stepId(game.onboarding) : 'complete');
  const tutorialEnabled = $derived(game?.scenario === 'messenger' && game.settings.show_tutorial && !game.onboarding.skipped && tutorialStep !== 'complete');
  const tutorialVisible = $derived(tutorialEnabled && section !== 'guide' && section !== 'settings');
  const step = $derived(onboarding.find((item) => item.id === tutorialStep));
  const defaults = $derived(Object.fromEntries(Object.entries(catalog?.components.api.fields ?? {}).map(([key, field]) => [key, field.default])));
  const currentView = $derived(step && game ? tutorialView(step, {
    game, section, ui: section === 'build' ? tutorialUi : undefined, compact, event: tutorialEvent,
    apiDefaults: defaults, monitorSlots: Number(catalog?.components.monitor.fields.slots.default)
  }) : {});
  const tutorialWaiting = $derived(pendingTutorial || ('mode' in (step ?? {}) && (
    pendingAction === '/draft' || pendingAction === '/deployments'
  )) || (section === 'build' && tutorialUi?.dialog === 'review' && tutorialUi.reviewPending));

  const primary: Section[] = ['build', 'monitor', 'growth', 'finance'];
  const speedOptions: { value: Speed; label: string; shortcut: string }[] = [
    { value: 0, label: 'Pause simulation', shortcut: 'Space' },
    { value: 1, label: 'Run simulation at normal speed', shortcut: '1' },
    { value: 3, label: 'Fast speed (3×)', shortcut: '2' },
    { value: 5, label: 'Fast speed (5×)', shortcut: '3' }
  ];

  onMount(() => {
    mounted = true;
    const media = matchMedia('(max-width: 850px)');
    const resize = () => compact = media.matches;
    resize();
    media.addEventListener('change', resize);
    const flush = () => { if (document.hidden) void layout?.flush(); };
    document.addEventListener('visibilitychange', flush);
    return () => {
      mounted = false;
      ++generation;
      live?.close();
      layout?.close();
      clearTimeout(feedback);
      document.removeEventListener('visibilitychange', flush);
      media.removeEventListener('change', resize);
    };
  });
  beforeNavigate(({ from, to }) => {
    void layout?.flush();
    if (from?.url.searchParams.get('view') !== to?.url.searchParams.get('view')) {
      tutorialUi = undefined;
      tutorialEvent = undefined;
    }
  });

  $effect(() => { if (mounted && id !== currentId) void open(id); });

  function accept(next: Game) {
    if (next.id !== currentId || (game && next.saved_at < game.saved_at)) return;
    if (next.speed) lastSpeed = next.speed;
    if (game) {
      // Keep structural references stable when REST replies or reconnect snapshots include them again.
      for (const key of ['production', 'draft', 'diagram', 'settings'] as const) {
        if (next[key] === game[key] || JSON.stringify(next[key]) !== JSON.stringify(game[key])) continue;
        Object.assign(next, { [key]: game[key] });
      }
    }
    game = next;
  }

  async function open(gameId: string) {
    live?.close();
    layout?.close();
    currentId = gameId;
    actionRequest = undefined;
    busy = false;
    pendingAction = '';
    pendingTutorial = false;
    completion = false;
    tutorialUi = undefined;
    tutorialEvent = undefined;
    rejected = undefined;
    recentEvent = undefined;
    lastSpeed = 1;
    const version = ++generation;
    loading = true;
    game = undefined;
    pendingDiagram = undefined;
    layoutFailed = false;
    error = '';
    connection = '';
    try {
      const [definitions, state] = await Promise.all([loadCatalog(), loadGame(gameId)]);
      if (version !== generation) return;
      catalog = definitions;
      accept(state);
      layout = syncLayout(gameId, (diagram) => pendingDiagram = diagram, accept, (failed) => layoutFailed = failed);
      live = subscribeGame(gameId, accept, (connected) => {
        connection = connected ? '' : 'Live connection lost. Reconnecting…';
      });
    } catch (reason) {
      if (version === generation) connection = apiMessage(reason);
    } finally {
      if (version === generation) loading = false;
    }
  }

  function saveDiagram(diagram: Diagram) {
    if (game) layout?.queue(pendingDiagram ?? game.diagram, diagram);
  }

  async function save() {
    await act('/save');
  }

  function speed(value: Speed) {
    if (game && game.speed !== value) void act('/clock', { speed: value }, 'PUT');
  }

  function shortcuts(event: KeyboardEvent) {
    if (!game || event.defaultPrevented || event.isComposing || event.repeat) return;
    const target = event.target instanceof HTMLElement ? event.target : undefined;
    if (target?.closest('input, textarea, select, [role=combobox], [contenteditable]:not([contenteditable=false])')) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      void save();
      return;
    }
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || document.querySelector('dialog[open]')) return;
    if (event.code === 'Space' && !target?.closest('button, a, summary, [role=button]')) {
      event.preventDefault();
      speed(game.speed ? 0 : lastSpeed);
    }
    const option = speedOptions.find((item) => item.shortcut === event.key);
    if (option) speed(option.value);
  }

  async function act(path: string, body: object = {}, method = 'POST') {
    if (!game || busy) return null;
    const gameId = currentId;
    if (path === '/save' && layout && (!await layout.flush() || busy || gameId !== currentId)) return null;
    const signature = JSON.stringify(body);
    if (actionRequest?.gameId !== gameId || actionRequest.path !== path || actionRequest.method !== method || actionRequest.body !== signature) {
      actionRequest = { gameId, path, method, body: signature, key: crypto.randomUUID() };
    }
    busy = true;
    pendingAction = path;
    error = '';
    try {
      const next = await gameAction(gameId, path, body, method, actionRequest.key);
      if (!mounted || currentId !== gameId) return null;
      actionRequest = undefined;
      accept(next);
      if (path === '/save') {
        saved = true;
        clearTimeout(feedback);
        feedback = setTimeout(() => saved = false, 2600);
      }
      return next;
    } catch (reason) {
      if (!mounted || currentId !== gameId) return null;
      error = apiMessage(reason);
      if (reason instanceof ApiError && reason.status < 500) actionRequest = undefined;
      if (reason instanceof ApiError && reason.status === 409) live?.reconnect();
      return null;
    } finally {
      if (currentId === gameId) {
        busy = false;
        pendingAction = '';
      }
    }
  }

  async function guide(interaction: TutorialAction) {
    if (!game || pendingTutorial || busy) return;
    const currentStep = tutorialStep;
    const gameId = game.id;
    pendingTutorial = true;
    rejected = undefined;
    try {
      const next = await act('/onboarding', { step_id: currentStep, interaction });
      if (!mounted || currentId !== gameId) return;
      if (!next || (interaction === 'observed' && stepId(next.onboarding) === currentStep)) {
        rejected = currentStep;
        return;
      }
      tutorialEvent = undefined;
      if (interaction === 'resume' || interaction === 'restart') {
        completion = false;
        if (section === 'settings' || section === 'guide') await goto(link('build'));
      } else if (stepId(next.onboarding) === 'complete' && currentStep !== 'complete') {
        completion = true;
      }
    } finally {
      if (currentId === gameId) pendingTutorial = false;
    }
  }

  function recordTutorial(name: TutorialEvent) {
    if (!tutorialEnabled) return;
    tutorialEvent = { step: tutorialStep, name };
    rejected = undefined;
  }

  function recoverTutorial(key?: Target) {
    rejected = undefined;
    if (key === target.api) architecture?.revealTutorialApi();
  }

  $effect(() => {
    if (!tutorialVisible || !currentView.observed || pendingTutorial || busy || rejected === tutorialStep) return;
    const modal = openDialog();
    if (currentView.target && modal && !modal.querySelector(`[data-tutorial="${currentView.target}"]`)) return;
    untrack(() => void guide('observed'));
  });
</script>

<svelte:window onkeydown={shortcuts} />

<div class="game" data-reduced-motion={game?.settings.reduced_motion ?? false}>
  <header class="topbar" data-tutorial-obstruction="top">
    <Brand />
    {#if game}
      <nav class="primary-nav" aria-label={t("Primary navigation")}>
        {#each primary as item}<a data-tutorial={nav(item)} href={link(item)} aria-current={section === item ? 'page' : undefined}>{t(sections[item].name)}</a>{/each}
      </nav>
      <div class="controls row">
        <span class="badge good online"><i class="dot"></i>{game.speed ? t("Live") : t("Paused")}</span>
        <a class="balance" data-tutorial={target.balance} href={link('finance')} title={t('Cash balance and daily operating profit')} aria-label={t('Finance')}>
          <strong>{money(game.economy.balance)}</strong>
          <span class:positive={game.economy.daily_profit > 0} class:negative={game.economy.daily_profit < 0}>
            {#if game.economy.daily_profit > 0}<ArrowUpRight size={12} />{:else if game.economy.daily_profit < 0}<ArrowDownRight size={12} />{/if}
            {t('{0}/day', [(game.economy.daily_profit > 0 ? '+' : '') + preciseMoney(game.economy.daily_profit)])}
          </span>
        </a>
        <div class="speed-group row" data-tutorial={target.clock} role="group" aria-label={t('Game speed')}>
          {#each speedOptions as option (option.value)}
            <button class="btn" disabled={busy} aria-pressed={game.speed === option.value} aria-label={t(option.label)}
              title={t('{0} ({1})', [t(option.label), t(option.shortcut)])} onclick={() => speed(option.value)}>
              {#if option.value}{option.value}×{:else}<Pause size={14} />{/if}
            </button>
          {/each}
        </div>
        <span class="time mono">{game.snapshot.demand_overview ? t('Day {0} / {1}', [game.snapshot.demand_overview.day, minuteClock(game.snapshot.demand_overview.utc_minute)]) : when(game.tick)}</span>
        <button class="btn icon-btn quick-save" title={saved ? t("Game saved") : t("Save game (Ctrl/Cmd + S)")} aria-label={t("Save game")} disabled={busy} onclick={save}><SaveIcon size={15} /></button>
      </div>
    {/if}
  </header>

  {#if loading}
    <main class="fallback"><p aria-live="polite">{t("Loading service…")}</p></main>
  {:else if !game || !catalog}
    <main class="fallback stack"><h1>{t("Could not open game")}</h1><p class="notice error" role="alert">{connection ? message(connection) : t("The save is unavailable.")}</p>
      <div class="row"><button class="btn primary" onclick={() => open(id)}>{t("Retry connection")}</button><a class="btn" href="/?view=saves">{t("Saved games")}</a></div>
    </main>
  {:else}
    <nav class="rail" aria-label={t("Workbench navigation")}>
      {#each desktop as item}
        {@const Icon = sections[item].icon}
        <a data-tutorial={nav(item)} href={link(item)} aria-current={section === item ? 'page' : undefined}><span><Icon size={24} strokeWidth={1.8} /></span>{t(sections[item].name)}</a>
      {/each}
      <a href="/?view=saves" class="rail-saves" aria-label={t("Saved games")}><span class="avatar">{t("SU")}</span></a>
    </nav>
    <div class="main-area">
      {#if connection || error}
        <div class="server-message notice error row spread" role="alert"><span>{message(connection || error)}</span><button class="btn" onclick={() => { if (connection) live?.reconnect(); else error = ''; }}>{connection ? t("Reconnect") : t("Dismiss")}</button></div>
      {/if}
      {#if saved}<span class="save-feedback badge good" role="status">{t("Game saved")}</span>{/if}
      {#if game.migration}<p class="notice warn" role="status">{t('Architecture migration')} · {t('{0} ticks remaining', [Math.max(0, game.migration.ready_at - game.tick)])}</p>{/if}
      {#key `${game.id}:${section}`}
        {#if section === 'build'}
          <Architecture bind:this={architecture} {game} {catalog} {act} {busy} {error} tutorial={tutorialEnabled} tutorialSelect={currentView.target === target.api}
            tutorialState={(state) => tutorialUi = state} tutorialEvent={recordTutorial} {saveDiagram} {layoutFailed}
            retryDiagram={() => { if (game) void layout?.retry(game.diagram); }} savedDiagram={pendingDiagram ?? game.diagram}
            focusId={page.url.searchParams.get('component') ?? undefined}
            openConfiguration={page.url.searchParams.get('configure') === '1'} guideHref={link('guide')} />
        {:else}
          <Dashboard {section} {game} {catalog} {link} {act} {busy} {error} tutorialAction={guide} />
        {/if}
      {/key}
      {#if recentEvent && section !== 'events'}
        <aside class="event-feedback notice row spread" class:warn={recentEvent.severity !== 'info'} aria-live="polite">
          <a href={link('events')} onclick={() => recentEvent = undefined}>{message(recentEvent.title)}</a>
          <button class="btn icon-btn" aria-label={t('Dismiss notification')} onclick={() => recentEvent = undefined}><X size={14} /></button>
        </aside>
      {/if}
      {#if engineeringWalkthrough && engineeringStep}
        <Onboarding progress={game.onboarding} lesson={{ ...engineeringStep, index: game.engineering_lesson ?? 0 }}
          view={{ target: engineeringStep.target, open: engineeringStep.open, allowed: true }} {link} {busy} waiting={false}
          change={changeEngineering} recover={() => {}} />
      {:else if tutorialVisible || completion}
        <Onboarding progress={game.onboarding} view={rejected === tutorialStep
          ? { ...currentView, retry: true, instruction: 'Progress could not be saved. Retry this step or skip it.' } : currentView}
          {link} {busy} waiting={tutorialWaiting} change={(action) => void guide(action)} recover={recoverTutorial}
          complete={() => completion = false} />
      {/if}
    </div>
    <nav class="bottom" data-tutorial-obstruction="bottom" aria-label={t("Mobile navigation")}>
      {#each mobile as item}
        {@const Icon = sections[item].icon}
        {@const active = section === item || (item === 'more' && !mobile.includes(section))}
        <a data-tutorial={nav(item)} href={link(item)} aria-current={active ? 'page' : undefined}><span><Icon size={21} strokeWidth={1.8} /></span>{t(sections[item].mobile)}</a>
      {/each}
    </nav>
  {/if}
</div>

<style>
  .game { display: grid; min-height: 100dvh; grid-template: 65px 1fr / 76px minmax(0, 1fr); }
  .topbar { grid-column: 1 / -1; position: sticky; top: 0; z-index: var(--layer-workbench-navigation); display: grid; grid-template-columns: clamp(248px, 22.3vw, 350px) 1fr auto; align-items: center; gap: 10px; min-height: 65px; padding: 0 23px; background: var(--background); border-bottom: 1px solid var(--border); }
  .topbar :global(.brand) { font-size: 16px; }
  .primary-nav { display: flex; height: 100%; }
  .primary-nav a { min-width: 112px; padding: 0 8px; display: grid; place-items: center; color: var(--muted); font-size: 11px; text-transform: uppercase; font-weight: 600; border-bottom: 2px solid transparent; }
  .primary-nav a[aria-current], .primary-nav a:hover { border-color: var(--primary); color: var(--text); }
  .controls { gap: 6px; }
  .controls .online { margin-right: 8px; min-width: 65px; }
  .controls .btn { min-height: 31px; font-family: var(--mono); }
  .speed-group { gap: 2px; }
  .speed-group button { min-width: 32px; justify-content: center; padding-inline: 4px; }
  .balance { display: grid; min-width: max-content; gap: 1px; margin-inline: 4px; font-family: var(--mono); }
  .balance strong { font-size: 15px; }
  .balance span { display: flex; gap: 2px; align-items: center; font-size: 10px; color: var(--muted); }
  .balance span.positive { color: var(--primary); }
  .balance span.negative { color: var(--error); }
  .time { display: inline-flex; align-items: center; min-height: 31px; padding: 0 11px; border: 1px solid var(--border); border-radius: 7px; background: var(--surface); font-size: 11px; white-space: nowrap; text-transform: uppercase; }
  .rail { position: sticky; top: 65px; height: calc(100dvh - 65px); min-height: 630px; background: var(--rail); display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 4px; padding: 11px 5px 30px; }
  .rail a, .bottom a { display: grid; justify-items: center; gap: 3px; color: var(--muted); text-align: center; font-size: 10px; line-height: 1.2; }
  .rail a span { display: grid; place-items: center; width: 54px; height: clamp(37px, 6vh, 54px); border-radius: 12px; }
  .rail a[aria-current] span, .rail a:hover span { background: var(--surface); color: var(--primary); }
  .rail a[aria-current] { color: var(--text); }
  .rail .rail-saves { margin-top: 4px; }
  .rail .avatar { width: 32px; height: 32px; background: var(--surface); border-radius: 100%; font: 700 12px var(--head); color: var(--text); }
  .main-area { position: relative; min-width: 0; }
  .fallback { grid-column: 1 / -1; padding: 32px; max-width: 680px; }
  .server-message { position: sticky; top: 69px; z-index: 8; margin: 8px 14px; }
  .save-feedback { position: fixed; top: 73px; right: 20px; z-index: 8; }
  .event-feedback { position: sticky; bottom: 10px; z-index: 6; margin: 6px 15px; background: var(--surface); }
  .event-feedback a:hover { text-decoration: underline; }
  .bottom { display: none; }
  @media (max-width: 1120px) {
    .topbar { grid-template-columns: minmax(205px, 1fr) minmax(290px, 1.3fr) auto; padding-inline: 12px; }
    .primary-nav a { min-width: 72px; }
    .controls .online { display: none; }
  }
  @media (max-width: 850px) {
    .game { grid-template: 66px 1fr / minmax(0, 1fr); padding-bottom: calc(69px + env(safe-area-inset-bottom)); }
    .topbar { display: flex; justify-content: space-between; padding: 0 16px; min-height: 66px; }
    .topbar :global(.brand) { font-size: 14px; }
    .primary-nav, .rail, .time { display: none; }
    .controls .btn { min-height: 34px; }
    .topbar { padding-inline: 8px; gap: 5px; }
    .topbar :global(.brand) { min-width: 0; font-size: 12px; }
    .topbar :global(.brand > span:last-child) { display: none; }
    .controls { gap: 3px; }
    .balance strong { font-size: 12px; }
    .main-area { grid-column: 1; }
    .bottom { position: fixed; inset: auto 0 0; z-index: var(--layer-workbench-navigation); display: grid; grid-template-columns: repeat(5, 1fr); padding: 8px 8px calc(8px + env(safe-area-inset-bottom)); background: var(--background); border-top: 1px solid var(--border); }
    .bottom a { min-height: 49px; align-content: center; gap: 4px; }
    .bottom a span { display: grid; place-items: center; height: 31px; width: 58px; border-radius: 12px; }
    .bottom a[aria-current] { color: var(--text); }
    .bottom a[aria-current] span { background: var(--tint); color: var(--primary); }
    .event-feedback { bottom: 68px; }
  }
</style>
