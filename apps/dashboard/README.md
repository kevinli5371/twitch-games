# Streamer dashboard fixture preview

Buildless, dependency-free HTML/CSS/JavaScript prototype. From the repository root run `npm run dev` and visit `http://127.0.0.1:4173/`. The preview server serves this dashboard directory only. ES modules require HTTP; opening `index.html` directly is unsupported.

The preview supports local approval/rejection, question creation, bank filters, exact-order setup and random-rotation configuration, and a channel-wide cooldown **draft**. Local fixture edits are stored in this browser; reset returns sample questions. The game plan is an illustrative 3–5 question range only; no questions are reserved or drawn. The 1–20 round and 0–1000 cooldown form limits are prototype input bounds, not approved product rules.

Run model checks: `node --test apps/dashboard/model.test.mjs`.

This is privileged development fixture data with sample answers and provenance. Never serve it as the viewer Extension bundle. It does not authenticate a streamer or moderator, enforce permissions, connect to FastAPI/Twitch, collect captions, validate source evidence, reserve questions, run games, schedule starts, calculate scores, or recover authoritative progress. Disabled controls identify unimplemented/dependent operations. Scheduling, exact permission grants, cooldown counting/reset, timer recovery and scoring require owner decisions and backend integration.
