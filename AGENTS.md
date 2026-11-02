# Project context

Read `README.md` and `docs/product-spec.md` before working on this repository. The specification is self-contained and records the owner's decisions; the original chat is not required.

Read `docs/backend-scope.md` for backend ownership, work packages and proposed API contracts. Python + FastAPI and Supabase PostgreSQL are confirmed choices; Kevin owns the backend. The dashboard teammate owns browser-side caption collection.

- The initial product is a native Twitch Extension with quote completion, niche, and hive mind, a streamer dashboard, and separate desktop/mobile presentation. All three games launch in the first release.
- Answers are private free text through our UI. Public Twitch chat and OBS are not required for the agreed gameplay.
- One final answer per viewer per question; no edits. Backend equivalence handling is required. Questions auto-advance with operator pause/skip/end controls; scores reset per game. Dashboard reconnection resumes saved progress; detailed timer recovery remains open.
- Previous broadcasts may supply quote questions, superseding current-stream-only scope; historical intake is deferred backend work. Niche rarity tiers and hive mind popularity derive from submitted answers. Exact points remain open; do not infer a formula from tier direction or the owner's participation-based wording.
- The dashboard supports all three modes, moderator question review/creation, an approved question bank, and streamer-controlled automatic/scheduled games. Streamers choose an exact round order or random rotation; random rotation never repeats the same mode in consecutive rounds. The streamer alone grants/revokes moderator permissions. Clarify remaining automation/scheduling details before implementing dependent behavior. Ad triggers remain future work.
- Existing Twitch captions are conditional and the proposed capture path is unverified. Do not claim live capture, platform approval, or device testing unless actually observed.
- Respect the document's **Confirmed**, **Proposed**, and **Open** labels. The owner explicitly requested no assumptions about unspecified product behavior. Ask about unresolved rules before implementing dependent behavior; continue independent work where possible.
- Keep unrevealed answers and credentials off viewer clients. Enforce channel ownership, submission eligibility, and scoring on the backend.
- FastAPI remains the game authority. Keep elevated Supabase/database credentials server-side and protect private tables from direct client access. Supabase Auth, Realtime and Queues are not implicitly selected.
- Record later owner decisions in the spec and keep actual setup, progress, validation, and limitations in the README. Do not present architectural plans as completed implementation.
