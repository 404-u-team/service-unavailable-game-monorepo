import type { Kind } from '../types';

export const componentNotes: Record<Kind, [string, string, string]> = {
  source: ['The service always has one traffic source. Demand grows with audience, campaigns, and releases.', 'Start with a balancer or limiter when you need more control over incoming load.', 'A source with no path to an API and primary database cannot serve write requests.'],
  balancer: ['Requires an API target to deliver requests.', 'Use multiple API targets for redundancy. Weighted capacity directs more traffic to larger instances.', 'One target leaves the service vulnerable to a single API instance failure.'],
  api: ['Link a primary database for writes and persistent reads.', 'Add a cache for repeated reads, a read replica to offload the primary, or a queue for background work.', 'More API instances cannot resolve downstream database saturation.'],
  database: ['Receives writes from an API and reads from an API or cache.', 'Add memory for reads, CPU for query processing, or faster storage for I/O pressure.', 'An oversized connection pool admits more work but does not increase processing capacity.'],
  replica: ['Subscribe to one primary database. Connect the API or cache to the replica for reads.', 'Use a replica when repeated reads compete with writes on the primary.', 'Replica reads can trail recent primary writes. Every follower adds write overhead on the primary.'],
  cache: ['Connect an API to the cache and give the cache a database or replica to serve misses.', 'Use cache memory and TTL to retain frequently read data.', 'Writes still go directly to the primary database. A cache without a data connection cannot fill.'],
  limiter: ['Place the limiter between the traffic source and an API or balancer.', 'Use a limit and burst allowance to protect downstream capacity during demand spikes.', 'A low ceiling rejects valid requests even when the rest of the system has spare capacity.'],
  queue: ['Connect the API to the queue and link at least one worker.', 'Buffer work that can run after a request completes.', 'Increasing capacity delays overflow. Workers must still process jobs as fast as they arrive.'],
  worker: ['Workers receive background jobs from queues.', 'Scale CPU, concurrency, or instances if the queue backlog grows.', 'Workers cannot help overloaded APIs or a saturated database read path.'],
  monitor: ['Link a component to Monitoring to collect its resource metrics and diagnose its incidents.', 'Increase collection slots or add collectors for larger topologies. Service history reserves two slots.', 'Over-capacity links lose metrics. Collection does not consume application request capacity.']
};

export const fieldNotes: Record<string, string> = {
  instances: 'Each instance adds resources, redundancy, and the full daily instance cost.',
  cpu: 'Additional vCPUs process more work in parallel and raise daily cost. Database gains taper as disk limits are reached.',
  memory: 'RAM raises daily cost. It supports connections, keeps cache data resident, and improves database reads.',
  network: 'Maximum network throughput. Increase it for larger payloads when bandwidth is saturated.',
  connections: 'Limits simultaneous connections or connection work. Raising admission limits does not increase CPU or disk throughput.',
  concurrency: 'Parallel work per instance. Increase it only when the component has spare resources.',
  algorithm: 'Round robin splits requests evenly. Weighted capacity directs more requests to larger API targets.',
  health: 'Health checks skip failed API targets. Disabling checks can send requests to failed instances.',
  storage: 'How much data the database can store. Running out of space blocks writes.',
  disk: 'NVMe raises I/O capacity and adds 35% of the base daily cost.',
  ttl: 'How long the cache retains values. Longer retention can improve hit rate and leave values stale for longer.',
  policy: 'LRU keeps recently used items. LFU favors frequently used items.',
  scope: 'Select which operations this component handles. Other operations follow the normal path.',
  limit: 'Number of requests allowed during each window. Requests above the limit and burst allowance are rejected.',
  window: 'Time interval over which the limiter applies the request limit.',
  burst: 'Extra requests allowed above the normal limit during a short spike.',
  capacity: 'Maximum jobs held in the queue. A larger buffer costs more and takes longer to drain.',
  retention: 'Jobs older than this limit expire. Increase retention for workloads that tolerate delays.',
  slots: 'Maximum collection slots. Each component uses one slot, and service history reserves two.',
  detail: 'Service history unlocks metric trends and improves forecasts. It uses two slots and adds 20% of base daily cost.'
};
