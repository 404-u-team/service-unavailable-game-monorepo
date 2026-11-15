export type ChartSeries = {
  id: string;
  label: string;
  values: readonly (number | null)[];
};

export function chartValue(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function chartDomain(series: readonly ChartSeries[], count: number, includeZero: boolean) {
  let min = Infinity;
  let max = -Infinity;
  for (const { values } of series) {
    for (let index = 0; index < Math.min(count, values.length); index++) {
      const value = chartValue(values[index]);
      if (value === null) continue;
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  }
  if (min === Infinity) return;
  if (includeZero) {
    min = Math.min(0, min);
    max = Math.max(0, max);
    return max === min ? { min: 0, max: 1 } : { min, max };
  }
  const padding = max === min ? Math.max(Math.abs(max) * 0.08, 0.1) : (max - min) * 0.08;
  return { min: min >= 0 ? Math.max(0, min - padding) : min - padding, max: max + padding };
}

export function lineSegments(values: readonly (number | null)[], count: number, x: (index: number) => number, y: (value: number) => number) {
  const segments: { x: number; y: number }[][] = [];
  let segment: { x: number; y: number }[] = [];
  for (let index = 0; index < Math.min(count, values.length); index++) {
    const value = chartValue(values[index]);
    if (value === null) {
      segment = [];
    } else {
      if (!segment.length) segments.push(segment);
      segment.push({ x: x(index), y: y(value) });
    }
  }
  return segments;
}
