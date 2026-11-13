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

Open [http://localhost:5173](http://localhost:5173). The frontend forwards API requests to `http://127.0.0.1:8000` by default. Create a game, choose a speed in the header, and select the Messenger API in Topology to begin onboarding. Guest saves belong to the current browser and persist in PostgreSQL.

If New game reports an incompatible catalog, check `docker compose ps` and open [the game catalog](http://127.0.0.1:8000/api/games/catalog). The current API includes a `difficulties` field. Stop any older local API listening on the same port and run `docker compose up --build -d --wait` again. If you changed `API_PORT`, set `CORE_API_URL` to the matching origin before starting the frontend.

To run the production frontend in Compose with the API and database, use the optional frontend file from `backend/core_api`.

```sh
docker compose -f docker-compose.yml -f docker-compose.frontend.yml up --build -d --wait
```

The Bun frontend listens on port 3000 by default.

### Run the API without Docker

Use Python 3.14, Poetry, and a PostgreSQL database. From `backend/core_api`:

```sh
poetry install
psql "$DATABASE_URL" -f init.sql
poetry run uvicorn src.main:app --reload
```

Set `DATABASE_URL` to your PostgreSQL connection string before running those commands. The API applies its additive game tables on startup. The Compose setup retains the existing `postgres_data` volume and user tables.

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
bun test ./tests/routing.unit.ts
bun --bun x playwright install chromium
bun --bun run test
bun --bun run build
```

Set `TEST_BASE_URL` to use a different frontend URL. Set `CHROMIUM_PATH` to use an installed Chromium. Set `VISUAL_OUTPUT_DIR` to save screenshots while running browser tests.

For production, run `bun --bun run build` then `bun --bun run start` in `frontend`. Set `CORE_API_URL` to the API origin if the services are on separate hosts. Set the SvelteKit `ORIGIN` to the public HTTPS origin when deploying behind a proxy. Run FastAPI with the PostgreSQL connection string, a stable private `JWT_SECRET`, and `GAME_COOKIE_SECURE=true` for HTTPS.

## Simulation and API

The [Core API reference](backend/core_api/README.md) describes persistence, clock behavior, component routing, forecasts, and the REST endpoints. Interactive API documentation is served at [http://localhost:8000/docs](http://localhost:8000/docs).

Messenger is playable at three difficulty settings. The other product scenarios are shown as unavailable. Choose English or Russian under Settings. The preference is saved in the browser.

## Architecture editor

Drag cards to rearrange the saved diagram. Use Ctrl/Cmd or Shift while clicking, Shift-drag to draw a selection box, or turn on **Select multiple** for touch input. Create a named group from the selection and use its header control to collapse or expand it.

Select a connection and choose **Add waypoint**. Drag the point to route around components, or use the arrow keys to nudge the focused point. Remove it with Delete or its context menu. **Reset route** restores obstacle-aware routing. These diagram changes save independently of Draft. Add, reconnect, and remove actual connections through Draft and deploy them to affect requests.

Monitoring links collect diagnostic metrics from their origin. Each linked component uses one collector slot. Service history reserves two slots and needs at least one linked component. Collectors at capacity recognize links in component-ID order. Add slots or distribute coverage across collectors when links exceed capacity.

A database starts at 155 reads and 62 writes per simulated second on two vCPUs, 8 GB RAM, and SSD. CPU scales both limits with a diminishing return. RAM raises read capacity, and NVMe raises I/O limits at an additional 35% base daily cost. Connection limits can restrict admission. Existing read/write settings are retained as throttles capped by the derived hardware capacity. Replication lag is estimated from replica pressure and primary availability, with an 8% primary write overhead per attached reachable replica.
