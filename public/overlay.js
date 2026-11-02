const MODE_META = Object.freeze({
  quote: { title: "Quote Completion", symbol: "“ ”", promptLabel: "Complete the quote", answerLabel: "Your missing word" },
  niche: { title: "Niche", symbol: "◇", promptLabel: "Find the uncommon answer", answerLabel: "Your answer" },
  hive: { title: "Hive Mind", symbol: "◎", promptLabel: "Think like the crowd", answerLabel: "Your answer" },
});

const ICONS = Object.freeze({
  clock: "◷",
  lock: "▣",
  check: "✓",
  spark: "✦",
  chart: "▥",
  warning: "!",
  retry: "↻",
});

const root = document.getElementById("overlay-root");
const isVideoOverlayContext = new URLSearchParams(window.location.search).get("anchor") === "video_overlay";
let adapter = null;
let currentState = null;
let countdownInterval = null;
let previewViewerHidden = false;

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function icon(className, text) {
  const node = element("span", className, text);
  node.setAttribute("aria-hidden", "true");
  return node;
}

function button(text, className, action) {
  const node = element("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

function modeInfo(mode) {
  const normalizedMode = String(mode || "quote").toLowerCase();
  if (["niche", "niche_game"].includes(normalizedMode)) return MODE_META.niche;
  if (["hive", "hive_mind", "hivemind"].includes(normalizedMode)) return MODE_META.hive;
  return MODE_META.quote;
}

function normalizeMode(mode) {
  const normalizedMode = String(mode || "quote").toLowerCase();
  if (["niche", "niche_game"].includes(normalizedMode)) return "niche";
  if (["hive", "hive_mind", "hivemind"].includes(normalizedMode)) return "hive";
  return "quote";
}

function promptText(prompt) {
  if (typeof prompt === "string") return prompt;
  if (!prompt || typeof prompt !== "object") return "The next prompt is being prepared.";
  return prompt.displayText || prompt.text || prompt.blankedQuote || "The next prompt is being prepared.";
}

function addPromptText(target, rawText) {
  const text = String(rawText || "");
  const blankPattern = /_{3,}/g;
  let position = 0;
  let match;
  while ((match = blankPattern.exec(text))) {
    target.append(document.createTextNode(text.slice(position, match.index)));
    target.append(element("span", "blank-token", "____"));
    position = match.index + match[0].length;
  }
  target.append(document.createTextNode(text.slice(position)));
}

function roundLabel(state) {
  const roundNumber = Number(state.roundNumber || 1);
  const roundCount = Number(state.roundCount || 5);
  return `Round ${roundNumber} of ${roundCount}`;
}

function startCountdown(deadlineAt) {
  clearInterval(countdownInterval);
  if (!deadlineAt) return;
  const timer = root.querySelector("[data-round-timer]");
  if (!timer) return;

  const update = () => {
    const remaining = new Date(deadlineAt).getTime() - Date.now();
    if (!Number.isFinite(remaining)) {
      timer.textContent = "--:--";
      return;
    }
    const seconds = Math.max(0, Math.ceil(remaining / 1000));
    timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    timer.classList.toggle("is-low", seconds > 0 && seconds <= 10);
    timer.classList.toggle("is-expired", seconds === 0);
  };

  update();
  countdownInterval = setInterval(update, 1000);
}

function addCardHeader(card, state) {
  const info = modeInfo(state.mode);
  const inner = element("div", "card-inner");
  const topline = element("div", "card-topline");
  const brand = element("div", "card-brand");
  brand.append(icon("brand-mark", ICONS.spark), element("span", "", state.isPreview ? "LOCAL PREVIEW" : "STREAM GAME"));
  const phase = state.phase || state.round?.phase;
  const statusLabel = phase === "ended" ? "Game ended" : phase === "cancelled" ? "Round canceled" : phase === "results" || phase === "scored" ? "Round results" : phase === "submitted" ? "Answer received" : "Round live";
  topline.append(brand, element("span", "live-status", statusLabel));
  if (state.isPreview || (isVideoOverlayContext && typeof window.Twitch?.ext?.actions?.minimize === "function")) {
    const hideButton = button("Hide", "visibility-toggle", () => {
      if (state.isPreview) {
        previewViewerHidden = true;
        render(currentState);
      } else {
        window.Twitch.ext.actions.minimize();
      }
    });
    hideButton.setAttribute("aria-label", "Hide this overlay for me");
    hideButton.title = "Hide this overlay for me";
    topline.append(hideButton);
  }
  inner.append(topline);

  const heading = element("div", "mode-heading");
  heading.append(icon("mode-symbol", info.symbol));
  const titleGroup = element("div");
  titleGroup.append(element("p", "mode-eyebrow", "CURRENT MODE"), element("h2", "mode-title", info.title));
  heading.append(titleGroup);
  inner.append(heading);

  const meta = element("div", "round-meta");
  const count = element("span", "round-count", roundLabel(state));
  const timer = element("span", "timer-chip");
  timer.append(icon("timer-icon", ICONS.clock), element("span", "", state.deadlineAt ? "00:30" : "--:--"));
  timer.lastElementChild.dataset.roundTimer = "true";
  timer.setAttribute("aria-label", "Time remaining");
  meta.append(count, timer);
  inner.append(meta);
  card.append(inner);
  return inner;
}

function addPrivateNote(parent) {
  const note = element("span", "private-note");
  note.append(icon("", ICONS.lock), document.createTextNode("Private submission"));
  parent.append(note);
}

function showNotice(parent, message, isError = false) {
  const notice = element("div", `notice${isError ? " is-error" : ""}`);
  notice.setAttribute("role", isError ? "alert" : "note");
  notice.append(icon("", isError ? ICONS.warning : ICONS.spark), element("span", "", message));
  parent.append(notice);
}

function appendSourceNote(inner, sourceTimestamp) {
  if (!sourceTimestamp) return;
  const divider = element("div", "card-divider");
  const note = element("div", "source-note");
  note.append(icon("", "◉"), element("span", "", `Source from this stream · ${sourceTimestamp}`));
  inner.append(divider, note);
}

function renderAnswering(state) {
  const info = modeInfo(state.mode);
  const card = element("section", "game-card");
  card.setAttribute("aria-label", `${info.title} round`);
  const inner = addCardHeader(card, state);
  const prompt = element("section", "prompt-block");
  prompt.append(element("p", "prompt-label", info.promptLabel));
  const promptBody = element("p", "prompt-text");
  addPromptText(promptBody, promptText(state.prompt));
  prompt.append(promptBody);
  inner.append(prompt);

  const isLinked = Boolean(state.identityLinked || state.isPreview);
  if (isLinked) {
    const form = element("form", "answer-form");
    const labelRow = element("div", "field-label-row");
    const inputId = "answer-input";
    const label = element("label", "field-label", info.answerLabel);
    label.htmlFor = inputId;
    labelRow.append(label);
    addPrivateNote(labelRow);

    const row = element("div", "answer-row");
    const input = element("input", "answer-input");
    input.id = inputId;
    input.name = "answer";
    input.type = "text";
    input.required = true;
    input.maxLength = 160;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder = state.mode === "quote" ? "Type the missing word" : "Type your answer";
    input.setAttribute("aria-label", info.answerLabel);
    const submit = element("button", "submit-button");
    submit.type = "submit";
    submit.append(document.createTextNode("Submit answer "), icon("button-arrow", "↗"));
    row.append(input, submit);
    form.append(labelRow, row);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const answer = input.value.trim();
      if (!answer || !adapter) return;
      submit.disabled = true;
      input.disabled = true;
      try {
        await adapter.submit(answer);
      } catch (error) {
        const latest = { ...currentState, submitError: error?.message || "Your answer could not be submitted. Please try again." };
        render(latest);
      }
    });
    inner.append(form);
    if (state.submitError) showNotice(inner, state.submitError, true);
  } else {
    const identityButton = button("Link Twitch identity to answer", "identity-button", () => adapter?.requestIdentityShare());
    identityButton.setAttribute("aria-label", "Link Twitch identity to answer this round");
    inner.append(identityButton);
    inner.append(element("p", "identity-note", "You can watch the round without linking. Your answer stays private."));
  }

  const footnote = element("p", "card-footnote");
  footnote.append(document.createTextNode("One submission"), icon("footnote-separator", ""), document.createTextNode("No speed bonus"));
  inner.append(footnote);
  appendSourceNote(inner, state.sourceTimestamp);
  root.replaceChildren(card);
  startCountdown(state.deadlineAt);
}

function renderSubmitted(state) {
  const info = modeInfo(state.mode);
  const card = element("section", "game-card");
  card.setAttribute("aria-label", "Answer received");
  const inner = addCardHeader(card, state);
  const panel = element("div", "state-panel");
  const badge = element("div", "state-icon is-success", ICONS.check);
  panel.append(badge, element("h2", "state-title", "Answer received"));
  panel.append(element("p", "state-description", "Your answer is in. Results will appear when the round closes."));
  if (state.ownSubmission?.answer) {
    const echo = element("div", "submission-echo");
    echo.append(icon("", ICONS.check), element("span", "", state.ownSubmission.answer));
    panel.append(echo);
  }
  panel.append(element("p", "card-footnote", "No speed bonus · You can keep watching"));
  inner.append(panel);
  root.replaceChildren(card);
  startCountdown(state.deadlineAt);
}

function appendLeaderboard(parent, entries, ownStanding) {
  const board = element("section", "leaderboard");
  board.setAttribute("aria-label", "Leaderboard");
  const header = element("div", "leaderboard-heading");
  header.append(element("span", "", "Leaderboard"), element("span", "", "SCORE"));
  board.append(header);
  const rows = Array.isArray(entries) ? entries.slice(0, 5) : [];
  const containsOwn = ownStanding && rows.some((row) => row.isYou || row.isSelf);
  if (ownStanding && !containsOwn && rows.length < 5) rows.push({ ...ownStanding, isYou: true });
  else if (ownStanding && !containsOwn && rows.length === 5) rows.push({ ...ownStanding, isYou: true });

  if (rows.length === 0) {
    board.append(element("p", "board-empty", "Standings will appear after results are ready."));
  } else {
    for (const entry of rows) {
      const row = element("div", `board-row${entry.isYou || entry.isSelf ? " is-self" : ""}`);
      const displayName = entry.isYou || entry.isSelf ? "You" : (entry.displayName || "Player");
      row.append(element("span", "board-rank", entry.rank ? `#${entry.rank}` : "—"));
      const name = element("span", "board-name");
      name.append(document.createTextNode(displayName));
      if (entry.isYou || entry.isSelf) name.append(element("span", "you-tag", "YOU"));
      row.append(name, element("span", "board-score", `${Number(entry.score || 0)} pts`));
      board.append(row);
    }
  }
  parent.append(board);
}

function renderResults(state, ended = false) {
  const card = element("section", "game-card");
  card.setAttribute("aria-label", ended ? "Final leaderboard" : "Round results");
  const inner = addCardHeader(card, state);
  const results = state.results || {};
  const panel = element("div", "state-panel");
  const badge = element("div", "state-icon is-success", ended ? ICONS.chart : ICONS.check);
  panel.append(badge, element("h2", "state-title", ended ? "Final leaderboard" : "Round results"));

  if (ended) {
    panel.append(element("p", "state-description", `That’s the game. Final standings after ${state.roundCount || 5} rounds.`));
  } else if (results.outcomeLabel) {
    panel.append(element("p", "state-description", results.outcomeLabel));
  } else {
    panel.append(element("p", "state-description", "The round is complete. Here are the current standings."));
  }

  if (results.pointsAwarded !== undefined && !ended) {
    const scoreline = element("p", "result-scoreline");
    scoreline.append(document.createTextNode("Points this round"), element("span", "points-badge", `+${Number(results.pointsAwarded)} pts`));
    panel.append(scoreline);
  }
  if (results.revealedAnswer) {
    const answer = element("p", "reveal-answer");
    answer.append(document.createTextNode("The missing word was "), element("strong", "", results.revealedAnswer));
    panel.append(answer);
  }
  inner.append(panel);
  appendLeaderboard(inner, ended ? (state.finalLeaderboard || state.leaderboard) : state.leaderboard, state.ownStanding);
  if (state.evaluationIsPlaceholder) {
    showNotice(inner, "Sample evaluation for preview only. Backend answer checking is not connected.");
  }
  root.replaceChildren(card);
  clearInterval(countdownInterval);
}

function renderClosed(state) {
  const card = element("section", "game-card");
  card.setAttribute("aria-label", "Round closed");
  const inner = addCardHeader(card, state);
  const panel = element("div", "state-panel");
  panel.append(element("div", "state-icon is-warning", ICONS.clock));
  panel.append(element("h2", "state-title", "Round closed"));
  panel.append(element("p", "state-description", "Answers are closed. The streamer will advance when results are ready."));
  inner.append(panel);
  root.replaceChildren(card);
  clearInterval(countdownInterval);
}

function renderCancelled(state) {
  const card = element("section", "game-card");
  card.setAttribute("aria-label", "Round canceled");
  const inner = addCardHeader(card, state);
  const panel = element("div", "state-panel");
  panel.append(element("div", "state-icon is-warning", ICONS.warning));
  panel.append(element("h2", "state-title", "Round canceled"));
  panel.append(element("p", "state-description", "This prompt was canceled by the streamer. No answer or points will be recorded."));
  inner.append(panel);
  root.replaceChildren(card);
  clearInterval(countdownInterval);
}

function renderEmpty(kind, message, detail, retry) {
  const card = element("section", "game-card empty-state");
  const badge = element("div", `state-icon${kind === "error" ? " is-warning" : ""}`, kind === "error" ? ICONS.warning : ICONS.spark);
  card.append(badge, element("h2", "state-title", message), element("p", "state-description", detail));
  if (retry) card.append(button("Try again", "retry-button", retry));
  root.replaceChildren(card);
  clearInterval(countdownInterval);
}

function render(state) {
  if (!root) return;
  currentState = state || {};
  if (currentState.overlayEnabled === false || currentState.game?.overlayEnabled === false) {
    root.replaceChildren();
    clearInterval(countdownInterval);
    return;
  }
  if (previewViewerHidden && currentState.isPreview) {
    const restore = button("Show overlay for me", "viewer-restore-button", () => {
      previewViewerHidden = false;
      render(currentState);
    });
    restore.setAttribute("aria-label", "Show the overlay for me");
    root.replaceChildren(restore);
    clearInterval(countdownInterval);
    return;
  }
  const gameStatus = currentState.gameStatus || currentState.game?.status;
  const phase = currentState.phase || currentState.round?.phase;
  if (currentState.loading) {
    const loading = element("section", "game-card loading-card");
    loading.append(icon("status-dot", ""), element("p", "", "Connecting to the game…"));
    root.replaceChildren(loading);
    return;
  }
  if (currentState.error) {
    renderEmpty("error", "Game unavailable", currentState.error, () => adapter?.refresh());
    return;
  }
  if (currentState.status === "not-in-twitch") {
    renderEmpty("info", "Open this view in Twitch", "The live Extension connection is not part of this local preview.", null);
    return;
  }
  if (currentState.status === "not-configured") {
    renderEmpty("info", "Waiting for the game service", "This local build is a visual and interaction preview. It is not connected to a game backend.", null);
    return;
  }
  if (currentState.transcriptUnavailable) {
    renderEmpty("info", "Waiting for a usable prompt", "The streamer’s source is unavailable or still collecting. No live question is being invented.", null);
    return;
  }
  if (currentState.status === "idle" || phase === "idle" || ["inactive", "ended"].includes(gameStatus) || phase === "ended") {
    if (gameStatus === "ended" || phase === "ended") renderResults(currentState, true);
    else renderEmpty("info", "No game right now", "When the streamer starts a game, its prompt will appear here.", null);
    return;
  }
  if (!currentState.round && !currentState.prompt) {
    renderEmpty("info", "Getting the next round ready", "The game is active, but there isn’t a playable prompt yet.", null);
    return;
  }
  if (phase === "results" || phase === "scored") return renderResults(currentState, false);
  if (phase === "cancelled" || phase === "canceled") return renderCancelled(currentState);
  if (phase === "closed" || phase === "scoring") return renderClosed(currentState);
  if (phase === "submitted" || ["submitted", "received", "accepted"].includes(currentState.ownSubmission?.status)) return renderSubmitted(currentState);
  renderAnswering(currentState);
}

function normalizeSnapshot(payload) {
  const game = payload?.game || {};
  const round = payload?.round || payload?.currentRound || null;
  const prompt = round?.prompt;
  const deadlineAt = round?.deadlineAt || round?.closesAt || null;
  const rawPhase = String(round?.phase || round?.state || (game.status === "ended" ? "ended" : "") || "").toLowerCase();
  const phase = rawPhase === "open" || rawPhase === "active" ? "answering" : rawPhase || null;
  const sourceStatus = String(payload?.source?.status || payload?.transcript?.status || "").toLowerCase();
  return {
    status: !game.id || game.status === "inactive" ? "idle" : undefined,
    game,
    gameStatus: game.status,
    gameId: game.id,
    round,
    roundId: round?.id,
    roundNumber: round?.number || round?.roundNumber || 1,
    roundCount: game.roundCount ?? game.configuredRoundCount ?? 5,
    mode: normalizeMode(round?.mode),
    phase,
    prompt,
    deadlineAt,
    transcriptUnavailable: Boolean(payload?.transcriptUnavailable) || ["unavailable", "stale", "collecting", "no_captions"].includes(sourceStatus),
    leaderboard: payload?.leaderboard || game.leaderboard || [],
    finalLeaderboard: payload?.finalLeaderboard || game.finalLeaderboard || [],
    results: round?.results || round?.result || payload?.results || null,
    sourceTimestamp: round?.sourceTimestamp || prompt?.sourceTimestamp || null,
    evaluationIsPlaceholder: false,
    identityLinked: false,
    overlayEnabled: payload?.overlayEnabled ?? game.overlayEnabled ?? true,
  };
}

function createTwitchAdapter() {
  const listeners = new Set();
  let auth = null;
  let snapshot = { loading: true };
  let poll = null;
  let authorizationTimer = null;
  let lastVersion = -1;
  const extension = window.Twitch?.ext;
  const apiBaseUrl = String(window.TWITCH_GAMES_CONFIG?.apiBaseUrl || "").replace(/\/$/, "");
  let isVisible = true;

  const emit = () => listeners.forEach((listener) => listener(snapshot));
  const linked = () => Boolean(extension?.viewer?.isLinked && extension?.viewer?.id);
  const headers = () => ({
    "Content-Type": "application/json",
    "x-extension-jwt": auth?.token || "",
  });

  function onVisibilityChanged(callback) {
    if (typeof extension?.onVisibilityChanged !== "function") return;
    extension.onVisibilityChanged((visible) => {
      isVisible = Boolean(visible);
      callback(isVisible);
    });
  }

  async function request(path, options = {}) {
    if (!apiBaseUrl) throw new Error("The local viewer has no backend configured yet.");
    const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers: { ...headers(), ...options.headers } });
    if (!response.ok) {
      if (response.status === 409) throw new Error("This round has already closed or your answer was already received.");
      if (response.status === 401 || response.status === 403) throw new Error("Twitch could not authorize this request. Reopen the Extension and try again.");
      throw new Error("The game service could not complete that request. Please try again.");
    }
    if (response.status === 204) return null;
    return response.json();
  }

  async function loadPrivateState(state) {
    if (!linked()) return state;
    const privatePath = state?.roundId
      ? `/rounds/${encodeURIComponent(state.roundId)}/me`
      : state?.gameId && state?.gameStatus === "ended"
        ? `/games/${encodeURIComponent(state.gameId)}/me`
        : null;
    if (!privatePath) return { ...state, identityLinked: true };
    try {
      const result = await request(privatePath);
      return {
        ...state,
        identityLinked: true,
        ownSubmission: result?.submission || null,
        ownResult: result?.result || null,
        ownStanding: result?.standing || null,
      };
    } catch {
      return { ...state, identityLinked: true };
    }
  }

  async function refresh() {
    if (!auth?.channelId) return;
    if (!apiBaseUrl) {
      snapshot = { status: "not-configured" };
      emit();
      return;
    }
    try {
      const payload = await request(`/channels/${encodeURIComponent(auth.channelId)}/game-state`);
      let next = normalizeSnapshot(payload);
      next = await loadPrivateState(next);
      const incomingVersion = Number.isFinite(Number(payload?.version)) ? Number(payload.version) : lastVersion + 1;
      if (incomingVersion >= lastVersion) {
        lastVersion = incomingVersion;
        snapshot = next;
        emit();
      }
    } catch (error) {
      snapshot = { error: error.message || "The game service could not be reached." };
      emit();
    }
  }

  function handlePubSub(_target, contentType, message) {
    if (contentType !== "application/json") return;
    try {
      const event = JSON.parse(message);
      if (!event || !["game_snapshot", "game_updated"].includes(event.type) || !event.snapshot) return;
      const version = Number(event.version ?? event.snapshot.version ?? 0);
      if (version < lastVersion) return;
      lastVersion = version;
      loadPrivateState(normalizeSnapshot(event.snapshot)).then((next) => {
        snapshot = next;
        emit();
      });
    } catch {
      // Ignore malformed public events; a fresh snapshot is the recovery path.
    }
  }

  if (!extension) {
    snapshot = { status: "not-in-twitch" };
  } else {
    extension.listen?.("broadcast", handlePubSub);
    authorizationTimer = setTimeout(() => {
      if (!auth) {
        snapshot = { status: "not-in-twitch" };
        emit();
      }
    }, 8000);
    extension.onAuthorized?.((authorization) => {
      auth = authorization;
      clearTimeout(authorizationTimer);
      refresh();
    });
    extension.viewer?.onChanged?.(() => {
      if (snapshot && snapshot.roundId) loadPrivateState(snapshot).then((next) => { snapshot = next; emit(); });
    });
    poll = setInterval(() => {
      if (isVisible && !document.hidden && auth?.channelId) refresh();
    }, 15000);
  }

  return {
    subscribe(listener) { listeners.add(listener); listener(snapshot); return () => listeners.delete(listener); },
    refresh,
    async submit(answer) {
      if (!auth?.token || !linked()) throw new Error("Link your Twitch identity before submitting.");
      if (!snapshot?.roundId) throw new Error("There is no open round to answer.");
      await request(`/rounds/${encodeURIComponent(snapshot.roundId)}/answers`, {
        method: "POST",
        body: JSON.stringify({ answer }),
      });
      snapshot = { ...snapshot, phase: "submitted", ownSubmission: { status: "submitted", answer } };
      emit();
    },
    requestIdentityShare() {
      if (typeof extension?.actions?.requestIdShare === "function") extension.actions.requestIdShare();
      else renderEmpty("error", "Twitch identity is unavailable", "This identity prompt is only available inside a configured Twitch Extension.", null);
    },
    onVisibilityChanged,
    dispose() { if (poll) clearInterval(poll); },
  };
}

function connect() {
  if (!root) return;
  adapter = window.OVERLAY_PREVIEW_ADAPTER || createTwitchAdapter();
  if (typeof adapter.onVisibilityChanged === "function") {
    adapter.onVisibilityChanged((isVisible) => {
      if (isVisible) adapter.refresh?.();
    });
  }
  adapter.subscribe(render);
}

window.StreamGameOverlay = Object.freeze({ connect, render });
connect();
