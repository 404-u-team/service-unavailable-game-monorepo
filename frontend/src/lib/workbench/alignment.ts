import type { Point } from '../types';
import type { Rect } from './routing';

export function alignCard(card: Rect, neighbors: Rect[], tolerance: number) {
  const position: Point = { x: card.x, y: card.y };
  const guides: Partial<Point> = {};

  for (const [axis, dimension] of [['x', 'width'], ['y', 'height']] as const) {
    let distance = tolerance;
    for (const neighbor of neighbors) {
      for (const fraction of [0.5, 0, 1]) {
        const coordinate = neighbor[axis] + (neighbor[dimension] - card[dimension]) * fraction;
        const offset = Math.abs(coordinate - card[axis]);
        if (offset >= distance) continue;
        distance = offset;
        position[axis] = coordinate;
        guides[axis] = neighbor[axis] + neighbor[dimension] * fraction;
      }
    }
  }
  return { position, guides };
}
