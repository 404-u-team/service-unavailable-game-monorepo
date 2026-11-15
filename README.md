# Service Unavailable

Service Unavailable is an infrastructure simulation game. Start a messenger, build and deploy its topology, release product features and decide when the service is ready for more users.

## Local development

Install [Docker Compose](https://docs.docker.com/compose/install/) and [Bun](https://bun.sh/) 1.4.2 or later.

```sh
cd backend/core_api
test -f .env || cp .env.example .env
docker compose up --build -d --wait
```

In a second terminal, from the repository root:

```sh
cd frontend
bun install --frozen-lockfile
bun --bun run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend forwards API requests to `http://127.0.0.1:8000` by default. Create a game, then use the spotlight guide to inspect the starter architecture and deploy monitoring. Guest saves belong to the current browser and persist in PostgreSQL.

If the game reports an incompatible catalog, check `docker compose ps` and open [the game catalog](http://127.0.0.1:8000/api/games/catalog). The current API includes `difficulties` and `diagram_layout: true`. Rebuild the API from the same checkout as the frontend with `docker compose up --build -d --wait`. If you changed `API_PORT`, set `CORE_API_URL` to the matching origin before starting the frontend.

To run the production frontend in Compose with the API and database, use the optional frontend file from `backend/core_api`.

```sh
docker compose -f docker-compose.yml -f docker-compose.frontend.yml up --build -d --wait
```

Open [http://localhost:3000](http://localhost:3000). Set `FRONTEND_ORIGIN` to the browser origin if it differs from `http://localhost` and the configured `FRONTEND_PORT`.

### Run the API without Docker

Use Python 3.14, Poetry, and a PostgreSQL database. From `backend/core_api`:

```sh
poetry install
psql "$DATABASE_URL" -f init.sql
poetry run uvicorn src.main:app --reload
```

Set `DATABASE_URL` to your PostgreSQL connection string before running those commands. The API applies its additive game tables on startup. The Compose setup retains the existing `postgres_data` volume and user tables.

### Design system

See [the UI package](packages/ui/README.md) to run the standalone Storybook and browse the workbench components and design tokens.

### Tests and production build

With the API running:

```sh
cd backend/core_api
TEST_GAME_API_URL=http://127.0.0.1:8000 poetry run python -m unittest discover -v
```

Omit `TEST_GAME_API_URL` to run the simulation tests without an API or database. Use a development database for integration tests, which create guest saves.

With the frontend and API running, from `frontend`:

```sh
bun --bun run check
bun test ./tests/*.unit.ts
bun --bun x playwright install chromium
bun --bun run test
bun --bun run build
```

Set `TEST_BASE_URL` to use a different frontend URL. Set `CHROMIUM_PATH` to use an installed Chromium. Set `VISUAL_OUTPUT_DIR` to save screenshots while running browser tests. For Firefox graph coverage, run `TEST_BROWSER=firefox bun --bun run test -g 'wheel and middle drag|canvas drag|production node dragging|inspector keeps'` with the Firefox build for your Playwright version.

For production, run `bun --bun run build` then `bun --bun run start` in `frontend`. Set `CORE_API_URL` to the API origin if the services are on separate hosts. Set the SvelteKit `ORIGIN` to the public HTTPS origin when deploying behind a proxy. Route `/api/games/{id}/live` upgrades to FastAPI with the original Host and Origin headers. Route ordinary requests to Bun. The stand includes this routing. Run FastAPI with the PostgreSQL connection string, a stable private `JWT_SECRET`, and `GAME_COOKIE_SECURE=true` for HTTPS.

## Self-hosted stand

From the repository root, prepare `.env`. Set `APP_ORIGIN` to the public HTTPS origin and use `openssl rand -hex 32` separately for `POSTGRES_PASSWORD` and `JWT_SECRET`. Keep the JWT secret across updates and restores so existing signed guest cookies can still open their saves.

```sh
test -f .env || (umask 077 && cp .env.example .env)
# Fill in .env before continuing.
docker network inspect intranet --format '{{.Name}}'
docker compose -f compose.stand.yaml config --quiet
docker compose -f compose.stand.yaml up -d --build --wait
```

In Nginx Proxy Manager Plus, add a Proxy Host for the domain in `APP_ORIGIN`. Set the scheme to **http**, the forward hostname to **service-unavailable**, and the forward port to **3000**. Choose a certificate on the SSL tab and enable **Force SSL**. Enable **WebSockets Support**. Send the whole host to the stand gateway. The gateway routes live upgrades directly to FastAPI and other requests to the Bun frontend, which forwards ordinary API calls. Only the gateway joins `intranet`. Bun, FastAPI and PostgreSQL use private networks. Compose publishes zero host ports. [Nginx Proxy Manager shared-network configuration](https://nginxproxymanager.com/advanced-config/)

```sh
docker compose -f compose.stand.yaml ps
docker compose -f compose.stand.yaml logs --tail=100 -f service-unavailable workbench core-api db
```

For updates, back up PostgreSQL, update the checkout and run the same `up -d --build --wait` command. FastAPI runs the additive database migration in a transaction under a PostgreSQL advisory lock before accepting requests. New stand databases start without development seed accounts.

PostgreSQL data lives in the `service-unavailable-stand_postgres_data` volume at `/var/lib/postgresql/data` in the database container. Ordinary Compose shutdown preserves it. Back up the database and protect a copy of `.env` separately.

```sh
umask 077
docker compose -f compose.stand.yaml exec -T db pg_dump -U postgres -Fc core_api > "service-unavailable-$(date +%F).dump"
```

To restore into an empty stand database, stop the application services, restore the dump and start the stack again.

```sh
docker compose -f compose.stand.yaml stop service-unavailable workbench core-api
docker compose -f compose.stand.yaml exec -T db pg_restore --exit-on-error -U postgres -d core_api < service-unavailable-YYYY-MM-DD.dump
docker compose -f compose.stand.yaml up -d --wait
```

To check connectivity from the proxy's network, use a disposable container after the stand is healthy.

```sh
docker run --rm --network intranet --entrypoint bun service-unavailable-stand-workbench \
  -e 'const r = await fetch("http://service-unavailable:3000/api/health"); console.log(await r.text()); if (!r.ok) process.exit(1)'
```

## Simulation and API

The [Core API reference](backend/core_api/README.md) describes persistence, clock behavior, component routing, forecasts, and the REST endpoints. [Messenger economy and balance](backend/core_api/BALANCE.md) explains monetization, regional demand, and the 35-day simulation results. Interactive API documentation is served at [http://localhost:8000/docs](http://localhost:8000/docs).

Messenger is playable at three difficulty settings. The other product scenarios are shown as unavailable. Choose English or Russian under Settings. The preference is saved in the browser.

## Architecture editor

Drag cards to rearrange the saved diagram. Production and Draft share the layout. New nodes appear in nearby open canvas space. Scroll to pan vertically, hold Shift for horizontal pan, and hold Ctrl to zoom around the pointer. Drag with the middle button to pan. The canvas also supports touch pan and pinch, zoom buttons, and Fit View. Use Ctrl/Cmd or Shift while clicking, Shift-drag to draw a selection box, or turn on **Select multiple** for touch input. Create a named group from the selection and use its header control to collapse or expand it.

Select a connection and choose **Add waypoint**. Drag the point to route around components, or use the arrow keys to nudge the focused point. Remove it with Delete or its context menu. **Reset route** restores obstacle-aware routing. These diagram changes save independently of Draft. Add, reconnect, and remove actual connections through Draft and deploy them to affect requests.

Monitoring links collect diagnostic metrics from their origin. Each linked component uses one collector slot. Service history reserves two slots and needs at least one linked component. Collectors at capacity recognize links in component-ID order. Add slots or distribute coverage across collectors when links exceed capacity.

Resource history records individual utilization measurements and peak load for components covered by a collector in Service history mode. Gaps show ticks without a recorded reading. Deployment comparisons report monitored resource pressure at the time of the deployment.

A database starts at 155 read and 62 write compute units per simulated second on two vCPUs and 8 GB RAM. Disk I/O has a shared budget. NVMe gives it 45% more headroom at an additional 35% of base daily cost. CPU, RAM, connection pools, storage space and legacy throttles can constrain throughput separately. A replica shares eligible reads and replays committed writes using its own hardware. Each available follower adds 8% of base disk work to primary writes. The in-game **Database Guide** explains the metrics, cache and replica routing, and recommended links.

Press **Ctrl/Cmd + S** to flush layout changes and save, **Space** to pause or resume, and **1**, **2**, or **3** to select 1×, 3×, or 5×. Press **Escape** to close the current dialog or clear a canvas selection.


## Engineering research

Product includes five engineering projects: Service Decomposition, Domain Data
Separation, Database Query Optimization, Database Sharding and API Autoscaling.
Research unlocks settings; players still configure and finance infrastructure in
Draft → Review → Deploy. Universal APIs remain the default. Domain moves and
shard-count changes use paid, clock-driven preparation while production stays live.
The English/Russian Guide includes contextual help and an optional resumable
engineering walkthrough. See [Engineering mechanics and balance](backend/core_api/ENGINEERING.md)
for operation routing, migration assumptions, save compatibility and measured
one/two/four-primary write-scaling results.

## Portable saves

In **Saved games**, select **Export** to download a JSON file. In another browser or on another device, open **Saved games**, select **Import save**, choose the file, and check the preview. **Import as new save** creates a new copy each time. The file limit is 8 MB. A running save resumes from its exported simulation time when imported. To freeze the game at that point, pause before exporting.
