# Core API

The existing FastAPI app serves authentication, health and gameplay. Game saves use PostgreSQL and share the app's connection pool. The [game migration](src/repositories/sql/games.sql) is applied transactionally under an advisory lock, including on existing databases. The API keeps the full simulation state, pending architecture, placements, ledger, incident history and deployment history in each save.

## Game endpoints

All paths below start with `/api/games`. FastAPI publishes request and response schemas at `/docs` and `/openapi.json`.

| Method and path | Behavior |
| --- | --- |
| `GET /catalog` | Scenario, difficulty, component, feature and campaign definitions |
| `GET /` and `POST /` | List or create saves. Use `/api/games` without a trailing slash. |
| `GET /{id}` | Current game, production and draft, telemetry, progression and finances |
| `GET /{id}/architecture?version=production\|draft` | Read one topology |
| `GET /{id}/monitoring` | Read current service and visible component metrics |
| `GET /{id}/finance` | Read revenue and expense breakdowns, cash and the rolling game-day history |
| `GET /{id}/incidents` | Read the visible incident history |
| `POST /{id}/save` | Persist and return the current snapshot |
| `PUT /{id}/clock` | Set speed to 0, 1, 3 or 5 |
| `POST /{id}/draft` | Start a draft from production |
| `PUT /{id}/diagram` | Replace diagram positions, routes, and groups |
| `PATCH /{id}/diagram` | Merge changed positions, routes, groups, and viewports |
| `WS /{id}/live` | Stream a game snapshot and ordered changes |
| `PUT /{id}/draft` | Persist an edited topology |
| `POST /{id}/draft/review` | Validate the draft or a supplied candidate topology and return the diff, costs and forecast |
| `POST /{id}/draft/discard` | Discard the draft |
| `POST /{id}/deployments` | Revalidate and deploy the saved draft |
| `POST /{id}/deployments/{deployment_id}/rollback` | Restore the topology before that deployment |
| `POST /{id}/features/{feature_id}` | Develop, release, enable or disable a feature |
| `PUT /{id}/product` | Set ad intensity, Premium terms, media quality, synchronization and market acquisition |
| `GET /{id}/campaigns/{campaign_id}/forecast` | Preview demand and availability, optionally with `region` or repeated `regions`, `budget`, and `duration` in ticks |
| `POST /{id}/campaigns/{campaign_id}` | Start a campaign with optional target regions, budget and duration |
| `POST /{id}/markets/{market_id}` | Develop or launch a regional market |
| `POST /{id}/languages/{name}` | Start Messenger localization |
| `POST /{id}/onboarding` | Record guided onboarding progress, skip, or resume |
| `POST /{id}/incidents/drill` | Run a one-instance failure drill |
| `POST /{id}/incidents/{event_id}/acknowledge` | Mark an event as reviewed |
| `PUT /{id}/settings` | Persist onboarding and motion preferences |
| `POST /{id}/tutorial` | Record an inspection or telemetry visit |

Call `GET /api/games` first to establish the signed, HTTP-only guest cookie. Clients with a valid existing access token use account-scoped saves. Save creation takes a client-generated UUID so retries can reopen the same save. Gameplay mutations require a UUID `request_id`. Retry a failed or interrupted request with the same UUID and body. Replays cannot charge twice. Draft and deployment actions also take the latest architecture `revision`. A stale revision returns 409 and invalid game actions return 422.

## Simulation model

- One step represents ten in-game minutes. The server advances saves from elapsed time at the selected speed. At 1×, two real seconds represent one step. At 3× and 5×, three and five steps take two seconds respectively. On return to a running save, at most two in-game days are simulated for a single elapsed gap. Paused saves retain their tick and any fractional progress.
- Demand is generated in operation cohorts from regional audience, local activity, enabled features, campaigns and seeded events. CPU, RAM, network, connections, concurrency, disk I/O, database reads and writes, and storage affect throughput. Latency rises with resource pressure. Availability is successful throughput divided by incoming request rate.
- Traffic can pass through a limiter or balancer to an API. Writes go directly to a primary. Read-only cohorts prefer linked caches, then use the cache's explicit data edges on a miss. If the cache has no eligible data links for that dataset, misses return through the originating API's database or replica links. A replica needs a subscription to the same primary the originating API uses. Available replicas split eligible reads, replay committed write units, and add primary disk I/O. A replica carries unapplied work into the next step. Indexed search and writes use the primary. Independent primaries hold separate datasets. New API configurations allow one primary link. Existing ambiguous links are retained for editing and use the first primary by component ID.
- Successful foreground operations can submit background jobs to attached queues. Notifications and media jobs contribute job load. Workers process at the minimum of their CPU, RAM and concurrency limits, scaled by healthy instances. Queues absorb excess arrivals up to their capacity. New submissions fail on overflow. Retention expires a fraction of old work per step. Accepted jobs can wait beyond the response, and queue wait is estimated from backlog and worker throughput capacity.
- Monitoring exposes metrics for linked components with a collection slot. Service history mode reserves two slots and exposes historical metrics. Forecasts evaluate representative future workload ranges with the same engine, excluding future random incidents. Higher monitoring coverage narrows the range.
- Campaigns incur a one-time cost and acquire users along a growth curve. Organic growth and churn respond to service quality and feature appeal. The game records revenue, cash receipts and operating costs each step. See [Messenger economy and balance](BALANCE.md) for formulas, save compatibility and reproducible results. Running topology changes that remove routing connections can briefly reduce throughput.
- Deployment rollback restores the earlier topology. Diagram positions, routes, and groups stay in the diagram. Runtime data on removed components is not recovered. Each save retains the last 20 deployments, 100 events and 144 history points.

### Diagram storage

`PUT /api/games/{id}/diagram` accepts `request_id` and a `diagram` object with `positions`, `routes`, and `groups`. Route keys are `source:target`. The game view returns this object independently of `production`, `draft`, and the topology revision. Saves without a layout render their stored topology positions. The optional `viewports` map uses `wide` and `compact` keys. Patch entries merge by node or edge ID and accept null to remove an override. Group edits include a baseline to detect concurrent group changes. The existing JSON save column stores the diagram and deployment metric comparisons.

### Live game state

Open `/api/games/{id}/live` on the application's origin using the same signed cookie as REST. The server sends a `snapshot` with the full state and sequence 1, followed by `patch` messages with changed fields. History updates specify how many leading samples to drop and which samples to append. Idle sockets receive heartbeat messages. Sequence numbers restart per connection, and reconnecting always starts with a snapshot. The browser uses the saved timestamp to reconcile REST replies with the stream. Simulation advancement uses the existing row lock across REST and WebSocket clients.

### Feature releases

Development checks feature prerequisites and budget. The API revalidates infrastructure against production under the save lock before release. Text and group messaging use a writable primary. Media uses primary database storage with at least 8 GB free at release. Voice messages and file sharing also need an API → Queue → Worker path. Search uses a primary with the message search index enabled. Calls use API signaling capacity of at least 40 MB/s and 1,500 connections per reachable API across its instances. These checks cover every API that receives traffic. Previously released features keep their saved release status and routing behavior. Release and re-enabling require enabled prerequisites. Disable enabled dependent features before disabling their prerequisite. Text messaging stays enabled as the core Messenger operation. Disabling a feature retains its release, data and development spend. Pending background jobs continue to drain. Paid subscription terms keep their price and benefits until expiry.


### Portable save API

- `GET /api/games/{id}/export` downloads a JSON snapshot of an owned save. The envelope has `format: "service-unavailable-save"`, `version: 1`, `exported_at` in UTC, and `game` containing the persisted simulation, topology, and layout. Random decisions derive from the seed and game tick. The file carries the fractional tick for both paused and running saves.
- `POST /api/games/import/preview` takes the raw JSON file as the request body and returns its service name, scenario, game day, audience, balance, file version and export date. It does not create a save.
- `POST /api/games/import` takes the same raw JSON, validates it again and returns a new save summary. The current owner receives a new save ID. Internal references stay intact. Each successful request creates a separate copy.
- Both upload endpoints accept at most 8 MiB and return localized error codes through `X-Game-Error-Code`. Database credentials, session credentials, and the server's request deduplication table are outside the envelope. Keep the version 1 loader when adding a new version, and migrate old state explicitly before validating it against newer models.

### Campaigns, accounting and capacity

Campaign forecasts accept one `region` or repeated `regions` query parameters. Campaign starts also accept a `regions` array. The server validates unique active markets and splits one total budget in cents. Each allocation uses the region's acquisition cost, language coverage and remaining audience potential. Existing single-region campaigns in saves keep their remaining acquisition schedule.

The discrete arrival curve sums to the planned acquisition at any supported duration. First-session traffic follows each step's new arrivals, so the same investment can create a sharper burst over a shorter period. The preview evaluates the curve over the campaign using the current audience, product settings and topology. It holds other growth, churn, infrastructure and future incidents fixed. Regional language weights represent simplified local segments. Each available non-English segment adds up to 18% times its weight to the acquisition multiplier.

The top bar shows cash and the trailing operating profit rate. Operating profit uses recognized ad and subscription revenue minus recurring infrastructure, traffic and payment fees. The Finance page records subscription cash receipts separately from recognition and shows one-time charges for the most recent game day. A zero-cost deployment can proceed in debt if the topology passes validation. Removal or downsizing produces no refund.

Deployment results compare the same workload and game tick before and after the topology change, before any new rollout interruption. The capacity estimate searches for the request rate that can sustain 99% success under the same request mix. It uses current storage, backlog and incidents and requires service history in both topologies for a displayed comparison. Estimated p95 weights the modeled operation and API cohort latencies by successful requests.

### Datasets, recovery and background queues

New Messenger deployments must use one shared writable dataset across reachable API nodes. Connect each interchangeable API to the same primary. Read replicas only serve eligible reads for their own primary. Existing split-dataset saves can be opened and reviewed, with an explicit warning until their links are corrected. Sharding and separate logical services would require their own routing model.

Each instance shares its node configuration and downstream links and contributes its own capacity, cost and availability. Separate nodes have independent links and settings. Managed replacement adds 30% of base API cost per instance and approximately halves random hardware recovery time. Redundant capacity and balancer health checks can avoid a service interruption while a failed instance is replaced. Component incident causes require coverage of the affected component.

Queues can subscribe to notifications, media, search or all background jobs. Distribute splits a job stream among eligible queues. Each Broadcast queue receives its own copy, and its attached workers compete for the work. This creates separate consumer backlogs with capacity limits and expiration. A full destination can reject submissions. Queue state tracks aggregate jobs and does not model per-message acknowledgements or durable replay.

Database disk telemetry uses read-equivalent modeled IOPS. For a tier with a 420-unit read budget and a 115-unit write budget, a write contributes `420 / 115` read-equivalent units before index and replica overhead. These values represent simulation workload. The monitored Disk I/O ratio divides combined demand by effective disk capacity.
