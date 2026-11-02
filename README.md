# Twitch Games

A Twitch Extension for streamer-controlled audience games, with a desktop video overlay and a mobile Extension view. The first build includes Quote Completion, Niche, and Hive Mind. Read the [product and architecture specification](docs/product-spec.md) and [backend API handoff](docs/backend-scope.md) before extending the project.

## Implemented backend and integration status

The FastAPI quote-game backend now implements Twitch dashboard OAuth, owner-controlled moderator grants, private Supabase persistence, caption intake, algorithmic quote selection/matching, 30-second rounds, editable answers, scoring, leaderboards and restart recovery. See [backend setup](backend/README.md), [frontend contract](backend/docs/frontend-handoff.md) and [verification evidence](backend/docs/backend-verification.md).

All 24 documented backend API operations passed real local HTTP checks. Real Supabase migrations and Twitch browser OAuth/refresh checks also passed. On November 2, the owner approved backend merge with full Twitch/frontend E2E deferred until the test stream is ready. Installed Extension JWTs/PubSub, actual caption capture, frontend contract wiring, mobile/device checks and production deployment remain pending.

The broader three-mode product plan and UI fixtures below are separate from the implemented quote runtime. Quote mode currently uses manual advancement, no early close, editable answers and 1/0 scoring. [Reconciliation notes](backend/docs/pr-1-reconciliation.md) record these differences; merging the backend does not claim the entire broader plan is implemented.

## Viewer overlay preview and Twitch Local Test

### Local design workspace

Run `npm run dev:design` and open `http://127.0.0.1:4175/` to review the desktop overlay, separate mobile composition, and dashboard together. No certificates, package installation, Twitch login, or backend are needed. Set `PORT` to override the port.

The workspace provides surface switching, full-preview links, and fluid/1280px/390px width controls. It reuses the existing independent fixtures: dashboard actions do not drive the viewer. The mobile composition omits the Twitch Helper and uses only synthetic local data. This HTTP server binds to loopback, serves only the three UI directories, and is for local visual design; Twitch Local Test continues to use the HTTPS setup below. Design-workspace files live outside the viewer asset directory.

The source documents and merged quote runtime differ on mode scope, submission editing, progression, and scoring. Visual exploration does not resolve those differences or establish backend integration/device validation.

Observed November 2, 2026 for this workspace: all 11 Node tests, existing viewer syntax checks, new workspace/server syntax checks, and `git diff --check` pass. Browser review verified switching among desktop, mobile (390px), and dashboard previews, including their rendered sample content. The route test checks that private project paths are unavailable. No live Twitch or backend checks were performed for this design setup.

The dashboard now uses the owner's Outcrowd design reference, with horizontal pill navigation, compact metrics, violet bank visualizations and a purple next-step card. Two independent skeptic review passes checked the visual style, local workflows, copy and 390px layout; reported usability issues were fixed and rechecked. See [dashboard design review](docs/dashboard-design-review.md) for evidence and limitations.

The dashboard now defaults to light mode, with a Dark mode / Light mode switch beside the preview status. Light overview/bank rendering and theme switching were browser-checked. The overlay's minimize/reopen cycle was rechecked before PR publication; the separate Hide restore button is now anchored inside the simulated player instead of the whole page. All 14 Node tests and syntax/diff checks pass. These remain local UI checks.

A [pixel overlay exploration](docs/pixel-overlay-design.md) is available at `http://127.0.0.1:4175/design/pixel.html`. It includes 12 screen mockups across all three games, a clickable desktop/mobile flow, interim/final standings, and sample failure/permission states. Its Integrated viewer link opens the subsequent implementation on the shared overlay renderer. Timers, receipts and outcomes in the lab are illustrative; no real answers are evaluated. Browser checks and the 11 existing Node tests passed for the initial exploration.

The pixel lab defaults to a light theme for comparison with Twitch's white UI. Use the header's Light/Dark controls or `?theme=light` / `?theme=dark`; changing themes preserves the active draft. Both desktop and mobile compositions and the screen gallery share the theme.

Requires Node.js 20+ and OpenSSL (included with macOS). No package install is needed.

Create and trust the local development certificate once:

1. Run `npm run cert` from the project folder.
2. In Keychain Access, import `certs/localhost-ca.pem` into the **login** keychain.
3. Double-click **Twitch Games Local Development CA**, expand **Trust**, select **Always Trust**, close it, and approve the macOS prompt if shown. Restart the browser if it was already open.

Run the overlay server:

```sh
npm run dev
```

Open `https://localhost:4173/` for a local preview. It uses synthetic prompts and mock states; it does not connect to Twitch or evaluate real answers.

For Twitch Local Test, configure the Extension Developer Console with Testing Base URI `https://localhost:4173/`, Video - Fullscreen Viewer Path `viewer.html?demo=1`, and Mobile Viewer Path `mobile.html?demo=1`. Start the server and activate Local Test on your channel. The browser used for Twitch must trust the local CA. See [Twitch's Local Test guide](https://dev.twitch.tv/docs/tutorials/extension-101-tutorial-series/local-test/).

The demo mode uses placeholder evaluation. Remove `demo=1` only after configuring the backend URL in `public/extension-config.js` and connecting the backend. Never put the Twitch Client Secret, Extension signing secret, or database credentials in viewer files.

## Local dashboard fixture

The dashboard is a separate local fixture, served from loopback and not packaged as viewer Extension assets:

```sh
npm run dev:dashboard
```

Open `http://127.0.0.1:4173/`. If the port is occupied, set `PORT` to another port before starting. The fixture uses sample data and browser-local storage; live controls are disabled. See [dashboard setup and limitations](apps/dashboard/README.md) and [backend setup and limitations](backend/README.md).

## Current implementation status

- Viewers can collapse the pixel card to a small **Just watching · Open game** tab using the **−** control. The choice persists for the browser tab's session and does not reopen on round changes. Restoring preserves the current draft/receipt state. Channel-wide hiding suppresses the compact tab; desktop Hide remains a separate native Twitch action. Local browser checks verified collapse/restore, draft preservation, mode changes, channel visibility and refresh persistence. No native Twitch/device verification was performed.
- The pixel UI is now implemented on the existing desktop/mobile viewer renderer, with locally bundled font/sprites, mode accents, light/dark themes, receipts, revealed quotes and standings. Review it at `http://127.0.0.1:4175/preview.html` using `npm run dev:design`. The Twitch Helper theme callback is connected but not live-platform tested. Same-round drafts survive snapshot re-renders; pending submissions show Sending and late receipts cannot overwrite a new round/results. Final boards show all entries supplied by the snapshot. See [viewer UI integration](docs/viewer-overlay.md).
- Observed November 2 for this integration: all 14 Node tests, `npm run check`, and `git diff --check` pass. Browser checks covered all three mode presentations across the preview/mobile fixtures, light/dark styling, draft preservation, submission receipt, six-entry final standings, and a 390px mobile layout. No live Twitch/backend/device test was performed.
- The local overlay preview and Twitch viewer/mobile asset shells are implemented.
- The Extension uses Twitch's Extension Helper identity callback, private HTTPS snapshot/submission calls, and Extension PubSub updates. A viewer can minimize the overlay for themselves; the streamer dashboard/backend handoff includes a channel-wide visibility flag.
- The backend URL is blank, and live API calls, Twitch Local Test, and device behavior have not been verified. The local demo is not live gameplay.
- The streamer dashboard remains a fixture. The implemented quote backend runs locally; the viewer’s proposed auth, payload and PubSub contract still needs wiring to the actual API. No public deployment or real caption capture is verified.

## First-build gameplay decisions

- All three modes are included. Per-round mode can be streamer-selected or randomized; randomized selection excludes the immediately previous mode.
- Games default to five rounds; the separate streamer dashboard will allow changing that count.
- Each round has a 30-second answer window. The streamer may close early and advances after results; rounds do not auto-advance.
- One submission per viewer per round; no speed bonus. Editable submissions may be considered later.
- Answer validity and equivalent-answer grouping are backend-owned and remain placeholders in this build. First-build scoring and tie handling are documented in [the product spec](docs/product-spec.md).

Never commit credentials. Update the README with commands actually run, observed results, and known limitations.
