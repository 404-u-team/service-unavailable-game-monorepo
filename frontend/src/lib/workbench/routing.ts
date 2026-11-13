import type { Point } from '../types';

export type Rect = { x: number; y: number; width: number; height: number };
type Segment = [Point, Point];
const padding = 10;
const bendCost = 24;

export function segments(points: Point[]): Segment[] {
  return points.slice(1).map((point, index) => [points[index], point]);
}

function equal(a: Point, b: Point) { return a.x === b.x && a.y === b.y; }

function simplify(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const p of points) {
    const b = result.at(-1);
    const a = result.at(-2);
    if (b && equal(b, p)) continue;
    if (a && b && ((a.x === p.x && b.x === p.x) || (a.y === p.y && b.y === p.y))) {
      result[result.length - 1] = p;
    } else result.push(p);
  }
  return result;
}

function intersects(a: Point, b: Point, r: Rect) {
  return a.x === b.x
    ? a.x > r.x && a.x < r.x + r.width && Math.min(a.y, b.y) < r.y + r.height && Math.max(a.y, b.y) > r.y
    : a.y > r.y && a.y < r.y + r.height && Math.min(a.x, b.x) < r.x + r.width && Math.max(a.x, b.x) > r.x;
}

type Step = { x: number; y: number; axis: number; cost: number; score: number; parent?: Step };
class Queue {
  private items: Step[] = [];

  push(item: Step) {
    let index = this.items.length;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      if (this.items[parent].score <= item.score) break;
      this.items[index] = this.items[parent];
      index = parent;
    }
    this.items[index] = item;
  }

  pop() {
    const first = this.items[0];
    const last = this.items.pop();
    if (!this.items.length || !last) return first;
    let index = 0;
    while (index * 2 + 1 < this.items.length) {
      let child = index * 2 + 1;
      if (this.items[child + 1]?.score < this.items[child].score) child++;
      if (last.score <= this.items[child].score) break;
      this.items[index] = this.items[child];
      index = child;
    }
    this.items[index] = last;
    return first;
  }
}

function occupiedLanes(segments: Segment[]) {
  const horizontal = new Map<number, [number, number][]>();
  const vertical = new Map<number, [number, number][]>();
  for (const [a, b] of segments) {
    const alongX = a.y === b.y;
    const lanes = alongX ? horizontal : vertical;
    const key = alongX ? a.y : a.x;
    const start = alongX ? a.x : a.y;
    const end = alongX ? b.x : b.y;
    const entries = lanes.get(key) ?? [];
    entries.push([Math.min(start, end), Math.max(start, end)]);
    lanes.set(key, entries);
  }
  return { horizontal, vertical };
}

function overlapCost(a: Point, b: Point, occupied: ReturnType<typeof occupiedLanes>): number {
  const horizontal = a.y === b.y;
  const entries = horizontal ? occupied.horizontal.get(a.y) : occupied.vertical.get(a.x);
  if (!entries) return 0;
  const start = horizontal ? a.x : a.y;
  const end = horizontal ? b.x : b.y;
  const low = Math.min(start, end);
  const high = Math.max(start, end);
  return entries.reduce((sum, [left, right]) => sum + Math.max(0, Math.min(high, right) - Math.max(low, left)), 0) * .65;
}

function elbow(a: Point, b: Point): Point[] {
  return [a, { x: b.x, y: a.y }, b];
}

function routeLeg(start: Point, end: Point, obstacles: Rect[], occupied: ReturnType<typeof occupiedLanes>, lane: number): Point[] {
  if (equal(start, end)) return [start];
  // A waypoint placed inside a card remains editable.
  const containing = (p: Point, r: Rect) => p.x > r.x && p.x < r.x + r.width && p.y > r.y && p.y < r.y + r.height;
  const walls = obstacles.filter((r) => !containing(start, r) && !containing(end, r));
  const midpoint = (start.x + end.x) / 2 + lane;
  const x = [...new Set([start.x, end.x, midpoint, ...walls.flatMap((r) => [r.x, r.x + r.width])])].sort((a, b) => a - b);
  const y = [...new Set([start.y, end.y, (start.y + end.y) / 2 + lane, ...walls.flatMap((r) => [r.y, r.y + r.height])])].sort((a, b) => a - b);
  const queue = new Queue();
  const distance = (p: Point) => Math.abs(end.x - p.x) + Math.abs(end.y - p.y);
  const key = (ix: number, iy: number, axis: number) => (iy * x.length + ix) * 3 + axis;
  const best = new Map<number, number>();
  const passages = new Map<number, boolean>();
  const directions = [[1, 0], [-1, 0], [0, 1], [0, -1]] as const;
  const first = { x: x.indexOf(start.x), y: y.indexOf(start.y), axis: 0, cost: 0, score: distance(start) };
  queue.push(first);
  best.set(key(first.x, first.y, 0), 0);
  for (let step = queue.pop(); step; step = queue.pop()) {
    if (best.get(key(step.x, step.y, step.axis)) !== step.cost) continue;
    const a = { x: x[step.x], y: y[step.y] };
    if (equal(a, end)) {
      const path = [end];
      for (let prev = step.parent; prev; prev = prev.parent) path.push({ x: x[prev.x], y: y[prev.y] });
      return path.reverse();
    }
    for (const [dx, dy] of directions) {
      const ix = step.x + dx;
      const iy = step.y + dy;
      if (x[ix] === undefined || y[iy] === undefined) continue;
      const b = { x: x[ix], y: y[iy] };
      const axis = dx ? 1 : 2;
      const passage = key(Math.min(step.x, ix), Math.min(step.y, iy), axis);
      if (!passages.has(passage)) passages.set(passage, !walls.some((r) => intersects(a, b, r)));
      if (!passages.get(passage)) continue;
      const bend = step.axis && step.axis !== axis ? bendCost + (axis === 2 ? Math.abs(a.x - midpoint) * .015 : 0) : 0;
      const cost = step.cost + Math.abs(a.x - b.x) + Math.abs(a.y - b.y) + bend + overlapCost(a, b, occupied);
      const id = key(ix, iy, axis);
      if (cost >= (best.get(id) ?? Infinity)) continue;
      best.set(id, cost);
      queue.push({ x: ix, y: iy, axis, cost, score: cost + distance(b), parent: step });
    }
  }
  return elbow(start, end);
}

export function routeConnection(start: Point, end: Point, boxes: Rect[], waypoints: Point[] = [], occupied: Segment[] = [], lane = 0) {
  const obstacles = boxes.map((r) => ({ x: r.x - padding, y: r.y - padding, width: r.width + padding * 2, height: r.height + padding * 2 }));
  const offset = padding + 6;
  const stops = [{ x: start.x + offset, y: start.y }, ...waypoints, { x: end.x - offset, y: end.y }];
  const lanes = occupiedLanes(occupied);
  return simplify([start, ...segments(stops).flatMap(([a, b]) => routeLeg(a, b, obstacles, lanes, lane)), end]);
}

export function labelPosition(points: Point[], width: number, boxes: Rect[], labels: Rect[]): Point | undefined {
  const ordered = segments(points).slice(1, -1).sort(([a, b], [c, d]) =>
    Math.hypot(d.x - c.x, d.y - c.y) - Math.hypot(b.x - a.x, b.y - a.y));
  for (const [a, b] of ordered.length ? ordered : segments(points)) {
    if (Math.hypot(b.x - a.x, b.y - a.y) < 30) continue;
    for (const fraction of [.5, .32, .68]) {
      const center = { x: a.x + (b.x - a.x) * fraction, y: a.y + (b.y - a.y) * fraction };
      for (const side of [-1, 1]) {
        const p = a.y === b.y ? { x: center.x, y: center.y + 12 * side } : { x: center.x + (width / 2 + 5) * side, y: center.y };
        const r = { x: p.x - width / 2, y: p.y - 8, width, height: 16 };
        if ([...boxes, ...labels].some((box) => r.x < box.x + box.width + 4 && r.x + r.width + 4 > box.x &&
              r.y < box.y + box.height + 4 && r.y + r.height + 4 > box.y)) continue;
        labels.push(r);
        return p;
      }
    }
  }
}
