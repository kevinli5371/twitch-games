# Runtime endpoint verification

Observed November 2, 2026. Every operation in the running server’s OpenAPI had a successful HTTP case against real Uvicorn and isolated Docker PostgreSQL. Twitch used the explicitly labelled loopback HTTP fixture. This is backend integration coverage, not frontend/device or production Twitch E2E verification.

`scripts/postgres_checks.py` runs the check; `scripts/live_game_checks.py` compares observed responses with runtime OpenAPI and fails if any operation lacks a 2xx/3xx response. The generated machine-readable report is ignored at `.cache/endpoint-coverage.json`.

| Method | Runtime path | Observed HTTP statuses |
| --- | --- | --- |
| DELETE | `/api/v1/channels/{channel_id}/moderators/{moderator_id}` | 204 |
| GET | `/api/v1/auth/me` | 200, 401 |
| GET | `/api/v1/auth/session` | 200 |
| GET | `/api/v1/auth/twitch` | 302 |
| GET | `/api/v1/auth/twitch/callback` | 200 |
| GET | `/api/v1/channels/{channel_id}/aliases` | 200 |
| GET | `/api/v1/channels/{channel_id}/game-state` | 200, 401 |
| GET | `/api/v1/channels/{channel_id}/moderators` | 200 |
| GET | `/api/v1/dashboard/channels/{channel_id}` | 200, 403 |
| GET | `/api/v1/games/{game_id}/leaderboard` | 200 |
| GET | `/api/v1/rounds/{round_id}/me` | 200, 404 |
| GET | `/api/v1/streams/{stream_id}/questions` | 200, 403 |
| GET | `/health/live` | 200 |
| GET | `/health/ready` | 200 |
| POST | `/api/v1/auth/logout` | 204 |
| POST | `/api/v1/channels/{channel_id}/games` | 201 |
| POST | `/api/v1/channels/{channel_id}/stream` | 200 |
| POST | `/api/v1/games/{game_id}/end` | 200 |
| POST | `/api/v1/games/{game_id}/rounds` | 201 |
| POST | `/api/v1/rounds/{round_id}/answers` | 202, 403, 409, 413 |
| POST | `/api/v1/rounds/{round_id}/close` | 202 |
| POST | `/api/v1/streams/{stream_id}/transcript-batches` | 202 |
| PUT | `/api/v1/channels/{channel_id}/aliases` | 200 |
| PUT | `/api/v1/channels/{channel_id}/moderators` | 200 |

A successful case for each route does not establish exhaustive error, concurrency, browser, or platform coverage. See [backend-verification.md](backend-verification.md) for additional observations and outstanding checks.
