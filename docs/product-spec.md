# Stream Quote Game — product and architecture specification

Version: 0.5 · November 1, 2026

This specification captures the agreed product and proposes an architecture for delivering it. It is a product specification, not an implementation or a claim that Twitch captions have been tested successfully. Items marked **Proposed** are recommendations for review. Items marked **Open** have not been decided and must not silently become implementation defaults.

## 0. Start here: context for a fresh implementation agent

The repository is `kevinli5371/twitch-games`. The owner is building a project for the **Codex x TwitchCon Hackathon**. Its product is live, stream-specific audience games controlled by the streamer. The name “Stream Quote Game” in this document describes the initial mode; a final product/brand name has not been selected.

**Repository baseline:** the remote repository was empty when this specification was added. This commit provides documentation only. There is no application, dependency setup, database, deployed backend, registered Extension, configured OAuth integration, verified caption feed, or completed test run supplied by this repository. Do not interpret architectural diagrams or acceptance criteria as implemented features. External account setup has not been inspected and must not be presumed absent or complete.

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
| Initial modes | Quote completion, niche, and hive mind all launch in the first release. Design the dashboard for all three. |
| Quote answers | Typed free text, normally one missing word, lenient spelling, and reasonable paraphrases/equivalents. Not multiple choice. |
| Control | Hybrid operation: streamer-controlled automation and scheduling, with moderator-reviewed questions entering an approved bank for automatic play. Detailed permissions, triggers, and progression rules remain open. |
| Results | Scores reset per game; show interim standings after each round and everyone at game/session end. Exact points and final-list presentation remain open. |
| Captions | A documented caption event was researched, but real stream capture has **not** been proven. Automatic transcripts for arbitrary channels are not an available assumption. |
| Backend ownership and stack | Kevin owns the backend, transcript processing and generation. Python + FastAPI and Supabase PostgreSQL are selected; the backend work scope is approved. |

### Product example, not a scoring decision

A captioned passage contains “I cannot believe we won with a spoon.” The game can present “I cannot believe we won with a ____.” Viewers privately type an answer in the Extension. At the agreed round boundary, the backend evaluates answers and publishes results and updated standings. “spoon” is canonical; whether another word or typo is accepted follows the answer policy that still needs to be finalized. No example here establishes a point value, timer length, or answer-editing policy.

## 1. Product and agreed scope

Build a Twitch Extension that lets a streamer run games based on what has been said during their live broadcast. Viewers participate through the Extension's own interface. The streamer monitors and controls play from a dashboard.

The first release contains **quote completion, niche, and hive mind**, with a dashboard designed for all three. The following quote-completion requirements remain confirmed; mode-specific rules for niche and hive mind still need refinement:

- Use sourced broadcast quotes to generate fill-in-the-blank prompts. Previous broadcasts are allowed as product direction; historical intake is deferred backend work, not an implemented fallback.
- Each prompt normally removes one word.
- Viewers type their answers into our UI, rather than public Twitch chat.
- Accept spelling mistakes and reasonable equivalent wording. The exact boundary for semantic equivalents remains open.
- Award points and show interim results, an interim leaderboard, and a final leaderboard.
- The streamer chooses when to activate the game.
- Support desktop and mobile viewers.
- Desktop uses a native Twitch Extension over the video. OBS is not required.
- Ad-triggered starts remain future work. Streamer-controlled automatic starts and dashboard scheduling are now confirmed product direction; detailed rules and release placement remain open (section 4).

Additional first-release game modes:

| Mode | Agreed direction | Still unspecified |
| --- | --- | --- |
| Niche | Each question has a set of valid words. Rank submitted valid answers into tiers dynamically by frequency during that question; the least-used valid words occupy the highest tier. No pre-sorted rarity tiers. | Tier boundaries, tied frequencies, point mapping, and how the owner's participation-based scoring direction relates to rarity tiers. |
| Hive mind | Submitted-answer frequency determines which word/group is most common dynamically. | Whether a valid-word list is required, tied frequencies, point mapping, and participation-based scoring details. |

All three modes require playable viewer flows, dashboard support, and agreed scoring in the first release. Chat-command answer participation, monetization, and cross-stream competitions remain outside the agreed first-release scope unless added explicitly. Previous-broadcast quote sourcing is permitted but its backend ingestion is deferred from the current dashboard work; no VOD import is implemented or selected. Audience question suggestions use an Extension form and require approval into the bank.

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

**Proposed interface:** a compact quote card containing the incomplete quote, one answer field, a submit button, round status, and the viewer's score. Results and leaderboards occupy the same interface after a round rather than opening another page.

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
| Answering | Quote with a blank and the round's status/deadline. | Type and submit an answer. |
| Submitted | Server-confirmed submission receipt. | Continue watching; one final answer per question, with no revisions. |
| Closed / scoring | Submissions are closed; results are being finalized. | Wait for results. |
| Round results | Full quote, own outcome, awarded points, interim leaderboard. | View results and wait for the next round. |
| Game ended | Final leaderboard for the completed game. | View final standing. |
| Disconnected | Connection status and retry state. | Reconnect and restore the current server state. |

**Proposed:** do not reveal other viewers' answers or the correct word while submissions are open. The precise content of interim results remains open; participation counts can be shown without exposing answers.

### Identity and answer privacy

Answers go to our backend, not Twitch chat. Distinguish public round information from individual submissions and feedback.

The Extension must follow Twitch's identity requirements for user-submitted text. Its policy requires users to grant access to their Twitch ID before submitting user content. If raw answers are published, additional username-display and moderation requirements apply. [User-content policy](https://dev.twitch.tv/docs/extensions/guidelines-and-policies/#7-moderation).

**Proposed:** allow spectators to view the game; request identity sharing when they choose to participate. Show appropriate permission states. Whether raw answers will ever appear publicly is open; they are not automatically included in a leaderboard.

## 4. Streamer application: standalone dashboard

The dashboard is a separate web application authenticated with the streamer's Twitch account. Keeping it separate makes room for a properly visible embedded player if we use Twitch's caption event. Embedding the dashboard controls in Twitch Live Config can be a later integration.

**Confirmed responsibilities:** activate the game, monitor interim results and leaderboards, and end with a final leaderboard.

### Confirmed dashboard direction — November 1, 2026

- Use a hybrid system: automate play while keeping control over how games run with the streamer.
- The streamer has a moderator team that can review audience-submitted questions, create their own questions, and approve AI-generated questions for fill-in-the-blank play.
- Approved questions enter a question bank and can be launched automatically into subsequent games. Approval is separate from launching a question; the streamer need not approve each question again at launch.
- Support automatic game starts and games scheduled through the dashboard, under streamer control. Exact automatic-start conditions, scheduling rules, and first-release delivery scope still need to be settled. Ad-triggered starts remain deferred unless explicitly added.
- Quote completion, niche, and hive mind all launch in the first release. Design the dashboard for all three modes.
- **Confirmed mode selection:** offer an exact round order chosen by the streamer or randomized mode selection. Automatic + randomized operation requires no manual mode choices from the streamer. Random rotation must never select the same mode in consecutive rounds. A separately selected random-mode pool is not a required setup step. Whether an explicitly chosen order may repeat modes consecutively remains open; the confirmed no-repeat restriction applies to random rotation. The pre-start supply check applies to either selection method.
- **Confirmed hierarchy:** a question is one prompt; a round is 3–5 questions in one mode; a game contains multiple rounds, potentially mixing modes, and ends with a final leaderboard. Random rotation's no-consecutive-repeat rule applies between rounds.
- **Confirmed game length:** randomly choose 3, 4, or 5 questions for each round; the streamer chooses the number of rounds per game. The random distribution, when the count is drawn/displayed, allowed round-count range, and behavior when too few approved questions are available remain open.
- **Confirmed authority model:** the streamer is the top-level channel owner and can assign different permissions to individual moderators. Question management and live game operation are permission categories the streamer can delegate; moderators do not automatically receive all dashboard powers. The streamer alone grants/revokes permissions and retains overall control. Exact permission granularity, defaults, and team onboarding remain open.
- **Confirmed moderator-created question approval:** a moderator who has approval permission can create a question directly in the approved bank; a second person's review is not required. The workflow for authors without approval permission remains open.
- **Confirmed audience question submission:** viewers suggest questions through a form in our Extension UI. Suggestions enter the moderator review queue; only approved questions enter the playable bank. Twitch chat commands are not a question-submission surface. Form fields, mode selection, submission limits, and feedback to the submitting viewer remain open.
- **Confirmed question reuse:** after a question is used, it becomes unavailable for selection while on cooldown, rather than being permanently retired. Use one channel-wide cooldown setting for all questions, measured in completed games, with no per-question or per-mode overrides. Moderators can configure the number of completed games subject to the streamer's permission model. The default/allowed values, whether the game containing the question counts toward cooldown, effects of changing the setting on already-cooling questions, manual early release, and cancellation/early-end counting remain open. Cooldown expiry does not override source validation: current or historical broadcast quotes must remain approved and traceable to their actual source.
- **Confirmed pre-start supply check:** before starting a game, reserve enough approved, off-cooldown, source-eligible questions to finish its planned rounds. Account for the configured round count, random 3–5-question round lengths, and selected/random mode rules. Do not start a game if sufficient eligible supply cannot be reserved. Instead, offer the streamer/authorized moderator a cooldown adjustment/reset or cancellation of that game start; after any adjustment, recheck eligibility and reserve before starting. This applies to manual, scheduled, and automatic starts. Exact planning/draw timing and missed scheduled-start behavior remain open.
- **Confirmed low-bank experience:** notify the streamer/moderator operators when question supply is low without pausing the ongoing game just to deliver the warning. The pre-start reservation supplies the current game; dashboard bank counts should flag the need to replenish questions for future games. The insufficient-supply popup offers cooldown shortening/reset or cancellation of the attempted game start. Warning thresholds, precise cooldown reset scope/permissions, reservation release on cancellation, and handling edits/removal/source invalidation of reserved questions remain open. Do not silently bypass approval, cooldown, source eligibility, or the random-mode no-consecutive-repeat rule.

### Latest owner decisions — gameplay and recovery

These decisions supersede earlier open questions or narrower proposals elsewhere in this document.

- **Quote sources:** previous broadcasts may supply quote-completion questions. Historical sourcing/transcript intake is deferred backend work outside the current dashboard scope. This relaxes the earlier current-stream-only restriction, including its cooldown restriction; reuse still requires an approved, traceable, eligible source. Live captions are unverified, and no live-audio fallback has been selected. Show source broadcast provenance; never label historical material as current-stream capture.
- **Niche:** maintain a set of valid words per question, then calculate popularity tiers from actual answers during that question. Least-used valid words occupy the highest tier, with more-used valid words in lower tiers. Tiers are not preassigned to the answer list. Exact tier boundaries and ties remain open.
- **Hive mind:** determine the most common word/equivalent group from actual submitted answers. Whether hive mind also requires a predefined valid-word list remains open.
- **Scoring clarification needed:** the owner's response to speed/scoring was: “No for niche + hive mind its just whether or not you got an answer out.” Do not introduce speed weighting for those modes. Whether every submission earns participation points, whether validity matters for participation points, and how points relate to niche tiers/hive mind popularity remain open. Quote-completion points and tie ranking are also unresolved.
- **Progression and controls:** questions automatically close on a streamer-configured timer, reveal results, and advance. Authorized operators can pause, skip questions, and end the game; the streamer has full control. Exact timer defaults, result-display duration, and skip/cancellation scoring remain open.
- **Submissions and equivalence:** one final answer per viewer per question, without revisions. Build backend equivalence handling for answers; exact normalization, synonym/alias policy, and evaluation rules still need definition and validation.
- **Results:** reset scores for each game, show an interim leaderboard after each round, and show everyone at the end of the whole game/session. Do not limit the final standings to only top players. Whether “everyone” means all participants including zero-score players, and how to present the full list, remain open. No additional hierarchy above game/session has been established. Public answer/group visibility is still undecided.
- **Authority:** the streamer can perform all operations and alone grants/revokes individual moderator permissions. Question review, live controls, and settings are separate permission categories. Detailed onboarding and permissions within categories remain open.
- **Dashboard recovery:** reopening/reconnecting continues from the saved game position rather than starting over. Do not assume the game finishes unattended after a dashboard disconnect. The exact disconnect/pause trigger, remaining timer treatment, multiple-operator connection behavior, and viewer display during interruption remain open; preserve accepted submissions, scores, and reserved questions.
- **Deferred:** revisit automatic-start triggers and scheduling rules in a later discussion; do not invent defaults for them.

**Open:** moderator onboarding and exact permission granularity/defaults; workflow for question authors without approval permission; audience suggestion form fields, mode selection, limits, and feedback; question editing/rejection; bank organization, cooldown configuration, and stream boundaries; mode-specific question requirements; timer defaults and detailed operator-control outcomes; schedule recurrence/timezone; reservation edge cases and detailed disconnect/timer recovery. Audience question suggestions through the Extension form are distinct from private gameplay answer submissions, which also remain through our UI.

**Proposed dashboard areas:**

| Area | Information / controls |
| --- | --- |
| Connection | Connected channel, active stream, transcript-source status. |
| Transcript | Recent text, capture freshness, gaps or missing captions. |
| Question queue | Incomplete quote, canonical answer, supporting source text and timestamp, generation status. |
| Game controls | Start game, start/advance round, close round, cancel round, end game. |
| Live monitoring | Current prompt, participation count, round state, scoring status. |
| Results | Round outcome, interim leaderboard, final leaderboard. |

Question approval into a bank, automatic question advancement, and operator pause/skip/end controls are **Confirmed**. Detailed editing, timing, and cancellation behavior remain **Open**.

Only authorized channel controllers may start games, see unrevealed answers, or manage questions. The streamer assigns permissions to individual moderators, including question-management and live-operation access. Enforce those grants on the backend; a Twitch moderator role alone does not imply every dashboard permission. Exact permissions, defaults, and access to unrevealed answers remain open. General editor access is not confirmed.

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

**Deferred backend decision:** previous-broadcast quote sourcing is permitted, but historical transcript ingestion is outside the current dashboard scope. No audio/transcription fallback has been chosen for missing live captions; do not assume automatic historical import or audio capture works.

An audio path would add capture controls, a transcription integration, capture status, and stop/pause behavior. Capturing a microphone alone does not capture the entire broadcast mix. That work is not silently included in the first release.

### Transcript boundaries

- Quotes may come from the current stream or previous broadcasts. Historical ingestion is deferred backend work; preserve and display actual source provenance.
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

Generate a shared question queue for the channel, not a separate queue for every viewer. Generation frequency, minimum context, quote age, and detailed repeat limits remain open. Generated questions require approval into the bank before play.

## 7. Game service and round lifecycle

**Confirmed terminology:**

- **Stream:** the Twitch broadcast providing source material.
- **Game / game session:** multiple rounds, potentially mixing modes, ending with a final leaderboard. Starts may be manual, scheduled, or automatic under the streamer's configured rules.
- **Round:** 3–5 questions in one mode. Random rotation chooses the next round's mode without repeating the preceding mode.
- **Question:** one prompt viewers answer within a round.

The hierarchy and final leaderboard at game end are confirmed. Each round randomly contains 3–5 questions, and the streamer sets the number of rounds per game. Scores reset per game; detailed configuration limits remain open. Older references elsewhere in this document to a single-prompt “round” or “round ID” should be interpreted as question-level behavior pending a detailed lifecycle/interface revision; they do not override this hierarchy.

**Proposed session lifecycle:**

```text
Inactive -> Active -> Ended
```

**Proposed question lifecycle:**

```text
Prepared -> Answering -> Closed -> Scored -> Results
                |          |
                +----------+-> Cancelled
```

The backend owns transitions, deadlines, question selection, submission eligibility, and score updates. A viewer's clock or UI cannot reopen a closed question.

**Proposed operational rules:** one active question per channel; do not open a question without a valid prepared prompt; preserve completed results; cancelled questions do not award points. Timed closing and automatic advancement with operator pause/skip/end controls are confirmed. Timer defaults, cancellation behavior, detailed round lifecycle, and pause/resume mechanics require confirmation.

### Future triggers

All starts flow through the same authorized game-start operation. Dashboard manual starts, scheduled starts, and agreed automatic-start conditions should use this operation with an explicit trigger source. Exact scheduling/automation behavior and release placement remain open. A later ad-break adapter can invoke the same operation.

Do not implement ad-event subscriptions or ad-related permissions in this release. Dashboard scheduling and automatic starts are now confirmed product direction in section 4; their detailed rules and release placement must be resolved before implementation. Keep trigger handling separate from the game engine.

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

**Confirmed:** one final submission per question, no answer revisions; backend equivalence handling is required. Niche tiers and hive mind popularity are determined dynamically from submitted answers, with no speed weighting for those modes. See section 4 for the owner's participation-based scoring clarification and unresolved point mapping. **Open:** quote-completion points/speed policy, mode-specific point formulas, incorrect/invalid-answer treatment, exact equivalence rules, tie placement, adjudication overrides, and timer defaults.

No score formula or numeric default is assumed in this document. Scores must be applied exactly once per accepted result, even when requests or events are retried. Never deliver unrevealed answers or private scoring keys to viewer clients.

## 9. Results and leaderboards

**Confirmed:** reset scores per game, show interim results/leaderboard after each round, and show everyone in the final game/session standings. See section 4 for unresolved zero-score inclusion and full-list presentation. Raw/grouped-answer publication remains open.

**Proposed round-results view:** complete quote, canonical missing word, the player's result, points earned, updated cumulative score, and current leaderboard. Include the source timestamp where meaningful.

**Proposed leaderboard entries:** display name, score, rank, and the current player's position even if outside the visible leaders.

The backend calculates rankings from finalized score records. All clients receive the same finalized ranking version. Interim-list size, final full-list presentation, tie presentation, exact result breakdown, and historical retention remain open. Scores reset per game. Finalization ends submissions for that game session and publishes its final standings.

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
| Game session | Channel; stream; multiple rounds; state; start/end; scoring-policy version. |
| Round | Session; mode; 3–5 questions; sequence; lifecycle state. |
| Question | Round; candidate; lifecycle state; timing; answer-policy version. Submissions and score entries must identify the individual question. |
| Participant | Twitch identity; display information; participation permissions. |
| Submission | Question; participant; one final answer; normalized answer; receipt time; evaluation state. |
| Score entry | Session; round; question; participant; finalized outcome; awarded points; policy version. |

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
| Dashboard disconnects | Preserve game position, submissions, scores, and reservations; reopening/reconnecting resumes from where it left off. Do not assume unattended completion. Disconnect detection, timers, multi-operator behavior, and interruption display remain open. Live intake becomes stale if its collector is disconnected. |
| Answer dispute | Preserve the source and evaluation record. Streamer override capability is an open decision. |

Validation must cover the real caption event, desktop player Extension, iOS and Android entry/keyboard behavior, authorization, wrong-channel isolation, unrevealed-answer leakage, spelling acceptance/rejection, closure boundaries, reconnection, and duplicate score prevention. Load targets and expected concurrent player counts have not been specified.

## 13. First-release acceptance criteria

These describe the intended outcome; unresolved rules below must be filled in before using them as a final implementation checklist.

1. A streamer connects a channel and sees whether the selected transcript source is working.
2. Quote questions use actual broadcast text with traceable provenance. Live capture and historical intake require separate backend validation and must not be claimed as working from a fixture.
3. A generated question is traceable to an actual stored quote and removes normally one word.
4. The streamer and appropriately authorized moderators can operate all three modes through the dashboard, including pause/skip/end controls.
5. The same active round is available through the desktop and mobile Extension views.
6. Eligible viewers submit answers through our UI, privately to the backend.
7. Answers are judged according to the agreed spelling/equivalence and scoring rules.
8. Players see confirmed submission state, interim results/leaderboard, and a final leaderboard.
9. Reconnection restores current state and does not duplicate points.
10. Quote completion, niche, and hive mind are all playable and manageable from the dashboard. The streamer can select games or enable random rotation; random rotation never repeats the same game consecutively. Ad-triggered starts remain deferred.

For the hackathon, Extension approval is a separate delivery dependency. The organizer warns of a 5–14 day review window and says judges cannot install unreviewed Extensions. A standalone test/judging surface is a proposed contingency, not an agreed replacement for the Extension. [Hackathon FAQ](https://twitchcon-codex.devpost.com/resources).

## 14. Decisions still needed

| Decision | What is known | What remains open |
| --- | --- | --- |
| Transcript fallback | Current or previous broadcasts may supply quotes; historical sourcing is deferred backend work outside current dashboard scope. Live captions remain unverified. | Historical intake implementation and fallback selection; no audio or VOD pipeline is assumed working. |
| Question approval | Moderators review audience suggestions submitted through an Extension form, create questions, and approve AI fill-in-the-blank questions into a bank for automatic play. Moderators with approval permission can add their own questions directly to the approved bank without a second reviewer. | Suggestion form fields/mode selection/limits/feedback, workflow for authors without approval permission, edit/reject workflow, bank selection, and mode-specific requirements. |
| Question cooldown | One channel-wide setting, measured in completed games, applies to all used questions without per-question or per-mode overrides. Moderators configure the count subject to streamer-assigned permissions; source eligibility still applies. | Default/allowed counts, whether the game containing the question counts, changes affecting existing cooldowns, manual early release, cancellation/early-end counting, and detailed permissions. |
| Low question supply | Before any game starts, reserve enough eligible approved/off-cooldown questions to finish. If insufficient, offer cooldown adjustment/reset or cancel the start, then recheck before starting. In-game low-bank warnings do not pause play; dashboard flags replenishment needs for future games. | Warning thresholds, reset scope/permissions, planning/draw timing, missed scheduled starts, reservation release, and changes/invalidation of reserved questions. |
| Dashboard access | Streamer can do everything and alone grants/revokes moderator permissions; question review, live controls, and settings are separate categories. | Team onboarding, fine-grained permission defaults, and unrevealed-answer access. |
| Game starts and scheduling | Streamer-controlled hybrid automation, automatic starts, and dashboard scheduling are confirmed direction; insufficient supply prevents starting. Owner explicitly deferred the detailed scheduling discussion. | Trigger conditions, schedule rules/timezone/recurrence, failed-start retries, and first-release placement. Ad triggers remain deferred. |
| Release modes | All three launch. Niche has a valid-word list and frequency-derived tiers, rarest highest. Hive mind uses the most common submitted word/group. | Tier boundaries/ties, hive mind validity requirements, equivalent grouping, and exact point mapping. |
| Game selection | Streamer chooses an exact round order or randomized mode selection. Auto + randomized requires no manual mode choices. Each round randomly contains 3–5 questions in one mode; the streamer chooses rounds per game. A game ends with a final leaderboard. Random rotation never repeats the same mode in consecutive rounds; pre-start reservation ensures supply. | Question-count distribution/draw timing, round-count configuration limits, and whether exact orders may repeat a mode consecutively. |
| Round progression | Streamer-configured timers close questions, reveal results, and auto-advance. Authorized operators can pause, skip, and end games. Each round randomly has 3–5 questions; rounds per game are streamer-set. | Timer defaults/ranges, result-display duration, skip/cancellation outcomes, and precise pause/resume behavior. |
| Scoring | Dynamic niche tiers and hive mind popularity; no speed weighting for these two modes. Owner described scoring as whether a player “got an answer out.” | Participation versus tier/popularity points, validity effects, quote points/speed weighting, wrong-answer treatment, and ties. |
| Answer revisions | One final private free-text answer per viewer per question; no edits. | No revision-policy decision remains; retries must preserve the original accepted submission. |
| Equivalents | Backend equivalence handling is required, including the existing lenient quote-answer direction. | Exact normalization, synonym/alias policy, grouping, and validation. |
| Leaderboard boundary | Scores reset per game; interim standings after each round; final standings show everyone at game/session end. | Zero-score participant inclusion, full-list presentation, and historical retention. |
| Result detail | Interim results and final standings are required. | Public raw/grouped answers, response counts, and exact breakdown. |
| Source eligibility | Quotes may come from current or previous broadcasts; historical intake is deferred backend work. | Eligible speakers, languages, quote age, and historical-source validation. |
| Operations | Preserve state and resume from the saved position when the dashboard reopens/reconnects. | Retention, budget, concurrency, disconnect/pause detection, timer recovery, and multiple-operator connections. |

No recommendations in this document resolve these open decisions by implication.

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
2. **Confirm the dependent product rules.** Resolve the first set of decisions in section 14: scoring, answer revisions/equivalence, round timing/progression, score reset boundary, and prompt approval. Independent auth, data-model, and preview work need not wait.
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

- What all three first-release games do, how streamer-selected versus random rotation works, which rules remain open, and why play is not ad-only.
- Why the primary desktop surface is a Twitch Extension, why OBS is unnecessary, and how mobile differs.
- Where typed answers go and why Twitch chat is not the required input surface.
- Which service owns game state, source evidence, answer evaluation, and scores.
- Why captions are conditional, where the caption collector runs, and what has not been tested.
- Which product rules are confirmed versus still open, and which independent work can proceed.
- What integration setup, live/device tests, and hackathon deliverables remain outstanding.

When implementation starts, preserve this document as the product source of truth and update the repository's status to describe actual progress. New explicit owner decisions supersede earlier proposals; document those changes rather than carrying contradictory requirements forward.
