import { expect, test } from 'bun:test';
import { applyFrame } from '../src/lib/live';
import type { Diagram, Game } from '../src/lib/types';
import { diagramPatch, mergeLayout } from '../src/lib/workbench/diagram';
import { findPlacement } from '../src/lib/workbench/placement';
import { spotlightBounds } from '../src/lib/workbench/spotlight';

test('new cards use the closest visible space around an occupied viewport center', () => {
  const view = { x: 5500, y: -3600, width: 620, height: 450 };
  const size = { width: 160, height: 100 };
  const center = { x: 5730, y: -3425 };
  expect(findPlacement(view, size, [])).toEqual(center);
  const position = findPlacement(view, size, [{ ...center, ...size }]);
  expect(position.x).toBe(center.x);
  expect(Math.abs(position.y - center.y)).toBe(116);
  expect(position.y).toBeGreaterThanOrEqual(view.y);
  expect(position.y + size.height).toBeLessThanOrEqual(view.y + view.height);
});

test('layout diffs contain only local changes, including undo and viewport changes', () => {
  const base: Diagram = { positions: { api: { x: 1, y: 2 } }, routes: {}, groups: [] };
  const next: Diagram = { ...base, positions: {}, viewports: { wide: { x: 1, y: 2, zoom: 0.5 } } };
  expect(diagramPatch(base, base)).toBeUndefined();
  expect(diagramPatch(base, next)).toEqual({ positions: { api: null }, routes: {}, viewports: next.viewports! });
  expect(mergeLayout({ ...base, positions: { ...base.positions, db: { x: 50, y: 30 } } }, base, next).positions)
    .toEqual({ db: { x: 50, y: 30 } });
});

test('live deltas preserve topology identity, append history, and reject gaps', () => {
  const first = { tick: 1 } as Game['history'][number];
  const second = { tick: 2 } as Game['history'][number];
  const initial = { tick: 1, production: { nodes: [], edges: [] }, history: [first], business_history: [], economy: { history: [] } } as unknown as Game;
  const snapshot = applyFrame(undefined, { type: 'snapshot', seq: 1, state: initial });
  const patch = { type: 'patch', seq: 2, changes: { tick: 2 }, histories: { history: { drop: 1, append: [second] } } } as const;
  const next = applyFrame(snapshot, { ...patch, histories: { history: { drop: 1, append: [second] } } });
  expect(next.state.history).toEqual([second]);
  expect(next.state.production).toBe(initial.production);
  expect(applyFrame(next, { ...patch, histories: {} })).toBe(next);
  expect(() => applyFrame(next, { ...patch, seq: 4, histories: {} })).toThrow();
});

test('the spotlight clamps to the viewport and hides fully off-screen targets', () => {
  expect(spotlightBounds({ left: -30, top: 18, right: 55, bottom: 120 }, 360, 100))
    .toEqual({ left: 0, top: 14, width: 59, height: 86 });
  expect(spotlightBounds({ left: 12, top: 101, right: 55, bottom: 120 }, 360, 100)).toBeUndefined();
});
