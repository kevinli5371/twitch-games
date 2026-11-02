# Approved implementation sequence

On November 1, 2026 the owner initially requested approval at each step, then explicitly superseded those gates: build the full backend, verify every stage with live checks, test schema changes in Docker before applying them remotely, fix failures and continue. Stop only for necessary owner input or external configuration; continue independent work while answers are pending.

| Step | Deliverable | Verification gate | Current status |
| --- | --- | --- | --- |
| 1 | FastAPI foundation, settings, health routes, typed frontend contracts and fixtures. | Startup/config validation, health behavior, public-data boundaries, contract examples and lint. | Implemented, verified and accepted. |
| 2 | Supabase PostgreSQL connection, schema and migrations. | Disposable PostgreSQL migration/transaction checks and separately identified Supabase connection test. | Locally verified and hosted Supabase connected. |
| 3 | Twitch streamer OAuth and Extension-token authorization. | Invalid/expired/wrong-channel credentials, viewer/controller boundaries; separate live auth validation. | Implemented and verified against real local HTTP/PostgreSQL; external checks below. |
| 4 | Transcript intake and caption feasibility. | Retries, deduplication, ordering, stale state and a real caption-source test with the dashboard owner. | Implemented and verified against real local HTTP/PostgreSQL; external checks below. |
| 5 | Algorithmic passage/word ranking and quote candidates. | Source preservation, one exact blank, quality filters, repeats and reproducible fixture output. | Implemented and verified against real local HTTP/PostgreSQL; external checks below. |
| 6 | Conservative backend answer matcher. | Owner-reviewed typo/alias examples, short-word collisions, consistent outcomes and input preservation. | Implemented and verified against real local HTTP/PostgreSQL; external checks below. |
| 7 | Game lifecycle, private submissions, scoring and leaderboards. | Agreed rules, concurrent close/submit, retry-safe points, interim/final results. | Implemented and verified against real local HTTP/PostgreSQL; external checks below. |
| 8 | Live synchronization and frontend/deployment integration. | Reconnect/restart recovery, multiple viewers, real Twitch surfaces and actual device testing with teammates. | Implemented and verified against real local HTTP/PostgreSQL; external checks below. |

All new files live under `backend/`. Those features were not implemented by Step 1; the current backend now implements persistence, OAuth, intake, algorithms, gameplay and synchronization. Browser caption collection, actual Twitch surfaces and public deployment remain external integration work.

## Live verification after every step

The owner requested automatic live checks wherever feasible so they do not need to manually run verification. Before presenting a step for review:

1. Run the relevant automated tests and a real server/process check for the delivered behavior. Exercise actual HTTP endpoints where available.
2. Exercise real configured dependencies relevant to the step: PostgreSQL/Supabase transactions and persistence, Twitch authentication/captions, and later the connected application surfaces. Use isolated test records/resources and clean them up; do not alter unrelated data.
3. Keep the checks repeatable under `backend/scripts/` or integration tests. Record the commands, actual responses/results, and cleanup status in that step's verification report.
4. Distinguish unit tests, in-process HTTP tests, real-process HTTP tests, and external-service/device tests. A real local server check does not establish live Twitch or hosted Supabase behavior.
5. If external credentials or a test channel/device are unavailable, complete independent checks and report the exact gap. Do not claim full verification or require the owner to run checks the agent can run itself.

Step 1 already includes `scripts/smoke_test.py`, which starts a real loopback-only Uvicorn process, tests liveness/readiness/docs and the missing game route, then shuts down. Future steps extend or add scripts for their actual functionality. Report results without requiring the owner to repeat executable checks manually; routine approval gates have been removed.

## Current technical decisions

- FastAPI with validated Python contracts; Supabase PostgreSQL is the durable storage target; local PostgreSQL verification comes first.
- No runtime LLM. Use deterministic quote selection and conservative server-side normalization, explicit aliases and bounded Damerau–Levenshtein matching later.
- One service initially; no separate queue/worker dependency is added before a demonstrated need.
- The browser caption collector remains owned by the dashboard teammate.
- Planned endpoint names and payloads are a draft handoff. The running app advertises only implemented routes.

## Decisions still needed

Gameplay decisions are recorded below and no longer require clarification. Supabase, Twitch Application credentials and Extension signing configuration have been verified. Remaining prerequisites are a captioned live test stream, installed Extension/frontend integration, actual device checks and hosting. Retention and a caption fallback remain open if required. Step 1 fixtures are not implemented policies.

## Confirmed gameplay rules (latest owner answers)

- Streamer starts each quote round manually; a 30-second timer closes it; streamer advances.
- Correct answers receive 1 point; incorrect answers receive 0. No speed bonus. Ties share ranks.
- Scores reset for each started game. Viewers may edit answers until the round closes.
- Quote selection is automatic. Spelling tolerance and streamer-managed aliases provide equivalence; no runtime LLM is required.

## November 2 extension of Step 3

The owner asked to continue implementation while setup questions are answered. Incorporate Jia Yi’s dashboard OAuth requirements: verified Twitch profiles, encrypted refreshable authorizations, 24-hour opaque sessions, explicit owner-controlled moderator grants, current per-operation permission checks, and rich `/api/v1/auth/me` workspace JSON. The owner explicitly confirmed `question_review` may see unrevealed answers; `live_control` and `settings` may not. Preserve the original quote-game rules when reconciling PR #1. See frontend-handoff.md and pr-1-reconciliation.md.

## Verification status on November 2

Real Twitch browser OAuth, verified identity, cross-workspace denial and refresh exchange passed. Local HTTP checks successfully exercised all 24 runtime operations, including matching, scoring, deadlines, restart recovery and permission revocation. See [endpoint-test-coverage.md](endpoint-test-coverage.md). Step 4 still needs observed real caption capture; Step 8 still needs installed Extension JWTs/PubSub, connected frontend and device/deployment verification. The broader three-mode product requirements on main are separate from the implemented quote runtime and remain subject to scope alignment.

## Supabase HTTPS change

The owner subsequently selected project URL + server secret for runtime storage. The complete HTTP adapter and atomic RPC migration pass isolated PostgreSQL/PostgREST verification; the real gateway accepts the key. Hosted RPC installation and HTTP-mode activation are now verified, including ready API, a removable hosted write probe and real dashboard session restoration. The actual caption-enabled stream/installed Extension E2E remains pending. See supabase-http-migration.md for exact implementation, migration and deployment status. This keeps Twitch auth and the agreed quote policies unchanged.
