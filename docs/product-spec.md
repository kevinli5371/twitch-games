# Stream Quote Game — product and architecture specification

Version: 0.2 · November 1, 2026

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
| Initial modes | Implement **only quote completion** initially. Niche and hive mind remain future modes. |
| Quote answers | Typed free text, normally one missing word, lenient spelling, and reasonable paraphrases/equivalents. Not multiple choice. |
| Control | The streamer chooses when to activate the game. Per-question approval and round progression were not resolved. |
| Results | Interim results/leaderboard and a final leaderboard are required. Exact point values and reset boundaries were not resolved. |
| Captions | A documented caption event was researched, but real stream capture has **not** been proven. Automatic transcripts for arbitrary channels are not an available assumption. |

### Product example, not a scoring decision

A captioned passage contains “I cannot believe we won with a spoon.” The game can present “I cannot believe we won with a ____.” Viewers privately type an answer in the Extension. At the agreed round boundary, the backend evaluates answers and publishes results and updated standings. “spoon” is canonical; whether another word or typo is accepted follows the answer policy that still needs to be finalized. No example here establishes a point value, timer length, or answer-editing policy.

## 1. Product and agreed scope

Build a Twitch Extension that lets a streamer run games based on what has been said during their live broadcast. Viewers participate through the Extension's own interface. The streamer monitors and controls play from a dashboard.

The first release contains **only the quote-completion game**:

- Use quotes from the current stream to generate fill-in-the-blank prompts.
- Each prompt normally removes one word.
- Viewers type their answers into our UI, rather than public Twitch chat.
- Accept spelling mistakes and reasonable equivalent wording. The exact boundary for semantic equivalents remains open.
- Award points and show interim results, an interim leaderboard, and a final leaderboard.
- The streamer chooses when to activate the game.
- Support desktop and mobile viewers.
- Desktop uses a native Twitch Extension over the video. OBS is not required.
- Future automatic triggers, such as starting during an ad break, are accounted for in the architecture but are **not implemented in this release**.

Later game modes, recorded for future work:

| Mode | Agreed direction | Still unspecified |
| --- | --- | --- |
| Niche | Answers submitted by fewer players score better. | Validity checking, scoring formula, grouping equivalent answers, ties. |
| Hive mind | Players submitting the most common answer receive points. | Point value, tie handling, grouping equivalent answers. |

Neither later mode has screens, generation logic, or scoring in the first release. Chat-command participation, VOD import, monetization, and cross-stream competitions are also outside the agreed first-release scope unless added explicitly.

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

**Proposed deployment:** two web interfaces, one application backend, a background generation worker, and a durable database. These are logical responsibilities, not a requirement to create separate microservices. The backend and worker may share a deployment initially. Hosting, framework, database vendor, transcription provider, and model provider remain unselected.

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
| Submitted | Server-confirmed submission receipt. | Continue watching; editing depends on the open submission rule. |
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
- **Round:** one quote prompt within that game session.

This session boundary is a proposal because the user requested interim and final leaderboards but has not yet specified when scores reset.

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

**Proposed operational rules:** one active quote round per channel; do not open a round without a valid prepared question; preserve completed results; cancelled rounds do not award points. Timed versus manual closing, automatic versus manual advancement, cancellation behavior, and session reset rules require confirmation.

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

**Open scoring rules:** points per correct answer; whether incorrect answers earn zero; speed bonuses; exact versus spelling-tolerant versus synonym acceptance; one submission versus editable answers; tie placement; adjudication/override powers; and the answer window.

No score formula or numeric default is assumed in this document. Scores must be applied exactly once per accepted result, even when requests or events are retried. Never deliver unrevealed answers or private scoring keys to viewer clients.

## 9. Results and leaderboards

**Confirmed:** interim results and leaderboard, followed by a final leaderboard at the end.

**Proposed round-results view:** complete quote, canonical missing word, the player's result, points earned, updated cumulative score, and current leaderboard. Include the source timestamp where meaningful.

**Proposed leaderboard entries:** display name, score, rank, and the current player's position even if outside the visible leaders.

The backend calculates rankings from finalized score records. All clients receive the same finalized ranking version. The number of visible entries, tie presentation, exact interim-result breakdown, score-reset boundary, and historical retention are open. Finalization ends submissions for that game session and publishes its final standings.

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
4. The streamer can activate and end a quote game through the dashboard.
5. The same active round is available through the desktop and mobile Extension views.
6. Eligible viewers submit answers through our UI, privately to the backend.
7. Answers are judged according to the agreed spelling/equivalence and scoring rules.
8. Players see confirmed submission state, interim results/leaderboard, and a final leaderboard.
9. Reconnection restores current state and does not duplicate points.
10. Niche mode, hive mind, and automatic triggers are not implemented or presented as working features.

For the hackathon, Extension approval is a separate delivery dependency. The organizer warns of a 5–14 day review window and says judges cannot install unreviewed Extensions. A standalone test/judging surface is a proposed contingency, not an agreed replacement for the Extension. [Hackathon FAQ](https://twitchcon-codex.devpost.com/resources).

## 14. Decisions still needed

| Decision | What is known | What remains open |
| --- | --- | --- |
| Transcript fallback | Current-stream text powers questions; Twitch captions are conditional. | Require captions, or add live audio transcription in the MVP? |
| Question approval | Prompts are generated dynamically. | Streamer approves/edits each prompt, or generation can publish automatically? |
| Round progression | Streamer activates the game. | Who advances questions; timer duration; who closes rounds; number of rounds? |
| Scoring | Correct answers receive points. | Point values, speed weighting, wrong-answer treatment, ties. |
| Answer revisions | Free-text answers through our UI. | One final answer, or allow changes until close? |
| Equivalents | Spelling mistakes and some equivalent wording are accepted. | Do synonyms count, and how strict is one-word completion? |
| Leaderboard boundary | Interim and final boards exist. | One activated game, one stream, or another reset boundary? |
| Result detail | Interim results are required. | Aggregate correctness, raw/grouped answers, or only personal outcome and ranks? |
| Source eligibility | Quotes come from the stream so far. | Only the streamer, or other speakers too; supported languages; minimum quote age? |
| Operations | Durable state and source status are required. | Retention periods, deployment budget, concurrency target, and dashboard-loss behavior. |

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

- What the first-release quote game does, which modes are deferred, and why it is not ad-only.
- Why the primary desktop surface is a Twitch Extension, why OBS is unnecessary, and how mobile differs.
- Where typed answers go and why Twitch chat is not the required input surface.
- Which service owns game state, source evidence, answer evaluation, and scores.
- Why captions are conditional, where the caption collector runs, and what has not been tested.
- Which product rules are confirmed versus still open, and which independent work can proceed.
- What integration setup, live/device tests, and hackathon deliverables remain outstanding.

When implementation starts, preserve this document as the product source of truth and update the repository's status to describe actual progress. New explicit owner decisions supersede earlier proposals; document those changes rather than carrying contradictory requirements forward.
