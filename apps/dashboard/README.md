# Streamer dashboard fixture preview

Buildless, dependency-free HTML/CSS/JavaScript prototype. From the repository root run `npm run dev:design` and visit `http://127.0.0.1:4175/dashboard/`, or use `npm run dev:dashboard` for the dashboard-only server at `http://127.0.0.1:4173/`. ES modules require HTTP; opening `index.html` directly is unsupported.

The preview supports local approval/rejection, question creation, bank filters, exact-order setup and random-rotation configuration, and a channel-wide cooldown **draft**. Question edits and the cooldown draft are stored in this browser; reset returns sample questions and clears bank filters. Rotation drafts are temporary and reset on reload. The setup view follows the newer viewer-first-build design defaults: five rounds, 30-second answer windows, and manual advance after results. This does not change the backend or settle inconsistencies between earlier product plans and the merged runtime. No questions are reserved or drawn. The 1–20 round and 0–1000 cooldown form limits are prototype input bounds, not approved product rules.

The visual design follows the owner's [Outcrowd reference](https://dribbble.com/shots/27167729-AI-Analytics-Dashboard): a near-black rounded shell, horizontal active-pill navigation, violet area chart/question map, lime status accents, purple action card and bank-composition donut. Counts derive from the local bank; they are not live analytics. Metric arrows, map tiles, status breakdowns and review shortcuts open matching bank filters. Successful creation reveals the new approved question. See [design review evidence](../../docs/dashboard-design-review.md).

Run model checks: `node --test apps/dashboard/model.test.mjs`.

The dashboard defaults to light mode. Use Dark mode / Light mode beside the preview status to compare themes; the preference is saved locally without resetting question-bank state.

This is privileged development fixture data with sample answers and provenance. Never serve it as the viewer Extension bundle. It does not authenticate a streamer or moderator, enforce permissions, connect to FastAPI/Twitch, collect captions, validate source evidence, reserve questions, run games, schedule starts, calculate scores, or recover authoritative progress. Disabled controls identify unimplemented/dependent operations. Scheduling, exact permission grants, cooldown counting/reset, timer recovery and scoring require owner decisions and backend integration.

The implemented quote-game backend and dashboard OAuth contract live in `backend/docs/frontend-handoff.md`. Use API base `http://localhost:8000/api/v1`, and open this preview as `http://localhost:4173` for same-site cookie integration. This preview remains fixture-driven until its controls are wired to that API; the three-game planner is not a claim that all three backend modes are implemented.
