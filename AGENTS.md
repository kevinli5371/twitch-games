# Project context

Read `README.md` and `docs/product-spec.md` before working on this repository. The specification is self-contained and records the owner's decisions; the original chat is not required.

Read `docs/backend-scope.md` for backend ownership, work packages and proposed API contracts. Python + FastAPI and Supabase PostgreSQL are confirmed choices; Kevin owns the backend. The dashboard teammate owns browser-side caption collection.

- The first build includes Quote Completion, Niche, and Hive Mind in a native Twitch Extension, with a separate streamer dashboard and desktop/mobile viewer surfaces.
- Answers are private free text through our UI. Public Twitch chat and OBS are not required for the agreed gameplay.
- Implement all three modes in the first build. Automatic ad/other triggers remain future work.
- Mode selection is per round: streamer-selected or randomized; random selection must exclude the immediately previous mode. Games default to five rounds, configurable by the separate dashboard. A round lasts 30 seconds, the streamer may close early and advance after results, and rounds do not auto-advance. Viewers get one submission per round and no speed bonus.
- Existing Twitch captions are conditional and the proposed capture path is unverified. Do not claim live capture, platform approval, or device testing unless actually observed.
- Respect the document's **Confirmed**, **Proposed**, and **Open** labels. The owner explicitly requested no assumptions about unspecified product behavior. Ask about unresolved rules before implementing dependent behavior; continue independent work where possible.
- Keep unrevealed answers and credentials off viewer clients. Enforce channel ownership, submission eligibility, and scoring on the backend.
- FastAPI remains the game authority. Keep elevated Supabase/database credentials server-side and protect private tables from direct client access. Supabase Auth, Realtime and Queues are not implicitly selected.
- Record later owner decisions in the spec and keep actual setup, progress, validation, and limitations in the README. Do not present architectural plans as completed implementation.
