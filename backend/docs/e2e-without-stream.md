# End-to-end verification without a live stream

November 2, 2026. The owner deferred the live stream and Extension Local Test setup. All executable non-broadcast checks below passed. This is not a claim of complete Twitch or device E2E coverage.

## Real connected services

- The local FastAPI service uses the configured hosted Supabase HTTPS project and server secret. Liveness and readiness return 200; the hosted revision is `0005_http_rpc`.
- Real Twitch authorization-code sign-in, dashboard session restoration, sign-out, and sign-in again worked in the browser. The verified account is kevinli16, with its owned channel and all three owner permissions.
- An invalid OAuth state returns 401. An ungranted workspace is denied. Earlier hosted write/consume/replay checks removed their temporary record; no synthetic game was inserted into hosted Supabase for these browser scenarios.
- The real channel was offline. No caption capture or broadcast round was asserted.
- Viewer/mobile assets, API adapter/configuration, and proxied liveness return 200 on `https://localhost:4174`. TLS was validated against the generated development CA, without disabling certificate checks or changing system/browser trust. Browser certificate trust and native Local Test installation remain pending.

## Full browser flow using explicit Twitch fixtures

The actual dashboard, viewer/mobile HTML, JavaScript API adapter, FastAPI, generation/scoring workers, PostgreSQL 17.11 and real PostgREST ran together. The browser harness defaults to `supabase_http`, uses disposable Docker resources, never reads `.env`, and supplies synthetic OAuth, caption/player, viewer identity and Twitch network responses. Those provider fixtures are not real Twitch observations.

1. Signed in as the fixture owner, connected the visible fixture player and submitted a caption through the dashboard collector. The normal backend generated a source-backed quote candidate.
2. Saved the accepted alias `amazing` for `incredible` through the dashboard. Added and revoked a disposable moderator's live-control grant through the real forms.
3. Started a game and opened a round. A desktop viewer submitted an incorrect answer, edited it to `amazing`, and reloaded before closure; its private receipt was restored. A separate mobile-entry viewer submitted `wrong` and saw only its own receipt.
4. The actual 30-second deadline closed the round. The alias earned 1 point; the incorrect answer earned 0. Both viewers displayed the same standings and their own result. Ending the game displayed final standings.
5. Started a second game with another sourced caption and verified the board reset. At a measured 390 × 844 viewport, the mobile entry had no horizontal overflow, focused its answer field, and submitted the unchanged typo `discvered`. The backend accepted it for `discovered`, awarded 1 point, and showed a total of 1 rather than carrying over the prior game's score. The dashboard ended this game and the desktop viewer received final standings.

The harness replaces the normal three-second fallback poll with a one-hour interval, solely in its test response. State transitions arrived through the public-notice bridge (eight notices across the two games), invoking the viewer's broadcast listener. The bridge relays only the actual publisher's `{event, channel_id, version}` payload, never authentication headers. This verifies publication payloads, client invalidation and fresh-state fetching. It does not verify Twitch's actual PubSub delivery or SDK token issuance. Initial loads and deliberate reloads still fetch state normally.

Alias changes after the first round closed were observed in the dashboard; immutable active-round policy is covered by backend integration tests, not claimed from that UI action. The responsive viewport check does not establish physical mobile keyboard, iOS or Android behavior.

## Repeatable verification

- From `backend/`, `.venv/bin/python scripts/postgres_checks.py`: **151 Python tests plus 10 subtests**, Docker migration up/repeat/down/up, legacy encrypted-session preservation, real SQL and HTTP-storage API suites, and actual JavaScript client rounds passed. Both storage modes include successful cases for **all 24 mounted API operations**. See `endpoint-test-coverage.md` for the operation matrix.
- Real HTTP-storage checks also cover rollback, 105 concurrent submissions, retry identity, stale versions, exactly-once scoring, own rank outside the top 100, refresh fencing and immediate grant revocation. A deliberate transient startup RPC failure recovers before readiness succeeds.
- `npm run check` and `npm test`: **16 Node tests** passed, including cookies/CSRF, private answer handling, stale-workspace responses, retry-safe captions and path isolation.
- Ruff, formatting and `git diff --check` passed for the changes.
- `.venv/bin/python scripts/browser_stack.py --smoke` passed: real PostgREST readiness, denied anon/authenticated RPC execution, fixture HTTP assets, notice route, disabled-poll instrumentation and orderly resource cleanup. `.venv/bin/python scripts/browser_stack.py` starts the interactive disposable browser setup; `--storage postgres` selects SQL mode.

All disposable browser-test processes, PostgREST gateways and Docker databases were removed. The real local API/dashboard remain available.

## Still pending

- Captions from a real caption-enabled broadcast entering the collector and producing playable prompts.
- Native Extension installation, Twitch-issued viewer JWTs/identity sharing, and actual Extension PubSub delivery.
- Desktop Twitch placement and physical iOS/Android Extension behavior.
- Public HTTPS deployment with production callback/CORS/cookie settings.

For unpublished testing, the Extension owner can add kevinli16 (numeric ID 1602828445) and viewer testers to the version's **Testing Account Allowlist**, then the streamer installs and activates it on their channel. Review/publication is not required for allowlisted testing. This is distinct from the post-release Streamer Allowlist. See [Twitch Extension access](https://dev.twitch.tv/docs/extensions/life-cycle/#access) and [Local Test](https://dev.twitch.tv/docs/tutorials/extension-101-tutorial-series/local-test/).
