# Step 2 — PostgreSQL persistence verification

Verified November 1, 2026, on Python 3.14.3 and isolated PostgreSQL 17.11 in Docker. Hosted Supabase verification is pending the owner's database URI; no hosted migration or connectivity claim is made yet.

## Implemented

- SQLAlchemy/Psycopg connection pooling, secret PostgreSQL URI settings, explicit remote TLS requirement, bounded connect/pool timeouts and transaction commit/rollback handling.
- Alembic migrations and frozen SQL in a private `twitch_games` schema. Eleven business tables cover channels, participants, streams, caption batches/segments, quote candidates/source links, games, rounds, submissions and score entries.
- Composite foreign keys reject mismatched channel/stream/game identities. Database uniqueness constraints prevent duplicate request records and repeated point awards. Numeric scores and policies are required data, not selected gameplay defaults.
- Private-schema client grants are revoked and row-level security is enabled on business tables. The trusted database owner is expected to be privileged; later FastAPI authorization must still enforce channel/player access.
- Live readiness reports `not_configured`, `unavailable`, `migration_required` or `ok` for PostgreSQL, while overall readiness stays HTTP 503 because auth/gameplay are not implemented yet.
- Repeatable Docker verification and a separate hosted connection/migration/rollback probe. The hosted probe never runs destructive downgrade tests.

## Executed checks

`python scripts/postgres_checks.py` created an isolated loopback PostgreSQL container, used nonprivileged stand-in client roles, applied the migration twice, and ran **86 tests** with warnings as errors: **68 foundation/config/contract tests and 18 live PostgreSQL tests**. All passed.

Database checks covered source/answer preservation; request uniqueness; duplicate and concurrent duplicate score rejection; cross-channel/stream constraints; policy identity; quote blank spans including long Unicode text; mandatory policies; competing active sessions; client-role read/write denial; RLS with temporary grants; rollback; persistence through pool disposal/new connections; and migration/readiness states.

Real Uvicorn processes were started and stopped over loopback to verify the database states `ok`, `unavailable`, `migration_required`, and `not_configured`. They returned HTTP 200 for liveness/docs, HTTP 503 for overall readiness with the correct database substatus, and HTTP 404 for unimplemented game routes.

The script exercised migration **up → repeat up → down → up**. It verified that downgrade removed business tables, then restored the schema. Its disposable container and anonymous data volume were removed in cleanup. This is real PostgreSQL and real HTTP validation, not an SQLite substitution or an in-process-only mock.

## Hosted boundary

Provide `TWITCH_GAMES_DATABASE_URL` locally in `.env`. `scripts/check_supabase.py` can verify a TLS connection; `--apply-migrations --exercise-writes` applies the app schema and checks a rolled-back probe insert. Direct or session-pooler URLs are appropriate for migrations. A Supabase HTTPS project URL/API key is a different connection method and is not used for these SQL transactions.

No Twitch authentication, actual captions, viewer devices, matching, game behavior or deployment was verified by this stage. Further routine approval gates were explicitly removed by the owner; implementation continues while external configuration is pending.
