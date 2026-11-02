# Pixel viewer overlay exploration

November 2, 2026. The owner requested a pixel-game design inspired by [Krillion](https://krillion.io) and UI/UX mockups for all three games. This is an exploratory alternative; it does not replace the existing viewer implementation or settle gameplay-policy differences.

## Open the mockup

Run `npm run dev:design`, then open `http://127.0.0.1:4175/design/pixel.html`. The design workspace footer also links to it. The owner subsequently authorized integrating the pixel direction into the existing viewer. **Integrated viewer** now opens that implementation at `/preview.html`; see [implementation status](viewer-overlay.md). The gallery remains a separate visual exploration.

The lab now defaults to a light exploration for Twitch's white UI: warm white cards, dark text, teal/rose/gold accents and pale tinted prompt panels. The header's **Light / Dark** controls switch the preview and all 12 gallery screens without resetting the active answer draft. `?theme=light` and `?theme=dark` provide direct comparison links; this is a manual prototype selector, not automatic Twitch theme detection. Browser review verified the light desktop card, light Niche result/mobile composition, and draft retention when switching themes. JavaScript syntax and `git diff --check` passed for this theme change.

The mockup is in `apps/design/`, outside the production viewer assets. No backend or Twitch Helper is loaded. Local Silkscreen font files and their OFL license are in `apps/design/fonts/`; the source is [Google Fonts](https://github.com/google/fonts/tree/main/ofl/silkscreen). The sprites and sample broadcast scene are original CSS/SVG artwork, not copied from Krillion.

## Proposed visual direction

Dark navy game panels, stepped corners, hard offset borders/shadows, pixel typography for headings/status, readable system-font prompt text, and original pixel sprites. Quote completion uses cyan/speech bubbles, Niche pink/gems, and Hive Mind yellow/bees. Mode names and instructions communicate differences without relying only on color.

The desktop proposal is a compact bottom-right card over a synthetic broadcast. The mobile toggle demonstrates a separate 390px chat-region composition without a broadcast behind it. These are proposed layouts, not verified Twitch safe zones or device results. The optional scanline texture is confined to the sample broadcast artwork.

## Screens and flows

The static gallery contains answering, submitted, round result, and final standings for each mode (12 mockups). The live preview includes those screens plus interim round standings, closed/waiting, idle, participation permission, disconnected, and submission failure. Result examples offer points, zero points, and no submission. Scores, timer values, receipts and outcomes are labeled samples; typed answers are never evaluated.

| Game | Answering | Illustrative result |
| --- | --- | --- |
| Quote completion | Sourced quote with a blank, one private text field, send action | Full quote with the missing word highlighted; sample point outcome |
| Niche | Category question, uncommon-valid-answer explanation, free text without exposing a valid-word menu | Own answer and an illustrative unique-valid-answer outcome; no public raw-answer list |
| Hive Mind | Category question and most-common-answer explanation, private free text | Own answer and an illustrative most-common-group outcome |

Submitting produces an intermediate **Sending** screen, then a simulated locked receipt after 700ms. There is no edit action in the locked screen. Hiding/restoring retains the sample state. Simulated recovery returns to a confirmed sample answer when available, or preserves unsent draft text. The permission action explicitly simulates permission; it does not grant Twitch access. Round results link to interim standings and back. Final standings list all four sample players. A restart and screen/mode selectors are design controls, separate from the viewer card.

The audience-suggestion form is not mocked here because its fields, supported modes and feedback remain unresolved. The later UI integration uses the existing viewer renderer and transport hooks; backend wiring remains pending.

## Observed validation

- Browser inspected the current Krillion landing and answering screens before designing.
- Verified the 12 gallery cards render for all three modes and the local font loads visually.
- Exercised quote input → Sending → locked receipt, quote reveal, Niche result, Hive Mind result and mobile composition.
- Exercised hide/restore, zero-point result, interim standings navigation, and disconnected recovery to answering.
- All 11 existing Node tests, pixel JavaScript syntax check, and `git diff --check` passed.

No real answer evaluation, Twitch identity, caption collection, live backend, Twitch device/keyboard test, or platform approval was performed.

## Connected integration review

PR #6 now depends on PR #5 (which depends on #4). The shared pixel renderer imports `public/api-adapter.mjs`; it does not retain the earlier proposed headers, snapshot messages or answer contract. The connected quote game keeps editable raw answers, actual backend points, manual rounds and truthful round labels. Compact mode, themes, pixel sprites, in-memory drafts and supplied final standings are preserved. The standalone design gallery still uses labelled sample data. Native viewer/mobile bundled assets use relative paths; the connected server serves the bundled font as `font/ttf`.
