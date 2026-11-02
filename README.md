# Twitch Games

A Twitch Extension for streamer-controlled games based on the current live broadcast. The first release is a quote-completion game: viewers privately type the missing word from a stream quote and receive points, with interim and final leaderboards.

## Start here

Read the [product and architecture specification](docs/product-spec.md) before implementation. It contains the complete project context, confirmed decisions, proposed architecture, platform constraints, open product questions, and acceptance criteria. No access to the original chat is required.

## Current status

**Documentation only.** This repository does not yet contain application code, installation/run commands, deployments, or validated live integrations. Caption capture, mobile behavior, and Extension approval have not been demonstrated by this repository.

## Agreed first release

- Native Twitch Extension over the video on desktop; mobile-enabled Extension view in Twitch's mobile app.
- Streamer dashboard for activating and monitoring games. OBS is not required.
- Current-stream quote prompts, normally with one missing word.
- Private free-text answers through our UI, with lenient spelling/equivalence handling.
- Interim results and leaderboard, followed by a final leaderboard.
- Quote game only. Niche, hive mind, and automatic triggers such as ad breaks are future work.

Twitch captions are **conditional**, not automatic transcripts for every channel. The spec explains the documented caption path, the required proof of concept, and the unresolved fallback choice.

## Before implementing dependent gameplay

Resolve the [open decisions](docs/product-spec.md#14-decisions-still-needed), including scoring, timing/progression, answer revisions, leaderboard reset boundaries, question approval, and transcript fallback. Proposed recommendations are not confirmed defaults.

Use the [implementation sequence](docs/product-spec.md#16-recommended-implementation-sequence) and [acceptance criteria](docs/product-spec.md#13-first-release-acceptance-criteria) to plan work. Add reproducible setup and test instructions here as the application is implemented. Never commit credentials.
