import type { Article } from './guide';
export const engineeringArticles: Record<string, Article> = {
  "engineering-research": {
    "category": "architecture",
    "title": "Engineering Research",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Engineering projects use the Product development budget and the same ten-minute game ticks as feature development."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Research when a measured bottleneck calls for a new architectural capability. Universal APIs remain usable without research."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Open Product → Engineering, check prerequisites and start research. Run the clock to complete it."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "The cost is booked once as development. Completion unlocks settings and never edits production or adds demand."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "New capabilities let you target particular workloads instead of increasing every resource."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Servers, migration, monitoring and recurring infrastructure bills are paid separately from research."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Do not spend the infrastructure reserve on research; an unlocked role still needs a connected service."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Research Service Decomposition. While the Universal API serves production traffic, prepare Messages and Accounts services in a draft."
        ]
      }
    ],
    "related": [
      "universal-specialized",
      "architecture-migration"
    ]
  },
  "universal-specialized": {
    "category": "architecture",
    "title": "Universal API versus Specialized API",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Universal executes every modeled Messenger operation. Each specialized role accepts only its operation family."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Use Universal for a simple low-cost service; specialize when one workload needs independent resources."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "After Service Decomposition, set the API roles in a draft. A deployment uses either Universal APIs or specialized APIs and must cover all released operations."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "Messages handles sends, history, conversation lists, connections, groups, calls and ads; Accounts handles authentication; Media handles uploads, voice and files; Search handles search."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Roles isolate compute pressure and allow different instance sizes and counts."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Specialization adds 6% compute and network overhead plus identity calls. It does not unlock product features."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Changing the name alone never changes routing. A Media role is idle until media features create demand."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "A Messages API handles chats and calls. A separate Accounts API handles authentication and identity checks."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "service-decomposition": {
    "category": "architecture",
    "title": "Service Decomposition and Microservices",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Decomposition separates logical API groups without creating new component types."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Use it when messaging CPU and media network demand need different scaling decisions."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Research decomposition, configure roles, connect the balancer, data stores and directed service-to-Accounts identity links."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "Each non-Accounts specialized request adds 0.02 identity calls on average. These calls consume Accounts compute and database reads; their completion ratio gates dependent requests."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "A hot media pool can be scaled without buying identical messaging capacity."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Identity adds downstream latency and propagates Accounts failures. The model aggregates calls rather than simulating individual RPCs."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "A specialized service without its Accounts link cannot successfully finish requests. Universal keeps identity local."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "In the same draft, replace Universal with the required specialized services. Connect Media to Accounts and its data owner."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "service-routing": {
    "category": "architecture",
    "title": "Request Routing by Service",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Routing uses the existing feature operations and regional activity, with no new external traffic percentages."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Inspect routing when one operation fails despite apparently spare total capacity."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Connect source or balancer request links to all required service roles. Identity links go only from specialized services to Accounts."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "API pools that support an operation share its traffic. Round robin splits it equally, and Weighted capacity splits it by CPU times active instances."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "The same seeded workload can be compared before and after deployment without duplicating requests."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Routing does not spill overloaded requests into an unrelated role. Each path retains its own finite resources."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "A disconnected Search API cannot rescue search traffic. Connect it and an indexed owning database."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Two Messages pools share send and history traffic; an Accounts pool receives authentication and explicit identity calls."
        ]
      }
    ],
    "related": [
      "universal-specialized",
      "architecture-migration"
    ]
  },
  "api-instances": {
    "category": "architecture",
    "title": "Instances versus Separate API Nodes",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "An API node is one logical service group. Its instances are identical copies with shared settings and dependencies."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Add instances for more capacity of the same service; add nodes for independent roles, hardware or routes."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Set Instances inside configuration, or add another API node and connect it separately."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "Instance count multiplies per-instance capacity and cost. Separate nodes are routed independently by eligible operation."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Two nodes can scale or fail independently while sharing one consistent dataset."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Each deployed instance incurs its full operating cost. A disconnected node is still billed."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Two nodes pointing at unrelated independent primaries are not synchronized copies."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Two Messages nodes may both use Messages Primary; one Messages and one Media node process different operation families."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "data-domains": {
    "category": "architecture",
    "title": "Data Domains and Database Separation",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "A domain owns the data operations of Messages, Accounts, Media or Search. Shared retains legacy combined storage."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Separate domains when account, media or search demand competes with message work."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Research Domain Data Separation. To deploy domain databases, assign every primary a domain and connect each API to the owners of the data it uses."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "With domain databases, an operation goes to the primary for its domain and carries its original read and write work."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Accounts work leaves Messages storage, isolating its resource demand."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Separation does not reduce message writes. Search is an aggregate index domain, not a synchronized message primary."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Every API that uses a domain must connect to the same primary or the same complete set of partitions."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Connect a Universal API to Messages and Accounts databases. It routes chat history to Messages and authentication to Accounts."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "shared-primary": {
    "category": "architecture",
    "title": "Shared Primary versus Independent Primary",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Several API pools may share one primary. Several independent primaries represent different data, not automatic copies."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Share a primary when equivalent services handle the same conversations. Use independent primaries for different domains."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Connect each equivalent API to the same primary ID, or configure the same complete partition set after sharding research."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "Deployment review rejects conflicting owners and independent primaries pretending to contain one dataset."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Sharing preserves consistency while API capacity can grow independently."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "One shared primary still has a finite write ceiling. Read replicas only offload eligible reads."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Do not add a second independent Messages primary expecting write scaling. Research and configure partitions first."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Messages API A and B → Messages Primary is valid; A → Primary A and B → unrelated Primary B is rejected."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "database-sharding": {
    "category": "architecture",
    "title": "Database Sharding",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Sharding partitions one domain across primaries. Each stores distinct keys and retains its own finite resources."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Use it after vertical scaling, query tuning and read offload cannot resolve a domain write ceiling."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Complete Database Sharding research and open a draft. Add a shard router from the component library. Set its data domain, assign the same domain and Partition membership to two or more primary databases, and connect the router to each one.",
          "Connect every API that uses this domain to the router. Remove those APIs' direct links to primaries for that domain. To cache reads, add API → Cache and Cache → Shard router. The direct API → Shard router link handles writes."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "128 deterministic conversation buckets distribute both reads and writes. One hot bucket carries 12% of activity; the rest share 88%. Each replica follows one shard and reads only its partition."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Several primaries can sustain more total writes than one maximum-size primary."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Each extra partition adds 3% API compute coordination. Partition lookup adds 4 milliseconds plus 1 millisecond per shard, and the router adds its own capacity limit and daily cost. A failed shard loses its share of requests."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "A hot shard can saturate while others are idle. Removing a shard requires migration and enough remaining storage."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "To shard chat history and messages from a shared database, configure the original database and a second primary as Messages partitions. Add an Accounts primary and any other domain primaries needed by released features. Connect the API to its Accounts primary and the Messages router. In Deployment review, check storage and cost, start migration, and run the clock until copying completes."
        ]
      }
    ],
    "related": [
      "universal-specialized",
      "architecture-migration"
    ]
  },
  "query-optimization": {
    "category": "architecture",
    "title": "Database Query Optimization",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "History indexes are an optional per-primary query plan unlocked through Engineering."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Use them when history and conversation-list reads dominate measured database work."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Research Query Optimization and choose History indexes in each relevant primary configuration."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "History reads use 65% of their former units; conversation-list reads use 80%. Send and group writes use 110% for index maintenance. Replicas inherit the owning primary plan."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "The same successful read traffic can consume less database CPU and disk work."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Authentication, media and message-write demand are not reduced. The existing search index remains a separate setting."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Do not enable indexes blindly on a write-bound primary: maintenance can worsen write pressure."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Compare Chat history read units and Send message write units in the same draft forecast before enabling the plan."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "api-autoscaling": {
    "category": "architecture",
    "title": "API Autoscaling",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Autoscaling changes active API instances within a deployed minimum and maximum."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Use it for regional peaks when API load changes and the database has spare capacity."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Research Autoscaling, enable it on an API, set bounds and utilization target, and deploy monitoring coverage for that node."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "After two observed pressure ticks and a three-tick cooldown, one instance is added above target or removed below half target. Counts stay between 1 and 24 and within configured bounds."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Quiet periods can cost less while busy periods receive extra API capacity."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Every active instance is billed. Scale-up needs cash for one day at the new group size. Missing monitoring freezes decisions. Database capacity does not grow."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "A slow reaction can still lose burst traffic. Raising maximum instances does not fix a saturated Messages primary."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Set Messenger API to 1–4 instances at 65%, observe scaling events during a peak and compare the actual service-group bill."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "architecture-migration": {
    "category": "architecture",
    "title": "Architecture Migration",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Changing a live domain owner or partition count schedules preparation rather than instantly relabeling data."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Use it when splitting Shared data, moving a domain or adding and removing shards."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Keep Draft → Review → Deploy. Review includes transfer cost, preparation ticks and destination storage checks. Deploy pays once and starts preparation."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "Preparation takes at least three ticks, copying at up to 4 GB per tick bounded by the slowest destination CPU. Production keeps serving with 10% database capacity reserved."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "The clock finishes the prepared topology automatically. Stored GB are conserved, including shard removal and rollback migrations."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Transfer costs $120 plus $4 per GB and destination preparation expense. Legacy Shared GB are apportioned by modeled persistent growth, not individual records."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Leave spare storage and capacity. The pending topology is locked until preparation completes; pausing the clock also pauses migration."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "Add a third Messages partition, review the new imbalance and copy charge, then run the clock while the two-partition production remains live."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  },
  "monolith-microservices": {
    "category": "architecture",
    "title": "Tradeoffs of Monoliths versus Microservices",
    "sections": [
      {
        "id": "overview",
        "title": "What it does",
        "body": [
          "Monolith and specialized architectures are alternatives with the same external Messenger demand."
        ]
      },
      {
        "id": "use",
        "title": "When to use it",
        "body": [
          "Keep Universal at small scale. Consider separation for independent scaling, isolation or data ownership."
        ]
      },
      {
        "id": "configuration",
        "title": "Configuration",
        "body": [
          "Compare a candidate draft against production before deploying; keep monitoring coverage equivalent."
        ]
      },
      {
        "id": "simulation",
        "title": "Simulation and costs",
        "body": [
          "Universal keeps identity work local. Specialized services add 6% compute and network overhead and a shared Accounts dependency. Demand is split by operation, never copied."
        ]
      },
      {
        "id": "advantages",
        "title": "Advantages",
        "body": [
          "Different resource sizes can fit messaging CPU and media bandwidth more closely."
        ]
      },
      {
        "id": "costs",
        "title": "Costs and limitations",
        "body": [
          "Additional pools, databases and monitoring increase costs and failure paths; research alone improves no resource."
        ]
      },
      {
        "id": "mistakes",
        "title": "Common mistakes",
        "body": [
          "Do not assume more nodes means more successful requests. A missing dependency or hot shard can reduce availability."
        ]
      },
      {
        "id": "example",
        "title": "Messenger example",
        "body": [
          "At the starter audience, compare one Universal pool against Messages plus Accounts: the latter pays for another API and identity overhead without reducing message writes."
        ]
      }
    ],
    "related": [
      "engineering-research",
      "service-routing",
      "database-sharding"
    ]
  }
};
