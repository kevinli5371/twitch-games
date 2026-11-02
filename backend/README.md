# Twitch Games backend

Python + FastAPI backend for the quote-completion Twitch Extension. Supabase PostgreSQL is the selected database. All new backend code, configuration, tests, generated contracts and documentation live in this directory.

## Current status — Step 1 foundation

Implemented: application factory, validated environment settings, explicit-origin CORS configuration, liveness/readiness endpoints, public/private/dashboard Pydantic contracts, artificial frontend fixtures, a planned OpenAPI handoff, and automated tests.

**Not implemented:** database connection/migrations, Twitch OAuth or Extension authentication, caption capture/intake, quote selection, answer matching, scoring, game routes, live messaging, or deployment. No live Twitch/Supabase integration or mobile-device behavior has been verified.

The runtime deliberately returns **503 from readiness**, because the game dependencies do not exist yet. Liveness returns 200 when the foundation process is running. Game routes return 404 rather than fake successful responses.

The [implementation plan](docs/implementation-plan.md) records the owner's step-by-step approval requirement. Step 2 must wait for a new green light.

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

Optionally copy `.env.example` to `.env`. No credentials are needed for Step 1. Do not add Twitch, Supabase, database or model credentials to fixtures, Git, or viewer code.

```sh
.venv/bin/python -m uvicorn twitch_games.main:app --host 127.0.0.1 --port 8000
```

Local URLs:

- `http://127.0.0.1:8000/health/live` — process liveness, HTTP 200.
- `http://127.0.0.1:8000/health/ready` — honest dependency readiness, HTTP 503 in Step 1.
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

Supabase/Auth settings are intentionally deferred to their approved steps, rather than accepting unused credentials now.

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

## Open product decisions

Do not assign defaults for point values/speed weighting, round duration/progression, answer revisions, game/stream score resets, question approval, synonym rules, or transcript fallback. These are explicitly unresolved. A required `policy_id` in the draft start-game contract references a future agreed policy; no policies exist yet. The example score of 1 and `closes_at: null` are fixture data, not adopted gameplay rules.
