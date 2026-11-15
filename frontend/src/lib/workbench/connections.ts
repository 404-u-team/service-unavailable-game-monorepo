import type { Catalog, Connection, Kind, Topology } from '../types';

export const connectionLabels = {
  identity: 'Identity service calls',
  request: 'Application requests',
  queries: 'Read and write queries',
  reads: 'Read queries',
  cache: 'Cache lookups',
  enqueue: 'Queue submission',
  jobs: 'Background jobs',
  replication: 'Replication subscription',
  telemetry: 'Metrics collection'
};

type ConnectionKind = keyof typeof connectionLabels;
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
