# Backend implementation context

Read `README.md` and `docs/implementation-plan.md` in this directory as well as the repository product documents. The backend README records newer owner decisions that supersede the original runtime-AI proposal.

- All new backend implementation, tests, configuration, migrations and backend documentation belong under root `backend/`.
- Use Python/FastAPI and Supabase PostgreSQL. Quote selection and matching are algorithmic; no runtime LLM is selected or required.
- The owner requires tests and an explicit green light at the end of **each** step. Step 1 approval does not authorize Step 2. Report what passed, what was actually exercised and any external validation still missing, then stop.
- Step 1 mounts only honest health routes. Keep planned game OpenAPI separate from runtime routes. Do not manufacture authenticated users, capture status, persisted games or successful game responses.
- Keep public state, private viewer receipts/results and privileged dashboard candidates in separate schemas. Never send unrevealed answers or source passages through public state or events.
- Preserve typed answers. Matching and scoring occur on the backend in later steps.
- Do not settle unresolved gameplay policies through schema defaults, fixtures or implementation convenience.
- Do not claim real Supabase, Twitch, device or deployment testing from local contract tests.
