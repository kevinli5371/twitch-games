import {createTwitchAdapter} from "./api-adapter.mjs";
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
let viewerMinimized = false;
try { viewerMinimized = sessionStorage.getItem('stream-games.viewer.minimized') === '1'; } catch { /* Storage is optional. */ }
const answerDrafts = new Map();
const pendingSubmissions = new Set();

function setViewerMinimized(minimized) {
  viewerMinimized = minimized;
  try { sessionStorage.setItem('stream-games.viewer.minimized', minimized ? '1' : '0'); } catch { /* Keep the choice in memory. */ }
  render(currentState);
  const target = minimized ? root.querySelector('.minimized-card') : root.querySelector('.mode-title, .state-title');
  if(target){if(!minimized)target.tabIndex=-1;target.focus({preventScroll:true});}
  if(!minimized && !currentState?.isPreview)adapter?.refresh();
}

function minimizeButton() {
  const control = button('−', 'visibility-toggle minimize-toggle', () => setViewerMinimized(true));
  control.setAttribute('aria-label', 'Minimize game');control.setAttribute('aria-expanded','true');
  control.title = 'Minimize game for me. Any submitted answer is kept.';
  return control;
}

function renderMinimized(state) {
  const label = `Open ${state.mode ? modeInfo(state.mode).title : 'stream games'}. Game is minimized.`;
  if(root.querySelector('.minimized-card')?.getAttribute('aria-label')===label)return;
  const card = button('', 'game-card minimized-card', () => setViewerMinimized(false));
  card.dataset.mode = normalizeMode(state.mode);
  card.setAttribute('aria-label', label);
  card.setAttribute('aria-expanded','false');
  const sprite = icon('minimized-sprite','');sprite.append(pixelSprite(normalizeMode(state.mode)));
  const copy = element('span','minimized-copy');
  copy.append(element('strong','',state.mode ? modeInfo(state.mode).title : 'Stream games'),element('span','','Just watching · Open game'));
  card.append(sprite,copy,icon('minimized-expand','+'));
  root.replaceChildren(card);
}

function roundKey(state) {
  return `${state?.gameId || state?.game?.id || ''}:${state?.roundId || state?.round?.id || state?.roundNumber || ''}:${normalizeMode(state?.mode)}`;
}

function pixelSprite(kind) {
  const shapes = {
    quote: 'M2 3h12v9H8v3H5v-3H2z M5 6v3h2V6z M9 6v3h2V6z',
    niche: 'M5 1h6v2h3v3h1v4h-2v2h-2v2H9v2H7v-2H5v-2H3v-2H1V6h1V3h3z',
    hive: 'M3 2h4v3h2V2h4v4h2v7h-3v2H4v-2H1V6h2z M5 7v6h2V7z M9 7v6h2V7z',
    check: 'M1 7h3v3h2V8h2V6h2V4h2V2h3v4h-2v2h-2v2H9v2H7v3H4v-3H2v-2H1z',
    trophy: 'M4 1h8v2h3v6h-3v2H9v3h3v2H4v-2h3v-3H4V9H1V3h3z M2 4v3h2V4z M12 4v3h2V4z',
  };
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'pixel-sprite');svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('shape-rendering', 'crispEdges');svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(svg.namespaceURI, 'path');
  path.setAttribute('d', shapes[kind] || shapes.quote);path.setAttribute('fill', 'currentColor');path.setAttribute('fill-rule', 'evenodd');
  svg.append(path);return svg;
}

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
  if (!state.roundNumber) return "Quote round";
  return state.roundCount ? `Round ${state.roundNumber} of ${state.roundCount}` : `Round ${state.roundNumber}`;
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
  card.dataset.mode = normalizeMode(state.mode);
  const inner = element("div", "card-inner");
  const topline = element("div", "card-topline");
  const brand = element("div", "card-brand");
  brand.append(icon("brand-mark", ICONS.spark), element("span", "", state.isPreview ? "LOCAL PREVIEW" : "STREAM GAME"));
  const phase = state.gameStatus === "ended" ? "ended" : state.phase || state.round?.phase;
  const statusLabel = phase === "ended" ? "Game ended" : phase === "cancelled" ? "Round canceled" : phase === "results" || phase === "scored" ? "Round results" : phase === "submitted" ? "Answer received" : "Round live";
  topline.append(brand, element("span", "live-status", statusLabel));
  topline.append(minimizeButton());
  if (!document.body.classList.contains('mobile-view') && (state.isPreview || (isVideoOverlayContext && typeof window.Twitch?.ext?.actions?.minimize === "function"))) {
    const hideButton = button("Hide", "visibility-toggle", () => {
      if (state.isPreview) {
        previewViewerHidden = true;
        render(currentState);
      } else {
        window.Twitch.ext.actions.minimize();
      }
    });
    hideButton.setAttribute("aria-label", "Hide this extension for me");
    hideButton.title = "Hide the extension entirely; restore it using Twitch’s Extension controls.";
    topline.append(hideButton);
  }
  inner.append(topline);

  const heading = element("div", "mode-heading");
  const modeSymbol = icon("mode-symbol", "");modeSymbol.append(pixelSprite(normalizeMode(state.mode)));heading.append(modeSymbol);
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
  timer.setAttribute('role','timer');timer.setAttribute('aria-live','off');
  meta.append(count, timer);
  if (["ended", "results", "scored", "closed", "scoring", "cancelled", "canceled"].includes(phase)) timer.hidden = true;
  inner.append(meta);
  if (Number.isInteger(state.roundCount) && state.roundCount > 0) {
    const progress = element('div', 'round-progress');progress.setAttribute('aria-hidden', 'true');
    const rounds = Math.min(20, state.roundCount);
    for(let i=0;i<rounds;i++)progress.append(element('i', phase==='ended' || i < (Number(state.roundNumber)||1) ? 'is-done' : ''));
    inner.append(progress);
  }
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
  note.append(icon("", "◉"), element("span", "", `Broadcast source · ${sourceTimestamp}`));
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
  const instructions = { quote: 'Remember the missing word from the broadcast.', niche: 'Give a valid answer you think fewer viewers will choose.', hive: 'Give the answer you think most viewers will choose.' };
  inner.append(element('p', 'mode-instruction', instructions[normalizeMode(state.mode)]));

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
    const key = roundKey(state);
    input.value = answerDrafts.get(key) ?? state.editingAnswer ?? '';
    input.addEventListener('input', () => answerDrafts.set(key, input.value));
    input.setAttribute("aria-label", info.answerLabel);
    const submit = element("button", "submit-button");
    submit.type = "submit";
    submit.append(document.createTextNode("Send ▸"));
    if(pendingSubmissions.has(key)){submit.disabled=true;input.disabled=true;submit.textContent='Sending…';form.setAttribute('aria-busy','true');}
    row.append(input, submit);
    form.append(labelRow, row);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const answer = input.value;
      if (!answer.trim() || !adapter || pendingSubmissions.has(key)) return;
      pendingSubmissions.add(key);
      submit.disabled = true;
      input.disabled = true;
      submit.textContent = 'Sending…';form.setAttribute('aria-busy', 'true');
      try {
        await adapter.submit(answer);
      } catch (error) {
        pendingSubmissions.delete(key);
        if (roundKey(currentState) !== key || (!root.querySelector('.answer-form') && !viewerMinimized)) return;
        const latest = { ...currentState, submitError: error?.message || "Your answer could not be submitted. Please try again." };
        render(latest);
      } finally {
        pendingSubmissions.delete(key);
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
  footnote.append(document.createTextNode(state.canEdit ? "Edit until time ends" : "One submission"), icon("footnote-separator", ""), document.createTextNode("No speed bonus"));
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
  badge.replaceChildren(pixelSprite('check'));
  panel.append(badge, element("h2", "state-title", "Answer received"));
  panel.append(element("p", "state-description", "Your answer has been received. Keep watching; results will appear when the round is revealed."));
  if (state.ownSubmission?.answer) {
    const echo = element("div", "submission-echo");
    echo.append(icon("", ICONS.check), element("span", "", state.ownSubmission.answer));
    panel.append(echo);
  }
  if (state.canEdit) panel.append(button("Edit answer", "retry-button", () => render({...state, ownSubmission:null, editingAnswer:state.ownSubmission?.answer || ""})));
  panel.append(element("p", "card-footnote", state.canEdit ? "Edit until time ends · No speed bonus" : "One final answer · No edits after sending"));
  if(state.isPreview)panel.append(element('p','card-footnote','Simulated receipt · nothing sent to Twitch.'));
  inner.append(panel);
  root.replaceChildren(card);
  startCountdown(state.deadlineAt);
}

function appendLeaderboard(parent, entries, ownStanding, final = false) {
  const board = element("section", "leaderboard");
  board.setAttribute("aria-label", "Leaderboard");
  const header = element("div", "leaderboard-heading");
  header.append(element("span", "", "Leaderboard"), element("span", "", "SCORE"));
  board.append(header);
  const rows = Array.isArray(entries) ? (final ? [...entries] : entries.slice(0, 5)) : [];
  const containsOwn = ownStanding && rows.some((row) => row.isYou || row.isSelf);
  if (ownStanding && !containsOwn) rows.push({ ...ownStanding, isYou: true });

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
  const results = { ...(state.results || {}), ...(state.ownResult || {}) };
  const panel = element("div", "state-panel");
  const badge = element("div", "state-icon is-success", ended ? ICONS.chart : ICONS.check);
  badge.replaceChildren(pixelSprite(ended ? 'trophy' : normalizeMode(state.mode)));
  panel.append(badge, element("h2", "state-title", ended ? "GG, everyone." : "Round results"));

  if (ended) {
    panel.append(element("p", "state-description", state.roundCount ? `That’s the game. Final standings after ${state.roundCount} rounds.` : "That’s the game. Here are the final standings."));
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
    if(normalizeMode(state.mode)==='quote' && state.prompt){
      const quote=element('div','prompt-block');quote.append(element('p','prompt-label','The full quote'));
      const text=element('p','prompt-text');const parts=promptText(state.prompt).split(/_{3,}/);
      if(parts.length===2){text.append(document.createTextNode(parts[0]),element('strong','blank-token',results.revealedAnswer),document.createTextNode(parts[1]));quote.append(text);panel.append(quote);}
    }
  }
  inner.append(panel);
  appendLeaderboard(inner, ended ? (state.finalLeaderboard || state.leaderboard) : state.leaderboard, state.ownStanding, ended);
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
  card.append(minimizeButton());
  const badge = element("div", `state-icon${kind === "error" ? " is-warning" : ""}`, kind === "error" ? ICONS.warning : ICONS.spark);
  card.append(badge, element("h2", "state-title", message), element("p", "state-description", detail));
  if (retry) card.append(button("Try again", "retry-button", retry));
  root.replaceChildren(card);
  clearInterval(countdownInterval);
}

function renderState(state) {
  if (!root) return;
  clearInterval(countdownInterval);
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
  if(viewerMinimized){renderMinimized(currentState);return;}
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

function render(state) {
  if(!root)return;
  const key=roundKey(state);
  const focused=document.activeElement===root.querySelector('.answer-input');
  const compactFocused=document.activeElement?.classList.contains('minimized-card');
  const selection=focused ? [document.activeElement.selectionStart,document.activeElement.selectionEnd] : null;
  const sameRound=roundKey(currentState)===key;
  renderState(state);
  if(state?.ownSubmission || ['results','scored','ended','cancelled','canceled'].includes(state?.phase))answerDrafts.delete(key);
  const input=root.querySelector('.answer-input');
  if(focused && sameRound && input){input.focus({preventScroll:true});if(selection)input.setSelectionRange(...selection);}
  if(compactFocused)root.querySelector('.minimized-card')?.focus({preventScroll:true});
  // Bound in-memory drafts; no answers are stored on disk or sent by this cache.
  if(answerDrafts.size>20)answerDrafts.delete(answerDrafts.keys().next().value);
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

window.addEventListener("pagehide", () => adapter?.dispose?.());
