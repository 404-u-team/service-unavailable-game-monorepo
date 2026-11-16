import { parseDashboardState, type DashboardState } from '@service-unavailable/ui/dashboard';

const dashboardSections = ['monitor', 'growth', 'finance'] as const;
export type DashboardSection = typeof dashboardSections[number];
export type DashboardLayout = Record<DashboardSection, DashboardState | null>;
type Preset = { id: string; name: string; layout: DashboardLayout };
export type DashboardLayoutLibrary = { defaultId: string | null; presets: Preset[] };
type LayoutFile = { name: string; layout: DashboardLayout };
type Store = Pick<Storage, 'getItem' | 'setItem'>;

const format = 'service-unavailable-dashboard-layout';
const libraryKey = 'service-unavailable:dashboard-presets';
export const dashboardLayoutNameLength = 60;
export const maxDashboardLayoutBytes = 512 * 1024;

function record(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, unknown>;
}

function parse(text: string | null): unknown {
  try { return text === null ? null : JSON.parse(text); } catch { return null; }
}

function nameOf(value: unknown) {
  if (typeof value !== 'string') return;
  const name = value.trim();
  if (name && name.length <= dashboardLayoutNameLength) return name;
}

function parseLayout(input: unknown): DashboardLayout | null {
  const data = record(input);
  if (!data) return null;
  const layout: DashboardLayout = { monitor: null, growth: null, finance: null };
  for (const section of dashboardSections) {
    if (data[section] === null) continue;
    const board = record(data[section]);
    if (!board || !Array.isArray(board.widgets) || board.widgets.length > 64
      || (Array.isArray(board.mobileOrder) && board.mobileOrder.length > 128)) return null;
    const valid = parseDashboardState(board);
    if (!valid) return null;
    layout[section] = valid;
  }
  return layout;
}

export function parseDashboardLayoutFile(text: string): LayoutFile | null {
  const data = record(parse(text));
  if (data?.format !== format || data.version !== 1) return null;
  const name = nameOf(data.name);
  const layout = parseLayout(data.layout);
  return name && layout ? { name, layout } : null;
}

export function serializeDashboardLayout({ name, layout }: LayoutFile) {
  return JSON.stringify({ format, version: 1, name, layout }, null, 2);
}

export function readDashboardLibrary(storage: Store = localStorage): DashboardLayoutLibrary {
  const data = record(parse(storage.getItem(libraryKey)));
  const presets: Preset[] = [];
  if (data?.version === 1 && Array.isArray(data.presets)) {
    const seen = new Set<string>();
    for (const item of data.presets) {
      const preset = record(item);
      if (!preset || typeof preset.id !== 'string' || !preset.id || seen.has(preset.id)) continue;
      const name = nameOf(preset.name);
      const layout = parseLayout(preset.layout);
      if (!name || !layout) continue;
      seen.add(preset.id);
      presets.push({ id: preset.id, name, layout });
    }
  }
  return { presets, defaultId: presets.find(({ id }) => id === data?.defaultId)?.id ?? null };
}

export function writeDashboardLibrary(library: DashboardLayoutLibrary, storage: Store = localStorage) {
  storage.setItem(libraryKey, JSON.stringify({ version: 1, ...library }));
}

export function isDashboardLibraryChange(key: string | null) {
  return key === null || key === libraryKey;
}

function gameLayoutKey(gameId: string) {
  return `service-unavailable:dashboard:${gameId}`;
}

function readBase(gameId: string, storage: Store) {
  const data = record(parse(storage.getItem(gameLayoutKey(gameId))));
  if (typeof data?.revision !== 'string') return null;
  const layout = parseLayout(data.layout);
  return layout ? { revision: data.revision, layout } : null;
}

export function isGameDashboardChange(gameId: string, section: DashboardSection, key: string | null) {
  const base = gameLayoutKey(gameId);
  return key === null || key === base || key === `${base}:${section}`;
}

export function readGameDashboardLayout(gameId: string, storage: Store = localStorage): DashboardLayout {
  const base = readBase(gameId, storage);
  const key = gameLayoutKey(gameId);
  function read(section: DashboardSection) {
    const value = parse(storage.getItem(`${key}:${section}`));
    if (!base) return parseDashboardState(value);
    const override = record(value);
    return (override?.revision === base.revision ? parseDashboardState(override.snapshot) : null) ?? base.layout[section];
  }
  return { monitor: read('monitor'), growth: read('growth'), finance: read('finance') };
}

// Replacing the base switches all three dashboards at once and invalidates edits to the previous layout.
export function applyDashboardLayout(gameId: string, layout: DashboardLayout, storage: Store = localStorage) {
  storage.setItem(gameLayoutKey(gameId), JSON.stringify({ revision: crypto.randomUUID(), layout }));
}

export function writeGameDashboard(gameId: string, section: DashboardSection, snapshot: DashboardState, storage: Store = localStorage) {
  const base = readBase(gameId, storage);
  storage.setItem(`${gameLayoutKey(gameId)}:${section}`, JSON.stringify(base ? { revision: base.revision, snapshot } : snapshot));
}

export function applyDefaultDashboardLayout(gameId: string, storage: Store = localStorage) {
  const { defaultId, presets } = readDashboardLibrary(storage);
  const preset = presets.find(({ id }) => id === defaultId);
  if (preset && !readBase(gameId, storage)) applyDashboardLayout(gameId, preset.layout, storage);
}
