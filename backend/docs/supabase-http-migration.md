# Supabase HTTPS migration — in progress

The owner requested switching runtime storage to the Supabase project URL and server secret key on November 2, 2026. This does not introduce Supabase Auth or browser access to private data.

## Actual status

Branch `backend/supabase-http` starts from connected-client PR #4. Validated `TWITCH_GAMES_SUPABASE_URL` / `TWITCH_GAMES_SUPABASE_SECRET_KEY`, an HTTPS preflight transport and a credential-safe check script are implemented. The project URL was derived and saved only in ignored `.env`. A real unauthenticated HTTPS request returned 401, confirming gateway reachability; the server key is still missing.

**The running SQL backend has not switched.** New configuration alone is insufficient. Existing SQL tests do not establish an HTTP storage implementation. No unfinished storage selector or automatic fallback is advertised.

## Transaction boundaries to port

PostgREST gives each HTTP request its own transaction. Replacing a current SQL transaction with several REST calls would lose its locks and rollback guarantees. Preserve the existing frontend API, Twitch OAuth, private schema, quote rules and conservative Python matching.

| Responsibility | Required HTTP boundary |
| --- | --- |
| OAuth states, profiles, opaque sessions and revocation | Narrow atomic RPCs; keep token encryption in FastAPI. |
| Twitch token refresh | Per-user claim/version fencing around external refresh, protected completion, existing hourly/startup validation. |
| Workspace/grant administration | Verified actor and current grants checked inside each operation; owner-only grant mutations. |
| Public/private/dashboard reads | Separate result shapes, channel isolation, no unrevealed fields in public responses. |
| Caption intake | Atomic batch checksum/dedup/source storage. Generation remains resumable after intake/restart. |
| Quote candidates | Keep weighted selection in Python; persist candidates with checked source spans/provenance and deduplication. |
| Start/open/close/end and private answer revisions | One atomic RPC per command including permission, channel lock, request receipt, expected version, deadline and notification version. |
| Scoring | Claim immutable closed-round input, match in Python, atomically finalize once with claim fencing. |
| PubSub | Claim due notice, call Twitch, then acknowledge/retry with version fencing and existing rate limits. |

Claims/fencing are proposed internal mechanisms to preserve atomicity across external Twitch/Python work, not changes to game policy. Do not expose arbitrary SQL execution or the entire private schema through HTTP.

Expose only narrow backend RPCs. Revoke EXECUTE from PUBLIC/anon/authenticated, grant only to service_role, qualify schema objects and fix search paths for SECURITY DEFINER functions. Each operation rechecks current actor/channel/grants. Browser/Extension clients still call FastAPI; the Supabase server secret never enters their bundles.

## Migration and verification gates

1. Test HTTPS destination validation, secret-header handling, redirects, missing credentials and sanitized errors. Preflight is not full readiness.
2. Test new RPC/claim migrations in disposable Docker PostgreSQL with up/down/up and role-isolation checks before hosted application.
3. Run actual local PostgREST checks for rollback, concurrent submissions, request retries, stale versions, revoked grants, token-refresh fencing, deadlines, repeat scoring and notification recovery.
4. Run all 24 API operations and the actual dashboard/viewer JS round through HTTP storage. Do not count SQL-mode passes as HTTP-mode verification.
5. Verify the configured server key with `scripts/check_supabase_http.py`; install the tested migration through an authorized SQL path and run a disposable hosted round with cleanup.
6. Activate HTTP runtime only after passing these gates; keep real Twitch/device/deployment checks explicitly separate.

A normal secret Data API key cannot apply arbitrary DDL. Alembic migration installation still needs a working SQL connection (such as the session pooler), or the Supabase SQL editor. Retain `TWITCH_GAMES_DATABASE_URL` while migration installation/current runtime require it.

Required new values, backend-only:

```dotenv
TWITCH_GAMES_SUPABASE_URL=https://PROJECT_REF.supabase.co
TWITCH_GAMES_SUPABASE_SECRET_KEY=YOUR_SERVER_SECRET_KEY
```

No public key or changed Twitch/encryption credentials are needed.

References: [Supabase Data API](https://supabase.com/docs/guides/api), [database functions](https://supabase.com/docs/guides/database/functions), [PostgREST transactions](https://docs.postgrest.org/en/stable/references/transactions.html).
