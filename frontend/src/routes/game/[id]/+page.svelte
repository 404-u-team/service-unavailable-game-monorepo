<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { ArrowRight, ChevronDown, Pause, Play, Save as SaveIcon } from '@lucide/svelte';
  import Brand from '#lib/Brand.svelte';
  import Architecture from '#lib/workbench/Architecture.svelte';
  import Dashboard from '#lib/workbench/Dashboard.svelte';
  import { ApiError, gameAction, loadCatalog, loadGame } from '#lib/api.ts';
  import { desktop, mobile, sections, tutorial, type Section } from '#lib/labels.ts';
  import { when } from '#lib/format.ts';
  import type { Catalog, Game, Speed } from '#lib/types.ts';

  let catalog = $state<Catalog>();
  let game = $state.raw<Game>();
  let error = $state('');
  let connection = $state('');
  let loading = $state(true);
  let busy = $state(false);
  let saved = $state(false);
  let clockOpen = $state(false);
  let currentId = '';
  let mounted = $state(false);
  let polling = false;
  let generation = 0;
  let feedback: ReturnType<typeof setTimeout>;
  let actionRequest: { gameId: string; path: string; method: string; key: string; body: string } | undefined;
  const id = $derived(page.params.id ?? '');
  const section = $derived.by((): Section => {
    const key = page.url.searchParams.get('view') || 'build';
    return Object.hasOwn(sections, key) && key !== 'saves' ? key as Section : 'build';
  });
  const link = (target: Section, focus?: string) => `/game/${id}?view=${target}${focus ? `&component=${encodeURIComponent(focus)}` : ''}`;
  const primary: Section[] = ['build', 'monitor', 'growth', 'finance'];
  const speedOptions: { value: Speed; label: string }[] = [
    { value: 0, label: 'Pause game' }, { value: 1, label: 'Normal speed (1×)' }, { value: 3, label: 'Fast speed (3×)' }
  ];

  onMount(() => {
    mounted = true;
    const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 1500);
    const visible = () => { if (!document.hidden) void refresh(); };
    document.addEventListener('visibilitychange', visible);
    return () => {
      mounted = false;
      clearInterval(timer);
      clearTimeout(feedback);
      document.removeEventListener('visibilitychange', visible);
    };
  });

  $effect(() => { if (mounted && id !== currentId) void open(id); });

  function accept(next: Game) {
    if (next.id !== currentId) return;
    if (!game || next.saved_at >= game.saved_at) game = next;
  }

  async function open(gameId: string) {
    currentId = gameId;
    const version = ++generation;
    loading = true;
    game = undefined;
    error = '';
    connection = '';
    try {
      const [state, definitions] = await Promise.all([loadGame(gameId), catalog ? Promise.resolve(catalog) : loadCatalog()]);
      if (version === generation) { game = state; catalog = definitions; }
    } catch (reason) {
      if (version === generation) connection = (reason as Error).message;
    } finally {
      if (version === generation) loading = false;
    }
  }

  async function refresh(force = false) {
    if (!game || (!force && busy) || polling) return;
    const gameId = currentId;
    polling = true;
    try {
      const next = await loadGame(gameId);
      if (mounted && currentId === gameId) { accept(next); connection = ''; }
    } catch (reason) {
      if (currentId === gameId) connection = (reason as Error).message;
    } finally { polling = false; }
  }

  async function act(path: string, body: object = {}, method = 'POST') {
    if (!game || busy) return null;
    const gameId = currentId;
    const signature = JSON.stringify(body);
    if (actionRequest?.gameId !== gameId || actionRequest.path !== path || actionRequest.method !== method || actionRequest.body !== signature) {
      actionRequest = { gameId, path, method, body: signature, key: crypto.randomUUID() };
    }
    busy = true;
    error = '';
    try {
      const next = await gameAction(gameId, path, body, method, actionRequest.key);
      actionRequest = undefined;
      if (!mounted || currentId !== gameId) return null;
      accept(next);
      connection = '';
      if (path === '/save') {
        saved = true;
        clearTimeout(feedback);
        feedback = setTimeout(() => saved = false, 2600);
      }
      return next;
    } catch (reason) {
      error = (reason as Error).message;
      if (reason instanceof ApiError && reason.status < 500) actionRequest = undefined;
      if (reason instanceof ApiError && reason.status === 409) await refresh(true);
      return null;
    } finally { busy = false; }
  }

  function note(interaction: 'inspect' | 'monitor') {
    if ((interaction === 'inspect' && game?.tutorial === 0) || (interaction === 'monitor' && game?.tutorial === 3)) {
      void act('/tutorial', { interaction });
    }
  }
</script>

<div class="game" data-reduced-motion={game?.settings.reduced_motion ?? false}>
  <header class="topbar">
    <Brand />
    {#if game}
      <nav class="primary-nav" aria-label="Primary navigation">
        {#each primary as item}<a href={link(item)} aria-current={section === item ? 'page' : undefined}>{sections[item].name}</a>{/each}
      </nav>
      <div class="controls row">
        <span class="badge good online"><i class="dot"></i>{game.speed ? 'Live' : 'Paused'}</span>
        <button class="btn quick-pause" aria-label={game.speed ? 'Pause simulation' : 'Run simulation at normal speed'} disabled={busy} onclick={() => act('/clock', { speed: game?.speed ? 0 : 1 }, 'PUT')}>
          {#if game.speed}<Pause size={15} />{:else}<Play size={15} />{/if}
        </button>
        <div class="clock-control">
          <button class="btn speed" aria-label="Game speed" aria-expanded={clockOpen} onclick={() => clockOpen = !clockOpen}>
            {game.speed ? `${game.speed}×` : 'Paused'} <ChevronDown size={13} />
          </button>
          {#if clockOpen}
            <div class="clock-options panel stack">
              {#each speedOptions as speed}<button class="btn" disabled={busy} aria-pressed={game.speed === speed.value}
                onclick={async () => { if (await act('/clock', { speed: speed.value }, 'PUT')) clockOpen = false; }}>{speed.label}</button>{/each}
            </div>
          {/if}
        </div>
        <span class="time mono">{when(game.tick)}</span>
        <button class="btn icon-btn quick-save" title={saved ? 'Game saved' : 'Save game'} aria-label="Save game" disabled={busy} onclick={() => act('/save')}><SaveIcon size={15} /></button>
      </div>
    {/if}
  </header>

  {#if loading}
    <main class="fallback"><p aria-live="polite">Loading service…</p></main>
  {:else if !game || !catalog}
    <main class="fallback stack"><h1>Could not open game</h1><p class="notice error" role="alert">{connection || 'The save is unavailable.'}</p>
      <div class="row"><button class="btn primary" onclick={() => open(id)}>Retry connection</button><a class="btn" href="/?view=saves">Saved games</a></div>
    </main>
  {:else}
    <nav class="rail" aria-label="Workbench navigation">
      {#each desktop as item}
        {@const Icon = sections[item].icon}
        <a href={link(item)} aria-current={section === item ? 'page' : undefined}><span><Icon size={24} strokeWidth={1.8} /></span>{sections[item].name}</a>
      {/each}
      <a href="/?view=saves" class="rail-saves" aria-label="Saved games"><span class="avatar">SU</span></a>
    </nav>
    <div class="main-area">
      {#if connection || error}
        <div class="server-message notice error row spread" role="alert"><span>{connection || error}</span><button class="btn" onclick={() => { error = ''; void refresh(); }}>{connection ? 'Reconnect' : 'Dismiss'}</button></div>
      {/if}
      {#if saved}<span class="save-feedback badge good" role="status">Game saved</span>{/if}
      {#key `${game.id}:${section}`}
        {#if section === 'build'}
          <Architecture {game} {catalog} {act} {busy} {error} {note} focusId={page.url.searchParams.get('component') ?? undefined} />
        {:else}
          <Dashboard {section} {game} {catalog} {link} {act} {busy} {error} {note} />
        {/if}
      {/key}
      {#if game.settings.show_tutorial && tutorial[game.tutorial] && (section === 'build' || section === 'home')}
        {@const step = tutorial[game.tutorial]}
        <aside class="tutorial panel row spread" aria-label="Onboarding tip">
          <div><p class="eyebrow">Onboarding · {game.tutorial + 1} / {tutorial.length}</p><strong>{step.title}</strong></div>
          <a class="btn" href={link(step.section === section ? 'guide' : step.section)}>{step.section === section ? 'Guide' : 'Open'} <ArrowRight size={14} /></a>
        </aside>
      {/if}
    </div>
    <nav class="bottom" aria-label="Mobile navigation">
      {#each mobile as item}
        {@const Icon = sections[item].icon}
        {@const active = section === item || (item === 'more' && !mobile.includes(section))}
        <a href={link(item)} aria-current={active ? 'page' : undefined}><span><Icon size={21} strokeWidth={1.8} /></span>{sections[item].mobile}</a>
      {/each}
    </nav>
  {/if}
</div>

<style>
  .game { display: grid; min-height: 100dvh; grid-template: 65px 1fr / 76px minmax(0, 1fr); }
  .topbar { grid-column: 1 / -1; position: sticky; top: 0; z-index: 12; display: grid; grid-template-columns: clamp(248px, 22.3vw, 350px) 1fr auto; align-items: center; gap: 10px; min-height: 65px; padding: 0 23px; background: var(--background); border-bottom: 1px solid var(--border); }
  .topbar :global(.brand) { font-size: 16px; }
  .primary-nav { display: flex; height: 100%; }
  .primary-nav a { min-width: 112px; padding: 0 8px; display: grid; place-items: center; color: var(--muted); font-size: 11px; text-transform: uppercase; font-weight: 600; border-bottom: 2px solid transparent; }
  .primary-nav a[aria-current], .primary-nav a:hover { border-color: var(--primary); color: var(--text); }
  .controls { gap: 6px; }
  .controls .online { margin-right: 8px; min-width: 65px; }
  .controls .btn { min-height: 31px; font-family: var(--mono); }
  .quick-pause { width: 32px; padding: 0; }
  .clock-control { position: relative; }
  .speed { min-width: 54px; }
  .clock-options { position: absolute; right: 0; top: calc(100% + 8px); width: 170px; padding: 7px; gap: 5px; }
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
  .tutorial { position: fixed; bottom: 19px; right: 19px; z-index: 4; max-width: calc(100vw - 38px); padding: 8px 11px; box-shadow: 0 5px 18px #0005; }
  .tutorial strong { font-size: 13px; }
  .tutorial p { font-size: 9px; }
  .tutorial .btn { min-height: 31px; }
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
    .primary-nav, .rail, .time, .quick-save, .quick-pause { display: none; }
    .controls .btn { min-height: 34px; }
    .main-area { grid-column: 1; }
    .bottom { position: fixed; inset: auto 0 0; z-index: 12; display: grid; grid-template-columns: repeat(5, 1fr); padding: 8px 8px calc(8px + env(safe-area-inset-bottom)); background: var(--background); border-top: 1px solid var(--border); }
    .bottom a { min-height: 49px; align-content: center; gap: 4px; }
    .bottom a span { display: grid; place-items: center; height: 31px; width: 58px; border-radius: 12px; }
    .bottom a[aria-current] { color: var(--text); }
    .bottom a[aria-current] span { background: var(--tint); color: var(--primary); }
    .tutorial { position: static; margin: 0 17px 14px; }
  }
</style>
