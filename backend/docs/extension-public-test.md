# Extension test gateway and Chrome local-access failure

November 2, 2026. Actual Twitch supervisor HTML, CSS and JavaScript loaded with HTTP 200. Chrome's Issues panel identified the affected `viewer.html` request as blocked by Local Network Access restrictions. The owner allowed Local network and Apps on device and reported the same issue after reloading. The saved overlay URL is correct, and the local development certificate passes system verification. Cross-origin iframe permission delegation is controlled by Twitch, not by our viewer HTML or FastAPI CORS headers.

References: [Chrome Local Network Access](https://developer.chrome.com/docs/modern-web-guidance/guides/security/local-network-access) and [Twitch developer discussion](https://discuss.dev.twitch.com/t/if-your-twitch-extension-local-test-suddenly-started-throwing-a-cors-error/64438).

## Prepared workaround

`node backend/scripts/extension_gateway.mjs` starts a loopback-only HTTP listener on 127.0.0.1:4176. `PORT` can override the port; `API_ORIGIN` can override the loopback HTTP upstream (default http://127.0.0.1:8000). Starting this script does not open a public tunnel. Keep the existing dashboard at http://localhost:4173 and its OAuth callback unchanged.

A separately authorized HTTPS tunnel can forward only to this gateway. Do not tunnel port 8000, 4173, or the general-purpose 4174 server. The gateway serves an explicit list of viewer/mobile assets and generates the API base from the public page's own origin. It forwards only:

- GET /api/v1/channels/{numeric_channel_id}/game-state
- GET /api/v1/rounds/{uuid}/me
- GET /api/v1/games/{uuid}/leaderboard
- POST /api/v1/rounds/{uuid}/answers

Every forwarded request requires an Extension Bearer header. FastAPI still verifies the JWT signature, expiry, linked identity and channel/resource access. The gateway does not authenticate or mint identities itself. Dashboard cookies/CSRF values are not forwarded, response cookies are not returned, answer bodies are bounded to 16 KiB, and all dashboard/OAuth/control/health/docs/unlisted file routes return 404. Public assets contain no signing or database secrets. The gateway writes no request logs.

For a tunnel, the provider will terminate public HTTPS and relay Extension JWTs, submissions and game responses. Anyone with its URL can retrieve public assets; viewer API operations remain authenticated. Start it only with the owner's approval and stop it after the test. The installed ngrok CLI is an available option; its free plan can show a provider notice on HTML navigation, which may require visiting the public URL before Twitch embeds it. Do not disable browser security checks.

Once a public HTTPS URL exists, the Extension owner sets Testing Base URI to that origin plus '/', keeps overlay path viewer.html and mobile path mobile.html (without demo=1), and updates allowed fetch domains if configured. No localhost API calls should remain in that viewer: /extension-config.js derives the public origin. Recheck actual Twitch requests and gameplay before declaring the workaround successful. Request Identity Link is separately required for linked viewer submissions; current Extension metadata still reports it disabled.

## Verification completed before public exposure

- `node --test backend/tests/extension-gateway.test.mjs`: two passing tests, including real loopback gateway/upstream HTTP, bundled assets, all four viewer route shapes, exact answer forwarding, cookie/CSRF isolation, blocked private operations, body-size/content-type limits and upstream configuration restrictions. Successful upstream responses here are explicitly synthetic fixtures.
- A separate actual gateway process against the running FastAPI returned viewer.html 200; missing and invalid Extension credentials 401; auth/me, dashboard and backend/.env 404. No database writes were performed.
- Public hosting, native viewer authentication, identity sharing, real answer/scoring and physical-device tests are still pending. No public tunnel has been started by this preparation.

## Subsequent live-test progress

The owner approved the temporary ngrok tunnel. It exposes only the restricted gateway with traffic inspection disabled. After a network change, restarting the owned tunnel restored the same public origin. Twitch metadata confirms the overlay's public viewer URL was saved. Public HTTPS checks returned viewer/config 200 and missing-token API 401. A browser without ngrok's notice cookie receives the provider's HTML notice rather than our app: a successful nonbrowser HTML request alone does not establish native Extension rendering. After visiting the URL in the actual viewer browser, the owner reported that the native game card appeared and that identity was shared. A full real Twitch answer/scoring/leaderboard round is still pending; do not label it complete.

The local dashboard revealed a polling race: a new 3-second poll could invalidate an older request before it completed on a slower network, keeping the page at Loading. Polls now share one in-flight refresh per workspace epoch. Workspace changes and successful commands start fresh snapshots, and failed refreshes release the slot for recovery. Four deterministic concurrency tests cover slow polling, workspace changes, failure recovery and post-command freshness.

Verification rerun: 151 Python tests plus 10 subtests; real isolated SQL and PostgREST HTTP checks for all 24 operations; actual dashboard API/caption queue/viewer adapters through source intake, private edits, a real 30-second deadline, scoring, reconnect and final standings. Twitch inputs in those automated runs remain explicit fixtures. The disposable database and gateway were cleaned up. The Node suite now has 25 passing tests plus two gateway HTTP tests; syntax and diff checks pass. No hosted schema changes or real transcript passages are included in this change.
