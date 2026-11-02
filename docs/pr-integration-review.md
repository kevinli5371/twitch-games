# Open PR integration review — November 2, 2026

Reviewed all three open pull requests against current main (`8ef3e1b`). No PR was merged during this review. The intended dependency order is **#4 → #5 → #6**. PR #4 targets main, #5 targets integration/connected-demo, and #6 targets backend/supabase-http. Merge dependencies first and retarget remaining PRs to main as their bases land. No force push or history rewrite was needed.

## Findings resolved

| PR | Finding | Resolution |
| --- | --- | --- |
| #4 | Bundled native viewer/mobile asset URLs began at the host root, losing Twitch CDN extension/version prefixes. | Use relative asset URLs. A real local HTTP regression check loads both entrypoints and every bundled reference below a nested hosted prefix. |
| #6 | Redesign retained its older standalone API implementation; combining it without reconciliation would discard the connected Bearer/state/receipt/PubSub contract. | Import the single connected `public/api-adapter.mjs`; retain dashboard Live game, CSRF/session/permission handling, and distinct labelled fixture tabs. |
| #6 | Redesign removed quote answer editing, trimmed submitted input, and invented five-round labels/progress. | Preserve raw text and editable quote receipts/drafts. Display round counts/progress only when supplied; use actual backend scores and ended status. |
| #6 | Connected static server refused the bundled pixel font. | Serve `.ttf` as `font/ttf`; real HTTP test verifies status, MIME and font bytes. Browser confirms Silkscreen loaded. |
| #6 | Connected controls inherited unreadable text/background colors in the new light theme. | Add light-theme styles for Live game buttons/prompt/timer/errors. Browser inspection confirms dark text on the light controls. |
| #6 | Layout/doc merges could hide the real workspace or present the whole app as disconnected. | Resolve all eight overlapping files, preserve default Live game plus theme toggle, correct footer and update integration documentation. |

PR #5's atomic RPC, storage selection, token/session/grant handling, worker recovery and migration boundaries were reviewed. No additional merge-blocking runtime issue was found in this pass. The hosted 0005 migration was already applied and verified previously; this review did not change/reapply hosted schema or create hosted synthetic games.

## Verification

- PR #4: syntax and **17 Node tests** passed, including nested hosted asset resolution.
- Combined #4/#5/#6: **151 Python tests + 10 subtests** passed. Disposable Docker migration up/repeat/down/up and legacy encrypted-session preservation passed.
- Real Uvicorn SQL and HTTP-storage suites passed with successful cases for **all 24 mounted API operations**, actual 30-second deadlines, process restart, permission/token lifecycle, private edits and scoring.
- Real PostgREST/RPC checks passed rollback, 105 concurrent submissions, retry identity, exactly-once scores, rank outside top 100, refresh fencing, grant revocation and transient startup recovery.
- Actual JavaScript dashboard/caption/viewer clients completed both storage-mode API rounds.
- Combined frontend: **21 Node tests**, syntax, Ruff, formatting and diff checks passed. Late-answer regressions now exercise the real connected adapter/contract rather than the discarded proposed transport.
- Browser round: redesigned dashboard signs in, connects visible fixture source, ingests caption, generates quote, starts/opens a round. Viewer 1 submits raw text with surrounding spaces, edits it, minimizes/reopens with its draft, and submits the correct word. Viewer 2 submits an incorrect answer. Actual timer closes; results show 1/0 points and matching boards. Mobile stays compact across results; reopening restores current state. Ending the game yields final standings and accurate Game ended status; dashboard reload restores saved state. Dark/light switching and fixture-tab labels work.
- Mobile entry measured 390 × 844 with scrollWidth 390 and Silkscreen loaded. Screenshot proof was saved separately with the explicit synthetic-source banner.

The Twitch provider/player/SDK identities and notice transport in repeatable integration/browser checks are explicit fixtures. PostgreSQL/PostgREST/API/workers/clients execute normally. This review does not establish real broadcast captions, installed Extension JWT/identity sharing/PubSub, physical mobile behavior, public HTTPS deployment, production load capacity, or Niche/Hive Mind runtime implementation.

GitHub reported no configured check runs or submitted reviews on the initial PR heads. Local results above are evidence, not a claim of passing GitHub CI or independent approval.

## Merge recommendation

All three PRs are ready for the agreed quote-mode implementation scope after these fixes, in dependency order. They are not a claim of full native Twitch E2E or the broader three-game product. Keep the deferred caption-enabled broadcast, installed Extension and physical-device checks explicit before calling the public demo fully verified.
