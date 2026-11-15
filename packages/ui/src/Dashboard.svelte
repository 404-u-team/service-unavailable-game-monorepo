<script lang="ts">
  import { GripVertical, LayoutGrid, MoveDiagonal2, Pencil, Settings2 } from '@lucide/svelte';
  import { onDestroy, tick, untrack } from 'svelte';
  import Button from './Button.svelte';
  import Checkbox from './Checkbox.svelte';
  import Slideover from './Slideover.svelte';
  import DashboardWidget from './DashboardWidget.svelte';
  import DashboardWidgetSettings from './DashboardWidgetSettings.svelte';
  import {
    dashboardColumns, dashboardMobileOrder, dashboardPlacement, dashboardReorder, dashboardUpdate,
    parseDashboardState, resolveDashboard, type DashboardState, type DashboardTranslate, type DashboardWidgetDefinition,
    type DashboardWidgetState
  } from './dashboard';

  let { title, widgets, snapshot, onchange, t, columns: requestedColumns = 12, rowHeight = 56,
    compactWidth = 720, readonly = false }: {
    title: string;
    widgets: readonly DashboardWidgetDefinition[];
    snapshot?: unknown;
    onchange?: (snapshot: DashboardState) => void;
    t: DashboardTranslate;
    columns?: number;
    rowHeight?: number;
    compactWidth?: number;
    readonly?: boolean;
  } = $props();

  type Gesture = {
    id: string;
    pointer: number;
    handle: HTMLButtonElement;
    kind: 'move' | 'resize';
    startX: number;
    startY: number;
    columnStep: number;
    rowStep: number;
    direction: number;
    scrollRoot: HTMLElement;
    scrollLimit: number;
    snapX?: number;
    snapY?: number;
    centers?: number[];
    from: DashboardState;
    preview: DashboardState;
  };

  const titleId = $props.id();
  let saved = $state.raw(parseDashboardState(untrack(() => snapshot)));
  let gesture = $state.raw<Gesture>();
  let editing = $state(false);
  let manage = $state(false);
  let settingsOpen = $state(false);
  let settingsId = $state<string>();
  let settingsSession = $state(0);
  let notice = $state('');
  let grid: HTMLDivElement;
  let gridWidth = $state(0);
  let pointerPosition: { x: number; y: number } | undefined;
  let scrollFrame: number | undefined;

  const columns = $derived(dashboardColumns(requestedColumns));
  const row = $derived(Number.isFinite(rowHeight) ? Math.max(32, rowHeight) : 56);
  const compact = $derived(gridWidth > 0 && gridWidth < compactWidth);
  const editable = $derived(editing && !readonly);
  const definitions = $derived(new Map(widgets.map((widget) => [widget.id, widget])));
  const current = $derived(resolveDashboard(widgets, columns, saved));
  const display = $derived(gesture?.preview ?? current);
  const position = $derived(new Map(display.widgets.map((widget) => [widget.id, widget.placement])));
  const mobileOrder = $derived(visibleOrder(display));
  const ordered = $derived(compact ? visibleOrder(current).map((id) => current.widgets.find((widget) => widget.id === id)!)
    : current.widgets.filter((widget) => widget.visible));
  const selected = $derived(current.widgets.find(({ id }) => id === settingsId));
  const selectedDefinition = $derived(settingsId ? definitions.get(settingsId) : undefined);

  $effect(() => {
    const input = snapshot;
    const restored = parseDashboardState(input);
    if (restored || input == null) {
      saved = restored;
      settingsOpen = false;
    }
    untrack(cancelGesture);
  });

  $effect(() => {
    if (!editable) {
      untrack(cancelGesture);
      manage = settingsOpen = false;
    }
  });

  onDestroy(cancelGesture);

  function visibleOrder(state: DashboardState) {
    const visible = new Set(state.widgets.filter((widget) => widget.visible).map((widget) => widget.id));
    return dashboardMobileOrder(state).filter((id) => visible.has(id));
  }

  function commit(next: DashboardState, message: string) {
    if (readonly || next === current) return;
    const valid = parseDashboardState(next);
    if (!valid) return;
    const normalized = resolveDashboard(widgets, columns, valid);
    if (JSON.stringify(current) === JSON.stringify(normalized)) return;
    saved = normalized;
    notice = message;
    onchange?.(getSnapshot());
  }

  export function getSnapshot() {
    return parseDashboardState(current)!;
  }

  async function restoreHandleFocus(handle: HTMLElement) {
    await tick();
    if (handle.isConnected && document.activeElement === document.body) handle.focus({ preventScroll: true });
  }

  function describe(state: DashboardState, id: string) {
    const widget = state.widgets.find((item) => item.id === id);
    const definition = definitions.get(id);
    if (!widget || !definition) return '';
    if (compact) return t('{0} moved to position {1}.', [definition.title, visibleOrder(state).indexOf(id) + 1]);
    const { x, y, width, height } = widget.placement;
    return t('{0}, column {1}, row {2}, width {3}, height {4}.', [definition.title, x + 1, y + 1, width, height]);
  }

  function changeGrid(from: DashboardState, id: string, kind: Gesture['kind'], dx: number, dy: number): DashboardState {
    if (!dx && !dy) return from;
    const widget = from.widgets.find((item) => item.id === id);
    const definition = definitions.get(id);
    if (!widget || !definition) return from;
    const original = widget.placement;
    const proposed = kind === 'move'
      ? { ...original, x: original.x + dx, y: original.y + dy }
      : { ...original, width: original.width + dx, height: original.height + dy };
    const placement = dashboardPlacement(definition, proposed, columns, kind === 'resize');
    if (placement.x === original.x && placement.y === original.y
      && placement.width === original.width && placement.height === original.height) return from;
    return dashboardUpdate(from, { ...widget, placement }, columns);
  }

  function findScrollRoot() {
    for (let node = grid.parentElement; node && node !== document.body; node = node.parentElement) {
      if (node.scrollHeight > node.clientHeight && ['auto', 'scroll'].includes(getComputedStyle(node).overflowY)) return node;
    }
    return (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
  }

  function start(event: PointerEvent & { currentTarget: HTMLButtonElement }, id: string, kind: Gesture['kind']) {
    if (!editable || gesture || !event.isPrimary || event.button !== 0) return;
    const rect = grid.getBoundingClientRect();
    const style = getComputedStyle(grid);
    const columnGap = parseFloat(style.columnGap) || 0;
    const handle = event.currentTarget;
    const centers = compact ? [...grid.querySelectorAll<HTMLElement>(':scope > [data-widget]')]
      .filter((tile) => tile.dataset.widget !== id)
      .map((tile) => {
        const bounds = tile.getBoundingClientRect();
        return bounds.top - rect.top + bounds.height / 2;
      }).sort((a, b) => a - b) : undefined;
    const scrollRoot = findScrollRoot();
    gesture = {
      id, kind, pointer: event.pointerId, handle,
      startX: event.clientX - rect.left, startY: event.clientY - rect.top,
      columnStep: (rect.width + columnGap) / columns, rowStep: row + (parseFloat(style.rowGap) || 0),
      direction: style.direction === 'rtl' ? -1 : 1,
      scrollRoot, scrollLimit: scrollRoot.scrollHeight - scrollRoot.clientHeight, centers, from: current, preview: current
    };
    handle.focus({ preventScroll: true });
    handle.setPointerCapture(event.pointerId);
    event.preventDefault();
  }

  function move(event: PointerEvent) {
    if (!gesture || gesture.pointer !== event.pointerId) return;
    pointerPosition = { x: event.clientX, y: event.clientY };
    moveAt(pointerPosition);
    if (scrollFrame === undefined) scrollFrame = requestAnimationFrame(scrollNearEdge);
  }

  function scrollNearEdge() {
    scrollFrame = undefined;
    if (!gesture || !pointerPosition) return;
    const root = gesture.scrollRoot;
    const viewport = root === document.scrollingElement;
    const bounds = root.getBoundingClientRect();
    const top = viewport ? 0 : Math.max(0, bounds.top);
    const bottom = viewport ? window.innerHeight : Math.min(window.innerHeight, bounds.bottom);
    const edge = Math.min(48, (bottom - top) / 3);
    const speed = Math.max(0, pointerPosition.y - (bottom - edge)) - Math.max(0, top + edge - pointerPosition.y);
    const previous = root.scrollTop;
    const step = Math.sign(speed) * Math.min(16, Math.ceil(Math.abs(speed) / 3));
    if (!step) return;
    const limit = Math.max(previous, gesture.scrollLimit);
    root.scrollTop = Math.max(0, Math.min(limit, previous + step));
    if (root.scrollTop === previous) return;
    moveAt(pointerPosition);
    scrollFrame = requestAnimationFrame(scrollNearEdge);
  }

  function moveAt(pointer: { x: number; y: number }) {
    if (!gesture) return;
    const rect = grid.getBoundingClientRect();
    const y = pointer.y - rect.top;
    const { from, id, kind, startX, startY, direction, columnStep, rowStep, centers } = gesture;
    const snapX = centers ? 0 : Math.round((pointer.x - rect.left - startX) * direction / columnStep);
    const snapY = centers ? centers.filter((center) => center < y).length : Math.round((y - startY) / rowStep);
    if (snapX === gesture.snapX && snapY === gesture.snapY) return;
    const preview = centers ? dashboardReorder(from, id, snapY) : changeGrid(from, id, kind, snapX, snapY);
    gesture = { ...gesture, preview, snapX, snapY };
  }

  function finish(event: PointerEvent) {
    if (!gesture || gesture.pointer !== event.pointerId) return;
    const { handle, id, preview } = gesture;
    cancelGesture();
    commit(preview, describe(preview, id));
    void restoreHandleFocus(handle);
  }

  function cancelGesture(event?: PointerEvent) {
    if (!gesture || (event && gesture.pointer !== event.pointerId)) return;
    const { handle, pointer } = gesture;
    gesture = undefined;
    if (scrollFrame !== undefined) cancelAnimationFrame(scrollFrame);
    scrollFrame = undefined;
    pointerPosition = undefined;
    if (handle.hasPointerCapture(pointer)) handle.releasePointerCapture(pointer);
  }

  function keys(event: KeyboardEvent & { currentTarget: HTMLButtonElement }, id: string, kind: Gesture['kind']) {
    if (event.key === 'Escape' && gesture) {
      event.preventDefault();
      cancelGesture();
      return;
    }
    if (gesture) return;
    const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
    if (!delta) return;
    event.preventDefault();
    const next = compact
      ? dashboardReorder(current, id, visibleOrder(current).indexOf(id) + delta[1])
      : changeGrid(current, id, kind, delta[0] * (getComputedStyle(grid).direction === 'rtl' ? -1 : 1), delta[1]);
    commit(next, describe(next, id));
    void restoreHandleFocus(event.currentTarget);
  }

  function visibility(id: string, visible: boolean) {
    const widget = current.widgets.find((item) => item.id === id);
    if (!widget || widget.visible === visible) return;
    commit(dashboardUpdate(current, { ...widget, visible }, columns), t('Widget visibility updated.'));
  }

  function saveWidget(widget: DashboardWidgetState, mobilePosition?: number) {
    const definition = definitions.get(widget.id);
    if (!definition) return;
    const placement = dashboardPlacement(definition, widget.placement, columns);
    let next = dashboardUpdate(current, { ...widget, placement }, columns);
    if (mobilePosition !== undefined) next = dashboardReorder(next, widget.id, mobilePosition - 1);
    commit(next, t('Widget settings saved.'));
    settingsOpen = false;
  }
</script>

<section aria-labelledby={titleId}>
  <header class="toolbar">
    <h2 id={titleId}>{title}</h2>
    {#if !readonly}
      <div class="actions">
        {#if editable}<Button onclick={() => manage = true}><LayoutGrid size={16} aria-hidden="true" />{t('Widgets')}</Button>{/if}
        <Button variant={editable ? 'primary' : 'secondary'} onclick={() => editing = !editing}>
          {#if !editable}<Pencil size={16} aria-hidden="true" />{/if}
          {editable ? t('Done editing') : t('Edit layout')}
        </Button>
      </div>
    {/if}
  </header>
  {#if editable}
    <p class="instructions">{compact
      ? t('Drag a widget by its handle or use the up and down arrows.')
      : t('Use the handles to move or resize widgets. The arrow keys work on either handle.')}</p>
  {/if}
  <div bind:this={grid} bind:clientWidth={gridWidth} class="grid" class:compact class:dragging={!!gesture}
    style:--columns={columns} style:--row-height={`${row}px`}>
    {#each ordered as widget (widget.id)}
      {@const definition = definitions.get(widget.id)!}
      {@const place = position.get(widget.id) ?? widget.placement}
      {#snippet moveHandle()}
        <button type="button" class="sui-button grab" data-variant="ghost" data-icon-only
          aria-label={t('Move {0}', [definition.title])}
          onpointerdown={(event) => start(event, widget.id, 'move')} onpointermove={move} onpointerup={finish}
          onpointercancel={cancelGesture} onlostpointercapture={cancelGesture}
          onkeydown={(event) => keys(event, widget.id, 'move')}>
          <GripVertical size={19} aria-hidden="true" />
        </button>
      {/snippet}
      {#snippet widgetActions()}
        <Button variant="ghost" iconOnly aria-label={t('Configure {0}', [definition.title])}
          onclick={() => { settingsId = widget.id; settingsSession++; settingsOpen = true; }}>
          <Settings2 size={17} aria-hidden="true" />
        </Button>
      {/snippet}
      {#snippet resizeHandle()}
        <button type="button" class="sui-button size" data-variant="ghost" data-icon-only
          aria-label={t('Resize {0}', [definition.title])}
          onpointerdown={(event) => start(event, widget.id, 'resize')} onpointermove={move} onpointerup={finish}
          onpointercancel={cancelGesture} onlostpointercapture={cancelGesture}
          onkeydown={(event) => keys(event, widget.id, 'resize')}>
          <MoveDiagonal2 size={17} aria-hidden="true" />
        </button>
      {/snippet}
      <div class="widget" class:active={gesture?.id === widget.id} data-widget={widget.id}
        style:grid-column={compact ? '1' : `${place.x + 1} / span ${place.width}`}
        style:grid-row={compact ? String(mobileOrder.indexOf(widget.id) + 1) : `${place.y + 1} / span ${place.height}`}>
        <DashboardWidget title={definition.title}
          handle={editable ? moveHandle : undefined} actions={editable ? widgetActions : undefined}
          resize={editable && !compact ? resizeHandle : undefined}>
          {@render definition.content(widget)}
        </DashboardWidget>
      </div>
    {:else}
      <p class="empty">{t('No widgets are visible.')}</p>
    {/each}
  </div>
  <div class="sui-sr-only" aria-live="polite">{notice}</div>
</section>

<Slideover bind:open={manage} title={t('Widgets')} closeLabel={t('Close dialog')}>
  <div class="catalog">
    {#each [...definitions.values()].filter(({ id }) => id) as definition (definition.id)}
      <Checkbox label={definition.title} checked={current.widgets.find(({ id }) => id === definition.id)?.visible ?? false}
        onchange={(event) => visibility(definition.id, event.currentTarget.checked)} />
    {/each}
  </div>
  {#snippet footer()}
    <div class="actions">
      <Button onclick={() => commit(resolveDashboard(widgets, columns), t('Dashboard reset.'))}>{t('Reset dashboard')}</Button>
      <Button variant="primary" onclick={() => manage = false}>{t('Done')}</Button>
    </div>
  {/snippet}
</Slideover>

<Slideover bind:open={settingsOpen} title={t('Configure {0}', [selectedDefinition?.title ?? ''])} closeLabel={t('Close dialog')}>
  {#if selected && selectedDefinition}
    {#key settingsSession}
      <DashboardWidgetSettings definition={selectedDefinition} widget={selected} {columns} {t}
        mobilePosition={compact ? visibleOrder(current).indexOf(selected.id) + 1 : undefined}
        mobileCount={ordered.length}
        oncancel={() => settingsOpen = false} onsave={saveWidget} />
    {/key}
  {/if}
</Slideover>

<style>
  section { display: grid; gap: var(--sui-space-4); min-inline-size: 0; color: var(--sui-text); font: var(--sui-body); }
  .toolbar, .actions { display: flex; align-items: center; flex-wrap: wrap; gap: var(--sui-space-2); }
  .toolbar { justify-content: space-between; gap: var(--sui-space-3); }
  .actions { justify-content: end; }
  h2 { margin: 0; font: var(--sui-title); overflow-wrap: anywhere; }
  .instructions { margin: 0; color: var(--sui-muted); }
  .grid { display: grid; grid-template-columns: repeat(var(--columns), minmax(0, 1fr)); grid-auto-rows: var(--row-height); gap: var(--sui-space-3); min-inline-size: 0; }
  .grid.compact { grid-template-columns: minmax(0, 1fr); grid-auto-rows: auto; }
  .widget { min-inline-size: 0; min-block-size: 0; }
  .widget.active { z-index: 1; border-radius: var(--sui-radius-panel); outline: var(--sui-focus); }
  .dragging { user-select: none; }
  .grab, .size { touch-action: none; color: var(--sui-muted); }
  .grab { cursor: grab; }
  .active .grab { cursor: grabbing; }
  .size { position: absolute; z-index: 1; inset-inline-end: 0; inset-block-end: 0; cursor: nwse-resize; }
  .size:dir(rtl) { cursor: nesw-resize; }
  .size:dir(rtl) :global(svg) { transform: scaleX(-1); }
  .catalog { display: grid; gap: var(--sui-space-1); }
  .empty { grid-column: 1 / -1; align-content: center; margin: 0; color: var(--sui-muted); }
</style>
