# Approved implementation sequence

The owner approved this sequence and gave a green light for **Step 1 only** on November 1, 2026. Each step ends with tests, a reviewable result and a pause for the owner's next explicit green light. This file does not grant approval for subsequent steps.

| Step | Deliverable | Verification gate | Approval status |
| --- | --- | --- | --- |
| 1 | FastAPI foundation, settings, health routes, typed frontend contracts and fixtures. | Startup/config validation, health behavior, public-data boundaries, contract examples and lint. | Implemented and locally verified; awaiting owner review. |
| 2 | Supabase PostgreSQL connection, schema and migrations. | Disposable PostgreSQL migration/transaction checks and separately identified Supabase connection test. | Awaiting green light. |
| 3 | Twitch streamer OAuth and Extension-token authorization. | Invalid/expired/wrong-channel credentials, viewer/controller boundaries; separate live auth validation. | Awaiting green light. |
| 4 | Transcript intake and caption feasibility. | Retries, deduplication, ordering, stale state and a real caption-source test with the dashboard owner. | Awaiting green light. |
| 5 | Algorithmic passage/word ranking and quote candidates. | Source preservation, one exact blank, quality filters, repeats and reproducible fixture output. | Awaiting green light. |
| 6 | Conservative backend answer matcher. | Owner-reviewed typo/alias examples, short-word collisions, consistent outcomes and input preservation. | Awaiting green light. |
| 7 | Game lifecycle, private submissions, scoring and leaderboards. | Agreed rules, concurrent close/submit, retry-safe points, interim/final results. | Awaiting green light. |
| 8 | Live synchronization and frontend/deployment integration. | Reconnect/restart recovery, multiple viewers, real Twitch surfaces and actual device testing with teammates. | Awaiting green light. |

All new files live under `backend/`. No database, OAuth, caption collector, game endpoint, scoring engine or deployment is implemented by Step 1.

## Live verification after every step

The owner requested automatic live checks wherever feasible so they do not need to manually run verification. Before presenting a step for review:

1. Run the relevant automated tests and a real server/process check for the delivered behavior. Exercise actual HTTP endpoints where available.
2. Exercise real configured dependencies relevant to the step: PostgreSQL/Supabase transactions and persistence, Twitch authentication/captions, and later the connected application surfaces. Use isolated test records/resources and clean them up; do not alter unrelated data.
3. Keep the checks repeatable under `backend/scripts/` or integration tests. Record the commands, actual responses/results, and cleanup status in that step's verification report.
4. Distinguish unit tests, in-process HTTP tests, real-process HTTP tests, and external-service/device tests. A real local server check does not establish live Twitch or hosted Supabase behavior.
5. If external credentials or a test channel/device are unavailable, complete independent checks and report the exact gap. Do not claim full verification or require the owner to run checks the agent can run itself.

Step 1 already includes `scripts/smoke_test.py`, which starts a real loopback-only Uvicorn process, tests liveness/readiness/docs and the missing game route, then shuts down. Future steps extend or add scripts for their actual functionality. Owner review remains a green-light decision rather than a request to repeat these checks manually.

## Current technical decisions

- FastAPI with validated Python contracts; Supabase PostgreSQL supplies durable storage later.
- No runtime LLM. Use deterministic quote selection and conservative server-side normalization, explicit aliases and bounded Damerau–Levenshtein matching later.
- One service initially; no separate queue/worker dependency is added before a demonstrated need.
- The browser caption collector remains owned by the dashboard teammate.
- Planned endpoint names and payloads are a draft handoff. The running app advertises only implemented routes.

## Decisions still needed

Before dependent code: round timing/progression, score values/speed weighting, editing submitted answers, score-reset boundaries, candidate approval, equivalence thresholds, caption fallback, retention and hosting. Step 1 fixtures and opaque policy identifiers do not establish defaults.
