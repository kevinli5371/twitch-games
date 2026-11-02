# Frontend contract handoff — draft 0.1

These are proposed gameplay contracts, **not implemented game endpoints**. The running foundation serves only `/health/live`, `/health/ready`, `/docs` and `/openapi.json` where enabled. Planned gameplay paths currently return 404. Do not connect frontend writes to them expecting data to persist.

The generated [planned OpenAPI](openapi.planned.json) specifies request/response models and intended authorization. [examples.json](examples.json) contains artificial fixtures for UI development. The exporter and tests keep the files aligned with Python models. None of the fixture text, IDs, scores or timestamps came from a live stream.

## Three separate data boundaries

| Audience | Data | Never include before reveal |
| --- | --- | --- |
| Viewer public state | Channel/game IDs, version, phase, blanked prompt, applicable timing. | Canonical answer, accepted aliases, full quote or source evidence. |
| Private viewer | Server-confirmed receipt, then own result when permitted. | Another viewer's submission or premature correctness feedback. |
| Privileged dashboard | Source health, candidates with canonical answers/evidence, game state, submission count. | Secrets or unrelated channel data. |

`HiddenRound` and `RevealedRound` are separate variants, discriminated by `phase`. Only `phase: results` has reveal fields. All contract objects reject unknown fields. These safeguards constrain serialization; actual authorization and phase enforcement still require the later backend implementation.

## Proposed routes

All routes below are prefixed `/api/v1` and marked planned in the generated file.

| Method/path | Caller | Contract |
| --- | --- | --- |
| `GET /channels/{channel_id}/game-state` | Viewer | `PublicGameState` |
| `POST /rounds/{round_id}/answers` | Participating viewer | `AnswerSubmission` → HTTP 202 `SubmissionReceipt` |
| `GET /rounds/{round_id}/me` | Same viewer | `OwnParticipation` |
| `GET /games/{game_id}/leaderboard` | Viewer | `Leaderboard` |
| `GET /dashboard/channels/{channel_id}` | Streamer | `DashboardSnapshot` |
| `POST /streams/{stream_id}/transcript-batches` | Streamer-authenticated collector | `TranscriptBatch` → HTTP 202 `BatchReceipt` |
| `GET /streams/{stream_id}/questions` | Streamer | List of privileged `QuestionCandidate` |
| `POST /channels/{channel_id}/games` | Streamer | `StartGame` → HTTP 201 `PublicGameState` |
| `POST /games/{game_id}/rounds` | Authorized control path | `OpenRound` → HTTP 201 `PublicGameState` |
| `POST /rounds/{round_id}/close` | Authorized control path | `GameCommand` → HTTP 202 `PublicGameState` |
| `POST /games/{game_id}/end` | Streamer | `GameCommand` → `Leaderboard` |

Twitch OAuth start/callback and logout contracts are reserved for Step 3; no unauthenticated auth stub is provided now. Viewer gameplay requests will use an `Authorization: Bearer <Twitch Extension JWT>` header. Dashboard requests will use a streamer session; the draft cookie name is `twitch_games_session`. Cross-origin session requests need explicit origins, credential handling and CSRF protection in Step 3. Cookie mechanics and OAuth setup are not implemented here.

Path channel IDs do not authorize access. The server must bind tokens/sessions to the channel and player, validate identity-sharing requirements and verify controller roles. Supabase keys never belong in viewer payloads.

## Request and state conventions

- IDs are opaque strings; Twitch channel IDs are decimal strings. IDs in fixtures are examples, not a chosen database primary-key format.
- Times are timezone-aware ISO 8601 strings. `server_time` supports reconnection/timer display; client clocks do not decide acceptance. `closes_at` is nullable until round policies are settled, not evidence that rounds are always manual.
- `request_id` is a client-generated UUID for retry identity. Reuse it only for the same request. Exact idempotency storage and answer revision semantics are implemented later; it is not permission for unlimited guesses.
- `expected_version` is a proposed concurrency guard on control commands. State versions are monotonic within their documented scope; clients reload a snapshot after stale-state errors or reconnects.
- `policy_id` is required to avoid silently choosing scoring/progression defaults. No selectable policy is implemented yet. Frontends must not hardcode the example policy as a real one.
- Answer transport accepts up to 256 characters, preserves entered spelling/case/spaces and rejects blank/control-character input. This is an input bound, not the final one-word/equivalence rule. Never send a client verdict or point award.
- Caption batches accept 1–100 segments with sequence numbers, text and `observed_at`. Text is bounded to 4,000 characters per segment. These are draft transport bounds, not a promise of matching Twitch's native batch structure. `observed_at` is collector observation time, not guaranteed word-level video timing.
- A received submission is not a correct answer. A private result includes an explicit scoring-policy identifier after reveal. Example points do not establish the future formula.

## Event contract

`StateChanged` contains `event: game_state_changed`, `channel_id`, `version` and public `state`. The identifiers must agree with the enclosed snapshot. The proposed transport is Twitch Extension messaging, not a browser subscription to raw private database tables. No transport is wired in Step 1. Check platform payload/rate limits before finalizing the event implementation.

Clients should reload HTTP state on reconnect or missed versions and use `/me` to restore their own receipt. Do not assume the Extension stays mounted when hidden or that an event was delivered exactly once.

## Proposed error envelope

```json
{"error":{"code":"round_closed","message":"This round is closed."}}
```

| HTTP status | Proposed application codes |
| --- | --- |
| 401 | `unauthenticated` |
| 403 | `forbidden` |
| 404 | `not_found` |
| 409 | `stale_state`, `round_closed`, `request_conflict`, `policy_unresolved` |
| 422 | `validation_error` |
| 503 | `transcript_unavailable` |

This envelope is reserved for later gameplay handlers. FastAPI's foundation 404s are its normal `detail` response; `/health/ready` has its separately documented readiness body. Do not assume planned errors are already installed globally. Error messages must not echo credentials, source text or answer keys.
