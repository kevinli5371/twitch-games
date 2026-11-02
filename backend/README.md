# Twitch Games backend

FastAPI + Supabase PostgreSQL backend for the native Twitch quote-completion Extension. All backend code, migrations, configuration, tests and handoff documents live here. This README describes the implemented quote runtime. Newer root product documents describe additional three-game workflows; see the scope-alignment note in `docs/pr-1-reconciliation.md` before treating those as implemented.

## Implemented

- Twitch authorization-code login, verified profiles, encrypted access/refresh tokens, rotating opaque HttpOnly sessions, CSRF checks, startup/hourly token validation and serialized refresh. No Supabase Auth.
- Owner-controlled moderator grants: `question_review`, `live_control`, `settings`. Every protected operation checks current database grants. Owners alone manage grants. Question review may see hidden answers; other grants cannot.
- Private PostgreSQL schema and versioned Alembic migrations; no automatic migration at API startup.
- Authenticated current-stream registration via Helix; retry-safe caption batches with source evidence and current-stream isolation.
- Algorithmic quote selection and backend spelling/alias matching. No runtime LLM or transcription provider.
- Manual round starts, actual 30-second closure, manual advancement, editable private answers, atomic scoring, shared ranks and final leaderboards.
- Persistent deadlines and state versions; restart recovery; durable/coalesced Twitch PubSub notifications containing only channel/version information.
- Runtime OpenAPI, frontend handoff, Docker packaging and repeatable real-server/database verification.

This implements the backend for quote mode. The viewer and dashboard Live game workspace now call this API; see root docs/fullstack-integration.md. The original planning UI remains a fixture. Niche, hive mind, ad triggers, VOD import, bank scheduling and audio transcription are not implemented. The broader PR #1 planning tabs remain fixture previews.

Read [frontend handoff](docs/frontend-handoff.md), [current API](docs/openapi.json), [implementation plan](docs/implementation-plan.md), [verification](docs/backend-verification.md), and [PR #1 reconciliation](docs/pr-1-reconciliation.md).

## Confirmed rules

The streamer starts each round. The database records an exact 30-second window. The timer closes/scorers finalize it; the streamer advances manually. An early close/end during answering is rejected, preserving that window. There is no pause/skip policy in this release.

Correct: 1 point. Incorrect: 0. No speed bonus. Latest accepted answer revision wins. Retries preserve the original receipt; edits require a new request ID. Scores reset for each started game; ties share ranks. Questions are selected automatically from current-stream text, with immutable round quotes/answers/aliases/policy snapshots.

The owner subsequently confirmed moderator access: `question_review` may see unrevealed answers. `live_control` and `settings` alone may not. App grants are distinct from a Twitch moderator badge; a badge alone grants no privileged backend access.

## Supabase HTTPS storage

The owner selected project URL + server secret for runtime connectivity. Install tested migration `0005_http_rpc` before setting `TWITCH_GAMES_STORAGE_BACKEND=supabase_http`. See [migration/setup and verification](docs/supabase-http-migration.md) and [SQL-editor install](docs/supabase-http-install.sql). The hosted gateway has accepted the configured key; hosted RPC installation/activation is still pending. SQL mode remains available for local Docker tests and migration tooling. Existing game and Twitch authentication contracts are unchanged.

## Setup

From `backend/`, using Python 3.12–3.14 (verified with 3.14.3):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' -c requirements-dev.lock
cp .env.example .env
```

Fill `.env` locally; it is Git-ignored and excluded from the Docker build. Configuration is read from the environment and `.env` in the current working directory. Run from `backend/`.

| Variable | Purpose |
| --- | --- |
| `TWITCH_GAMES_STORAGE_BACKEND` | `postgres` (default) or `supabase_http` after migration. |
| `TWITCH_GAMES_SUPABASE_URL` | HTTPS project URL for the selected HTTP runtime. |
| `TWITCH_GAMES_SUPABASE_SECRET_KEY` | Server secret key, kept only in FastAPI. |
| `TWITCH_GAMES_DATABASE_URL` | Supabase PostgreSQL URI, with explicit TLS. Direct/session-pooler URI recommended for migrations. |
| `TWITCH_GAMES_TWITCH_CLIENT_ID` | OAuth Application Client ID for dashboard login and public Helix lookups. |
| `TWITCH_GAMES_TWITCH_CLIENT_SECRET` | OAuth Application Client Secret, server-only. |
| `TWITCH_GAMES_TWITCH_REDIRECT_URI` | Exact registered backend callback. Dev: `http://localhost:8000/api/v1/auth/twitch/callback`. |
| `TWITCH_GAMES_TOKEN_ENCRYPTION_KEY` | Stable Fernet key protecting stored access/refresh tokens. |
| `TWITCH_GAMES_TWITCH_EXTENSION_CLIENT_ID` | Extension Client ID. |
| `TWITCH_GAMES_TWITCH_EXTENSION_SECRET` | Base64 shared **Secret Keys → Key**, not the OAuth Client Secret. |
| `TWITCH_GAMES_TWITCH_EXTENSION_OWNER_ID` | Numeric ID of the Extension creator. The Application may have a different owner. |
| `TWITCH_GAMES_DASHBOARD_URL` | Fixed successful-login destination. Dev for PR #1: `http://localhost:4173`. No browser-supplied return URL is used. |
| `TWITCH_GAMES_CORS_ORIGINS` | JSON list of exact frontend origins; include the dashboard and actual Extension origin. Default `[]`. |
| `TWITCH_GAMES_ENVIRONMENT` | `local` (default), `test`, or `production`. |
| `TWITCH_GAMES_DOCS_ENABLED` | Default `true`; must be `false` in production. |
| `TWITCH_GAMES_DATABASE_CONNECT_TIMEOUT_SECONDS` | Default 3; allowed 1–30. |
| `TWITCH_GAMES_DATABASE_POOL_SIZE` | Default 5, no overflow; allowed 1–20. |

The Application and Extension can belong to different teammates. The Extension owner ID must match the Extension owner. Neither credential set determines which streamer is signed in: verified Twitch identity determines that.

Generate the encryption key once:

```sh
.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

SQL mode needs no Data API key. HTTP mode uses the server secret above; neither mode adds Supabase Auth or an AI key. `TWITCH_GAMES_TEST_TWITCH_BASE_URL`, `TWITCH_GAMES_TEST_SUPABASE_HTTP_URL` and `TWITCH_GAMES_TEST_DATABASE_URL` are test-harness-only; do not add them to ordinary `.env` files. The HTTP provider override is restricted to test-mode loopback.

Read-only Twitch checks and explicit owner-ID setup:

```sh
.venv/bin/python scripts/check_twitch.py --owner-login EXTENSION_OWNER_LOGIN --save-owner-id --check-extension
```

This checks app credentials and an Extension authentication endpoint without sending Twitch messages. Actual viewer tokens, browser authorization, PubSub reception and captions require connected Twitch surfaces.

## Migrations and run

```sh
.venv/bin/alembic upgrade head
.venv/bin/python -m uvicorn twitch_games.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Disable access logs so OAuth callback query codes are not logged. Do not enable SQL parameter logging. The backend never prints credentials through health/error responses.

- `http://localhost:8000/health/live`: process health.
- `http://localhost:8000/health/ready`: database revision and credential configuration; 503 when incomplete. Configuration readiness does not prove real caption delivery or device testing.
- `http://localhost:8000/docs`: implemented API, development only.
- `http://localhost:8000/api/v1/auth/twitch`: dashboard login.
- `http://localhost:8000/api/v1/auth/me`: verified user/workspace/session JSON after login.

The canonical schema is `twitch_games`. Do not apply PR #1's independent `game_private` SQL alongside these migrations as a second game/auth authority. See reconciliation notes first. Migrations refuse an unmanaged nonempty application schema.

## Verification

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q -m 'not integration' -W error
.venv/bin/python scripts/postgres_checks.py
.venv/bin/python scripts/docker_image_checks.py
.venv/bin/python scripts/check_supabase.py
```

`postgres_checks.py` requires Docker and Node 22+ for actual JavaScript client checks. It provisions disposable loopback PostgreSQL, tests migration upgrades/downgrades and legacy session preservation, runs all tests, then starts a real Uvicorn server for a full game. It verifies real HTTP OAuth, moderator grants, refresh/revocation, a true 30-second timer, a process restart, scoring and final standings. Twitch in that script is an explicitly identified HTTP fixture. Containers and test records are cleaned up.

After Docker verification, the hosted additive migration and a temporary rolled-back write can be checked with:

```sh
.venv/bin/python scripts/check_supabase.py --apply-migrations --exercise-writes
```

Never point disposable integration tests or migration downgrades at hosted Supabase. Hosted checks preserve unrelated data.

## Deployment

`Dockerfile` pins the verified Python base image and runs as a non-root user. Environment files never enter the image. The Docker healthcheck probes liveness; configure platform readiness separately. Migrate explicitly before starting the new revision. A continuously running service is required for deadline closure and retry workers; their state is in PostgreSQL and survives process restarts.

Use HTTPS, production mode, disabled docs, exact CORS origins, and matching registered callback/dashboard URLs. The HttpOnly cookie uses `SameSite=Lax`; serve dashboard and API on the same site (or reverse proxy API requests). On localhost, use `localhost` consistently rather than mixing it with `127.0.0.1`. CSRF tokens come from `/auth/me` and are required for cookie-authenticated POST/PUT/DELETE requests.

Hosting/domain selection and actual desktop/iOS/Android Twitch surfaces remain external integration work. Do not claim deployment, caption-source feasibility, Twitch approval or device testing from the automated local checks.

The Docker verifier now runs the API suite through both SQL and actual PostgREST HTTP storage. Its fake API-key gateway models Supabase gateway authentication only; SQL/RPC execution uses the official pinned PostgREST image. All test keys are synthetic, loopback-only and isolated from `.env`.
