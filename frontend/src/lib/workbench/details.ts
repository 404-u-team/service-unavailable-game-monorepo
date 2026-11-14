import type { Kind } from '../types';

export const componentNotes: Record<Kind, [string, string, string]> = {
  source: ['The service always has one traffic source. Demand grows with audience, campaigns, and releases.', 'Start with a balancer or limiter when you need more control over incoming load.', 'A source with no path to an API and primary database cannot serve write requests.'],
  balancer: ['Requires an API target to deliver requests.', 'Use multiple API targets for redundancy. Weighted capacity directs more traffic to larger instances.', 'One target leaves the service vulnerable to a single API instance failure.'],
  api: ['Link a primary database for writes and persistent reads.', 'Add a cache for repeated reads, a read replica to offload the primary, or a queue for background work.', 'More API instances cannot resolve downstream database saturation.'],
  database: ['Receives writes from an API and reads from an API or cache.', 'Add memory for reads, CPU for query processing, or faster storage for I/O pressure.', 'An oversized connection pool admits more work but does not increase processing capacity.'],
  replica: ['Subscribe to one primary database. Connect the API or cache to the replica for reads.', 'Use a replica when ordinary reads compete with writes on the primary.', 'Replica reads can trail recent primary writes. Every follower adds write overhead on the primary.'],
  cache: ['Keep a direct API-to-primary connection for writes. Add API-to-cache for read lookups.', 'On a miss, the cache uses its own database or replica links first. With no such links, the API uses its direct data connections.', 'Use cache memory and TTL to retain frequently read data.'],
  limiter: ['Place the limiter between the traffic source and an API or balancer.', 'Use a limit and burst allowance to protect downstream capacity during demand spikes.', 'A low ceiling rejects valid requests even when the rest of the system has spare capacity.'],
  queue: ['Connect API → Queue → Worker to run work such as message notifications or image thumbnails after the API responds.', 'The queue absorbs bursts while workers catch up. The backlog grows when jobs arrive faster than workers can process them.', 'A full queue rejects new jobs. Retention limits how much old work survives each simulation step.'],
  worker: ['Workers consume jobs from connected queues. For example, a worker can transcode an uploaded voice message.', 'Throughput is limited by CPU, RAM and concurrent jobs per instance. Add instances or increase the resource at its limit.', 'Extra workers help when processing limits the queue. They cannot speed up database writes or make a disconnected queue receive jobs.'],
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
  disk: 'NVMe and NVMe array raise the shared disk I/O budget and daily cost.',
  ttl: 'How long the cache retains values. Longer retention can improve hit rate and leave values stale for longer.',
  policy: 'LRU keeps recently used items. LFU favors frequently used items.',
  scope: 'Select which operations this component handles. Other operations follow the normal path.',
  limit: 'Number of requests allowed during each window. Requests above the limit and burst allowance are rejected.',
  window: 'Time interval over which the limiter applies the request limit.',
  burst: 'Extra requests allowed above the normal limit during a short spike.',
  capacity: 'Maximum jobs held in the queue. A larger buffer costs more and takes longer to drain.',
  retention: 'Longer retention reduces the share of waiting jobs that expires each step.',
  slots: 'Maximum collection slots. Each component uses one slot, and service history reserves two.',
  detail: 'Service history unlocks metric trends and improves forecasts. It uses two slots and adds 20% of base daily cost.',
  search_index: 'Indexed search uses 65% fewer read units. Maintaining the index adds 20% write work.'
};
