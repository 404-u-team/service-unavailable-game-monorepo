import type { DiagramGroup } from '../types';

export function groupComponents(group: DiagramGroup, groups: DiagramGroup[]): string[] {
  const byId = new Map(groups.map((item) => [item.id, item]));
  const ids = [...group.members];
  const seen = new Set([group.id]);
  const components = new Set<string>();
  for (const id of ids) {
    if (seen.has(id)) continue;
    seen.add(id);
    const child = byId.get(id);
    if (child) ids.push(...child.members);
    else components.add(id);
  }
  return [...components];
}

export function nestedGroups(group: DiagramGroup, groups: DiagramGroup[]): Set<string> {
  const byId = new Map(groups.map((item) => [item.id, item]));
  const ids = [...group.members];
  const seen = new Set<string>();
  for (const id of ids) {
    const child = byId.get(id);
    if (!child || seen.has(id) || id === group.id) continue;
    seen.add(id);
    ids.push(...child.members);
  }
  return seen;
}

export function removeGroup(id: string, groups: DiagramGroup[]): DiagramGroup[] {
  const group = groups.find((item) => item.id === id);
  if (!group) return groups;
  return groups.filter((item) => item.id !== id)
    .map((item) => item.members.includes(id)
      ? { ...item, members: item.members.flatMap((member) => member === id ? group.members : [member]) }
      : item);
}
