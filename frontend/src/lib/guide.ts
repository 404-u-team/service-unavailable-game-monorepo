import type { Catalog, Kind } from './types';
import { engineeringArticles } from './engineering-guide';
import { componentNotes } from './workbench/details';

export const categories = {
  start: 'Getting started',
  components: 'Infrastructure components',
  architecture: 'System architecture',
  business: 'Product and business',
  interface: 'Game interface'
} as const;

export type Category = keyof typeof categories;
export type GuideSection = { id: string; title: string; body?: string[]; diagram?: string };
export type Article = {
  category: Category; title: string; sections: GuideSection[]; related: string[]; kind?: Kind;
};

function component(kind: Kind, title: string, use: string, impact: string, example: string, related: string[]): Article {
  return {
    category: 'components', kind, title, related,
    sections: [
      { id: 'overview', title: 'What it does' },
      { id: 'use', title: 'When to use it', body: [use] },
      { id: 'connections', title: 'How to connect it', body: [componentNotes[kind][0]] },
      { id: 'configuration', title: 'Configuration' },
      { id: 'simulation', title: 'Simulation and costs', body: [impact] },
      { id: 'mistakes', title: 'Common mistakes', body: [componentNotes[kind][2]] },
      { id: 'example', title: 'Messenger example', body: [example] }
    ]
  };
}

export const componentArticles: Record<Kind, Article> = {
  source: component("source", "Traffic source",
    "Available from the start. Use its request breakdown to check how a release or campaign changes demand.",
    "Audience, local time, enabled features and campaigns change the operation mix. The source is fixed and has no hardware settings or operating cost.",
    "When launching group chats, select Group messages in the traffic filter to follow the new requests to Messenger API.",
    ["game-time", "campaigns"]),
  balancer: component("balancer", "Load balancer",
    "Use a balancer when Messenger needs several API targets or health-based routing. Connect the source or a limiter to the balancer, then connect the balancer to each API.",
    "Round robin splits requests evenly. Weighted capacity favors larger API pools. Health checks skip unavailable pools. Network bandwidth and connection work can saturate the balancer itself.",
    "Connect two Messenger APIs to the same primary. With health checks enabled, run a failure drill and inspect how traffic and latency change.",
    ["routing", "availability"]),
  api: component("api", "API server",
    "Use an API to process Messenger requests. Connect incoming traffic from the source, balancer or limiter and link one primary for persistent data.",
    "Each instance adds CPU, RAM, network, connections and concurrency. A pool survives individual failures if enough instances remain. Every instance adds its full operating cost.",
    "If CPU is saturated while sending messages, preview a larger instance or an extra instance. Check the primary separately for new pressure.",
    ["routing", "database", "scaling"]),
  limiter: component("limiter", "Rate limiter",
    "Use a limiter to protect downstream resources from bursts. Put it between the source and a balancer or API.",
    "The admitted rate for the selected scope is (limit + burst) divided by window seconds. Excess requests fail at the limiter. It has a fixed daily cost.",
    "Select Writes during a Messenger spike to protect history reads. Watch rejected requests and availability while you upgrade the primary.",
    ["bottlenecks", "routing"]),
  database: component("database", "Primary database",
    "Use one primary per Messenger dataset. It handles all application writes, reads bundled with writes, and search that requires an index. It can also serve ordinary reads.",
    "CPU sets processing capacity. RAM improves reads and memory headroom. The disk tier sets I/O speed, while storage in GB sets free space. The search index cuts search read work by 65% and adds 20% CPU and disk work per write. Hardware adds daily cost.",
    "Keep Messenger API → Primary database when adding a cache or replica. Compare write demand and sustainable writes after deployment.",
    ["database-io", "read-write-throughput", "database-scaling"]),
  replica: component("replica", "Read replica",
    "Use a replica when ordinary reads compete with writes or when cache misses still overload the primary. The replica serves eligible reads for one dataset.",
    "A replica uses its own CPU, RAM, pool and disk for reads and replay. Its base latency is 21 ms. Every available follower adds disk work on the primary and has its own operating cost.",
    "Keep API → Primary database. Add Replica → Primary database, then add API → Replica or Cache → Replica for reads. Link both databases to Monitoring and check lag after deployment.",
    ["replication", "database-scaling"]),
  cache: component("cache", "Cache",
    "Use a cache for repeated history and conversation reads. Keep API → Primary for writes. Link API → Cache and optionally Cache → Primary or Cache → Replica for misses.",
    "Hits finish at the cache with a 4 ms base latency. More RAM relative to audience, longer TTL and LFU can improve hit rate, up to 91%. RAM also raises cache throughput and cost.",
    "Start with History only for repeat chat history reads. Compare the hit rate and primary read demand before widening the scope to All reads.",
    ["routing", "database-scaling"]),
  queue: component("queue", "Queue",
    "Use a queue to absorb bursts of Messenger notifications or media jobs. Connect API → Queue → Worker.",
    "Capacity limits waiting jobs. Retention controls how much backlog expires each step. Larger buffers cost more, while worker throughput determines how fast the backlog clears.",
    "At 30 notification jobs/s and 20 jobs/s of worker capacity, roughly 10 jobs/s accumulate before expiration or overflow. Add processing capacity for sustained load.",
    ["async-processing", "worker"]),
  worker: component("worker", "Worker",
    "Use workers to drain queues. Connect Queue → Worker for notifications or media processing.",
    "Per-instance throughput is the smallest of 10 jobs/s per vCPU, 10 jobs/s per GB of RAM and 3 jobs/s per concurrency slot. A worker shares capacity across connected reachable queues. Each instance adds its full daily cost.",
    "For voice messages, connect the queue and watch estimated wait. If CPU is the smallest limit, add CPU or another worker instance.",
    ["async-processing", "queue"]),
  monitor: component("monitor", "Monitoring",
    "Use monitoring to diagnose hardware pressure and follow capacity over time. Connect each observed component → Monitoring and deploy.",
    "Each linked component needs one slot. Service history reserves two slots and adds 20% of base daily cost. Links beyond capacity lose coverage.",
    "Link Messenger API and Primary database, enable Service history, then use Telemetry to compare service errors with node pressure.",
    ["monitoring-setup", "monitoring-charts"]),
};

export const articles: Record<string, Article> = {
  ...engineeringArticles,
  "game-basics": { category: "start", title: "Game basics",
    sections: [
      { id: "messenger", title: "Messenger", body: ["Run a messaging service. Traffic includes sending messages, reading history, listing conversations, authenticating and keeping connections open. The starting topology already serves text messaging."] },
      { id: "first-deployment", title: "First deployment", body: ["Inspect Messenger API and its primary database. Add Monitoring in a draft, connect both nodes to it, review and deploy. Open Telemetry to see where the service spends its capacity."], diagram: "Traffic source → Load balancer → API server → Primary database" }
    ],
    related: ["game-time", "deployment", "monitoring-setup"]
  },
  "game-time": { category: "start", title: "Simulation time",
    sections: [
      { id: "clock", title: "Game clock", body: ["Each step advances ten game minutes. Use the speed controls to pause while you plan. Audience, bills, revenue, development and market projects advance with the clock."] },
      { id: "traffic", title: "Daily traffic patterns", body: ["Regional demand varies with local time and weekends. Compare ordinary peaks with campaign or incident spikes in the traffic charts."] }
    ],
    related: ["regions", "monitoring-charts"]
  },
  "deployment": { category: "start", title: "Drafts, deployment and rollback",
    sections: [
      { id: "drafts", title: "Drafts", body: ["Draft changes are isolated from production. Review warnings, operating cost, installation cost and estimated capacity before deploying. Saving configuration edits updates the draft."] },
      { id: "rollback", title: "Rollback", body: ["Open deployment history in Events to restore an earlier topology. Rollback restores infrastructure configuration. Time, audience and finances continue from the current game state."] }
    ],
    related: ["topology-editing", "bottlenecks"]
  },
  "monitoring-setup": { category: "start", title: "Monitoring setup",
    sections: [
      { id: "links", title: "Connect a collector", body: ["Add a Monitoring node in a draft. Draw outgoing telemetry links from Messenger API and the primary to the collector. Deploy the draft to see their metrics."] },
      { id: "coverage", title: "Coverage and history", body: ["Check the coverage list for dropped links. Choose Service history and leave two slots for history to populate resource charts over subsequent steps."] }
    ],
    related: ["monitor", "monitoring-charts", "bottlenecks"]
  },
  ...componentArticles,
  "routing": { category: "architecture", title: "Request routing and connection types",
    sections: [
      { id: "types", title: "Connection types", body: ["Solid request edges carry operations from the source through limiters and balancers to APIs. Data edges carry queries. Enqueue and worker edges carry background jobs. Replication subscribes a replica to a primary. Telemetry carries measurements."] },
      { id: "data", title: "Data routing", body: ["The API splits eligible reads evenly between its linked primary and linked replicas that follow that primary. Failed replicas are skipped. If caches are attached, they receive ordinary reads first. Cache misses use the cache’s eligible data links, or the originating API’s links when the cache has none eligible. A saturated target keeps its share of the load."] },
      { id: "dataset", title: "Datasets and primaries", body: ["Messenger deployment requires the same primary for every API that serves traffic. Connect both APIs behind a load balancer to one primary, and add replicas that follow that primary for eligible reads.", "Separate services can own separate datasets when routing assigns requests to the correct service. Sharding requires explicit partitioning and routing. Messenger has a single application dataset."] },
      { id: "cache-misses", title: "Cache hits and misses", body: ["The hit estimate improves with memory relative to the audience, longer TTL and LFU. TTL represents how long a cached value can be reused. There is no per-message invalidation or write-through. The simulator estimates hit rate without tracking cached values or stale responses."] }
    ],
    related: ["cache", "replication", "async-processing"]
  },
  "scaling": { category: "architecture", title: "Scaling",
    sections: [
      { id: "instances", title: "Resources and instances", body: ["Scale vertically to add resources to one instance or horizontally to add instances. Shared databases still receive the requests handled by all API instances. Check reads and writes independently when evaluating a database bottleneck.", "Instances within a node share size, settings and connections. Separate nodes can use different presets and links, and have separate metrics, costs and incident targets.", "Managed replacement costs 30% of the API base price per instance and roughly halves the duration of random hardware failures. It leaves the chance of failure unchanged. Extra instances and balancer health checks help the service keep serving traffic during an outage."] },
      { id: "preview", title: "Compare upgrades", body: ["Find the pressured resource in the inspector. Preview a configuration change and compare the estimated range and daily cost before applying it to the draft."] }
    ],
    related: ["api", "database-scaling", "bottlenecks"]
  },
  "database-io": { category: "architecture", title: "Database disk I/O",
    sections: [
      { id: "io", title: "Disk I/O utilization", body: ["Disk I/O is a shared budget. Add read demand divided by the read budget and write demand divided by the write budget, including index and replication overhead. SSD budgets are 420 reads/s or 115 writes/s in weighted units. NVMe gives 609 or 166.75. NVMe array gives 1,890 or 517.5.", "Combined disk load above 100% throttles requests. NVMe adds 35% of base daily cost. NVMe array adds 240%. Every available follower adds 8% of base disk work per primary write.", "Modeled IOPS use a read unit as the reference. A write uses the ratio of read to write budgets, multiplied by the index and replica overhead for its workload. Dividing the combined work by effective disk capacity gives the Disk I/O meter."] },
      { id: "space", title: "Storage types and space", body: ["SSD and NVMe set the I/O budget. Storage (GB) sets the volume available for persistent data. Messenger images, voice messages and files consume more space than texts. Media quality affects bytes stored.", "When a data volume fills up, writes are limited and reads can continue. Add GB or reduce media quality to conserve space. NVMe alone leaves free space unchanged. Extra space and NVMe raise costs, and lower media quality can reduce user satisfaction."] }
    ],
    related: ["read-write-throughput", "database-scaling", "replication"]
  },
  "read-write-throughput": { category: "architecture", title: "Read and write throughput",
    sections: [
      { id: "reads", title: "Reads per second", body: ["Reads counts weighted query work arriving at a database. One chat history request uses 1.8 read units. The Reads meter divides this demand by the lower of the read processing limit, the disk read limit and any legacy read throttle.", "At capacity, requests slow down and some fail. Add CPU or RAM for read processing, or NVMe when disk is limiting. Cache repeated reads or split eligible reads with a replica. More storage space leaves read speed unchanged. Hardware and extra components add cost. Cache entries and replica data can be stale."] },
      { id: "writes", title: "Writes per second", body: ["Writes counts weighted application write work reaching a primary. Sending a message uses 1 write unit, an image upload uses 1.5, and authentication uses 0.25 plus 1 read unit. The Writes meter compares demand with the standalone write limit for CPU, disk and any legacy throttle. The message search index raises compute and disk work per write by 20%.", "At capacity, writes and other requests sharing that database can fail. Add CPU for compute pressure, NVMe for disk pressure, or remove a binding legacy throttle in configuration. Extra replicas and caches leave application write demand unchanged. They can free shared resources when reads contribute to the bottleneck. Replication itself adds disk work."] },
      { id: "sustainable", title: "Database throughput", body: ["Throughput counts completed application requests per second. Demand meters use work arriving after upstream routing and throttling. The largest capacity ratio determines the share of requests served, with a separate check for available storage on writes. Incidents can reduce effective capacity.", "Near capacity, latency grows. Above it, requests are dropped. Sustainable writes estimates how many write units can fit while current reads keep their share and the write mix stays the same. It can be lower than the standalone Writes limit. Preview upgrades using the draft forecast and check the operating cost."] },
      { id: "cpu", title: "CPU utilization", body: ["CPU shows the larger of read and write compute pressure. At 2 vCPUs and 8 GB RAM, the compute limits are 155 read units/s and 62 write units/s before indexing. Both grow with (vCPU / 2) to the power of 0.74. Read compute also scales with (RAM / 8) to the power of 0.22.", "At capacity, the database admits fewer requests. More vCPUs raise compute capacity with diminishing returns and higher daily cost. NVMe leaves compute capacity unchanged. RAM improves read processing and memory headroom while the write compute limit is set by CPU."] },
      { id: "memory", title: "Memory utilization", body: ["The memory estimate is 0.8 GB base plus 0.014 GB per incoming read unit/s and 0.02 GB per write or replay unit/s, divided by configured RAM.", "High memory pressure slows traffic and saturation reduces throughput. Add RAM or reduce eligible read load. More disk speed or connection slots leave the memory budget unchanged. RAM upgrades raise daily cost."] },
      { id: "connections", title: "Connection limits", body: ["The database pool is an admission budget. The Connections meter divides incoming read and write or replay units per second by the configured limit. It does not count sockets or the Messenger’s persistent client connections.", "When the pool binds, raising it admits more work if compute, memory and disk have room. Raising it has no effect on those limits. The pool setting has no additional operating charge in this simulation."] }
    ],
    related: ["database-io", "database-scaling", "bottlenecks"]
  },
  "replication": { category: "architecture", title: "Replication",
    sections: [
      { id: "datasets", title: "Datasets and primaries", body: ["An API uses one directly connected primary for its dataset. In older layouts with several primary links, the first by component ID is selected. Independent primaries hold independent datasets. An upstream balancer can distribute traffic across APIs, but it has no dataset-aware routing and does not replicate or shard the data."] },
      { id: "lag", title: "Replication lag", body: ["Each replica receives the write units its primary commits. The replica replays them using its own CPU, RAM, disk and pool while serving reads. Unapplied work carries into the next step. Lag estimates how long the remaining work takes to replay at the current rate, plus 0.2 seconds. If there is pending work and no replay, lag cannot be estimated.", "A replica can still serve reads while catching up, so reads may trail the primary. Upgrade the pressured replica resource or reduce its read load to help it catch up. Increasing primary storage space does not make replay faster. The simulation tracks write work and lag without storing individual messages or comparing versions."] },
      { id: "example", title: "Connect a replica in Messenger", body: ["Attach Replica → Primary database to subscribe to changes. Route ordinary reads using API → Replica or Cache → Replica. Keep the direct API → Primary database link for writes."], diagram: "API server → Read replica → Primary database" }
    ],
    related: ["replica", "routing", "database-io"]
  },
  "database-scaling": { category: "architecture", title: "Database scaling",
    sections: [
      { id: "compare", title: "Cache versus read replica", body: ["Use a cache for repeatable reads. Use a replica for ordinary reads, including cache misses and rarely repeated requests. A replica increases primary disk work for every write it follows."] },
      { id: "mixed-load", title: "Heavy Messenger workload", body: ["At 321 read units/s and 254 write units/s, NVMe is already over its 166.75 write-only budget. Cache hits or replica reads alone cannot cover the gap. Increase CPU for compute and use NVMe array for disk I/O. Raise the pool or RAM if either reaches capacity after the upgrade.", "A useful preview starts with 16 vCPU, 16 GB RAM, an 800-unit pool and NVMe array. For indexed writes or more peak headroom, try up to 32 vCPU. Compare projected writes and remaining load. The array still has a finite ceiling."] },
      { id: "demand", title: "Reduce demand", body: ["Relax history sync to cut read demand. Disabling an optional feature such as group chats or image attachments can reduce write demand and removes that capability from users. A write limiter protects capacity by rejecting excess requests."] }
    ],
    related: ["database-io", "read-write-throughput", "cache", "replica"]
  },
  "async-processing": { category: "architecture", title: "Asynchronous processing",
    sections: [
      { id: "flow", title: "Request and job flow", body: ["Use API → Queue → Worker for Messenger notifications or media processing. Jobs are generated after the synchronous database operation succeeds. Workers do not write back to the database. Queue capacity, worker count and retention leave the primary’s write capacity unchanged. The game has no batching control."], diagram: "API server → Queue → Worker" },
      { id: "topics", title: "Job topics and delivery", body: ["Set separate queues to Notifications, Media processing or Search jobs. A connected Distribute queue shares matching jobs with other Distribute queues. A Broadcast queue receives a copy of each matching job for an independent consumer group. Workers attached to one queue share its jobs.", "For example, connect a distributed Notifications queue to delivery workers and a broadcast Notifications queue to audit workers. Copies add their own workload and backlog, and a full destination can reject submissions."] },
      { id: "backlog", title: "Backlog and errors", body: ["When jobs arrive faster than workers drain them, waiting time grows. Expiration removes old work. Overflow rejects new submissions and can count as a failed request."] }
    ],
    related: ["queue", "worker"]
  },
  "bottlenecks": { category: "architecture", title: "Bottlenecks and resource utilization",
    sections: [
      { id: "diagnose", title: "Find the limiting resource", body: ["Compare incoming demand, successful throughput and latency. A component can throttle when one resource exceeds 100%. A near-capacity meter signals little headroom. Use Monitoring to identify the resource."] },
      { id: "forecast", title: "Capacity forecast", body: ["Draft review estimates a range by varying audience demand. For databases visible in production and the draft, compare live utilization with projected utilization and sustainable writes. Estimates assume no active incidents."] }
    ],
    related: ["monitoring-setup", "database-scaling", "availability"]
  },
  "availability": { category: "architecture", title: "Availability and incidents",
    sections: [
      { id: "availability", title: "Availability", body: ["Availability is the share of requests that succeed. Failed nodes, saturation and traffic rejected by a limiter can lower it. Several API instances and balancer health checks can preserve enough capacity after a failure."] },
      { id: "events", title: "Events and drills", body: ["Use Events to inspect incidents and run a failure drill. Read replicas serve ordinary reads and do not take over as the write primary."] }
    ],
    related: ["balancer", "monitoring-charts", "deployment"]
  },
  "product-features": { category: "business", title: "Product features and releases",
    sections: [
      { id: "development", title: "Development and activation", body: ["Meet prerequisites, pay the development cost and let the clock run. Release the finished feature when the live topology meets its requirements. Released features can be enabled or disabled. Enabled features change demand and can improve organic growth."] },
      { id: "requirements", title: "Release requirements", body: ["Check each feature in Product. For example, image attachments require a reachable primary with at least 8 GB free for media on each API path. Voice messages also need working background processing. Message search needs an index."] }
    ],
    related: ["async-processing", "database", "satisfaction"]
  },
  "advertising": { category: "business", title: "Advertising",
    sections: [
      { id: "ads", title: "Advertising intensity", body: ["Develop and enable Advertising, then compare ad intensity in Product. More slots can raise impressions and delivery work. Fill rates, regional ad value and engagement affect the actual revenue. Ads also add friction and churn."] },
      { id: "example", title: "Messenger example", body: ["Try a low intensity first. Compare net profit and satisfaction as the simulation advances."] }
    ],
    related: ["premium", "satisfaction", "finances"]
  },
  "premium": { category: "business", title: "Premium subscriptions",
    sections: [
      { id: "benefits", title: "Premium benefits", body: ["Develop and enable Premium subscriptions. Choose a monthly price and any enabled benefits in Product. Ad-free premium removes ad delivery for subscribers. Faster sync adds load from premium users."] },
      { id: "renewals", title: "Adoption and renewal", body: ["Service quality, recent reliability and price affect subscription adoption and renewal. Compare subscriber count and fees in Finance after a price change."] }
    ],
    related: ["advertising", "satisfaction", "finances"]
  },
  "satisfaction": { category: "business", title: "Satisfaction and churn",
    sections: [
      { id: "quality", title: "Service quality", body: ["Slow or failing requests reduce service quality. Satisfaction follows the experience over time and affects organic growth and churn. Advertising friction can lower satisfaction even when capacity is sufficient."] },
      { id: "settings", title: "Sync and media settings", body: ["Less frequent sync reduces history demand and satisfaction. Compressed media cuts bytes transferred and stored, but needs more API compute and can reduce satisfaction."] }
    ],
    related: ["product-features", "database-scaling", "advertising"]
  },
  "regions": { category: "business", title: "Regional expansion",
    sections: [
      { id: "markets", title: "Markets and localization", body: ["Open new markets and complete language projects in Growth. Markets differ in activity patterns, acquisition cost, ad value and price sensitivity. Localization improves opportunities for that audience."] },
      { id: "example", title: "Messenger example", body: ["Compare Europe with North America in the demand chart. The local evening peaks arrive at different times on the service clock."] }
    ],
    related: ["game-time", "campaigns", "finances"]
  },
  "campaigns": { category: "business", title: "Marketing campaigns",
    sections: [
      { id: "planning", title: "Plan a campaign", body: ["Choose active markets, a total budget and duration. The budget is allocated in cents across the selected markets. Local acquisition cost and supported languages affect how many users each share can reach.", "At the same budget, a shorter campaign brings in the same expected total faster. It concentrates first-session traffic and can raise peak demand. Compare the arrival curve, forecast and baseline peak before committing."] },
      { id: "example", title: "Messenger example", body: ["Preview a community campaign before launch. If projected availability drops, address the saturated component or reduce campaign demand."] }
    ],
    related: ["regions", "bottlenecks", "finances"]
  },
  "finances": { category: "business", title: "Revenue and operating costs",
    sections: [
      { id: "revenue", title: "Revenue sources", body: ["Operating profit uses recognized revenue and recurring expenses. Prepaid subscription cash arrives at purchase and is recognized over the subscription term. Development, campaigns and installations appear as cash outflows."] },
      { id: "costs", title: "Recurring and one-time costs", body: ["Infrastructure and traffic accrue operating costs as time advances. Deployments, projects and campaigns can charge one-time costs. Disconnected components still cost money while deployed.", "Removing components and reducing settings can lower the daily bill. A change with a zero installation cost can be deployed while the balance is negative. Review capacity and routing warnings before deployment."] }
    ],
    related: ["advertising", "premium", "deployment"]
  },
  "topology-editing": { category: "interface", title: "Topology editing",
    sections: [
      { id: "edit", title: "Nodes and connections", body: ["Use Add node and Connect in a draft. On the canvas, draw from a source port to a valid target. Use the connection reference to check allowed types. Select a node to open Configuration or Metrics."] },
      { id: "layout", title: "Canvas and inspector", body: ["Drag the divider beside the inspector to resize it on desktop. Focus it and use Left or Right to resize, Home or End for the limits, or Enter to reset. On mobile, open the component panel from its card."] }
    ],
    related: ["deployment", "routing", "groups", "edge-routing", "shortcuts"]
  },
  "groups": { category: "interface", title: "Visual grouping",
    sections: [
      { id: "groups", title: "Create and collapse groups", body: ["Select several components, then create a named group. Collapse it to simplify the canvas. Groups can be nested. Grouping is saved with the diagram and does not change routing or costs."] }
    ],
    related: ["topology-editing", "edge-routing"]
  },
  "edge-routing": { category: "interface", title: "Manual edge routing",
    sections: [
      { id: "waypoints", title: "Waypoints", body: ["Select a connection and add a waypoint. Drag waypoints to route the edge around other nodes. Reset the route to restore automatic routing. Waypoints change only the drawing."] }
    ],
    related: ["topology-editing", "routing"]
  },
  "monitoring-charts": { category: "interface", title: "Monitoring charts",
    sections: [
      { id: "history", title: "Service and component history", body: ["In Telemetry, choose a time range and a component. Compare incoming and successful requests and peak resource load at the same game time. Component history requires service history coverage at the time of collection."] }
    ],
    related: ["monitoring-setup", "bottlenecks", "availability"]
  },
  "shortcuts": { category: "interface", title: "Keyboard shortcuts",
    sections: [
      { id: "canvas", title: "Canvas controls", body: ["On the canvas, use Ctrl or Command + A to select components, Delete to remove the draft selection, and Escape to clear the selection. Ctrl or Command + Z undoes the last edit. Shift + Z with the same modifier, or Ctrl or Command + Y, redoes it."] },
      { id: "divider", title: "Inspector controls", body: ["Focus the inspector divider to change its width with Left and Right. Hold Shift for larger steps. Press Enter to restore the default width."] }
    ],
    related: ["topology-editing"]
  },
  "save-files": { category: "interface", title: "Save export and import",
    sections: [
      { id: "transfer", title: "Portable saves", body: ["Export a save from Saved games or Settings. In Saved games, select a save file, inspect its preview and import it. Import creates a separate local game with its own identity."] }
    ],
    related: ["game-basics", "deployment"]
  },
};

export function guideArticleHref(base: string, article: string | readonly [string, string], section?: string) {
  const [id, anchor] = typeof article === 'string' ? [article, section] : article;
  return `${base}&article=${id}${anchor ? `#${anchor}` : ''}`;
}

export function fieldArticle(kind: Kind, field: string) {
  const engineering: Record<string, string> = { role: 'universal-specialized', domain: 'data-domains', partition: 'database-sharding', query_plan: 'query-optimization', autoscale: 'api-autoscaling', min_instances: 'api-autoscaling', max_instances: 'api-autoscaling', target_utilization: 'api-autoscaling', instances: 'api-instances' };
  if (engineering[field]) return [engineering[field], 'configuration'] as const;
  if (kind === 'database' || kind === 'replica') {
    if (field === 'disk') return ['database-io', 'io'] as const;
    if (field === 'storage') return ['database-io', 'space'] as const;
    if (field === 'search_index') return ['read-write-throughput', 'writes'] as const;
    if (field === 'cpu' || field === 'memory' || field === 'connections') return ['read-write-throughput', field] as const;
  }
  return [kind, 'configuration'] as const;
}

export function resourceArticle(resource: string) {
  switch (resource) {
    case 'Disk I/O': return ['database-io', 'io'] as const;
    case 'Storage': return ['database-io', 'space'] as const;
    case 'Replication': return ['replication', 'lag'] as const;
    case 'CPU': return ['read-write-throughput', 'cpu'] as const;
    case 'RAM': return ['read-write-throughput', 'memory'] as const;
    case 'Connections': return ['read-write-throughput', 'connections'] as const;
    case 'Reads':
    case 'Legacy read throttle': return ['read-write-throughput', 'reads'] as const;
    default: return ['read-write-throughput', 'writes'] as const;
  }
}

export function searchArticles(query: string, catalog: Catalog, translate: (message: string) => string, language: string) {
  const normalize = (value: string) => value.toLocaleLowerCase(language).replaceAll('ё', 'е');
  const words = normalize(query.trim()).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return Object.entries(articles).flatMap(([id, article]) => {
    const definition = article.kind ? catalog.components[article.kind] : undefined;
    const title = normalize(translate(article.title));
    const category = normalize(translate(categories[article.category]));
    const body = [
      ...(definition ? [definition.name, definition.description, ...Object.values(definition.fields).map((field) => field.label)] : []),
      ...article.sections.flatMap((section) => [section.title, ...(section.body ?? []), section.diagram ?? ''])
    ].map(translate).join(' ');
    const content = normalize(`${title} ${category} ${body}`);
    if (!words.every((word) => content.includes(word))) return [];
    return [{ id, article, rank: words.filter((word) => title.includes(word)).length }];
  }).sort((a, b) => b.rank - a.rank);
}
