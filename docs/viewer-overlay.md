# Viewer overlay implementation

**Integration update — November 2:** the real viewer now uses the implemented FastAPI contract described in [fullstack-integration.md](fullstack-integration.md). The proposed wire schema below is historical; `public/api-adapter.mjs` and the backend handoff are the actual contract. Local HTTPS now defaults to port 4174; `/preview.html` is the in-memory simulator and `/` is the connected dashboard. Use no `demo=1` for connected play.

This workstream contains the viewer-facing game card. The streamer dashboard and backend implementation are owned separately.

## Current state

### Pixel UI integration — November 2, 2026

**Viewer-only minimized state:** the owner requested a compact version for viewers who prefer not to participate. The expanded card now has a **− / Minimize game** control. It collapses to a roughly 240×64px pixel tab with the mode icon/name and **Just watching · Open game**. It shows no prompt, input, countdown, scores or results, and stays collapsed as rounds/modes update. Activating the tab restores the latest state and refreshes the live adapter. Minimize is also available on idle/error cards and in the separate mobile surface.

Before PR publication, browser rechecks verified minimize → compact tab → reopen. A separate preview Hide issue was found: its restore action used viewport-fixed positioning and could appear below/outside the simulated player. The preview now lays out that restore button inside the player; Hide and its restore action were rechecked visually. Native Twitch's own full-extension hiding remains separate and unverified in-platform.

Only the minimized preference is saved in session storage (with an in-memory fallback). It persists for that browser tab's session; drafts and answers are not written there. Minimizing preserves draft/receipt state and does not submit or withdraw answers, alter scores or control another viewer. The separate desktop **Hide** action still uses Twitch's native minimize API to remove the extension entirely. Channel-wide `overlayEnabled: false` suppresses the compact tab too. Browser checks verified collapse/restore with a draft, mode changes staying collapsed, channel-wide hiding, and persistence through refresh. Native Twitch Hide remains unverified in-platform.

The owner authorized building the pixel direction on the existing overlay infrastructure. `viewer.html`, `mobile.html`, and `preview.html` now load `overlay-pixel.css` over the base stylesheet and `overlay-theme.js` alongside the existing `overlay.js` renderer. The local mobile workspace uses those same assets. The font and OFL license are bundled in `public/fonts/`; production assets do not import the design lab's fixture renderer or screen-gallery code.

The shared renderer now includes per-mode pixel sprites/accents and instructions, round-progress blocks when a round count is supplied, editable quote receipts, revealed quote text, results and standings. All values still come from its adapter; no scoring/equivalence logic was introduced. Final standings render every entry supplied in the snapshot, rather than truncating to five; the backend's ability to supply a complete participant list remains a separate contract issue.

The skin defaults to light and follows the documented [`Twitch.ext.onContext` theme](https://dev.twitch.tv/docs/extensions/reference/#oncontext) when available. `?theme=light` / `?theme=dark` and the preview's Theme selector provide manual comparison. Real callback behavior has not been tested inside Twitch. Theme changes do not remount the form. The mobile composition omits the desktop Hide control.

In-memory drafts are scoped by game/round/mode and survive same-round snapshot re-renders. Pending forms show Sending, block duplicate clicks, and retain draft text after errors. Drafts are cleared on receipt/result, bounded in memory, and never written to browser storage. A late submission response no longer marks a newer round or already-published result as submitted. Existing identity/minimize/visibility/snapshot hooks remain in place.

Observed: all 14 Node tests and `npm run check` pass. Three new adapter regressions cover late responses after round changes/results and failed requests never becoming receipts. Browser checks exercised draft preservation via Refresh snapshot, a submitted receipt, Niche's dark theme/results, a six-entry final board, and the 390px mobile composition. These are local fixture checks, not real Twitch/backend/device validation.

**Connected integration:** PR #6 now depends on the connected client and HTTP-storage PRs. The renderer imports `api-adapter.mjs`, uses Bearer JWTs, the implemented snake_case state/private receipt contract and compact public version notices. Connected quote answers remain editable until the backend deadline; raw input is preserved and unknown round counts are not invented. Planning/other-mode screens remain labelled fixtures. Actual native Twitch delivery/captions and physical-device checks remain pending.

- `public/preview.html` is the standalone visual/demo harness at the local server root. Its controls simulate streamer actions and use synthetic prompts, names, answers, and scores. It now renders the integrated pixel UI; the separate design lab/gallery remains at `/design/pixel.html` on the design server.
- `public/viewer.html` and `public/mobile.html` are Twitch Extension entry points. Both include the Twitch Extension Helper, then the same viewer client. `viewer.html?demo=1` and `mobile.html?demo=1` use sample data for Twitch Local Test before the API is connected.
- The viewer card includes a per-viewer **Hide** control in Twitch video-overlay context, backed by `Twitch.ext.actions.minimize()`. Restoring it through Twitch's player Extension controls refreshes the latest snapshot. The standalone preview has a matching local hide/show simulation.
- The viewer hides all card content when the public snapshot has `overlayEnabled: false`. The streamer dashboard owns the channel-wide toggle and publishes the change; hiding does not alter game/round state.
- Without `demo=1`, the viewer client expects the backend URL in `public/extension-config.js`. That file may contain public configuration only.
- The root `.env` is git-ignored and holds backend environment placeholders, including the Client ID the backend uses when validating Extension JWTs. A static browser page does not read `.env`; Twitch's `onAuthorized` callback provides the Extension Client ID and signed viewer JWT at runtime. The signing secret and other private keys belong only in the backend environment.

## Run locally

```sh
npm run dev
```

Run `npm run cert` once, trust `certs/localhost-ca.pem` in the macOS login keychain, then start `npm run dev`. Open `https://localhost:4173/` for the local stream mock and UI controls. To render the sample overlay inside Twitch Local Test, configure the Extension's Testing Base URI as `https://localhost:4173/`, its video/fullscreen Viewer Path as `viewer.html?demo=1`, and its mobile Viewer Path as `mobile.html?demo=1`. Then activate the Local Test version on the creator's channel. The local CA must be trusted by the browser running Twitch; see the [official Local Test guide](https://dev.twitch.tv/docs/tutorials/extension-101-tutorial-series/local-test/).

The overlay's `demo=1` mode intentionally skips identity linking and uses only in-memory fixture data. It must not be mistaken for live answers, scoring, or a verified backend connection.

## Proposed viewer API contract

The route names follow the backend handoff. This response schema is a frontend integration proposal and still needs to be matched by the backend owner.

### Public snapshot

`GET /channels/{channel_id}/game-state`

Expected response shape:

```json
{
  "version": 12,
  "overlayEnabled": true,
  "game": {
    "id": "game-id",
    "status": "active",
    "roundCount": 5
  },
  "round": {
    "id": "round-id",
    "number": 1,
    "mode": "quote_completion",
    "phase": "answering",
    "deadlineAt": "2026-11-02T17:30:30Z",
    "prompt": {
      "text": "I cannot believe we won with a ____. ",
      "sourceTimestamp": "04:18"
    }
  },
  "source": { "status": "available" },
  "leaderboard": []
}
```

Recognized modes are `quote_completion`, `niche`, and `hive_mind`. The backend decides and publishes the per-round mode; the viewer never chooses or randomizes it. The client displays the server deadline as a countdown; the backend remains authoritative for accepting or rejecting submissions.

### Private participation

- `POST /rounds/{round_id}/answers` with `{ "answer": "..." }` creates the viewer's one submission. The request includes Twitch's Extension JWT in `x-extension-jwt`.
- `GET /rounds/{round_id}/me` restores that linked viewer's private receipt, revealed result, and current standing.
- `GET /games/{game_id}/me` restores the linked viewer's final standing when the game is over and no active round remains.

The UI asks viewers to link their Twitch identity before submitting. Other viewers' raw answers and unrevealed canonical answers are not rendered.

### Live updates and recovery

The viewer listens to Twitch Extension PubSub's `broadcast` topic for JSON messages shaped as `{ "type": "game_updated", "version": 13, "snapshot": { ... } }` (or `game_snapshot`). It ignores older versions and fetches a fresh snapshot on reconnect/refresh. A 15-second HTTP refresh is included as a fallback while the PubSub contract is wired up.

The public snapshot includes `overlayEnabled` (boolean, defaults to `true` for older backend payloads). The streamer dashboard/game service changes it for the whole channel and publishes the update. The viewer polls while visible even when no round is active, so turning the overlay back on can restore the current state. Twitch's visibility callback pauses polling while a viewer has minimized the overlay and triggers a refresh when it is shown again.

## Local implementation decisions

- The local preview's mode and round-count controls are a development simulator, not the streamer dashboard. It defaults to five rounds. Changing the count starts a new local sample game.
- Random mode selection in the simulator excludes the previous round's mode. Production mode selection belongs to the game service/dashboard and is only displayed by this viewer.
- The viewer shows personal outcome/points and published standings. It never displays other players' raw answers.
- The round count freezes when a game starts. Dashboard changes apply to the next game. Canceled rounds do not score or count toward that total.
- Standings reset per game session. Equal cumulative scores share competition rank.

## Combined PR review verification

The combined stack passed 151 Python tests plus 10 subtests, real SQL and HTTP API checks for all 24 operations, and 21 Node tests. Browser interaction through real PostgREST with explicit Twitch fixtures verified light/dark Live game, preserved raw answer text, edit draft through compact/reopen, the 30-second close, 1/0 scoring for separate viewers, final standings and dashboard reload. The 390px mobile result had no horizontal overflow and loaded Silkscreen. Native Twitch/mobile hardware and public deployment remain pending.
