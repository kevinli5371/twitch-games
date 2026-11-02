# Backend verification — November 2, 2026

## Actual observations

- macOS arm64, Python 3.14.3: 144 automated tests (plus 10 subtests) passed against an isolated PostgreSQL 17.11 Docker instance. This includes unit/contract checks and real PostgreSQL integration checks; in-process API tests are not labelled live Twitch tests.
- Alembic upgrade, repeat upgrade, downgrade to base and upgrade passed. The dashboard-auth migration also preserved a synthetic legacy encrypted session through 0003 → 0004 → 0003 → 0004. The disposable test container/data were removed.
- A real Uvicorn process handled HTTP OAuth callbacks/cookies, CSRF, moderator grants and revocation, hidden-answer boundaries, refresh-token rotation/revocation, caption intake and retries, automatic quote selection, private answer edits and receipt retries, the actual 30-second timer, an actual process restart, scoring, tied ranks, final results, per-game reset and request body limits.
- Twitch for those server tests is a real loopback HTTP provider **fixture**, not Twitch production. Its synthetic credentials never authorize a deployed service. The fixture override is limited to test-mode loopback.
- Scoring integration includes 150 participants, correct/incorrect points, idempotent finalization, shared ranks and restoration of an individual's rank outside the top 100. Round quote/answer/alias snapshots are frozen.
- Supabase connectivity was verified over explicitly required TLS. Additive migrations were applied only after isolated Docker verification. An insert was rolled back and absence of the probe record was checked. Client roles lack private-schema access. No hosted downgrade/disposable-test suite was run.
- Actual Twitch Application credentials were verified using a client-credentials token and `/validate`; public Helix user lookup succeeded. Actual Extension signing credentials plus the configured creator's numeric ID were accepted by the read-only `/extensions/jwt/secrets` endpoint (HTTP 200). Returned key material was not logged.
- The production-mode Docker image was built for Linux arm64 and probed over loopback HTTP: live 200, incomplete-config ready 503, docs 404, unauthenticated game state 401. Runtime UID is 10001 and `.env` is absent from the image. See the image-check script for repeatable checks.

- A real browser Twitch authorization-code flow completed successfully against the configured Application. The backend callback created a Supabase session and redirected to the configured dashboard destination. Authenticated `/api/v1/auth/me` returned the verified account, owned channel and owner permissions; access to a different ungranted workspace returned `forbidden`.
- A real Twitch refresh-token exchange and subsequent new-access-token validation succeeded through the implemented refresh path. The first expired-access validation result was forced locally to exercise that path; token exchange and identity validation used Twitch production. Updated tokens remained encrypted in Supabase, and the same authenticated browser session remained valid.
- The local dashboard preview on port 4173 was not running during the login check. Its connection-refused page occurred after the backend's successful callback, not instead of that callback.

All 24 documented runtime API operations had successful real HTTP cases. The live check now fails when a documented operation is unexercised. See [endpoint-test-coverage.md](endpoint-test-coverage.md) for the observed method/path/status matrix.

## Commands

Run from `backend/`:

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q -m 'not integration' -W error
.venv/bin/python scripts/postgres_checks.py
.venv/bin/python scripts/docker_image_checks.py
.venv/bin/python scripts/check_supabase.py --apply-migrations --exercise-writes
.venv/bin/python scripts/check_twitch.py --owner-login EXTENSION_OWNER_LOGIN --check-extension
```

Real-server checks isolate their working directory and configuration from the developer's `.env`. Test PostgreSQL URIs must point to a loopback database whose name ends in `_test`. Host/URI/password values are not printed. Docker resources and test data are cleaned up in `finally` blocks.

## Limits

The real Twitch browser consent/callback and refresh exchange are observed above. Viewer-issued Extension JWTs, PubSub reception on an installed Extension, live caption availability, frontend integration and desktop/iOS/Android behavior remain unverified. Actual OAuth revocation was tested with the HTTP fixture, not by disconnecting the user’s real Twitch integration. The frontend owners must supply working surfaces and a caption-enabled test stream for those observations. No universal transcript or fallback audio-capture implementation is claimed.

Production hosting/domain, callback/CORS values and real HTTPS cookie behavior remain deployment integration work. The image is packaged locally; no public deployment is claimed. Readiness verifies the database revision and configuration, not a complete Twitch experience.

## Main-branch reconciliation

Merged main at `9b16fec` (PR #1), preserved its dashboard and pure planning utilities, and replaced the duplicate API entry point with a compatibility alias to the implemented factory. The proposed legacy SQL is retained as documentation. After reconciliation, 144 Python tests plus 10 subtests and all 10 Node dashboard/preview tests passed; real HTTP auth/gameplay and migration checks passed again. The preview now rejects encoded backslash paths consistently on macOS and Windows-style paths. Product-policy differences with the newer main specification are flagged for review in pr-1-reconciliation.md.
