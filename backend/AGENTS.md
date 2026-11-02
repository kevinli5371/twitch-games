# Backend implementation context

Read `README.md` and `docs/implementation-plan.md` in this directory as well as the repository product documents. The backend README records newer owner decisions that supersede the original runtime-AI proposal.

- All new backend implementation, tests, configuration, migrations and backend documentation belong under root `backend/`.
- Use Python/FastAPI and Supabase PostgreSQL. Quote selection and matching are algorithmic; no runtime LLM is selected or required.
- The owner superseded the original approval gates: continue through the full backend, verify every stage with live tests where possible, apply/test schema changes in isolated Docker PostgreSQL first, and fix failures. Do not pause for routine stage approval. Ask only for missing configuration or unresolved product choices; continue independent work while waiting.
- After each step, automatically run real-server HTTP checks and relevant live integration tests wherever configured and feasible; do not leave executable verification to the owner. Use repeatable scripts, isolated test resources and cleanup. Report live-process checks separately from unit/in-process tests and from actual Supabase/Twitch/device validation. If credentials, a test channel or another prerequisite is missing, state precisely what could not be verified; do not substitute mocks and call them live tests.
- The original Step 1 mounted only health routes; the current API mounts implemented game/auth routes. Read the current README and frontend handoff. Keep planned game OpenAPI separate from runtime routes. Do not manufacture authenticated users, capture status, persisted games or successful game responses.
- Keep public state, private viewer receipts/results and privileged dashboard candidates in separate schemas. Never send unrevealed answers or source passages through public state or events.
- Preserve typed answers. Matching and scoring run on the backend.
- The owner confirmed moderator question_review may see hidden answers; live_control/settings may not. Check current database grants on every operation, and keep grant administration owner-only.
- Do not settle unresolved gameplay policies through schema defaults, fixtures or implementation convenience.
- Do not claim real Supabase, Twitch, device or deployment testing from local contract tests.
