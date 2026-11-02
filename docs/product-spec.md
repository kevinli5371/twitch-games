# Stream Quote Game — product and architecture specification

Version: 0.5 · November 2, 2026

This specification captures the agreed product and proposes an architecture for delivering it. It is a product specification, not an implementation or a claim that Twitch captions have been tested successfully. Items marked **Proposed** are recommendations for review. Items marked **Open** have not been decided and must not silently become implementation defaults.

## 0. Start here: context for a fresh implementation agent

The repository is `kevinli5371/twitch-games`. The owner is building a project for the **Codex x TwitchCon Hackathon**. Its product is live, stream-specific audience games controlled by the streamer. The name “Stream Quote Game” in this document describes the initial mode; a final product/brand name has not been selected.

**Repository baseline:** the remote repository was empty when this specification was first added. As of November 2, 2026, this repo has a local overlay preview and Twitch viewer/mobile HTML shells. The backend URL is unconfigured; live game API calls and Twitch Local Test have not yet been validated. No application backend, database, verified caption feed, or completed live/device test is supplied by this repository. Do not interpret architectural diagrams or acceptance criteria as implemented features. External account setup should not be presumed absent or complete.

Read this document without requiring the originating chat. The decision labels mean:

- **Confirmed:** directly requested or accepted by the owner; preserve this behavior.
- **Proposed:** an architecture or interaction recommendation supplied with this spec, available for review; not a user-approved business rule.
- **Open:** a decision the owner has not supplied. Ask before implementing behavior that depends on it. Work on independent foundations can continue.
- **Platform constraint / unverified dependency:** distinguish what the linked documentation describes from behavior actually tested in this project.

The owner explicitly asked that unspecified product behavior **not be assumed**. Routine internal engineering choices may be recommended, but must not settle scoring, session boundaries, automatic advancement, or other open product rules by accident. When decisions arrive, update both the relevant section and the decisions table in section 14.

### Decision history that matters

| Topic | Owner's settled direction / correction |
| --- | --- |
| Ad breaks | The game is **not ad-only**. The streamer may run it whenever they choose. Ad-triggered starts are future work only. |
| Placement | Earlier below-video panel discussions were superseded. The current desktop target is a **native Twitch Extension over the video**. |
| Broadcasting software | OBS is not required for the chosen native Extension. Do not replace it with broadcast graphics as the primary viewer interface. |
| Chat | “Chat” describes the participating audience. Players submit through **our own UI**, not public Twitch chat. |
| Platforms | Account for desktop and mobile. Native desktop and mobile presentation differ; do not promise an on-video mobile overlay. |
| Initial modes | The first build includes quote completion, Niche, and Hive Mind. |
| Mode selection | Each round's mode is either selected by the streamer or randomized. When randomized, exclude the previous round's mode so the same mode never appears twice consecutively. The selection controls are covered in the separate streamer-dashboard specification. |
| Round count | Default each game to 5 rounds. The streamer can change the configured count in the separate dashboard; the game service tracks the selected count and ends the game after that many rounds. |
| Quote answers | Typed free text, normally one missing word, lenient spelling, and reasonable paraphrases/equivalents. Not multiple choice. |
| Control | The streamer chooses when to activate the game, can close rounds early, and advances after results. Each round has a 30-second answer window and does not auto-advance. |
| Results | Interim results/leaderboard and a final leaderboard are required. First-build scoring and tie rules are set in section 8; standings reset per game session. |
| Submissions | One submission per viewer per round, with no speed bonus. Editable submissions are a possible later change. |
| Answer evaluation integration | Backend-owned answer validity and equivalent-answer grouping will be connected later; use placeholders until then. |
| Overlay implementation (Nov 2, 2026) | Keep a standalone local stream preview for iteration and provide Twitch viewer/mobile asset paths that use the Extension Helper. Use a clearly labeled sample adapter until the backend is configured. Do not put the Extension signing secret, Twitch Client Secret, or database credentials in viewer assets. |
| Overlay visibility (Nov 2, 2026) | The streamer can turn the game overlay content on/off for the whole channel. Each viewer can hide/show the Extension for themselves without affecting other viewers or game progress. A viewer cannot enable the Extension on a channel where that broadcaster has not activated it. |
| Round-count edits | Freeze the configured round count when a game starts; dashboard changes apply to the next game. |
| Cancellation | A canceled round awards no points and does not consume the configured count; the streamer opens a replacement round. |
| Leaderboard reset | Scores and standings are scoped to one game session and reset for the next game. |
| Results detail | Show the viewer's own result, points, and published standings. Do not show raw answers from other viewers. Quote Completion reveals its missing word after close. |
| Captions | A documented caption event was researched, but real stream capture has **not** been proven. Automatic transcripts for arbitrary channels are not an available assumption. |
| Backend ownership and stack | Kevin owns the backend, transcript processing and generation. Python + FastAPI and Supabase PostgreSQL are selected; the backend work scope is approved. |

### Product example, not a scoring decision

A captioned passage contains “I cannot believe we won with a spoon.” Quote Completion can present “I cannot believe we won with a ____.” Viewers privately type an answer in the Extension. The backend evaluates answers and publishes results and updated standings. “spoon” is canonical; answer acceptance and equivalence come from the backend integration. The point value, timer, and submission rule for this example follow the first-build rules in section 8.

## 1. Product and agreed scope

Build a Twitch Extension that lets a streamer run games based on what has been said during their live broadcast. Viewers participate through the Extension's own interface. The streamer monitors and controls play from a dashboard.

The first build contains all three game modes:

- **Quote completion:** use a quote from the current stream, normally with one word blanked out. Viewers type the missing word.
- **Niche:** players supply an answer; valid answers submitted by fewer players earn more points.
- **Hive Mind:** players try to match the most common valid answer.
- Select a mode for each round either from the streamer's choice or by random selection. Random selection must exclude the immediately preceding mode; the same mode can recur after another mode has appeared.
- A game has 5 rounds by default. The dashboard may provide a different configured count; the game service records that count and publishes the final leaderboard after that many rounds are complete. Dashboard controls are specified separately.
- Viewers type answers into our UI, rather than public Twitch chat. Each viewer gets one submission per round; editable answers are deferred as a possible change.
- Backend answer validity and equivalent-answer grouping are outside this UI plan and will be integrated later. Use explicit placeholders until connected; do not treat placeholder evaluation as authoritative.
- Award points and show interim results, an interim leaderboard, and a final leaderboard.
- The streamer chooses when to activate the game, can close a round early, and advances after results.
- Use a 30-second answer window. No speed bonus applies, so submitting early gives no advantage. Rounds do not auto-advance.
- Support desktop and mobile viewers.
- Desktop uses a native Twitch Extension over the video. OBS is not required.
- Future automatic triggers, such as starting during an ad break, are accounted for in the architecture but are **not implemented in this release**.

Mode rules and first-build scoring:

| Mode | Agreed direction | First-build scoring / dependency |
| --- | --- | --- |
| Niche | First-build mode; less common valid answers score more. | 3 points for a unique valid answer, 2 when two players submit an equivalent answer, 1 when three or more do; invalid answers score 0. |
| Hive mind | First-build mode; matching the most common valid answer scores. | 1 point to each player in a most-common answer group. If groups tie for most common, all tied groups score; no valid answers means no points. |

Quote completion awards 1 point for a backend-accepted answer and 0 otherwise. Niche equivalence grouping and all mode validity checks depend on the backend integration. The above scores are provisional first-build product rules, not a claim that the backend is already implemented. Chat-command participation, VOD import, monetization, and cross-stream competitions remain outside the agreed scope unless added explicitly.

## 2. Architecture at a glance

```text
STREAMER SIDE

Captioned Twitch player in standalone dashboard
           OR a separately agreed audio/transcription input
                         |
                         v
                 Transcript intake
                         |
                         v
           Timestamped current-stream segments
                         |
                         v
          Quote selection + prompt generation
                         |
                         v
              Candidate question queue
                         |
                         v
Streamer dashboard <--> Game service <--> Durable database
                             |
               Public round updates / snapshots
                             |
                  +----------+----------+
                  |                     |
            Desktop Extension      Mobile Extension
                  |                     |
                  +----- HTTPS answers--+
                             |
                    Answer evaluation
                             |
                  Scores + leaderboards
```

**Confirmed backend choices:** Python + FastAPI for the API and Supabase PostgreSQL for durable storage. Kevin owns backend implementation. See the [backend scope and API handoff](backend-scope.md) for the approved work packages.

The architecture uses two web interfaces, one application backend, a background generation worker, and the database. These are logical responsibilities, not a requirement to create separate microservices. The backend and worker may share a deployment initially. API/worker hosting, frontend framework, database access library, job mechanism, transcription provider, and model provider remain unselected.

Supabase is the database foundation; choosing it does not automatically choose Supabase Auth or Realtime as replacements for Twitch authentication or Extension messaging. The proposed clients call FastAPI for game operations. FastAPI enforces channel/player authorization and keeps unrevealed answers private. Configure database grants/RLS so private records cannot be read through a separate client-facing database API. Supabase does not by itself host the Python application.

### Engineering ownership

| Workstream | Owner / boundary |
| --- | --- |
| Viewer experience | One teammate owns the desktop Twitch overlay and mobile Extension view. |
| Streamer experience | Another teammate owns the dashboard, including the browser-side caption collector. |
| Backend and transcript/AI | Kevin owns authentication, caption ingestion/storage, generation, game state, evaluation, scoring, leaderboards, persistence and synchronization. |

The dashboard teammate implements browser collection against Kevin's authenticated intake contract. The team validates real caption delivery together. No team member should assume the collector or its backend is already implemented.

## 3. Viewer application: Twitch Extension

### Desktop surface

**Confirmed:** native Extension displayed over the video, with free-text answer entry. Viewers do not install a browser extension.

**Proposed interface:** a compact mode card containing the mode-specific prompt, one free-text answer field, a submit button, round status, and the viewer's score. Quote Completion shows the incomplete quote; Niche and Hive Mind show their prompt. Until backend validation is connected, show a clearly labeled placeholder evaluation state. Results and leaderboards occupy the same interface after a round rather than opening another page.

The overlay should avoid unnecessary coverage of the broadcast. Position, dimensions, idle appearance, and how it opens are design decisions still to make. The target is a video-overlay Extension. If a Component Extension is proposed as an alternative, explain its framing/placement differences; do not silently substitute a below-video panel or OBS graphic for the chosen desktop experience.

### Mobile surface

**Confirmed:** a mobile-enabled Extension view, adapted to Twitch's mobile presentation. It is not an on-video replica of the desktop overlay. Mobile viewers open the Extension in the app's chat-region surface.

**Proposed interface:** the same quote and answer field in a vertical layout, with the input kept usable when the keyboard opens. Essential controls must remain reachable in portrait and landscape. Test inside both the iOS and Android Twitch apps.

Twitch supports shared responsive or separate mobile and web front ends. Its mobile policy requires the interface to fit within the stream chat viewport. [Building Extensions](https://dev.twitch.tv/docs/extensions/building/#mobile-support), [mobile requirements](https://dev.twitch.tv/docs/extensions/guidelines-and-policies/#3-mobile).

### Viewer states

| State | Viewer sees | Viewer can do |
| --- | --- | --- |
| Idle | No active game / streamer has not started. | Open the Extension and view participation information. |
| Context unavailable | The game is waiting for sufficient usable stream context. | Wait; no invented live question is substituted. |
| Answering | Mode-specific prompt and 30-second round status/deadline. | Type and submit one answer. |
| Submitted | Server-confirmed submission receipt. | Continue watching; edits are not available in the first build. |
| Closed / scoring | Submissions are closed; results are being finalized. | Wait for results. |
| Round results | Full quote, own outcome, awarded points, interim leaderboard. | View results and wait for the next round. |
| Game ended | Final leaderboard for the completed game. | View final standing. |
| Disconnected | Connection status and retry state. | Reconnect and restore the current server state. |

**Proposed:** do not reveal other viewers' answers or the correct word while submissions are open. The precise content of interim results remains open; participation counts can be shown without exposing answers.

### Overlay visibility controls

- The streamer dashboard has a channel-wide **Show game overlay** toggle. Off hides the game card for all viewers; on restores the current game state. Toggling visibility does not start/end a game, close a round, reset submissions, or change scores.
- A viewer can hide the video-overlay Extension for themselves using Twitch's minimize action/player Extension controls. Restoring it shows the latest game snapshot. This does not change visibility for other viewers or stop the game.
- The broadcaster must first activate the Extension on their channel. Viewers cannot turn it on for a random channel from the viewer side. Twitch also hides video overlays when a channel is offline.
- Mobile remains a separate Extension surface; the video-overlay minimize action applies to video-overlay/component views.

### Identity and answer privacy

Answers go to our backend, not Twitch chat. Distinguish public round information from individual submissions and feedback.

The Extension must follow Twitch's identity requirements for user-submitted text. Its policy requires users to grant access to their Twitch ID before submitting user content. If raw answers are published, additional username-display and moderation requirements apply. [User-content policy](https://dev.twitch.tv/docs/extensions/guidelines-and-policies/#7-moderation).

**Proposed:** allow spectators to view the game; request identity sharing when they choose to participate. Show appropriate permission states. Whether raw answers will ever appear publicly is open; they are not automatically included in a leaderboard.

## 4. Streamer application: standalone dashboard

The dashboard is a separate web application authenticated with the streamer's Twitch account. Keeping it separate makes room for a properly visible embedded player if we use Twitch's caption event. Embedding the dashboard controls in Twitch Live Config can be a later integration.

**Confirmed responsibilities:** activate the game, monitor interim results and leaderboards, and end with a final leaderboard.

**Proposed dashboard areas:**

| Area | Information / controls |
| --- | --- |
| Connection | Connected channel, active stream, transcript-source status. |
| Transcript | Recent text, capture freshness, gaps or missing captions. |
| Question queue | Incomplete quote, canonical answer, supporting source text and timestamp, generation status. |
| Game controls | Start game, start/advance round, close round, cancel round, end game. |
| Live monitoring | Current prompt, participation count, round state, scoring status. |
| Results | Round outcome, interim leaderboard, final leaderboard. |

Question approval/editing and manual advancement are **proposed**, not yet agreed behavior. Whether the streamer approves every candidate or allows automatic selection must be decided before implementing that workflow.

Only authorized channel controllers may start games, see unrevealed answers, or manage questions. Moderator/editor access is not part of the agreed scope.

## 5. Transcript intake

### Twitch caption path

Twitch's embedded player documents `Twitch.Player.CAPTIONS`, which supplies caption text in batches when compatible captions exist in the video being played. This is not a general Helix transcript endpoint, and a channel connection alone does not create captions. [Player caption event](https://dev.twitch.tv/docs/embed/video-and-clips/#javascript-events).

**Proposed flow:**

1. The streamer opens a visible Twitch player in our standalone dashboard.
2. Dashboard code receives caption batches from that player.
3. Authenticated intake sends the batches to the backend for that channel and stream.
4. Intake records source timestamps where available, server receipt time, ordering, and provenance.
5. Text is deduplicated and assembled into candidate quote passages.

`Twitch.Player.CAPTIONS` is a client-side embedded-player event, **not an EventSub subscription** and not a `Twitch.ext` method. The Extension iframe cannot simply attach a listener to Twitch's enclosing channel player. The proposed collector runs in our standalone dashboard around a player we create there. The documented caption payload is text, not a guaranteed word-level timestamp/speaker record; preserve receipt and playback context without fabricating precise timing or speaker attribution.

The dashboard embed must follow Twitch's visibility, minimum-size, HTTPS, and parent-domain requirements. It must not be hidden as a background transcript extractor. [Embed requirements](https://dev.twitch.tv/docs/embed/#embedded-experiences-requirements).

**Unverified dependency:** test actual caption delivery and completeness on a real captioned channel before committing to this as the primary input. This design also depends on the intake dashboard remaining open and receiving captions. Show source freshness and stop generating new candidates when intake is stale; do not pretend capture continues after disconnection.

### Fallback decision

**Open:** when captions are absent, should the first release require the streamer to enable compatible captions, or should we build streamer-authorized microphone/broadcast-audio transcription?

An audio path would add capture controls, a transcription integration, capture status, and stop/pause behavior. Capturing a microphone alone does not capture the entire broadcast mix. That work is not silently included in the first release.

### Transcript boundaries

- Use material from the current stream for first-release prompts.
- Preserve evidence linking each generated question to the transcript it came from.
- Do not treat transcript text as instructions to the generation system.
- Do not infer that a named speaker is the streamer unless the source establishes that identity.
- Do not generate questions about visual events solely from an unrelated speech transcript.
- Transcript retention, supported languages, and which speakers are eligible for quote questions remain open.

## 6. Quote selection and prompt generation

**Confirmed output:** a real quote with normally one missing word, answered through free text.

**Proposed generation pipeline:**

1. Assemble complete passages from the recent transcript.
2. Select a passage with enough context to support an answer.
3. Choose a single word to remove.
4. Construct the blanked quote directly from the stored source, preserving the surrounding text.
5. Store the canonical word, proposed accepted alternatives, source reference, and source excerpt.
6. Validate the candidate and place it in the dashboard queue.

The model may select the passage and blank, but it must not invent or rewrite a sentence and present it as a verbatim quote. A transcript is still an imperfect record of speech; the dashboard must expose its source for inspection.

**Proposed rejection conditions:** incomplete or garbled source, no clear answer, overly ambiguous blank, repeated candidate, stale/wrong-stream source, or a source passage inappropriate to publish as a game prompt.

Generate a shared question queue for the channel, not a separate queue for every viewer. Generation frequency, minimum context, quote age, repeat limits, and prompt approval policy are open configuration decisions.

## 7. Game service and round lifecycle

**Proposed terminology:**

- **Stream:** the Twitch broadcast providing source material.
- **Game session:** one streamer-started run ending with a final leaderboard.
- **Round:** one mode-specific prompt within that game session.

Scores and standings belong to one game session and reset when a new game begins.

**Proposed session lifecycle:**

```text
Inactive -> Active -> Ended
```

**Proposed round lifecycle:**

```text
Prepared -> Answering -> Closed -> Scored -> Results
                |          |
                +----------+-> Cancelled
```

The backend owns transitions, deadlines, question selection, submission eligibility, and score updates. A viewer's clock or UI cannot reopen a closed round.

**First-build operational rules:** one active round per channel; default to 5 rounds per game, with a dashboard-supplied configured count frozen when the game starts; use a 30-second answer window; close submissions automatically at expiry; the streamer may close early and advances after results; rounds do not auto-advance. The game service tracks completed rounds and ends the game with a final leaderboard after the configured count. Do not open a round without a prepared prompt; preserve completed results; cancelled rounds award no points and do not consume a round from the configured count.

### Per-round mode selection

For each new round, use either a streamer-specified mode or random selection from the three first-build modes. In random mode, remove the immediately previous round's mode from the candidate set, then choose from the remaining modes at random. For the first round, choose from all three at random. This guarantees no identical adjacent modes while allowing a mode to recur later. The game service enforces the rule; dashboard selection controls are specified separately.

### Future triggers

All starts flow through the same authorized game-start operation. Initially, only the dashboard calls it. Later, an ad-break adapter or another trigger can invoke that operation with an explicit trigger source.

Do not implement ad-event subscriptions, scheduling screens, trigger configuration, or ad-related permissions in this release. The architecture should permit them without coupling the game engine to ad logic.

## 8. Answer evaluation and scoring

**Confirmed:** free-text answers; normally a one-word blank; leniency for spelling and reasonable equivalents.

**Proposed evaluation sequence:**

1. Validate the authenticated player, channel, active round, and submission eligibility.
2. Store the submitted answer privately and acknowledge receipt.
3. Normalize case, whitespace, and agreed punctuation differences.
4. Compare with the canonical answer and approved alternatives.
5. Apply a bounded spelling-tolerance rule for unmatched answers.
6. Resolve any supported semantic equivalents consistently against the source context.
7. Finalize the result and points according to the round's scoring policy.

Do not accept every near-spelling automatically: short words such as “cat” and “car” demonstrate why edit distance alone is insufficient. Do not allow a model to invent new scoring criteria per player.

**Proposed implementation approach:** establish the accepted-answer policy before opening the round, evaluate repeated normalized answers consistently, and avoid an unrestricted model call for every keystroke or submission.

**First-build scoring rules:**

- Quote Completion: 1 point for a backend-accepted answer; otherwise 0.
- Niche: 3 points for a unique valid answer, 2 points when exactly two players submit equivalent valid answers, and 1 point when three or more do; invalid answers score 0.
- Hive Mind: 1 point for each player in the most common valid answer group. If multiple groups tie for most common, players in all tied groups score. If there are no valid answers, no one scores.
- Equal cumulative scores share a competition rank. Display order among tied players does not change score or rank.
- There is no speed bonus. A viewer gets one submission per round; answer editing is deferred as a possible change.
- Each round has a 30-second answer window. The backend closes on expiry; the streamer can close early and advance after results. No automatic round advancement.

The UI can use placeholder evaluation until the separately developed backend supplies answer validity and equivalent-answer grouping. Do not represent placeholder evaluation as authoritative scoring. Scores must be applied exactly once per accepted result, even when requests or events are retried. Never deliver unrevealed answers or private scoring keys to viewer clients.

## 9. Results and leaderboards

**Confirmed:** interim results and leaderboard, followed by a final leaderboard at the end.

**Proposed round-results view:** complete quote, canonical missing word, the player's result, points earned, updated cumulative score, and current leaderboard. Include the source timestamp where meaningful.

**Proposed leaderboard entries:** display name, score, rank, and the current player's position even if outside the visible leaders.

The backend calculates rankings from finalized score records. All clients receive the same finalized ranking version. Ties share competition ranks. The number of visible entries, exact interim-result breakdown, and historical retention are open. Scores reset with each new game session. Finalization ends submissions for that game session and publishes its final standings.

## 10. Backend interfaces and real-time delivery

The following are proposed logical operations, not a locked URL design:

| Interface | Caller | Purpose |
| --- | --- | --- |
| Read public game snapshot | Viewer Extension | Restore current public round, phase, deadline, and published leaderboard. |
| Read own participation state | Authenticated viewer | Restore own submission receipt and any revealed result. |
| Submit answer | Authenticated viewer | Submit privately to the current round. |
| Ingest transcript batch | Authorized intake client | Append current-stream source text. |
| Manage candidate question | Authorized dashboard | Inspect and perform agreed candidate actions. |
| Start / advance / close / cancel / end | Authorized dashboard | Apply agreed lifecycle transitions. |
| Read monitoring state | Authorized dashboard | Show source health, participation, scoring, and results. |

**Proposed real-time approach:** use Twitch Extension PubSub for compact public round/phase/result updates, and authenticated HTTPS for answers, snapshots, and private feedback. Twitch documents this backend-to-Extension messaging pattern. [Extension backend and messaging](https://dev.twitch.tv/docs/extensions/building/).

Every update carries a channel ID, session ID, round ID when applicable, and state version. Reopening or reconnecting fetches a fresh snapshot rather than relying on having received every event. Public broadcasts do not contain individual unrevealed answers or the canonical word before reveal.

Validate Twitch Extension tokens on the backend. Verify the caller's channel and role for controller operations; never trust a channel ID or streamer role supplied only by the client. Keep model keys, OAuth tokens, and Extension signing secrets on the backend.

## 11. Data model

| Entity | Purpose / principal fields |
| --- | --- |
| Channel | Twitch channel ID; agreed settings and authorization references. |
| Stream | Twitch stream ID; channel; start/end; transcript-source state. |
| Transcript segment | Stream; sequence; source/receipt timestamps; text; provenance. |
| Question candidate | Stream; source references; complete quote; blanked quote; canonical word; alternatives; validation/review state. |
| Game session | Channel; stream; mode; state; start/end; scoring-policy version. |
| Round | Session; candidate; lifecycle state; timing; answer-policy version. |
| Participant | Twitch identity; display information; participation permissions. |
| Submission | Round; participant; answer; normalized answer; receipt time; evaluation state. |
| Score entry | Session; round; participant; finalized outcome; awarded points; policy version. |

Leaderboard views are derived from score entries. Transcript access, raw-answer access, retention periods, transcript deletion, and whether historical final boards remain accessible need explicit decisions before public launch.

## 12. Failure behavior and validation

| Condition | Required / proposed behavior |
| --- | --- |
| No captions or stale intake | Show unavailable/collecting status; do not fabricate a live-source question. |
| Generation fails | Keep the question out of the playable queue; show dashboard status. |
| Viewer reconnects | Fetch current state and own submission status; preserve server-confirmed scores. |
| Submission retry | Apply the agreed answer-revision policy without accidental duplicate scoring. |
| Round closes during submission | Decide acceptance using the server's agreed deadline rule. |
| Extension is hidden | Restore state on return; scoring does not depend on the UI staying mounted. |
| Dashboard disconnects | Intake status becomes stale; already-confirmed game state remains durable. Exact round continuation policy is open. |
| Answer dispute | Preserve the source and evaluation record. Streamer override capability is an open decision. |

Validation must cover the real caption event, desktop player Extension, iOS and Android entry/keyboard behavior, authorization, wrong-channel isolation, unrevealed-answer leakage, spelling acceptance/rejection, closure boundaries, reconnection, and duplicate score prevention. Load targets and expected concurrent player counts have not been specified.

## 13. First-release acceptance criteria

These describe the intended outcome; unresolved rules below must be filled in before using them as a final implementation checklist.

1. A streamer connects a channel and sees whether the selected transcript source is working.
2. The app obtains real current-stream text through the agreed source path.
3. A generated question is traceable to an actual stored quote and removes normally one word.
4. The streamer can activate and end a game in any of the three modes through the dashboard.
5. The same active round is available through the desktop and mobile Extension views.
6. Eligible viewers submit answers through our UI, privately to the backend.
7. The three modes use the first-build scoring rules in section 8; answer validity and equivalent-answer grouping are supplied by the backend integration, with placeholders until it is connected.
8. Players see confirmed submission state, interim results/leaderboard, and a final leaderboard.
9. Reconnection restores current state and does not duplicate points.
10. The streamer can hide/show game content for the whole channel without changing game state; a viewer can minimize/restore the Extension for themselves without affecting others.
11. Automatic triggers are not implemented or presented as working features.

For the hackathon, Extension approval is a separate delivery dependency. The organizer warns of a 5–14 day review window and says judges cannot install unreviewed Extensions. A standalone test/judging surface is a proposed contingency, not an agreed replacement for the Extension. [Hackathon FAQ](https://twitchcon-codex.devpost.com/resources).

## 14. Decisions still needed

| Decision | What is known | What remains open |
| --- | --- | --- |
| Transcript fallback | Current-stream text powers questions; Twitch captions are conditional. | Require captions, or add live audio transcription in the MVP? |
| Question approval | Prompts are generated dynamically. | Streamer approves/edits each prompt, or generation can publish automatically? |
| Round progression | 30-second answer window; streamer can close early and advance after results; no auto-advance; 5 rounds by default, configurable through the dashboard. | None. Round-count changes apply to the next game; canceled rounds do not count and are replaced. |
| Mode selection | Streamer choice or random per round; random mode excludes the immediately previous mode. | None; dashboard controls are documented separately. |
| Scoring | Section 8 defines first-build mode scores and tie rules; no speed bonus. | Adjudication/override powers. |
| Answer revisions | One submission per viewer per round. | Editing may be considered later. |
| Equivalents | Backend provides validity and equivalent-answer grouping; UI uses placeholders until connected. | Backend policy details and final integration contract. |
| Leaderboard boundary | Scores reset for each game session; interim and final boards exist. | None. |
| Result detail | Show personal result, points, and published standings; reveal the missing quote word after close; do not show other viewers' raw answers. | None. |
| Source eligibility | Quotes come from the stream so far. | Only the streamer, or other speakers too; supported languages; minimum quote age? |
| Operations | Durable state and source status are required. | Retention periods, deployment budget, concurrency target, and dashboard-loss behavior. |

The rules recorded above reflect explicit owner decisions and implementation choices for the first build. Remaining open items are not resolved by implication.

## 15. Twitch integration prerequisites and boundaries

These are setup requirements for the proposed design, not credentials or integrations already supplied by this repository.

| Integration | Required setup / boundary |
| --- | --- |
| Streamer authentication | Register/configure a Twitch OAuth application and callback URLs for the standalone dashboard. Authenticate the channel owner and request only scopes required by the implemented features. App registration and Extension registration are separate integration concerns. |
| Viewer Extension | Register the Extension, configure its desktop video-overlay and mobile viewer paths, include the Extension Helper, and configure its configuration view as needed for activation. The desktop/mobile assets can share application code. |
| Backend connectivity | Configure the Extension's allowed backend domains. Production viewer assets are packaged/hosted through Twitch's Extension system; the application backend and standalone dashboard require their own hosting. |
| Viewer identity | Use the Extension's authenticated context and identity-sharing flow. Do not equate an opaque Extension identifier with a disclosed Twitch user ID or trust a username sent in a request body. |
| Controller authorization | A streamer OAuth session or verified Extension broadcaster context authorizes only its own channel. The server must enforce this on every control and transcript-intake operation. |
| Captions | Use a compliant visible embedded player in the standalone dashboard for the caption proof of concept. A native viewer Extension is not an audio capture API. Do not assume access to another Extension's captions, raw stream media, or a full transcript download endpoint. |
| Live updates | Extension PubSub delivers compact public state changes. HTTPS endpoints deliver snapshots and receive private answers. Check current Twitch quotas before implementation and avoid broadcasting every individual answer. |
| Secrets | Keep OAuth secrets/tokens, Extension signing secrets, database credentials, and model-provider keys out of viewer bundles and Git. Public configuration such as a client ID is distinct from a secret. |

No chat-bot permissions or ad-related scopes are needed merely to support the agreed private-UI game. Add scopes only if a separately agreed feature actually needs them. The current input path needs no imaginary “read transcript” OAuth scope.

Use Twitch's [app registration](https://dev.twitch.tv/docs/authentication/register-app/), [Extension setup](https://dev.twitch.tv/docs/extensions/), [Extension backend guide](https://dev.twitch.tv/docs/extensions/building/), and [identity/helper reference](https://dev.twitch.tv/docs/extensions/reference/) as primary integration references. Platform behavior and submission rules may change; recheck relevant documentation during implementation.

## 16. Recommended implementation sequence

This sequence is a proposal for reducing uncertainty, not authorization to choose unresolved gameplay defaults.

1. **Resolve the transcript feasibility dependency.** With an owner-supplied test channel, prove that a visible dashboard player receives actual live caption batches. Report which channel/setup was tested, whether captions are complete enough, and what happens when captions stop. If unavailable, return to the fallback decision rather than quietly implementing audio capture or scraping undocumented endpoints.
2. **Connect backend answer evaluation.** Agree the validity/equivalence contract with the backend owner and replace UI placeholders. The first-build scoring, one-submission rule, timer, and streamer round controls are already set in sections 7 and 8.
3. **Build one end-to-end vertical slice.** Use a clearly labeled source fixture to prepare one real quote, display it in the Extension preview, accept a private answer, close the round, and show a result using the agreed scoring policy. Fixture mode is a development aid; it must never be labeled live caption capture.
4. **Connect real transcript intake and generation.** Preserve source text and validate the chosen blank by character span against that exact text. Blank one occurrence, including when a word appears more than once. Validate model output before adding candidates to the playable queue.
5. **Complete the streamer-controlled game.** Implement the agreed session/round transitions, interim and final leaderboards, and dashboard monitoring with durable state.
6. **Validate actual Twitch surfaces.** Test desktop Extension behavior and the separate iOS/Android view, including input focus, keyboard opening, hidden/reopened state, reconnection, and identity permissions.
7. **Prepare judging and release materials.** Follow the rules below; identify any unverified behavior or Extension approval dependency honestly.

Maintain a concise actual setup guide in the README as code is added: prerequisites, install/run commands, environment-variable names without values, callback/domain setup, migrations, fixtures, tests, and known limitations. Record commands actually run and results observed; do not claim live-platform or device validation based solely on a browser preview.

## 17. Hackathon context and deliverables

Historical context for this specification: the submission window is October 23–November 2, 2026, with a deadline of November 2 at 2:00 p.m. Pacific / 5:00 p.m. Toronto time. This is a dated deadline, not an instruction to treat it as upcoming if this document is read later.

The project must be newly built during the submission period, connect interactively to Twitch, and be built using OpenAI Codex. **This development-tool requirement does not by itself select a runtime model or speech-to-text provider.** Keep the Codex build thread/session ID for submission.

Required deliverables include a runnable source repository with assets/setup instructions; an English description explaining the functionality and Codex use; a publicly accessible YouTube demo under three minutes showing Twitch functionality and Codex use; and the relevant Codex session ID. The FAQ allows an unlisted video. Private repositories must be shared as directed by the organizer. Recheck the actual rules before submitting.

The Extension review issue described in section 13 is a delivery dependency. Do not claim that a preview or test-mode Extension is approved or publicly installable. A standalone judging preview can reuse game code if agreed, but must not be presented as the shipped Twitch Extension.

Primary sources: [official rules](https://twitchcon-codex.devpost.com/rules), [requirements](https://twitchcon-codex.devpost.com/), [FAQ/resources](https://twitchcon-codex.devpost.com/resources).

## 18. Handoff completion checklist

A fresh implementation agent should be able to explain, without the original chat:

- What the first-release quote game does, which modes are deferred, and why it is not ad-only.
- Why the primary desktop surface is a Twitch Extension, why OBS is unnecessary, and how mobile differs.
- Where typed answers go and why Twitch chat is not the required input surface.
- Which service owns game state, source evidence, answer evaluation, and scores.
- Why captions are conditional, where the caption collector runs, and what has not been tested.
- Which product rules are confirmed versus still open, and which independent work can proceed.
- What integration setup, live/device tests, and hackathon deliverables remain outstanding.

When implementation starts, preserve this document as the product source of truth and update the repository's status to describe actual progress. New explicit owner decisions supersede earlier proposals; document those changes rather than carrying contradictory requirements forward.
