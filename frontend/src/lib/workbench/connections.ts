import type { Catalog, Connection, Kind, Topology } from '../types';

export const connectionLabels = {
  identity: 'Identity service calls',
  request: 'Application requests',
  queries: 'Read and write queries',
  reads: 'Read queries',
  cache: 'Cache lookups',
  enqueue: 'Queue submission',
  jobs: 'Background jobs',
  objects: 'Attachment transfer',
  replication: 'Replication subscription',
  telemetry: 'Metrics collection'
};

export type ConnectionKind = keyof typeof connectionLabels;
export const connectionStyles = {
  application: { label: 'Application requests', color: '#c7f46c', dashed: false },
  data: { label: 'Data dependencies', color: '#5ed5c6', dashed: false },
  background: { label: 'Background jobs', color: '#ffd587', dashed: false },
  replication: { label: 'Replication subscription', color: '#d7aeed', dashed: true },
  monitoring: { label: 'Metrics collection', color: '#8cbdf3', dashed: true }
};

export type ConnectionCategory = keyof typeof connectionStyles;
const categories: Record<ConnectionKind, ConnectionCategory> = {
  request: 'application', identity: 'application', queries: 'data', reads: 'data', objects: 'data', cache: 'data',
  enqueue: 'background', jobs: 'background', replication: 'replication', telemetry: 'monitoring'
};

export function connectionCategory(kind: ConnectionKind) {
  return categories[kind];
}

export function connectionKind(catalog: Catalog, source?: Kind, target?: Kind): ConnectionKind {
  return source && target ? catalog.connection_types?.[source]?.[target] ?? 'request' : 'request';
}

export function connectionError(topology: Topology, catalog: Catalog, candidate: Connection, replaces = ''): string | undefined {
  const source = topology.nodes.find((node) => node.id === candidate.source);
  const target = topology.nodes.find((node) => node.id === candidate.target);
  if (!source || !target) return 'Choose two existing components.';
  if (source.id === target.id) return 'A component cannot connect to itself.';
  if (!catalog.connections[source.kind].includes(target.kind)) {
    if (source.kind === 'monitor') return 'Monitoring receives metrics from covered components.';
    if (target.kind === 'replica') return 'Read replicas accept application reads from API servers and caches.';
    return `${catalog.components[source.kind].name} cannot connect to ${catalog.components[target.kind].name}.`;
  }
  const remaining = topology.edges.filter((edge) => `${edge.source}:${edge.target}` !== replaces);
  if (remaining.some((edge) => edge.source === source.id && edge.target === target.id)) return 'A connection already exists between these components.';
  if (source.kind === 'api' && target.kind === 'api' &&
      (['Universal', 'Accounts'].includes(String(source.config.role ?? 'Universal')) || target.config.role !== 'Accounts')) {
    return 'Identity dependencies must connect a specialized service to an Accounts API.';
  }
  if (target.kind === 'object_storage' && !['Universal', 'Media'].includes(String(source.config.role ?? 'Universal'))) {
    return 'Connect Object Storage to a Universal or Media API.';
  }
  if (source.kind === 'replica' && target.kind === 'database' && remaining.some((edge) =>
    edge.source === source.id && topology.nodes.some((node) => node.id === edge.target && node.kind === 'database'))) {
    return 'A read replica can subscribe to one primary database.';
  }
  if (['telemetry', 'replication'].includes(connectionKind(catalog, source.kind, target.kind))) return;
  const kinds = new Map(topology.nodes.map((node) => [node.id, node.kind]));
  const reachable = new Set([target.id]);
  const queue = [target.id];
  for (const id of queue) {
    if (id === source.id) return 'Connections cannot form a cycle.';
    for (const edge of remaining) {
      if (edge.source === id && !reachable.has(edge.target) &&
          !['telemetry', 'replication'].includes(connectionKind(catalog, kinds.get(edge.source), kinds.get(edge.target)))) {
        reachable.add(edge.target);
        queue.push(edge.target);
      }
    }
  }
}
