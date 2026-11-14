import type { Diagram } from '../types';

function changes<T>(before: Record<string, T>, after: Record<string, T>): Record<string, T | null> {
  const result: Record<string, T | null> = {};
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) result[key] = after[key] ?? null;
  }
  return result;
}

export function diagramPatch(before: Diagram, after: Diagram) {
  const positions = changes(before.positions, after.positions);
  const routes = changes(before.routes, after.routes);
  const viewports = Object.fromEntries(Object.entries(after.viewports ?? {}).filter(([key, value]) =>
    JSON.stringify(value) !== JSON.stringify(before.viewports?.[key as 'compact' | 'wide'])));
  const groups = JSON.stringify(before.groups) === JSON.stringify(after.groups) ? undefined : after.groups;
  if (!Object.keys(positions).length && !Object.keys(routes).length && !Object.keys(viewports).length && !groups) return;
  return { positions, routes, viewports, ...(groups ? { groups, group_base: before.groups } : {}) };
}

export function mergeLayout(latest: Diagram, before: Diagram, after: Diagram): Diagram {
  const patch = diagramPatch(before, after);
  if (!patch) return latest;
  function merge<T>(values: Record<string, T>, updates: Record<string, T | null>) {
    const result = { ...values };
    for (const [key, value] of Object.entries(updates)) {
      if (value === null) delete result[key];
      else result[key] = value;
    }
    return result;
  }
  return {
    positions: merge(latest.positions, patch.positions),
    routes: merge(latest.routes, patch.routes),
    groups: patch.groups ?? latest.groups,
    viewports: { ...latest.viewports, ...patch.viewports }
  };
}
