import type { Snippet } from 'svelte';

export type DashboardValue = null | boolean | number | string | readonly DashboardValue[] | DashboardSettings;
export type DashboardSettings = { readonly [key: string]: DashboardValue };
export type DashboardPlacement = { x: number; y: number; width: number; height: number };

export type DashboardWidgetState = {
  id: string;
  placement: DashboardPlacement;
  visible: boolean;
  settings: DashboardSettings;
};

export type DashboardState = {
  version: 1;
  widgets: DashboardWidgetState[];
  mobileOrder?: string[];
};

export type DashboardWidgetDefinition = {
  id: string;
  title: string;
  placement?: Partial<DashboardPlacement>;
  minWidth?: number;
  maxWidth?: number;
  minHeight?: number;
  maxHeight?: number;
  initiallyHidden?: boolean;
  defaultSettings?: DashboardSettings;
  content: Snippet<[DashboardWidgetState]>;
  settings?: Snippet<[DashboardWidgetState, (patch: DashboardSettings) => void]>;
};

export type DashboardTranslate = (message: string, args?: readonly unknown[]) => string;

export const dashboardLastRow = 1000;
const maxWidgetRows = 24;
const maxColumns = 24;

function isObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object') return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function isJson(value: unknown, depth: number): value is DashboardValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (depth > 24) return false;
  if (Array.isArray(value)) return value.every((item) => isJson(item, depth + 1));
  return isObject(value) && Object.values(value).every((item) => isJson(item, depth + 1));
}

function parsePlacement(value: unknown): DashboardPlacement | undefined {
  if (!isObject(value)) return;
  const { x, y, width, height } = value;
  if (typeof x !== 'number' || typeof y !== 'number' || typeof width !== 'number' || typeof height !== 'number') return;
  if (![x, y, width, height].every(Number.isSafeInteger) || x < 0 || y < 0 || width < 1 || height < 1) return;
  return { x, y, width, height };
}

export function parseDashboardState(input: unknown): DashboardState | null {
  let data: unknown = input;
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch { return null; }
  }
  if (!isObject(data) || data.version !== 1 || !Array.isArray(data.widgets)) return null;

  const widgets: DashboardWidgetState[] = [];
  const ids = new Set<string>();
  for (const item of data.widgets) {
    if (!isObject(item)) return null;
    const { id, visible, settings } = item;
    const placement = parsePlacement(item.placement);
    if (typeof id !== 'string' || !id || ids.has(id) || typeof visible !== 'boolean'
      || !placement || !isObject(settings) || !isJson(settings, 0)) return null;
    ids.add(id);
    widgets.push({ id, visible, placement, settings: JSON.parse(JSON.stringify(settings)) as DashboardSettings });
  }
  if (data.mobileOrder === undefined) return { version: 1, widgets };
  if (!Array.isArray(data.mobileOrder) || !data.mobileOrder.every((id) => typeof id === 'string')) return null;
  return { version: 1, widgets, mobileOrder: [...new Set<string>(data.mobileOrder)] };
}

function bounded(value: number | undefined, fallback: number, min: number, max: number) {
  return Math.round(Math.min(max, Math.max(min, value != null && Number.isFinite(value) ? value : fallback)));
}

export function dashboardColumns(columns: number) {
  return bounded(columns, 12, 1, maxColumns);
}

export function dashboardLimits(widget: DashboardWidgetDefinition, columns: number) {
  const minWidth = bounded(widget.minWidth, Math.min(2, columns), 1, columns);
  const minHeight = bounded(widget.minHeight, 1, 1, maxWidgetRows);
  return {
    minWidth,
    minHeight,
    maxWidth: bounded(widget.maxWidth, columns, minWidth, columns),
    maxHeight: bounded(widget.maxHeight, maxWidgetRows, minHeight, maxWidgetRows)
  };
}

export function dashboardPlacement(
  definition: DashboardWidgetDefinition,
  placement: Partial<DashboardPlacement>,
  columns: number,
  keepOrigin = false
): DashboardPlacement {
  const limits = dashboardLimits(definition, columns);
  const x = bounded(placement.x, 0, 0, columns - limits.minWidth);
  const width = bounded(placement.width, Math.min(4, columns), limits.minWidth, Math.min(limits.maxWidth, keepOrigin ? columns - x : columns));
  return {
    x: Math.min(x, columns - width),
    y: bounded(placement.y, 0, 0, dashboardLastRow),
    width,
    height: bounded(placement.height, 3, limits.minHeight, limits.maxHeight)
  };
}

export function dashboardCompare(a: DashboardWidgetState, b: DashboardWidgetState) {
  const position = a.placement.y - b.placement.y || a.placement.x - b.placement.x;
  if (position || a.id === b.id) return position;
  return a.id < b.id ? -1 : 1;
}

function overlaps(a: DashboardPlacement, b: DashboardPlacement) {
  return a.x < b.x + b.width && a.x + a.width > b.x
    && a.y < b.y + b.height && a.y + a.height > b.y;
}

function belowBlockers(placement: DashboardPlacement, placed: readonly DashboardPlacement[], columns: number) {
  let next = placement;
  while (next.y <= dashboardLastRow) {
    const blockers = placed.filter((item) => overlaps(item, next));
    if (!blockers.length) return next;
    next = { ...next, y: Math.max(...blockers.map((item) => item.y + item.height)) };
  }
  return firstSpace(placement, placed, columns);
}

function firstSpace(placement: DashboardPlacement, placed: readonly DashboardPlacement[], columns: number) {
  const rows = [0, ...new Set(placed.map((item) => item.y + item.height))].sort((a, b) => a - b);
  for (const y of rows) {
    for (let x = 0; x <= columns - placement.width; x++) {
      const candidate = { ...placement, x, y };
      if (!placed.some((item) => overlaps(item, candidate))) return candidate;
    }
  }
  return { ...placement, x: 0, y: rows.at(-1)! };
}

export function resolveDashboard(
  definitions: readonly DashboardWidgetDefinition[],
  columns: number,
  saved?: DashboardState | null
): DashboardState {
  const savedWidgets = new Map(saved?.widgets.map((widget) => [widget.id, widget]));
  const definitionsById = new Map(definitions.map((widget) => [widget.id, widget]));
  const restored: DashboardWidgetState[] = [];
  const fixed: DashboardWidgetState[] = [];
  const automatic: DashboardWidgetState[] = [];
  for (const definition of definitionsById.values()) {
    if (!definition.id) continue;
    const previous = savedWidgets.get(definition.id);
    const widget = {
      id: definition.id,
      visible: previous?.visible ?? !definition.initiallyHidden,
      placement: dashboardPlacement(definition, previous?.placement ?? definition.placement ?? {}, columns),
      settings: { ...(isJson(definition.defaultSettings, 0) ? definition.defaultSettings : {}), ...previous?.settings }
    };
    if (previous) restored.push(widget);
    else if (definition.placement?.x !== undefined || definition.placement?.y !== undefined) fixed.push(widget);
    else automatic.push(widget);
  }

  const placed: DashboardPlacement[] = [];
  const widgets: DashboardWidgetState[] = [];
  for (const widget of [...restored.sort(dashboardCompare), ...fixed.sort(dashboardCompare)]) {
    const placement = widget.visible ? belowBlockers(widget.placement, placed, columns) : widget.placement;
    if (widget.visible) placed.push(placement);
    widgets.push({ ...widget, placement });
  }
  for (const widget of automatic) {
    const placement = firstSpace(widget.placement, placed, columns);
    if (widget.visible) placed.push(placement);
    widgets.push({ ...widget, placement });
  }
  widgets.sort(dashboardCompare);
  return saved?.mobileOrder === undefined
    ? { version: 1, widgets }
    : { version: 1, widgets, mobileOrder: dashboardMobileOrder({ version: 1, widgets, mobileOrder: saved.mobileOrder }) };
}

export function dashboardMobileOrder(state: DashboardState) {
  const registered = new Set(state.widgets.map((widget) => widget.id));
  return [...new Set([...(state.mobileOrder ?? []).filter((id) => registered.has(id)), ...state.widgets.map((widget) => widget.id)])];
}

export function dashboardReorder(state: DashboardState, id: string, targetIndex: number): DashboardState {
  const order = dashboardMobileOrder(state);
  const visible = new Set(state.widgets.filter((widget) => widget.visible).map((widget) => widget.id));
  const visibleOrder = order.filter((item) => visible.has(item));
  const index = visibleOrder.indexOf(id);
  const target = bounded(targetIndex, index, 0, visibleOrder.length - 1);
  if (index < 0 || index === target) return state;
  visibleOrder.splice(index, 1);
  visibleOrder.splice(target, 0, id);
  let next = 0;
  return { ...state, mobileOrder: order.map((item) => visible.has(item) ? visibleOrder[next++] : item) };
}

export function dashboardUpdate(state: DashboardState, widget: DashboardWidgetState, columns: number): DashboardState {
  const previous = state.widgets.find(({ id }) => id === widget.id);
  if (!previous) return state;

  const others = state.widgets.filter(({ id }) => id !== widget.id);
  if (!widget.visible || !previous.visible) {
    const occupied = others.filter((item) => item.visible).map((item) => item.placement);
    const placement = widget.visible ? belowBlockers(widget.placement, occupied, columns) : widget.placement;
    return { ...state, widgets: [...others, { ...widget, placement }].sort(dashboardCompare) };
  }

  const placed = [widget.placement];
  const widgets = [widget];
  for (const other of others) {
    const placement = other.visible ? belowBlockers(other.placement, placed, columns) : other.placement;
    if (other.visible) placed.push(placement);
    widgets.push({ ...other, placement });
  }
  return { ...state, widgets: widgets.sort(dashboardCompare) };
}
