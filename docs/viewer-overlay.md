# Viewer overlay implementation

This workstream contains the viewer-facing game card. The streamer dashboard and backend implementation are owned separately.

## Current state

- `public/preview.html` is the standalone visual/demo harness at the local server root. Its controls simulate streamer actions and use synthetic prompts, names, answers, and scores.
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
