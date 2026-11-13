import { expect, test } from 'bun:test';
import { labelPosition, routeConnection, segments } from '../src/lib/workbench/routing';

test('orthogonal routes avoid unrelated cards and keep waypoints', () => {
  const block = { x: 90, y: 5, width: 130, height: 90 };
  const from = { x: 40, y: 50 };
  const to = { x: 290, y: 50 };
  const auto = routeConnection(from, to, [block]);
  expect(auto[0]).toEqual(from);
  expect(auto.at(-1)).toEqual(to);
  for (const [a, b] of segments(auto)) {
    expect(a.x === b.x || a.y === b.y).toBe(true);
    if (a.y === b.y && a.y > block.y && a.y < block.y + block.height) {
      expect(Math.max(a.x, b.x) <= block.x || Math.min(a.x, b.x) >= block.x + block.width).toBe(true);
    }
    if (a.x === b.x && a.x > block.x && a.x < block.x + block.width) {
      expect(Math.max(a.y, b.y) <= block.y || Math.min(a.y, b.y) >= block.y + block.height).toBe(true);
    }
  }
  const waypoint = { x: 160, y: 140 };
  const manual = routeConnection(from, to, [block], [waypoint]);
  expect(segments(manual).some(([a, b]) =>
    (a.x === b.x && a.x === waypoint.x && Math.min(a.y, b.y) <= waypoint.y && Math.max(a.y, b.y) >= waypoint.y) ||
    (a.y === b.y && a.y === waypoint.y && Math.min(a.x, b.x) <= waypoint.x && Math.max(a.x, b.x) >= waypoint.x))).toBe(true);
  const labels: Parameters<typeof labelPosition>[3] = [];
  expect(labelPosition(auto, 42, [block], labels)).toBeDefined();
  expect(labelPosition(auto, 42, [block], labels)).not.toEqual(labelPosition(manual, 42, [block], labels));
});
