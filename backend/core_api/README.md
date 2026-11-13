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
| `GET /{id}/finance` | Read the game ledger and projected daily operating rates |
| `GET /{id}/incidents` | Read the visible incident history |
| `POST /{id}/save` | Persist and return the current snapshot |
| `PUT /{id}/clock` | Set speed to 0, 1 or 3 |
| `POST /{id}/draft` | Start a draft from production |
| `PUT /{id}/diagram` | Save diagram positions, routes, and groups |
| `PUT /{id}/draft` | Persist an edited topology |
| `POST /{id}/draft/review` | Validate the draft or a supplied candidate topology and return the diff, costs and forecast |
| `POST /{id}/draft/discard` | Discard the draft |
| `POST /{id}/deployments` | Revalidate and deploy the saved draft |
| `POST /{id}/deployments/{deployment_id}/rollback` | Restore the topology before that deployment |
| `POST /{id}/features/{feature_id}` | Develop or release a feature |
| `GET /{id}/campaigns/{campaign_id}/forecast` | Preview campaign demand and availability |
| `POST /{id}/campaigns/{campaign_id}` | Start a campaign |
| `POST /{id}/incidents/drill` | Run a one-instance failure drill |
| `POST /{id}/incidents/{event_id}/acknowledge` | Mark an event as reviewed |
| `PUT /{id}/settings` | Persist onboarding and motion preferences |
| `POST /{id}/tutorial` | Record an inspection or telemetry visit |

Call `GET /api/games` first to establish the signed, HTTP-only guest cookie. Clients with a valid existing access token use account-scoped saves. Save creation takes a client-generated UUID so retries can reopen the same save. Gameplay mutations require a UUID `request_id`. Retry a failed or interrupted request with the same UUID and body. Replays cannot charge twice. Draft and deployment actions also take the latest architecture `revision`. A stale revision returns 409 and invalid game actions return 422.

## Simulation model

- One step represents ten in-game minutes. The server advances saves from elapsed time at the selected speed. At 1×, two real seconds represent one step. At 3×, three steps take two seconds. On return to a running save, at most two in-game days are simulated for a single elapsed gap. Paused saves retain their tick and any fractional progress.
- Demand is generated in operation cohorts from audience, scenario activity, daily variation, released features, campaigns and seeded events. CPU, RAM, network, connections, concurrency, disk I/O, database reads and writes, and storage affect throughput. Latency rises with resource pressure. Availability is successful throughput divided by incoming request rate.
- Traffic can pass through a limiter or balancer to an API. Writes go directly to a primary. Read-only cohorts prefer linked caches, then use the cache's explicit data edges on a miss. If the cache has no explicit data links, misses return through the originating API's database or replica links. A replica needs a primary subscription and adds replication write overhead.
- Successful foreground operations can submit background jobs to attached queues. Notifications and media jobs contribute job load. Workers process at the minimum of their CPU, RAM and concurrency limits, scaled by healthy instances. Queues absorb excess arrivals up to their capacity. New submissions fail on overflow. Retention expires a fraction of old work per step. Accepted jobs can wait beyond the response, and queue wait is estimated from backlog and worker throughput capacity.
- Monitoring exposes metrics for linked components with a collection slot. Service history mode reserves two slots and exposes historical metrics. Forecasts evaluate representative future workload ranges with the same engine, excluding future random incidents. Higher monitoring coverage narrows the range.
- Campaigns incur a one-time cost and acquire users along a growth curve. Organic growth and churn respond to service quality and feature appeal. The game bills infrastructure each step. Messenger subscription revenue varies with audience, satisfaction and features. Running topology changes that remove routing connections can briefly reduce throughput.
- Deployment rollback restores the earlier topology. Diagram positions, routes, and groups stay in the diagram. Runtime data on removed components is not recovered. Each save retains the last 20 deployments, 100 events and 144 history points.

### Diagram storage

`PUT /api/games/{id}/diagram` accepts `request_id` and a `diagram` object with `positions`, `routes`, and `groups`. Route keys are `source:target`. The game view returns this object independently of `production`, `draft`, and the topology revision. Existing saves have an empty diagram and render their stored topology positions. The existing JSON save column stores the diagram and deployment metric comparisons.

### Feature releases

Development checks feature prerequisites and budget. The API revalidates infrastructure against production under the save lock before release. Text and group messaging use a writable primary. Media uses primary database storage with at least 8 GB free at release. Voice messages and file sharing also need an API → Queue → Worker path. Search uses a primary with the message search index enabled. Calls use API signaling capacity of at least 40 MB/s and 1,500 connections per reachable API across its instances. These checks cover every API that receives traffic. Previously released features keep their saved release status and routing behavior. The new release rules apply to later releases.
