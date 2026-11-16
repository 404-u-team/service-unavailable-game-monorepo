import type { Point } from '../types';
import type { Rect } from './routing';

export type CanvasTools = {
  fit: () => void;
  place: () => Point;
  reveal: (point: Point) => void;
  revealNode: (id: string) => void;
  revealNodes: (ids: string[]) => void;
};

const gap = 16;

export function findPlacement(view: Rect, size: Pick<Rect, 'width' | 'height'>, obstacles: Rect[]): Point {
  const bound = (value: number) => Math.max(-100_000, Math.min(100_000, value));
  const center = { x: bound(view.x + (view.width - size.width) / 2), y: bound(view.y + (view.height - size.height) / 2) };
  const clear = ({ x, y }: Point) => obstacles.every((box) =>
    x + size.width + gap <= box.x || x >= box.x + box.width + gap ||
    y + size.height + gap <= box.y || y >= box.y + box.height + gap);
  const visible = ({ x, y }: Point) => x >= view.x && y >= view.y &&
    x + size.width <= view.x + view.width && y + size.height <= view.y + view.height;
  const xs = new Set([center.x, view.x, view.x + view.width - size.width]);
  const ys = new Set([center.y, view.y, view.y + view.height - size.height]);
  for (const box of obstacles) {
    xs.add(box.x - size.width - gap);
    xs.add(box.x + box.width + gap);
    ys.add(box.y - size.height - gap);
    ys.add(box.y + box.height + gap);
  }
  let best: Point | undefined;
  let bestScore = Infinity;
  const outsidePenalty = (view.width ** 2 + view.height ** 2) + 1;
  for (const x of xs) {
    for (const y of ys) {
      if (Math.abs(x) > 100_000 || Math.abs(y) > 100_000) continue;
      const point = { x, y };
      const score = (x - center.x) ** 2 + (y - center.y) ** 2 + (visible(point) ? 0 : outsidePenalty);
      if (score >= bestScore || !clear(point)) continue;
      best = point;
      bestScore = score;
    }
  }
  return best ?? center;
}
