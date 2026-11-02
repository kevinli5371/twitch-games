# Backend handoff for dashboard and Extension

Development API base: `http://localhost:8000/api/v1`. Production API base/domain is not selected. All paths below are relative to this API base. The actual implemented schema is [openapi.json](openapi.json); `openapi.planned.json` and the old foundation fixtures are historical planning artifacts.

## Dashboard authentication

1. Navigate the browser to `/auth/twitch`; do not fetch it as a login AJAX request.
2. Twitch returns to the registered backend callback. The backend validates state, exchanges/verifies tokens and sets an opaque HttpOnly session cookie.
3. The backend redirects only to configured `TWITCH_GAMES_DASHBOARD_URL`.
4. Fetch `/auth/me` with `credentials: 'include'`. Send its `csrf_token` as `X-CSRF-Token` on cookie-authenticated POST/PUT/DELETE requests.
5. Select a workspace using `/auth/me?channel_id=...`; subsequent operations target their channel/resource paths. The backend validates access independently on each operation. Roles/permissions in UI state are never authoritative.
6. POST `/auth/logout` with credentials and CSRF to clear that browser session. A revoked OAuth authorization ends all linked sessions. An expired 24-hour session requires login; expired access tokens are refreshed under a database lock.

Exact development callback: `http://localhost:8000/api/v1/auth/twitch/callback`. Production callback must be the chosen HTTPS API origin plus `/api/v1/auth/twitch/callback`, registered exactly. There is no production domain to supply yet. The `/auth/session` basic response remains a deprecated compatibility endpoint; new UI should use `/auth/me`.

Artificial owner response:

```json
{
  "user": {"user_id":"90001","login":"example_owner","display_name":"Example Owner","avatar_url":"https://example.test/avatar.png"},
  "owned_channel":{"channel_id":"90001","display_name":"Example Owner"},
  "workspaces":[{"channel_id":"90001","login":"example_owner","display_name":"Example Owner","role":"owner","permissions":["live_control","question_review","settings"]}],
  "selected_workspace":{"channel_id":"90001","role":"owner","permissions":["live_control","question_review","settings"]},
  "csrf_token":"opaque-csrf-value"
}
```

A moderator receives their own verified user and owned channel, plus explicitly granted workspaces. Their selected workspace role is `moderator` with current granted permissions. Logging in or having a Twitch moderator badge alone does not grant another workspace.

If login ends at port 4173 with a connection-refused page, check that the dashboard preview is running. The backend may already have completed its callback and created the session. Visit `/auth/me` on the API in that same browser to verify. Keep the registered callback on port 8000; port 4173 is the subsequent dashboard destination.

## Moderator administration and data boundaries

| Operation | Required authority |
| --- | --- |
| GET `/channels/{id}/moderators` | Channel owner only. |
| PUT `/channels/{id}/moderators` with `{login, permissions}` | Channel owner only. Resolves the login through Twitch and replaces that user's grants. Empty list revokes all. |
| DELETE `/channels/{id}/moderators/{user_id}` | Channel owner only. |
| Dashboard snapshot | Owner or any currently granted workspace member. |
| Hidden question candidates and answer aliases | Owner or `question_review`. |
| Start/open/close/end games | Owner or `live_control`. |
| Connect a stream or ingest captions | Owner or `settings`. |

Permission values are `question_review`, `live_control`, `settings`. No grant permits granting other people access. Grant changes are checked in the database for each protected operation. A live-control/settings-only dashboard response contains `candidates: []`; it never silently includes unrevealed answers. The owner explicitly confirmed that question reviewers may see them.

Question selection is automatic; a manual question-bank approval/creation workflow from the PR #1 fixture is not implemented by these endpoints. Alias management is a question-review operation. Scheduling, pause/skip policies and additional modes remain outside the confirmed quote release.

## Cookie/CORS deployment

Development preview in PR #1 uses port 4173. Open it as `http://localhost:4173` and the API as `http://localhost:8000` so both use the same site. Cookie authentication requires `credentials: 'include'`, an exact allowed dashboard origin, and a CSRF header on mutations. CORS does not replace permission checks.

Production cookies are Secure, HttpOnly, SameSite=Lax. Use same-site dashboard/API domains or a reverse proxy. Cross-site deployments require a deliberate cookie/security change; do not switch to `SameSite=None` or wildcard CORS as an incidental frontend fix. No access/refresh token or client secret belongs in the dashboard bundle.

## Caption collector

POST `/channels/{channel_id}/stream` connects the channel's actual current Helix stream and returns the internal `stream_id`. POST `/streams/{stream_id}/transcript-batches` with a stable UUID `batch_id`, `source: "twitch_player_captions"`, and at most 100 segments containing `sequence`, `text`, and timezone-aware `observed_at`. Preserve original text and assign unique sequence numbers within each batch. Retry unchanged batches with the same ID; changed content requires a new ID.

The browser collector is owned by the dashboard teammate. A visible, compliant Twitch embed may provide conditional caption events. The backend does not create universal Twitch transcripts or acquire broadcast audio. Actual captions must be tested on a caption-enabled stream; fallback audio transcription is not implemented. Snapshot freshness distinguishes waiting, receiving, stale, and not connected. Generation uses stored current-stream source evidence.

## Quote game control

- POST `/channels/{id}/games`: `{request_id, mode:"quote", policy_id:"quote_v1"}`.
- POST `/games/{game_id}/rounds`: `{request_id, expected_version}`. Omit `question_id` for automatic selection; an unused candidate UUID may be supplied explicitly.
- Each round is exactly 30 seconds. Deadline enforcement uses the server/database clock. Early close/end during answering is rejected. The streamer opens the next round manually.
- POST `/rounds/{round_id}/close` can finalize an elapsed window; the worker normally does this automatically.
- POST `/games/{game_id}/end` after round results returns public game state. GET `/games/{game_id}/leaderboard` obtains final standings.
- Non-start commands require the current channel `version`. Stale commands return 409; refresh state rather than blindly retrying with a changed expected version and the same request ID.
- Repeating the exact command request ID returns its original response. Reusing an ID for a different payload/operation returns 409. Versions are monotonic across games on a channel.

Dashboard polling can fetch `/dashboard/channels/{id}` for counts, freshness and authorized candidate details. Essential monitoring does not depend on a private-data PubSub topic.

## Viewer Extension

Use the latest token supplied by `Twitch.ext.onAuthorized`; pass `Authorization: Bearer TOKEN`. Never ship the shared signing secret. The backend verifies token signature, expiry, role, channel and shared identity. Viewers without a shared Twitch user ID may spectate; typed submission requires identity sharing.

- GET `/channels/{id}/game-state` for the public snapshot.
- POST `/rounds/{round_id}/answers` with `{request_id, answer}`; answer is preserved exactly. An edit uses a new request ID. Retries use the same request ID and text.
- GET `/rounds/{round_id}/me` restores only that user's latest answer/receipt and, after results, their outcome. A receipt never indicates correctness.
- GET `/games/{game_id}/leaderboard` returns the top 100 plus `own_entry` even when outside the top 100. Rankings share ties; scores reset per game.

Twitch PubSub broadcast notifications contain only `{event:"game_state_changed",channel_id,version}`. On a notification, fetch the current snapshot with the latest token. Deduplicate old versions; always fetch a fresh snapshot after reconnect/reopen. Notifications are coalesced and sent at most once per second per channel, with persistent retry state. They never carry raw answers, source passages or hidden canonical words. Do not treat historical `StateChanged` fixtures containing a whole state as the actual wire message.

Desktop overlay and mobile Extension use the same API; presentation and actual iOS/Android testing belong to the viewer teammate. Render captions, answers and display names as text, never raw HTML. The backend alone calculates correctness and points.

## Errors and environment

Errors use `{ "error": {"code":"...","message":"..."} }` without secret/token/SQL details.

- 401: missing/expired/revoked authentication, invalid OAuth state, or `consent_denied`.
- 403: wrong channel, missing grant/CSRF, or identity sharing required.
- 409: stale version, request ID conflict, closed/active round, active/ended game, unavailable stream/quote context.
- 422: invalid fields or unsupported policy.
- 413: request body exceeds 512 KiB.
- 503: configuration, database, or Twitch dependency unavailable. Do not turn this into a successful fake login.

The complete backend environment-variable list and sources are in [README](../README.md) and `.env.example`. Application and Extension ownership can differ. Frontends need only API base, their own allowed origin, and the Extension Client ID/helper configuration; all client secrets, signing keys, database credentials and encryption keys stay server-side.

## Connected clients

The dashboard Live game workspace and native viewer now use this implemented contract; see root `docs/fullstack-integration.md`. `/auth/me` workspaces include a verified `login` for the visible Twitch player (nullable for legacy records). The local same-origin proxy preserves cookies/CSRF and serves the actual API client; no new production auth path or schema migration was added. Planning tabs remain explicitly labelled fixtures.
