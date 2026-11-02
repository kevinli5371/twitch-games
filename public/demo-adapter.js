(() => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("demo") !== "1") return;

  // Complete the native Twitch helper handshake without using its token or the API.
  window.Twitch?.ext?.onAuthorized?.(() => {});

  const modes = {
    quote: {
      prompt: "I cannot believe we won with a ____.",
      result: { outcomeLabel: "That answer matched the missing word.", pointsAwarded: 1, revealedAnswer: "spoon" },
    },
    niche: {
      prompt: "Name a game that looks easy, but takes hours to master.",
      result: { outcomeLabel: "Your answer landed in a smaller answer group.", pointsAwarded: 2 },
    },
    hive: {
      prompt: "Which game would most viewers pick for one last round?",
      result: { outcomeLabel: "You matched one of the most common answers.", pointsAwarded: 1 },
    },
  };
  const rawMode = String(params.get("mode") || "quote").toLowerCase();
  const mode = rawMode === "hive_mind" || rawMode === "hivemind" ? "hive" : modes[rawMode] ? rawMode : "quote";
  const selected = modes[mode];
  const resultsRequested = params.get("phase") === "results";
  let state = {
    isPreview: true,
    identityLinked: true,
    canEdit: true,
    status: "active",
    gameId: "local-twitch-demo",
    gameStatus: "active",
    mode,
    roundNumber: 1,
    roundCount: 5,
    phase: resultsRequested ? "results" : "answering",
    prompt: selected.prompt,
    deadlineAt: resultsRequested ? null : new Date(Date.now() + 30_000).toISOString(),
    results: resultsRequested ? selected.result : null,
    leaderboard: resultsRequested ? [
      { rank: 1, displayName: "NovaStar", score: 6 },
      { rank: 2, displayName: "PixelPilot", score: 4 },
      { rank: 3, displayName: "MapleMode", score: 3 },
    ] : [],
    ownStanding: resultsRequested ? { rank: 4, score: selected.result.pointsAwarded } : null,
    evaluationIsPlaceholder: resultsRequested,
  };
  const listeners = new Set();
  const emit = () => listeners.forEach((listener) => listener(state));

  function finalizeSampleRound() {
    if (state.phase !== "answering" && state.phase !== "submitted") return;
    state = {
      ...state,
      phase: "results",
      deadlineAt: null,
      results: selected.result,
      leaderboard: [
        { rank: 1, displayName: "NovaStar", score: 6 },
        { rank: 2, displayName: "PixelPilot", score: 4 },
        { rank: 3, displayName: "MapleMode", score: 3 },
      ],
      ownStanding: { rank: 4, score: selected.result.pointsAwarded },
      evaluationIsPlaceholder: true,
    };
    emit();
  }

  const demoTimer = setInterval(() => {
    if ((state.phase === "answering" || state.phase === "submitted") && Date.now() >= new Date(state.deadlineAt).getTime()) {
      finalizeSampleRound();
      clearInterval(demoTimer);
    }
  }, 250);

  window.OVERLAY_PREVIEW_ADAPTER = {
    subscribe(listener) { listeners.add(listener); listener(state); return () => listeners.delete(listener); },
    async submit(answer) {
      if (!["answering", "submitted"].includes(state.phase) || Date.now() >= new Date(state.deadlineAt).getTime()) throw new Error("The sample round has closed.");
      state = { ...state, phase: "submitted", ownSubmission: { status: "submitted", answer } };
      emit();
    },
    async requestIdentityShare() {},
    async refresh() { emit(); },
  };
})();
