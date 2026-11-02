# Dashboard design review — November 2, 2026

The owner requested a dashboard in the visual style of [Outcrowd's AI Analytics Dashboard](https://dribbble.com/shots/27167729-AI-Analytics-Dashboard) and an iterative skeptic sub-agent review of visual similarity, working UI, discoverability and copy. This work changes the local dashboard prototype only.

## Implemented design

The owner subsequently requested light mode first. The dashboard now defaults to white/lavender surfaces with dark text and the same violet visualizations/action card. A Dark mode / Light mode control switches the whole workspace, including dialogs, bank and setup, without replacing its state; the theme preference is stored separately from sample bank data. Browser review checked the light overview and question bank and both directions of the theme switch. The existing skeptic approval below covers the original dark layout/workflows; the later light theme received root-agent browser review, not an additional skeptic pass.

Near-black inset app shell, horizontal navigation with a white active pill, compact mode metrics, lavender area chart, violet question-map tiles, saturated purple next-step card, lime status accents, and a bank-composition donut. The chart shows a categorical snapshot of available questions, not invented activity over time. All counts and chart values derive from the browser-local bank. Question-map/status/review shortcuts open corresponding bank views.

All four dashboard areas share the updated visual system. Copy distinguishes working local actions from disabled live actions. Setup displays the newer viewer-first-build defaults already documented in the spec; no backend rules were changed. Rotation configuration is a temporary draft; question-bank changes and the cooldown draft persist locally.

## Skeptic loop and observed evidence

An independent skeptic inspected the reference and exercised the local browser UI. Pass one requested fixes for newly created questions disappearing behind existing filters, reset retaining filters, compressed phone navigation/metrics, and excess mobile chart space. Those fixes were implemented and sent back for review.

Pass two approved the prototype with no remaining material blockers. Observed checks included:

- Desktop reference-style composition and 390px browser layout, including the two-row mobile navigation.
- Invalid quote blank validation and successful creation from Game setup; the new question appears in an exact approved-bank search with heading focus.
- Approval/rejection updating counts, bank search/filtering, persistence across reload, reset restoring three pending questions and clearing filters.
- A cooldown question-map tile opening its matching bank record.
- Exact-order mode editing/removal and the five-round, 30-second, advance-after-results setup copy.
- Clear sample/offline labels and disabled live controls.

The root agent also visually inspected desktop/phone layouts. All 11 Node tests, viewer and dashboard syntax checks, and `git diff --check` passed. Browser test questions were removed using the sample-data reset.

## Limits

This is a design prototype. No live Twitch/backend integration, actual caption capture, authoritative gameplay, device testing, or production deployment was performed. Existing conflicts between broader product plans, the newer viewer-first-build decisions and the quote backend remain integration work; this visual change does not resolve them.
