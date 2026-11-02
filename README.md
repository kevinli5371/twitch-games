# Twitch Games

A native Twitch Extension, streamer dashboard and FastAPI/PostgreSQL backend. **Quote mode is connected across all three components.** The broader product plan includes Niche and Hive Mind; their workflow/visual previews remain separate from the working quote runtime.

The owner-selected app name is **Twillion**. Editable mascot-only and full-logo SVGs are in [public/brand](public/brand/README.md), with light, dark and transparent variants. Run the design server and open `http://127.0.0.1:4175/brand/index.html` to preview them. Wordmark letters are outlined paths, with no font or bitmap dependency. These assets are committed for use; dashboard/overlay branding has not yet been replaced.

## Run the connected app

Start FastAPI from `backend/` using its [setup guide](backend/README.md), then run from the repository root:

```sh
npm run dev:app
```

Open `http://localhost:4173/`. **Live game** uses actual Twitch OAuth sessions, verified workspaces, backend controls, caption intake, quote generation, private viewer answers, scoring and leaderboards. Planning tabs remain labelled fixture previews. Full contracts, Local Test setup and verified limits are in [full-stack integration](docs/fullstack-integration.md).

For the native Extension's HTTPS Local Test assets, run `npm run cert`, trust the local CA, and run `npm run dev` (port 4174 by default). Configure Testing Base URI `https://localhost:4174/`, Viewer Path `viewer.html`, Mobile Path `mobile.html`, without `demo=1`. The server proxies API calls to FastAPI. Uploaded viewer assets need their public HTTPS backend URL and allowed domains configured. Never include secrets in viewer files.

The original in-memory visual simulator remains at `/preview.html`; `viewer.html?demo=1` and `mobile.html?demo=1` also use sample state only. These are distinct from connected play.

## Observed verification and limits

151 Python tests plus 10 subtests and 21 Node tests pass. All 24 backend operations have successful real HTTP cases. The actual JavaScript clients also complete a real API/database round, and browser testing verified two viewers, private answers/edits, the 30-second close, backend scores, final standings and reconnect. Twitch/caption inputs in that repeatable flow are explicitly synthetic. See [evidence and setup](docs/fullstack-integration.md).

The owner selected Supabase HTTPS project URL + server secret to avoid the unreachable IPv6 direct endpoint. The HTTP storage adapter passes local real-PostgREST checks and the actual hosted gateway accepts the key. The tested migration is installed and the local API now runs through Supabase HTTPS with successful readiness, session restoration and a removable hosted write probe; see [HTTP storage setup](backend/docs/supabase-http-migration.md). Real caption-enabled broadcast, installed Extension/PubSub, physical devices and public deployment remain unverified.

The quote backend keeps its confirmed manual advancement, 30-second deadline, editable-answer and 1/0-scoring rules. The following broader UI plan is not a claim that all three runtime modes are implemented.

## First-build gameplay decisions

- All three modes are included. Per-round mode can be streamer-selected or randomized; randomized selection excludes the immediately previous mode.
- Games default to five rounds; the separate streamer dashboard will allow changing that count.
- Each round has a 30-second answer window. The streamer may close early and advances after results; rounds do not auto-advance.
- One submission per viewer per round; no speed bonus. Editable submissions may be considered later.
- Answer validity and equivalent-answer grouping are backend-owned and remain placeholders in this build. First-build scoring and tie handling are documented in [the product spec](docs/product-spec.md).

Never commit credentials. Update the README with commands actually run, observed results, and known limitations.

## Visual design

The connected dashboard and desktop/mobile viewer include the light/dark redesign and compact pixel viewer. `npm run dev:design` serves the separate visual gallery on port 4175. The gallery and planning tabs use sample data; the default Live game uses FastAPI. See [design notes](docs/pixel-overlay-design.md).
