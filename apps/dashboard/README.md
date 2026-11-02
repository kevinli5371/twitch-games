# Streamer dashboard

Buildless, dependency-free HTML/CSS/JavaScript prototype. From the repository root run `npm run dev:app` and visit `http://localhost:4173/`. The default Live game workspace connects to FastAPI through the same-origin proxy; the other tabs preserve the original workflow fixture. See [full-stack integration](../../docs/fullstack-integration.md). ES modules require HTTP; opening `index.html` directly is unsupported.

The workflow preview supports local approval/rejection, question creation, bank filters, exact-order setup and random-rotation configuration, and a channel-wide cooldown **draft**. Local fixture edits are stored in this browser; reset returns sample questions. The game plan is an illustrative 3–5 question range only; no questions are reserved or drawn. The 1–20 round and 0–1000 cooldown form limits are prototype input bounds, not approved product rules.

Run model checks: `node --test apps/dashboard/model.test.mjs`.

The workflow tabs contain privileged development fixture data with sample answers and provenance. Never serve it as the viewer Extension bundle. It does not authenticate a streamer or moderator, enforce permissions, connect to FastAPI/Twitch, collect captions, validate source evidence, reserve questions, run games, schedule starts, calculate scores, or recover authoritative progress. Disabled controls identify unimplemented/dependent operations. Scheduling, exact permission grants, cooldown counting/reset, timer recovery and scoring require owner decisions and backend integration.

The implemented quote-game backend and dashboard OAuth contract live in `backend/docs/frontend-handoff.md`. Use API base `http://localhost:8000/api/v1`, and open this preview as `http://localhost:4173` for same-site cookie integration. Live game now calls that API for authentication, workspaces, captions, controls, monitoring, aliases and moderator grants. The three-game planner remains a fixture and does not imply three runtime modes.
