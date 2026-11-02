# Backend scope — quote-game MVP

November 1, 2026 · Planning document, not implemented code

This document scopes the backend owned by Kevin. Read it alongside the [product specification](product-spec.md). **Confirmed: Python + FastAPI, Supabase for the managed PostgreSQL database, and approval of this backend work scope.** Backend hosting, model provider, and the gameplay policies listed below remain unselected. Endpoint names are proposed interface details; scope approval does not choose the explicitly unanswered product rules.

## 1. Ownership boundary

| Owner | Responsibility |
| --- | --- |
| Kevin — backend | Streamer authentication, Extension identity verification, channel isolation, transcript ingestion/storage, question generation, game state, private answers, evaluation, scoring, leaderboards, live updates, persistence and backend deployment. |
| Viewer frontend owner | Native desktop Twitch overlay and mobile Extension view, identity-sharing UI, private answer form, results, leaderboards and reconnect states. |
| Dashboard owner | Streamer connection screens, visible embedded-player/caption collector module, transcript status, question queue, controls and monitoring. |

The browser caption collector belongs to the dashboard workstream. Kevin supplies its authenticated intake contract and collaborates on the live-caption feasibility test. The backend does not receive the Twitch channel's audio or captions automatically.

## 2. Proposed runtime

```text
Dashboard caption collector -> FastAPI intake -> database transcript segments
                                                 |
                                         generation job/worker
                                                 |
                                         question candidates
                                                 |
Dashboard controls ---------> FastAPI game service -> database game state
Viewer private answers ---->         |
                               results / scores
                                     |
                         Twitch public update + snapshot APIs
                                     |
                           Desktop / mobile Extension
```

Start with one backend codebase backed by **Supabase PostgreSQL** for game state and work that must survive restarts; do not make process-local dictionaries or sleeping request handlers authoritative. A separate logical worker handles generation/retries without blocking normal requests. The worker/queue implementation and API/worker hosting remain choices to make.

### Supabase boundary

- FastAPI remains the application API and authority for authorization, game transitions, answer evaluation and scoring.
- Supabase supplies the managed PostgreSQL database. It does not by itself deploy the Python FastAPI service or generation worker.
- The proposed MVP clients call FastAPI rather than directly reading/writing private game tables through Supabase's Data API.
- Use a server-side PostgreSQL connection with bounded pooling and transactions for game updates. Select the connection/pooler mode appropriate to the eventual deployment; do not assume every hosting environment has identical connectivity.
- Keep database credentials and elevated Supabase secret keys on the server. A service using elevated access must enforce channel/player authorization itself; elevated credentials can bypass row-level policies.
- Restrict client-accessible database schemas and grants; enable appropriate row-level security on any tables exposed through the Data API. Private transcripts, submissions and unrevealed answers must not become readable through an alternative database endpoint.
- Selecting Supabase does not automatically select Supabase Auth, Realtime or Queues. Twitch OAuth and Extension JWT verification remain required; optional Supabase services must be adopted explicitly where they help.

References: [PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres), [API key privileges](https://supabase.com/docs/guides/getting-started/api-keys), [row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security).

FastAPI supports asynchronous API/database I/O. Its own background-task documentation describes after-response tasks and separate-worker options. A durable, retryable job design is our proposed application requirement; it is not a guarantee supplied by FastAPI `BackgroundTasks`. [Async guidance](https://fastapi.tiangolo.com/async/), [background task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/).

## 3. Backend work packages

### BE-01 — Contracts and foundation

- Define request, response and event schemas before teammates build against them.
- Provide OpenAPI documentation and a versioned set of example payloads.
- Separate public viewer, private viewer and privileged dashboard models.
- Add environment configuration, health/readiness checks, database migrations and reproducible local setup.
- Define error codes for unauthenticated, forbidden, stale round, closed round, duplicate/conflicting action and unavailable transcript.

Done when both frontend owners can build their states against shared fixtures and understand authentication and errors. A fixture is explicitly labeled development data, not live capture.

### BE-02 — Authentication and channel isolation

- Implement the streamer's Twitch OAuth callback, session and logout behavior.
- Verify viewer Extension JWTs, expiry, channel and participation identity.
- Verify identity-sharing requirements for typed submissions.
- Authorize dashboard controls and transcript intake against the connected channel.
- Store secrets on the backend, and enforce each channel's data boundary.

Done when an authenticated owner can control their channel, a viewer can submit only for their authorized channel/round, and invalid or wrong-channel credentials are rejected.

### BE-03 — Transcript intake

- Accept authenticated, ordered caption batches from the dashboard.
- Deduplicate retried batches; retain stream identity, provenance and receipt timing.
- Track latest received text, source freshness and connection gaps.
- Keep current-stream context isolated from other streams/channels.
- Expose intake health to the dashboard.

Done when a real captioned-stream batch reaches storage and a reconnect/retry does not duplicate it. Full live-source feasibility still needs validation. Audio capture/transcription is not silently included if captions are unavailable.

### BE-04 — Quote candidate generation

- Assemble transcript passages and schedule bounded generation work.
- Produce a quote, blank span, canonical answer, alternatives and source reference.
- Validate the selected quote and single blank against the stored source.
- Keep canonical answers and source review details privileged before reveal.
- Deduplicate candidates and expose generation status/failure for the dashboard.
- Implement the agreed candidate approval policy once selected.

Done when a candidate is traceable to actual stream text and cannot enter a round if its quote/blank is invalid. Generate candidates once for a channel rather than separately for each viewer.

### BE-05 — Game lifecycle

- Create a game, open a round with a prepared question, close the round and end the game.
- Implement agreed advancement, timer and cancellation rules.
- Snapshot the chosen prompt and answer policy into the round so subsequent candidate edits cannot change an active game.
- Serialize competing transitions with a stored state version/transaction boundary.
- Persist state and any deadlines; recover correctly after a restart.

Done when repeated commands cannot open competing rounds or accidentally reopen a closed round, and two connected viewers see the same authoritative state.

### BE-06 — Private submissions and evaluation

- Validate participation, answer size, active round and receipt eligibility.
- Acknowledge only server-confirmed receipt.
- Apply the selected one-answer/editable-answer policy.
- Normalize text and apply the agreed typo/equivalence policy consistently.
- Keep evaluation private until the round's reveal.

Done when accepted/rejected spelling examples behave consistently, late answers follow the agreed boundary, and retries do not create unintended duplicate entries. Point values and semantic-equivalence thresholds are not yet defaults.

### BE-07 — Scores, interim results and final leaderboard

- Finalize each submission's outcome and apply the agreed point policy.
- Make score application idempotent and transactional.
- Derive rankings and individual standing from finalized scores.
- Publish interim results and a final leaderboard at the agreed game boundary.
- Preserve evidence/policy versions for investigating an incorrect result.

Done when scoring a round twice produces the same totals and ranking, with the agreed tie and reset rules.

### BE-08 — Synchronization, deployment and verification

- Publish compact public phase/result changes using the agreed Twitch Extension transport.
- Provide fresh snapshots for reconnecting/reopened clients.
- Include channel, game, round and version identifiers in relevant state.
- Keep individual submissions and unrevealed answers out of public updates.
- Deploy API/worker/database with secrets, HTTPS, migrations and observable failures.
- Verify multiple viewers, channel isolation, submission/closure races, retries and restart recovery.

Done when both frontend surfaces can play a full round and recover their state. Mobile rendering and keyboard tests remain owned by the frontend owner, with backend support for integration.

## 4. Proposed API handoff

Route names below are suggestions; agree the exact contract before implementation. Channel path parameters never replace server-side authorization.

| Operation | Proposed endpoint | Access / response boundary |
| --- | --- | --- |
| Begin streamer login / callback | `GET /auth/twitch`, `GET /auth/twitch/callback` | Twitch OAuth; authenticated dashboard session. |
| Read game state | `GET /channels/{channel_id}/game-state` | Viewer-authorized public state; no hidden answer fields. |
| Submit an answer | `POST /rounds/{round_id}/answers` | Verified participating viewer; private receipt. |
| Restore own answer state | `GET /rounds/{round_id}/me` | Only that viewer's receipt and permitted revealed result. |
| Read standings | `GET /games/{game_id}/leaderboard` | Published standings only; reset/tie policy still open. |
| Dashboard snapshot | `GET /dashboard/channels/{channel_id}` | Owner-only context, candidates, current game and metrics. |
| Caption batch intake | `POST /streams/{stream_id}/transcript-batches` | Authorized collector; idempotent batch receipt. |
| Inspect candidates | `GET /streams/{stream_id}/questions` | Owner-only; canonical answers and source evidence. |
| Start game | `POST /channels/{channel_id}/games` | Authorized owner; agreed game policy required. |
| Open round | `POST /games/{game_id}/rounds` | Authorized control path; manual/automatic caller depends on selected progression. |
| Close round | `POST /rounds/{round_id}/close` | Authorized control path; server-enforced closure. |
| End game | `POST /games/{game_id}/end` | Authorized owner; finalization behavior to be agreed. |

Candidate approval/editing, cancellation and manual override endpoints depend on the associated product decisions. Do not expose unfinished operations as working controls.

Public state contains the blanked quote, phase, applicable timing, state version and published results. Private receipts contain submission identity/status. Privileged candidates contain the full quote, canonical answer, alternatives and evidence. Use separate schemas rather than serializing the database record directly to every caller.

## 5. Data and jobs

Logical records: channels/authorizations, streams, transcript segments/batches, question candidates, games, rounds, participants, submissions, score entries and generation jobs. Define migrations and uniqueness/idempotency boundaries for transcript batches, command retries and score entries. Whether answer revisions produce versions or update a single submission depends on the still-open revision rule.

Recommended job properties: explicit queued/running/succeeded/failed states, attempt counts, recoverable claims, source identifiers, bounded retries and a visible failure state. If timed rounds are selected, closing a round must remain possible after a restart and must not depend solely on a live Python task holding a timer.

## 6. Order of delivery

1. **Contract milestone:** shared payload examples, auth expectations and error states unblock both frontends.
2. **Source milestone:** dashboard collector sends real caption text to intake; resolve fallback if it cannot.
3. **Playable milestone:** one prepared quote, one game/round, two private answers, agreed evaluation, interim and final standings.
4. **Dynamic milestone:** replace prepared candidates with validated live-source generation.
5. **Reliable milestone:** real Twitch identity, live synchronization, retries, reconnect/restart behavior and deployment verified together.

Authentication and authorization must protect any publicly deployed milestone. Fixture/auth substitutes, if used for isolated local development, must be explicitly development-only and cannot be represented as validated Twitch integration.

## 7. Explicitly outside this backend release

- Viewer and dashboard visual implementation, except collaborating on contracts and collector integration.
- Niche and hive-mind generation/scoring.
- Automatic ad/event triggers, scheduling and related scopes.
- Public-chat answers, chat moderation or a chatbot.
- VOD imports and long-term historical competitions.
- Monetization and prizes.
- Audio capture/transcription unless explicitly added after the caption feasibility decision.

## 8. Decisions required before dependent implementation

- Round progression: manual open/close, manual open plus timed close, or automatically advancing timed rounds.
- Scoring: correct-answer points, wrong-answer treatment, speed weighting, ties and leaderboard reset boundary.
- Submission policy: final first answer or edits until closure.
- Quote equivalence: typo tolerance and how synonyms/paraphrases are judged.
- Candidate policy: streamer approves questions or generated candidates can be selected automatically.
- Infrastructure: API/worker hosting, PostgreSQL access library and connection mode, worker/job mechanism and model provider. FastAPI and Supabase PostgreSQL are already selected.
- Transcript source when compatible Twitch captions are absent; retention and supported language.

The owner has selected FastAPI and Supabase and approved the backend scope. Explicitly open gameplay and operational choices remain unresolved, not implied defaults.
