# Backend foundation

This is an independent foundation, not a playable backend. FastAPI exposes health
and typed snapshot contracts, with authentication and repository access failing
closed. There is no fake-login mode. `/health/ready` returns 503 until real
integrations are implemented; setting a database URL alone cannot make it ready.

With Python 3.11+ available, from `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m uvicorn twitch_games.app:app --reload
```

Open `/docs` for generated OpenAPI. `DATABASE_URL` is a server-only configuration
name; never put credentials in a browser bundle or commit a populated env file.
No OAuth environment names are prescribed before that adapter is implemented.

The pure planner takes explicit pre-drawn round modes/counts and explicitly
computed eligibility. It validates randomized no-repeat plans and reserves each
question once in its returned plan, or fails without changing the source input.
Exact-order repetition needs an explicit injected policy; no repetition policy
is inferred. The privileged snapshot is owner-only pending the hidden-answer
permission decision; moderator settings/control grants do not grant answer access.
The submission contract has a 2,000-character engineering transport safeguard;
that bound is not a gameplay rule and should be reviewed before live integration.
It does not draw a distribution, compute cooldowns, mutate durable reservations,
retry alternative plans, select scoring rules or resolve equivalence semantics.

`migrations/0001_private_foundation.sql` proposes private PostgreSQL tables with
channel-qualified foreign keys, unique final submissions, approval checks,
exclusive active reservations and no browser-role grants. It targets Supabase's
existing `anon`/`authenticated` roles. Apply only through a reviewed server-side
migration workflow; no migration is automatically applied. The server role and
connection mode still need selection. Elevated server code must enforce channel
authorization on every operation; RLS does not replace this check.

Before implementing gameplay, add transactional locking/revalidation of bank
eligibility and reservation insertion, authoritative state transitions, Twitch
OAuth/JWT verification and permission revocation, persisted recovery, and the
owner's unresolved timing/cooldown/scoring/equivalence decisions. The SQL stores
usage evidence without choosing completed-game cooldown counting semantics.
The owner-only grant check checks the recorded actor, not a trusted database
session identity: the future authenticated repository must supply it securely.
Submission updates are rejected; duplicate insert retries must fetch and preserve
the original receipt. API routes intentionally do not expose unimplemented writes.

No caption source, historical intake, AI provider, durable repository, worker,
schedule, scoring engine, live event transport or deployed Twitch integration is
implemented. The migration has not been run against PostgreSQL. Tests are supplied
but were not executed in this environment because Python was not found on PATH;
installation/runtime behavior has not been observed. This limitation must remain
visible until a real Python test run and database validation replace it.
