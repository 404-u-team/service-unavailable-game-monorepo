# Engineering and architectural evolution

Engineering uses the existing Product development clock, up-front `development`
ledger, action idempotency and transaction boundary. Completion unlocks settings;
it never edits production or releases a user-facing feature. A Universal API is
still the default and can use every new database capability without specializing.

| Research | Cost | Game duration | Prerequisite | Capability |
| --- | ---: | ---: | --- | --- |
| Service Decomposition | $1,800 | 6 hours | None | API roles and explicit identity dependencies |
| Domain Data Separation | $2,600 | 8 hours | Decomposition | Independent domain owners and planned data moves |
| Database Query Optimization | $2,100 | 7 hours | None | Optional history indexes |
| Database Sharding | $6,200 | 16 hours | Domain separation | Partitioned primaries for one domain |
| API Autoscaling | $3,200 | 9 hours | Decomposition | Monitored, bounded instance changes |

## Operations and routing

External request rates, product enablement, regional activity, campaign demand and
seeded variation remain in `demand.workload`. The architecture layer classifies
the existing operations, without replacing their demand coefficients:

| Role / domain | Operations |
| --- | --- |
| Messages | send, history, conversations, connection, groups, calls, ad |
| Accounts | auth; internal identity checks |
| Media | upload, voice, files |
| Search | search |
| Universal / Shared | All supported operations / legacy combined data |

Calls and ads stay with Messages because the existing model represents signaling
and delivery, not separate calling or advertising datasets. Search is an aggregate
index workload; this iteration does not introduce an index-replication simulator.

Request links from the source, limiter or balancer carry only eligible operations.
Universal and matching specialized groups share traffic equally under Round robin;
Weighted capacity uses vCPU × active instances. There is no hidden specialization
priority or overload spillover. Disconnected or ineligible APIs receive no demand.
Identity-only links cannot substitute for an external authentication route.

Instances are identical copies of a node's role, hardware and dependencies.
Separate nodes have independent settings and routes. Equivalent API groups must
agree on data ownership, including any Universal group retained during transition.

Specialized services reserve 6% extra CPU and network work for service boundaries.
Messages, Media and Search explicitly link to an Accounts API. They generate
0.02 identity checks per admitted request: an aggregate assumption of one shared
token/identity revalidation per fifty operations, rather than an extra login per
message. Checks consume Accounts CPU, network and account database reads. Their
aggregate success ratio gates dependent completion, and the dependency contributes
latency. Universal retains local identity behavior and has none of these new costs.
These balance constants are visible in the research cards and Guide.

## Data ownership and write scaling

An API's matching explicit domain link takes precedence over Shared. Operation
read/write/storage units follow that owner. Separating Accounts does not reduce
message-write units. Multiple independent primaries cannot masquerade as copies
of one domain; all participating APIs must use the same owner or complete shard
set. Existing legacy split links retain their original behavior until changed.

For sharding, set primary `domain` to a specific domain and `partition` to
`Partition`, then link every API serving that domain to all its primaries. Each
primary holds distinct conversation partitions. Each read replica still subscribes
to exactly one primary and receives only that shard's reads and committed writes.

The aggregate partitioner hashes 128 stable virtual conversation buckets by domain
and component-ID-sorted shard set. One hot conversation cohort carries 12% of
activity; the other 127 share 88%. This deliberately makes small shard sets uneven
and keeps a hot-key ceiling as shard count grows. Read and write placement use the
same weights. A shard failure loses its share rather than failing every partition
or rerouting writes into unrelated data. Each additional shard adds 3% API CPU
coordination; data routing adds `4 + shard count` ms when there is more than one.

To scale writes beyond a maximum primary: research Decomposition → Domains →
Sharding; keep Universal if preferred; move Accounts to its own owner; configure
multiple Messages partitions; connect the full set; offload eligible reads using
cache/replicas; review, finance and complete the migration. Monitor every shard,
including the hot one. CPU, RAM, I/O, connections and storage stay finite.

## Migrations and saves

Changing live domain ownership or shard membership starts paid preparation from
the existing deployment workflow. Review includes transfer cost and time and
checks 15% destination storage headroom. The one-time deployment charge includes
$120 + $4/GB + destination operating cost during preparation. Copy speed is at
most 4 GB per ten-minute tick, bounded by the slowest destination's vCPU count,
with a minimum of three ticks. Production keeps serving, reserving 10% of primary
capacity for copying. The pending topology is locked; diagram edits remain
independent. Pausing the clock pauses preparation. New feature releases/enables
wait until preparation finishes so they cannot invalidate an already paid plan.

At completion the prepared topology is deployed automatically and rollback history
is retained. Removing shards and rolling back ownership changes use the same paid
preparation. Stored GB are conserved. Explicit domains retain their own volume;
legacy Shared GB are apportioned by the existing persistent-growth coefficients,
including released but disabled features. Individual messages are not stored by
this aggregate simulator. Continued growth during copying can still exhaust the
planned storage headroom; the resulting storage pressure is simulated normally.

Research completion ticks, node roles/domains/partition membership, autoscaling
state, pending topology and optional lesson progress are additive JSON fields.
Old saves default to Universal/Shared/Independent with no research or pending
migration. PostgreSQL already stores the game in JSONB, so no DDL migration or
volume/identity replacement is needed. Portable imports validate research keys,
prerequisites, bounds, ownership, migration topology and component state. Draft,
production, rollback and diagram layout remain distinct. Live patches include the
new fields through the existing whole-view field iteration; snapshot resync is
unchanged.

## Optimization and autoscaling

History indexes reduce history read work by 35% and conversation-list reads by
20%, while increasing send/group write work by 10%. Replicas inherit their
primary's plan. Authentication, media and other operations are unaffected. The
existing search index is separate and keeps its existing write-maintenance cost.

Autoscaling requires deployed monitoring coverage of the API. It starts at the
minimum, observes utilization against a 40–90% target and changes by one instance
after two consistent observations and at least three ticks since the previous
change. Below half target it scales down. Minimum/maximum stay within 1–24;
scale-up also requires cash for one day at the proposed group size. All active
instances are billed through operating expenses. Missing monitoring freezes
decisions. Autoscaling does not increase database capacity.

## Reproducible balance comparison

`tests.test_engineering` uses seed 7, tick 0 and identical external workload for
each comparison. Both starter cases have equivalent monitoring. The large case
uses 28× the same external workload, maximum primary hardware (32 vCPU, 128 GB,
NVMe array, 10,000 connections), a separate Accounts owner, the same API resources,
and a 64 GB cache with 3,600-second TTL. These are infrastructure costs per game
day, excluding one-time research, installation and migration purchases.

| Architecture | External req/s | Successful req/s | Availability | Mean latency | Infrastructure/day |
| --- | ---: | ---: | ---: | ---: | ---: |
| Starter Universal | 137.19 | 137.19 | 100% | 79.66 ms | $25.60 |
| Starter Messages + Accounts | 137.19 | 137.19 | 100% | 128.94 ms | $31.60 |
| One maximum Messages primary + cache | 3,841.38 | 3,250.68 | 84.62% | 90.66 ms | $4,300.44 |
| Two Messages shards + cache | 3,841.38 | 3,775.04 | 98.27% | 61.24 ms | $5,078.88 |
| Four Messages shards + cache | 3,841.38 | 3,841.38 | 100% | 49.70 ms | $6,635.76 |

Starter primary write demand stays 36.06 units/s in both architectures; the
specialized case adds account read work (117.49 → 117.81 total read units/s).
At large scale, message writes are 965.27 units/s in every case, above one maximum
primary's write ceiling even with reads offloaded. Four-shard message write loads
are approximately 296.42, 167.21, 234.10 and 267.54 units/s. More shards help but
do not provide free or unlimited capacity; the tests also saturate the four-shard
topology at higher demand and verify partial failure and hotspot behavior.

## In-game help and walkthrough

Twelve English/Russian Guide articles cover Engineering Research; Universal versus
Specialized API; Service Decomposition and Microservices; Request Routing by
Service; Instances versus Separate API Nodes; Data Domains and Database Separation;
Shared versus Independent Primary; Database Sharding; Query Optimization; API
Autoscaling; Architecture Migration; and Monolith/Microservice Tradeoffs. Every
article includes configuration, simulation, costs, limitations, mistakes and a
Messenger example. Role, domain, shard, query, instance and autoscaling controls
link directly to their relevant sections. Cards explain prerequisites, duration,
costs, unlocks, benefits and tradeoffs.

Product offers an optional six-step engineering walkthrough: research; create a
specialized API; connect dependencies; review workload and cost; deploy; observe
monitored results. It reuses the onboarding spotlight/navigation component, saves
its own progress and supports skipping/resuming without restarting old onboarding.
Its safe example retains Universal while adding Accounts to the same primary.

## Deliberate limits

This remains an aggregate workload simulation: no individual conversations, RPC
traces, row copies, distributed transactions, index backfills or real orchestration
controller are modeled. Identity is the explicit cross-service dependency in this
iteration. Shard weights include one fixed hot cohort rather than configurable
user-record skew. Autoscaling uses fixed reaction/cooldown and a cash guard, not a
separate configurable spending budget. These limits are documented in the Guide;
none removes the resource costs or consistency checks above.

## Verification

Verified with Python 3.14 and an isolated PostgreSQL 17.7 database: all 100 backend
tests pass, including 15 engineering regressions and 11 real API integration tests.
Ruff passes. All nine Bun unit tests pass, including bilingual article/lesson and
stable help-link assertions. Svelte checking reports zero errors or warnings, and
the production build completes.

Chromium passed the full 52-test regression run before two additional engineering
checks were added; the final 11 engineering tests pass, covering all 54 distinct
scenarios. Firefox passed 53 of 54 on its full run; the remaining test incorrectly
requested a textbox for a numeric spinbutton. After correcting that selector, all
11 final engineering tests pass in Firefox as well. English/Russian research,
configuration and Guide states were exercised at 390, 768, 1440 and 1920 px, with
screenshots inspected at every width. Existing onboarding, touch, keyboard,
WebSocket reconnect, diagram editing, deployment, finance and save-transfer
coverage remains in the browser suite.
