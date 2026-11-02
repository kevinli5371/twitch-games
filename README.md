# Twitch Games

A Twitch Extension for streamer-controlled audience games. The first release includes quote completion, niche, and hive mind, with private free-text answers and interim/final leaderboards. Quote completion uses sourced broadcast quotes; historical intake and detailed scoring rules remain backend work to resolve.

## Start here

Read the [product and architecture specification](docs/product-spec.md) before implementation. It contains the complete project context, confirmed decisions, proposed architecture, platform constraints, open product questions, and acceptance criteria. No access to the original chat is required.

Read the [backend scope and API handoff](docs/backend-scope.md) for Kevin's work packages and the contracts used by both frontend owners.

## Confirmed backend stack and ownership

- **Python + FastAPI** for the application backend, owned by Kevin.
- **Supabase PostgreSQL** for durable storage.
- One teammate owns the viewer Extension; another owns the streamer dashboard and browser caption collector.
- Backend hosting, model provider and worker/job mechanism remain unselected. Supabase Auth/Realtime/Queues are not automatically included by the database choice.

## Current status

**Local fixture dashboard and backend foundation.** The dashboard supports local question approval/rejection, creation, filtering, round-order setup, and cooldown drafts. It uses labeled sample data and browser-local storage. Live controls are disabled. The FastAPI foundation supplies contracts, fail-closed authentication/repository seams, a pure planning helper, tests, and a proposed private PostgreSQL migration. It is not a playable live backend.

No deployed service, Twitch authentication, caption capture, historical intake, AI generation, scoring engine, viewer Extension, or real-device validation is implemented/verified. Backend setup and limitations are in [backend/README.md](backend/README.md).

## Run the local dashboard

Requires Node.js 22+; no frontend dependencies or installation are needed.

```powershell
npm run dev
```

Open `http://127.0.0.1:4173/`. If the port is occupied, set `$env:PORT = '4174'` before running. The server binds to loopback and serves only `apps/dashboard/`. This privileged fixture dashboard must never be packaged as viewer Extension assets.

```powershell
npm test
node --check apps/dashboard/app.js
```

Observed November 2, 2026: 10 Node tests pass, JavaScript syntax and `git diff --check` pass. Browser QA verified approval queue updates, creation/search of an approved niche question, exact/random setup switching, adding a round, and a 390px layout without page overflow while retaining Game status. These are local fixture checks, not Twitch/mobile-app validation. Python was not found on PATH, so Python tests/API runtime were not executed; the SQL migration was not applied.

Three fresh skeptic passes reviewed the foundation and drove fixes for hidden-answer authorization boundaries, strict eligibility inputs, dialog naming, mobile status visibility, module delivery, and malformed saved-data crashes. See [implementation review](docs/implementation-review.md). The loop is stopped for the unresolved gameplay decisions listed there.

## Agreed first release

- Native Twitch Extension over the video on desktop; mobile-enabled Extension view in Twitch's mobile app.
- Streamer dashboard for activating and monitoring games. OBS is not required.
- Dashboard direction includes moderator question creation/review, an approved question bank, and streamer-controlled automatic/scheduled games. Detailed workflow and automation/scheduling release placement are being scoped in section 4 of the specification.
- Broadcast quote prompts, normally with one missing word. Previous broadcasts are permitted sources; historical intake is deferred backend work.
- Private free-text answers through our UI, with lenient spelling/equivalence handling.
- Interim results and leaderboard, followed by a final leaderboard.
- Quote completion, niche, and hive mind all launch in the first release. The dashboard supports an exact round order or random rotation with no consecutive rounds of the same mode. Auto + randomized needs no manual mode selection; ad-triggered starts remain future work.
- A game contains streamer-set rounds; each round randomly has 3–5 questions in one mode. Reserve enough approved, off-cooldown questions before starting. Used questions enter a channel-wide cooldown measured in completed games. Low-bank warnings prompt replenishment without pausing an ongoing game.
- Questions auto-advance on streamer-configured timers; authorized operators can pause, skip, or end play. Viewers submit one final answer per question, without edits. Backend equivalent-answer handling is required.
- Scores reset per game; show interim standings after each round and all participants in final standings (zero-score inclusion/presentation still open). Reopening/reconnecting the dashboard resumes from its saved game position; timer recovery details remain open.
- Niche uses a valid-word list with rarity tiers calculated from submitted answers; hive mind identifies the most common submitted answer/group. Exact points and participation-versus-popularity scoring remain open. Automatic-start/scheduling details are explicitly deferred.

Twitch captions are **conditional**, not automatic transcripts for every channel. The spec explains the documented caption path, the required proof of concept, and the unresolved fallback choice.

## Before implementing dependent gameplay

Resolve the remaining [open decisions](docs/product-spec.md#14-decisions-still-needed), especially scoring, equivalence rules, timer/recovery details, permissions, and deferred scheduling/source intake. Answer revisions are disallowed and scores reset per game. Proposed recommendations are not confirmed defaults.

Use the [implementation sequence](docs/product-spec.md#16-recommended-implementation-sequence) and [acceptance criteria](docs/product-spec.md#13-first-release-acceptance-criteria) to plan work. Add reproducible setup and test instructions here as the application is implemented. Never commit credentials.
