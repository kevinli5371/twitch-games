# Project context

Read `README.md` and `docs/product-spec.md` before working on this repository. The specification is self-contained and records the owner's decisions; the original chat is not required.

- The initial product is a native Twitch Extension quote-completion game, with a streamer dashboard and separate desktop/mobile presentation.
- Answers are private free text through our UI. Public Twitch chat and OBS are not required for the agreed gameplay.
- Implement only quote mode initially. Niche, hive mind, and ad/other automatic triggers are future work.
- Existing Twitch captions are conditional and the proposed capture path is unverified. Do not claim live capture, platform approval, or device testing unless actually observed.
- Respect the document's **Confirmed**, **Proposed**, and **Open** labels. The owner explicitly requested no assumptions about unspecified product behavior. Ask about unresolved rules before implementing dependent behavior; continue independent work where possible.
- Keep unrevealed answers and credentials off viewer clients. Enforce channel ownership, submission eligibility, and scoring on the backend.
- Record later owner decisions in the spec and keep actual setup, progress, validation, and limitations in the README. Do not present architectural plans as completed implementation.
