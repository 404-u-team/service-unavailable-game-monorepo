import { expect, test } from 'bun:test';
import type { DashboardState } from '@service-unavailable/ui/dashboard';
import {
  applyDashboardLayout, applyDefaultDashboardLayout, parseDashboardLayoutFile, readDashboardLibrary,
  readGameDashboardLayout, serializeDashboardLayout, writeDashboardLibrary, writeGameDashboard, type DashboardLayout
} from '../src/lib/workbench/dashboard-layouts';

function store() {
  const items = new Map<string, string>();
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => { items.set(key, value); }
  };
}

const monitor: DashboardState = {
  version: 1,
  widgets: [{ id: 'traffic-history', visible: false, placement: { x: 2, y: 3, width: 5, height: 6 }, settings: { metric: 'error' } }],
  mobileOrder: ['traffic-history']
};
const growth: DashboardState = {
  version: 1,
  widgets: [{ id: 'audience', visible: true, placement: { x: 0, y: 4, width: 7, height: 8 }, settings: { hours: '6' } }]
};
const layout: DashboardLayout = { monitor, growth, finance: null };
const defaults: DashboardLayout = { monitor: null, growth: null, finance: null };

test('a dashboard layout file preserves all three boards and rejects invalid formats and incomplete or corrupt boards', () => {
  const text = serializeDashboardLayout({ name: 'Wide screen', layout });
  expect(parseDashboardLayoutFile(text)).toEqual({ name: 'Wide screen', layout });
  expect(parseDashboardLayoutFile('invalid')).toBeNull();
  expect(parseDashboardLayoutFile(text.replace('service-unavailable-dashboard-layout', 'game-save'))).toBeNull();
  expect(parseDashboardLayoutFile(JSON.stringify({ ...JSON.parse(text), version: 2 }))).toBeNull();
  expect(parseDashboardLayoutFile(JSON.stringify({ ...JSON.parse(text), layout: { monitor } }))).toBeNull();
  expect(parseDashboardLayoutFile(text.replace('"x": 2', '"x": -1'))).toBeNull();
});

test('existing board keys still work, importing replaces all boards and subsequent changes stay per board', () => {
  const storage = store();
  storage.setItem('service-unavailable:dashboard:game:monitor', JSON.stringify(monitor));
  expect(readGameDashboardLayout('game', storage)).toEqual({ ...defaults, monitor });
  applyDashboardLayout('game', { ...defaults, growth }, storage);
  expect(readGameDashboardLayout('game', storage)).toEqual({ ...defaults, growth });
  writeGameDashboard('game', 'monitor', monitor, storage);
  writeGameDashboard('game', 'finance', { version: 1, widgets: [] }, storage);
  expect(readGameDashboardLayout('game', storage)).toEqual({ ...layout, finance: { version: 1, widgets: [] } });
  applyDashboardLayout('game', defaults, storage);
  expect(readGameDashboardLayout('game', storage)).toEqual(defaults);
});

test('the default library layout is a copy for each new save and future changes do not update existing games', () => {
  const storage = store();
  writeGameDashboard('existing', 'growth', growth, storage);
  writeDashboardLibrary({ defaultId: 'wide', presets: [{ id: 'wide', name: 'Wide screen', layout }] }, storage);
  expect(readDashboardLibrary(storage).defaultId).toBe('wide');
  applyDefaultDashboardLayout('new', storage);
  expect(readGameDashboardLayout('new', storage)).toEqual(layout);
  expect(readGameDashboardLayout('existing', storage)).toEqual({ ...defaults, growth });
  writeDashboardLibrary({ defaultId: null, presets: [] }, storage);
  applyDefaultDashboardLayout('later', storage);
  expect(readGameDashboardLayout('new', storage)).toEqual(layout);
  expect(readGameDashboardLayout('later', storage)).toEqual(defaults);
});
