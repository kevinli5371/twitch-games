# Twitch Games backend

Python + FastAPI backend for the quote-completion Twitch Extension. Supabase PostgreSQL is the selected database. All new backend code, configuration, tests, generated contracts and documentation live in this directory.

## Current status — persistence foundation

Implemented: application factory, validated environment settings, explicit-origin CORS configuration, liveness/readiness endpoints, public/private/dashboard Pydantic contracts, artificial frontend fixtures, a planned OpenAPI handoff, and automated tests.

**Persistence implemented and tested:** PostgreSQL connection/transactions, private-schema migrations, database constraints and live readiness. See [Step 2 verification](docs/step-2-verification.md). Hosted Supabase needs a configured connection URI. Twitch auth, intake, matching, gameplay, live messaging and deployment remain later work.

The runtime returns **503 from overall readiness** while authentication/gameplay remain unfinished; its database field reports the actual configured connection and migration state. Liveness returns 200 when the foundation process is running. Game routes return 404 rather than fake successful responses.

The [implementation plan](docs/implementation-plan.md) records the owner's updated instruction: build the full backend with automatic verification between stages; pause only for necessary input or external configuration.

Each step also requires agent-run real-server and relevant live integration checks wherever feasible, with commands/results documented separately from unit tests. The owner should not need to manually repeat checks that can be automated. Missing external credentials or test resources must be disclosed explicitly.

## Product decisions carried forward

- Desktop: native Twitch Extension over the video, not a browser extension or OBS graphics.
- Mobile: Twitch's separate mobile Extension view.
- Viewers submit private free text through our UI, normally completing one missing word.
- Streamer chooses when to activate the game; interim and final results/leaderboards are required.
- Kevin owns the backend; the dashboard teammate owns the browser-side caption collector.
- Quote selection and answer evaluation are **algorithmic, with no runtime LLM**. Later steps will add deterministic passage/word ranking and a conservative server-side matcher with normalization, approved aliases and bounded Damerau–Levenshtein typo handling. No matching threshold or score policy is implemented by Step 1.
- Captions remain conditional and unverified. A caption event is not a universal transcript endpoint.
- Niche, hive mind, automatic ad/event triggers, public-chat answers and VOD import are deferred.

These later algorithmic and approval decisions supersede earlier model/worker proposals in the original [product spec](../docs/product-spec.md) and [backend scope](../docs/backend-scope.md). Start with one service; add separate processing infrastructure only when justified by the actual workload.

## Local setup

Run from the repository root:

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' -c requirements-dev.lock
```

Python 3.12–3.14 is declared supported by the project metadata. The checked dependency snapshot and verification report state which interpreter was actually tested; other versions/platforms are not implicitly verified. `requirements-dev.lock` pins the tested application/test dependency set. Build tooling follows the range in `pyproject.toml`.

Optionally copy `.env.example` to `.env`. Database connectivity requires the PostgreSQL URI described below; omitting it keeps liveness available and reports the database as not configured. Do not add Twitch, Supabase, database or model credentials to fixtures, Git, or viewer code.

```sh
.venv/bin/python -m uvicorn twitch_games.main:app --host 127.0.0.1 --port 8000
```

Local URLs:

- `http://127.0.0.1:8000/health/live` — process liveness, HTTP 200.
- `http://127.0.0.1:8000/health/ready` — honest dependency readiness, HTTP 503 until all required integrations are ready.
- `http://127.0.0.1:8000/docs` — interactive documentation of **implemented health routes only**.
- `http://127.0.0.1:8000/openapi.json` — runtime OpenAPI, not the planned game API.

## Configuration

Settings are read from process environment and then `.env` in the current working directory. Run from `backend/` so the intended `.env` is used. Unknown entries in that file are rejected. Tests isolate environment variables and dotenv loading.

| Variable | Default | Meaning |
| --- | --- | --- |
| `TWITCH_GAMES_ENVIRONMENT` | `local` | `local`, `test`, or `production`. |
| `TWITCH_GAMES_DOCS_ENABLED` | `true` | Enables `/docs` and runtime `/openapi.json`. |
| `TWITCH_GAMES_CORS_ORIGINS` | `[]` | JSON array of exact origins; empty grants no browser cross-origin access. |

Example local origin: `["http://localhost:5173"]`. CORS is not authentication. Wildcards, credentials embedded in URLs, paths, queries and fragments are rejected. Production settings require docs disabled and explicit HTTPS origins. This is configuration validation, not a claim that the unfinished application is production-ready.

## Database configuration and migrations

Set `TWITCH_GAMES_DATABASE_URL` in `.env` to a PostgreSQL URI. Remote URIs must explicitly use `sslmode=require`, `verify-ca` or `verify-full`. Direct/session-pooler URIs work for migrations; transaction-pooler prepared statements are disabled by the driver configuration. `TWITCH_GAMES_DATABASE_CONNECT_TIMEOUT_SECONDS` defaults to 3, and `TWITCH_GAMES_DATABASE_POOL_SIZE` defaults to 5 with no overflow. Database URLs are secret settings and are not returned by health checks.

```sh
.venv/bin/alembic upgrade head
.venv/bin/python scripts/check_supabase.py
```

The API never creates/migrates the database automatically. The migration CLI refuses an unmanaged nonempty application schema. All business tables are in private `twitch_games`, not `public`, with no direct client policies. Keep database credentials on the server; OAuth/JWT channel authorization is still required at the API layer.

Hosted connection checks are read-only by default. To apply this app's schema and verify a temporary rolled-back insert after isolated Docker validation:

```sh
.venv/bin/python scripts/check_supabase.py --apply-migrations --exercise-writes
```

Never run the integration test suite or migration downgrades against the hosted project. The Docker script creates and removes its own disposable loopback-only database:

```sh
.venv/bin/python scripts/postgres_checks.py
```

This runs the real PostgreSQL tests plus real server HTTP probes through all database readiness states. The standalone smoke script also accepts `--database-status ok` for an explicitly configured, migrated connection. No Docker database is required for production; Supabase is the hosted target.

## Frontend handoff

Read [contracts and examples](docs/contracts.md). The [planned OpenAPI](docs/openapi.planned.json) and [artificial JSON fixtures](docs/examples.json) let both frontend teammates build without depending on invented live endpoints. Every planned operation is marked `x-implementation-status: planned`.

Regenerate the checked-in handoff after changing contract models:

```sh
.venv/bin/python -m twitch_games.contracts.export
```

Canonical answers and source passages belong only in privileged dashboard contracts before reveal. Public answering-state contracts reject those fields. A submission receipt acknowledges receipt only; it does not say whether the answer is correct.

## Checks

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
.venv/bin/python scripts/smoke_test.py
```

The test suite covers configuration failure, health truthfulness, CORS origin boundaries, unimplemented game routes, public/private contract separation, input preservation, cross-channel/stream consistency and reproducible contract exports. See [Step 1 verification](docs/step-1-verification.md) for actual results and limitations.

The smoke test starts and stops a real Uvicorn process bound only to `127.0.0.1`, using an ephemeral port and isolated test configuration. It needs local socket permission and makes no calls to Twitch or Supabase.

## Confirmed gameplay and remaining setup

The owner selected manual round starts, automatic 30-second closure, manual advancement, 1 point for correct/0 for incorrect, no speed bonus, shared tie ranks, per-game score reset, and editable answers until closure. Quotes are automatically selected, with spelling tolerance and streamer-managed aliases. These rules will be implemented in the subsequent game stages; existing fixtures are still artificial and do not constitute working gameplay.

Remaining external setup includes the hosted database URI, Twitch OAuth/Extension credentials, a captioned test channel and deployment configuration. Caption fallback and retention remain to be resolved if needed.
