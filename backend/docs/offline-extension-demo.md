# Backend-free Extension demo

The owner paused real Twitch E2E verification and requested an in-memory demo and recording. This mode is explicitly sample data; it does not validate backend matching/scoring, Twitch identity, captions or PubSub.

From the repository root, run:

```sh
EXTENSION_DEMO_MODE=1 node backend/scripts/extension_gateway.mjs
```

The gateway listens on loopback port 4176. Open http://localhost:4176/preview.html for the interactive simulated-stream controls, /viewer.html for the native-style sample card, or /mobile.html for its mobile surface. Demo entrypoints redirect to demo=1, preserving Twitch context. Its API routes return demo_mode_no_backend locally and never forward to FastAPI. The connected gateway remains the default when EXTENSION_DEMO_MODE is omitted. Stop and restart the owned gateway to switch modes; do not run two listeners on the same port.

If the previously authorized public tunnel still forwards to this gateway, reloading Twitch picks up the demo without changing Testing Base URI. Public exposure still needs the owner's authorization for a new tunnel. The public viewer includes a no-op Twitch Helper authorization listener for the native initialization handshake; tokens are not used or forwarded in demo mode. The local preview has no live-video or Twitch-helper dependency.

Verification: 21 browser UI assertions passed, including blank validation, minimize/draft restoration, raw text, receipt editing/resubmission, a real 30-second close, fixture quote reveal/points, three mode flows, interim/final boards, theme/hide/restore and a 390×844 mobile viewport. Three gateway HTTP tests and 25 Node tests pass. All sample evaluations are fixtures, including fixed Niche/Hive Mind outcomes; these are not implementations of backend game logic. The browser test found and fixed receipt editing that otherwise remained on phase=submitted. No physical-device or real Twitch/backend E2E completion is claimed.

A 62.73-second silent MP4 was generated from actual browser frames. It includes the sample-data labels and passed a full decode check. Recording artifacts and local process logs are outside version control.
