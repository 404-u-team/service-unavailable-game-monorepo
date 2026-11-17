import type { DiagramGroup } from '../types';

export const maxDiagramGroups = 80;
export const maxGroupMembers = 80;

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
      ? { ...item, members: item.members.flatMap((member) => member === id
        ? group.members.slice(0, maxGroupMembers - item.members.length + 1) : [member]) }
      : item);
}

export function putGroup(groups: DiagramGroup[], group: DiagramGroup, parent: string): DiagramGroup[] {
  const members = new Set(group.members);
  const next = groups.map((item) => item.id === group.id ? group : {
    ...item,
    members: [
      ...item.members.filter((id) => id !== group.id && !members.has(id)),
      ...(item.id === parent ? [group.id] : [])
    ]
  });
  if (!groups.some((item) => item.id === group.id)) next.push(group);
  return dropEmptyGroups(next);
}

export function detachMember(groups: DiagramGroup[], id: string): DiagramGroup[] {
  return dropEmptyGroups(groups.map((item) => item.members.includes(id)
    ? { ...item, members: item.members.filter((member) => member !== id) }
    : item));
}

function dropEmptyGroups(groups: DiagramGroup[]): DiagramGroup[] {
  let remaining = groups;
  let empty = new Set(remaining.filter((item) => !item.members.length).map((item) => item.id));
  while (empty.size) {
    remaining = remaining.filter((item) => !empty.has(item.id))
      .map((item) => ({ ...item, members: item.members.filter((id) => !empty.has(id)) }));
    empty = new Set(remaining.filter((item) => !item.members.length).map((item) => item.id));
  }
  return remaining;
}
