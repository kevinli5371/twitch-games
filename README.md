# Twitch Games

A Twitch Extension for streamer-controlled audience games, with a video overlay on desktop and a mobile Extension view in Twitch's chat region. The first build includes Quote Completion, Niche, and Hive Mind.

## Run the viewer preview

Requirements: Node.js 20 or newer and OpenSSL (included with macOS). No package install is required.

One-time local HTTPS setup:

1. Run `npm run cert` from the project folder.
2. In **Keychain Access**, import `certs/localhost-ca.pem` into the **login** keychain.
3. Double-click **Twitch Games Local Development CA**, expand **Trust**, select **Always Trust**, and close it. Approve the macOS prompt if one appears. Restart the browser if it was already open.
4. Start the server with `npm run dev`.

```sh
npm run dev
```

Open `https://localhost:4173/` for the local overlay preview. It uses synthetic sample prompts and mock states. It does not connect to Twitch or evaluate real answers.

## Try the Extension on your own channel

The viewer assets are laid out for Twitch Local Test. In the Extension Developer Console, set the Testing Base URI to `https://localhost:4173/`, the video overlay Viewer Path to `viewer.html?demo=1`, and the mobile Viewer Path to `mobile.html?demo=1`. Start `npm run dev`, then activate Local Test on your channel. The local CA must be trusted by the browser running Twitch; see [Twitch's Local Test guide](https://dev.twitch.tv/docs/tutorials/extension-101-tutorial-series/local-test/).

The `demo=1` mode displays sample prompts and mock outcomes so the layout can be seen on Twitch without a backend. Remove `demo=1` after configuring the backend URL in `public/extension-config.js`. The API contract remains a proposed handoff until Kevin's service is available. Never put the Twitch Client Secret, Extension JWT signing secret, or database credentials in viewer files.

## Current implementation status

- The local overlay preview and Twitch viewer/mobile asset shells are implemented.
- The Extension assets use Twitch's Extension Helper identity callback, private HTTPS snapshot/submission calls, and Extension PubSub updates.
- Viewers can minimize the active video overlay for themselves; the dashboard/backend handoff includes a channel-wide visibility flag controlled by the streamer. The standalone preview simulates both controls.
- The backend URL is still blank and the service/API contract has not been connected or verified. The local demo is not live gameplay.
- The streamer dashboard and caption collector are owned by a separate workstream.
- Captions are conditional; live caption capture, Twitch registration/approval, and iOS/Android device behavior have not been validated here.

## Product decisions

- Per-round mode is streamer-selected or randomized; randomized selection excludes the previous round's mode.
- Games default to five rounds, configurable through the separate dashboard.
- Each round has a 30-second window. The streamer may close early and advances after results; rounds do not auto-advance.
- One submission per viewer per round; no speed bonus. Editing may be considered later.
- First-build scoring and tie rules are recorded in [the product spec](docs/product-spec.md).

Read [the product and architecture specification](docs/product-spec.md) and [the backend API handoff](docs/backend-scope.md) before extending the client. Local checks run: `npm run check`. Never commit credentials. Update this README with commands actually run, observed results, and known limitations.
