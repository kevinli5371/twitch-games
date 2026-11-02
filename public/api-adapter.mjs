// The only viewer mapping of the implemented FastAPI wire contract.
export function normalizeSnapshot(payload) {
  const round = payload.round;
  return {
    version: payload.version, gameId: payload.game_id, gameStatus: payload.status,
    status: payload.status === 'idle' ? 'idle' : undefined,
    round, roundId: round?.round_id, mode: 'quote', phase: round?.phase,
    prompt: round?.prompt, deadlineAt: round?.closes_at,
    results: round?.phase === 'results' ? { revealedAnswer: round.canonical_answer } : null,
    identityLinked: false, canEdit: true,
  };
}
export function mapStanding(entry, ownId) {
  return entry && { participantId: entry.participant_id, displayName: entry.display_name,
    rank: entry.rank, score: entry.points, isYou: entry.participant_id === ownId };
}
export function createTwitchAdapter({extension = window.Twitch?.ext,
  apiBaseUrl = window.TWITCH_GAMES_CONFIG?.apiBaseUrl || '', fetcher = fetch,
  pollMs = 3000, isDocumentHidden = () => document.hidden} = {}) {
  const listeners = new Set();
  let auth, snapshot = {loading: true}, visible = true, disposed = false;
  let lastVersion = -1, generation = 0, pendingAnswer = null, signature = '';
  const linked = () => Boolean(extension?.viewer?.isLinked && extension?.viewer?.id);
  const emit = (value) => {
    const next = JSON.stringify(value);
    if (signature === next || disposed) return;
    snapshot = value; signature = next; listeners.forEach(fn => fn(value));
  };
  async function request(path, options = {}) {
    const response = await fetcher(apiBaseUrl.replace(/\/$/, '') + path, {...options,
      credentials: 'omit', headers: {'Content-Type': 'application/json',
        Authorization: `Bearer ${auth?.token || ''}`}});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(body.error?.message || 'The game service could not complete the request.');
      error.status = response.status; error.code = body.error?.code; throw error;
    }
    return body;
  }
  async function refresh() {
    if (!auth?.channelId || disposed) return;
    if (!apiBaseUrl) return emit({status: 'not-configured'});
    const id = ++generation;
    try {
      const payload = await request(`/channels/${encodeURIComponent(auth.channelId)}/game-state`);
      const next = normalizeSnapshot(payload);
      next.identityLinked = linked();
      if (next.roundId && linked()) {
        try {
          const own = await request(`/rounds/${encodeURIComponent(next.roundId)}/me`);
          next.ownSubmission = own.receipt ? {status: 'received', answer: own.answer} : null;
          if (own.result) next.results = {...next.results,
            pointsAwarded: own.result.awarded_points,
            outcomeLabel: own.result.outcome === 'correct' ? 'You got the missing word!' : 'That answer did not match the missing word.'};
        } catch (error) { if (error.status !== 404) throw error; }
      }
      if (next.gameId && (next.phase === 'results' || next.gameStatus === 'ended')) {
        const board = await request(`/games/${encodeURIComponent(next.gameId)}/leaderboard`);
        const ownId = board.own_entry?.participant_id;
        next.leaderboard = board.entries.map(entry => mapStanding(entry, ownId));
        next.finalLeaderboard = next.leaderboard;
        next.ownStanding = mapStanding(board.own_entry, ownId);
      }
      if (id !== generation || disposed || payload.version < lastVersion) return;
      lastVersion = payload.version; emit(next);
    } catch (error) {
      if (id === generation) emit({...snapshot, error: error.message});
    }
  }
  const poll = extension ? setInterval(() => { if (visible && !isDocumentHidden()) refresh(); }, pollMs) : null;
  const authorizationTimer = extension ? setTimeout(() => {
    if (!auth) emit({status: 'not-in-twitch'});
  }, 8000) : null;
  extension?.listen?.('broadcast', (_target, type, message) => {
    if (type !== 'application/json') return;
    try {
      const event = JSON.parse(message);
      if (event.event === 'game_state_changed' && event.channel_id === auth?.channelId && event.version > lastVersion) refresh();
    } catch { /* A subsequent poll restores authoritative state. */ }
  });
  extension?.onAuthorized?.(value => {
    if (auth && value.channelId !== auth.channelId) { lastVersion = -1; pendingAnswer = null; }
    auth = value; clearTimeout(authorizationTimer); refresh();
  });
  extension?.viewer?.onChanged?.(() => refresh());
  if (!extension) snapshot = {status: 'not-in-twitch'};
  return {
    subscribe(fn) { listeners.add(fn); fn(snapshot); return () => listeners.delete(fn); },
    refresh,
    async submit(answer) {
      if (!auth?.token || !linked()) throw new Error('Link your Twitch identity before submitting.');
      if (!snapshot.roundId || snapshot.phase !== 'answering') throw new Error('There is no open round to answer.');
      // Network retries reuse the UUID and exact raw text. A changed answer is an edit.
      if (!pendingAnswer || pendingAnswer.roundId !== snapshot.roundId || pendingAnswer.answer !== answer) {
        pendingAnswer = {roundId: snapshot.roundId, request_id: crypto.randomUUID(), answer};
      }
      const {request_id, roundId} = pendingAnswer;
      try { await request(`/rounds/${encodeURIComponent(roundId)}/answers`, {
        method: 'POST', body: JSON.stringify({request_id, answer})});
      } catch (error) { if (error.status && error.status < 500) pendingAnswer = null; throw error; }
      pendingAnswer = null; await refresh();
    },
    requestIdentityShare() { extension?.actions?.requestIdShare?.(); },
    onVisibilityChanged(fn) { extension?.onVisibilityChanged?.(value => { visible = Boolean(value); fn(visible); }); },
    dispose() { disposed = true; clearInterval(poll); clearTimeout(authorizationTimer); listeners.clear(); },
  };
}
