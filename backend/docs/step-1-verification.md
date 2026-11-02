# Step 1 verification

Validated locally on November 1, 2026. Step 2 requires the owner's next green light.

## Environment

- macOS arm64; Python 3.14.3.
- FastAPI 0.162.0, Pydantic 2.14.2, pydantic-settings 2.16.2, Uvicorn 0.54.0.
- Current Starlette test client uses HTTPX2 2.16.0; no deprecated HTTPX fallback is used.
- The tested application/test versions are pinned in `../requirements-dev.lock`. Python 3.12/3.13 and other operating systems have not been exercised in this step.

## Results

| Check | Result |
| --- | --- |
| `python -m pytest -q -W error` | **55 passed**, no warnings. |
| `ruff check .` | Passed. |
| `ruff format --check .` | Passed. |
| `python -m pip check` | No broken requirements. |
| Generated contract/fixture reproducibility | Passed in the test suite, including local reference resolution. |
| Real Uvicorn startup over loopback | Passed; process stopped after the smoke test. |

The real server returned HTTP 200 for `/health/live`, HTTP 503 for `/health/ready`, HTTP 200 for `/docs`, and HTTP 404 for the unimplemented game-state path. The 503 body reports database, Twitch auth and gameplay as not implemented. The smoke script used isolated test settings and an ephemeral `127.0.0.1` port; it made no Twitch/Supabase requests.

## Behavior covered

- Invalid environment settings fail before serving the application.
- Production configuration disables interactive/runtime docs and requires explicit HTTPS origins.
- Allowed browser origins work; other origins do not receive cross-origin permission.
- Runtime OpenAPI advertises only implemented health operations.
- Planned game operations are clearly marked planned and are not mounted as successful stubs.
- Unknown privileged fields are rejected in public answering-state contracts.
- Receipts cannot include premature grading; clients cannot submit a verdict.
- Typed answer text is preserved; blank/control/oversized input is rejected.
- Time values require timezone information; dashboard/event identifiers remain internally consistent.
- Gameplay policy must be explicitly referenced, not filled from an example default.

## Limits

No database schema, connection or persistence test exists yet. No Twitch OAuth, real Extension-token verification, live caption intake, quote-ranking/matching engine, score calculation or real-time transport exists yet. No deployment or desktop/mobile Twitch surface has been tested. The planned schemas constrain data representation; they do not substitute for the authorization and phase enforcement required in later steps.
