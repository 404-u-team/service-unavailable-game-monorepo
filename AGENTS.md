# Service Unavailable

Service Unavailable is a browser game about running Messenger, growing its audience, and building infrastructure that can serve it. Keep the existing simulation and guest saves playable.

- `backend/core_api/src/simulation` owns deterministic workload, routing, capacity, clock-driven progression, and the economy. REST schemas and routers live in `src/api`, use cases and live updates in `src/services`, and PostgreSQL access in `src/repositories`.
- `frontend/src/routes` provides the SvelteKit pages and API proxy. Shared components, localization, and API contracts live in `src/lib`. The workbench uses Svelte Flow for the architecture editor.
- Keep gameplay authoritative in Python. Compare topologies with the same workload, distinguish demand from capacity, respect monitoring coverage, and account for cash receipts, recognized revenue, recurring expenses, and purchases separately.
- Keep the deployed topology, editable draft, and diagram layout distinct. Groups, positions, viewports, and waypoints are visual edits and save independently of deployment.
- Add explicit request and response fields to the FastAPI and TypeScript contracts together. Preserve optimistic revision checks and transaction boundaries. WebSocket frames deliver simulation updates through the existing live protocol and use a full snapshot to resynchronize. Update the live field selection alongside REST fields when required.
- Keep persisted JSON and portable saves compatible with additive defaults or explicit migrations. Validate imported and legacy data. Use additive PostgreSQL migrations in the repository SQL and preserve existing volumes and signed guest identities.
- Localize visible strings through `t()` and `frontend/src/lib/ru.json`. Reuse shared components and theme styles, and verify keyboard, touch, and narrow layouts.
- From `frontend`, use `bun install --frozen-lockfile`, `bun --bun run dev`, `bun --bun run check`, `bun test ./tests/*.unit.ts`, `bun --bun run test`, and `bun --bun run build`. Use `TEST_BROWSER=firefox` for the Firefox run.
- From `backend/core_api`, use Python 3.14 and `poetry run python -m unittest discover -v`. With a development PostgreSQL and FastAPI running, set `TEST_GAME_API_URL` to run the API integration suite. Add regression tests for significant gameplay, save, and UI changes.
- The production stand is defined in `compose.stand.yaml`. Only the gateway joins external `intranet`. It routes live WebSocket upgrades to FastAPI and ordinary traffic to Bun. See the root README for setup and backups.
- Verify changes before committing and pushing to `origin/master`. Use direct commits and pushes, avoid force pushes, and open a PR only when explicitly requested. Report incomplete work and checks that could not run.
