(() => {
  const PROMPTS = {
    quote: {
      text: "I cannot believe we won with a ____.",
      sourceTimestamp: "04:18",
      revealedAnswer: "spoon",
      answer: "spoon",
      outcomeLabel: "That answer matched the missing word.",
      points: 1,
    },
    niche: {
      text: "Name a game that looks easy, but takes hours to master.",
      sourceTimestamp: null,
      answer: "Tetris",
      outcomeLabel: "Your answer landed in a smaller answer group.",
      points: 2,
    },
    hive: {
      text: "Which game would most viewers pick for one last round?",
      sourceTimestamp: null,
      answer: "Mario Kart",
      outcomeLabel: "You matched one of the most common answers.",
      points: 1,
    },
  };

  const LABELS = { quote: "Quote Completion", niche: "Niche", hive: "Hive Mind" };
  let mode = "quote";
  let phase = "answering";
  let chosenMode = "quote";
  let roundNumber = 1;
  let roundCount = 5;
  let modeSelection = "streamer";
  let previousRandomMode = null;
  let lastAnswer = "";
  let streamerOverlayEnabled = true;
  let sessionScore = 0;
  let deadlineAt = new Date(Date.now() + 30_000).toISOString();

  function demoState() {
    const prompt = PROMPTS[mode];
    const leaderBoard = [
      { rank: 1, displayName: "NovaStar", score: 6 },
      { rank: 2, displayName: "PixelPilot", score: 4 },
      { rank: 3, displayName: "MapleMode", score: 3 },
    ];
    const points = phase === "results" ? prompt.points : 0;
    const ownStanding = phase === "results"
      ? { rank: 1 + [6, 4, 3].filter((score) => score > sessionScore).length, score: sessionScore }
      : null;
    const finalLeaderboard = [
      { displayName: "NovaStar", score: 12 },
      { displayName: "PixelPilot", score: 9 },
      { displayName: "MapleMode", score: 5 },
      { displayName: "You", score: sessionScore, isYou: true },
    ].sort((a, b) => b.score - a.score).map((entry, index, rows) => ({
      ...entry,
      rank: index > 0 && entry.score === rows[index - 1].score ? rows[index - 1].rank : index + 1,
    }));
    return {
      isPreview: true,
      overlayEnabled: streamerOverlayEnabled,
      identityLinked: true,
      gameId: "local-sample-game",
      gameStatus: phase === "ended" ? "ended" : "active",
      mode,
      roundNumber,
      roundCount,
      phase,
      prompt: prompt.text,
      sourceTimestamp: prompt.sourceTimestamp,
      deadlineAt: phase === "answering" || phase === "submitted" ? deadlineAt : null,
      ownSubmission: lastAnswer ? { status: "submitted", answer: lastAnswer } : null,
      results: phase === "results" ? { outcomeLabel: prompt.outcomeLabel, pointsAwarded: points, revealedAnswer: mode === "quote" ? prompt.revealedAnswer : null } : null,
      leaderboard: phase === "results" || phase === "ended" ? leaderBoard : [],
      finalLeaderboard: phase === "ended" ? finalLeaderboard : [],
      ownStanding,
      evaluationIsPlaceholder: phase === "results" || phase === "ended",
    };
  }

  function render() {
    window.StreamGameOverlay?.render(demoState());
    const modeLabel = document.getElementById("preview-mode-label");
    if (modeLabel) modeLabel.textContent = LABELS[mode];
    document.querySelectorAll("[data-mode]").forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.mode === mode);
    });
    document.querySelectorAll("[data-phase]").forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.phase === phase);
    });
  }

  function changeMode(nextMode) {
    if (!PROMPTS[nextMode]) return;
    mode = nextMode;
    chosenMode = nextMode;
    phase = "answering";
    lastAnswer = "";
    deadlineAt = new Date(Date.now() + 30_000).toISOString();
    render();
  }

  function selectRandomMode() {
    const choices = Object.keys(PROMPTS).filter((candidate) => candidate !== previousRandomMode);
    const next = choices[Math.floor(Math.random() * choices.length)];
    previousRandomMode = next;
    mode = next;
    chosenMode = next;
    phase = "answering";
    lastAnswer = "";
    deadlineAt = new Date(Date.now() + 30_000).toISOString();
    render();
  }

  function closeRound() {
    if (phase !== "answering" && phase !== "submitted") return;
    sessionScore += PROMPTS[mode].points;
    phase = "results";
    render();
  }

  function cancelRound() {
    if (phase !== "answering" && phase !== "submitted") return;
    phase = "cancelled";
    lastAnswer = "";
    render();
  }

  function advanceRound() {
    if (phase !== "results" && phase !== "cancelled") return;
    const wasCancelled = phase === "cancelled";
    if (wasCancelled) {
      if (modeSelection === "random") {
        previousRandomMode = mode;
        selectRandomMode();
      } else {
        phase = "answering";
        lastAnswer = "";
        deadlineAt = new Date(Date.now() + 30_000).toISOString();
        render();
      }
      return;
    }
    if (roundNumber >= roundCount) {
      phase = "ended";
      render();
      return;
    }
    roundNumber += 1;
    if (modeSelection === "random") {
      previousRandomMode = mode;
      selectRandomMode();
    }
    else {
      mode = chosenMode;
      phase = "answering";
      lastAnswer = "";
      deadlineAt = new Date(Date.now() + 30_000).toISOString();
      render();
    }
  }

  window.OVERLAY_PREVIEW_ADAPTER = {
    subscribe(listener) {
      const off = () => document.removeEventListener("stream-preview-state", onState);
      const onState = () => listener(demoState());
      document.addEventListener("stream-preview-state", onState);
      listener(demoState());
      return off;
    },
    async submit(answer) {
      lastAnswer = answer;
      phase = "submitted";
      render();
    },
    async requestIdentityShare() {},
    async refresh() { render(); },
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => changeMode(button.dataset.mode)));
    document.querySelectorAll("[data-phase]").forEach((button) => button.addEventListener("click", () => {
      phase = button.dataset.phase;
      lastAnswer = phase === "submitted" ? "spoon" : "";
      if (phase === "answering" || phase === "submitted") deadlineAt = new Date(Date.now() + 30_000).toISOString();
      render();
    }));

    const controls = document.querySelector(".preview-controls");
    const modeRow = controls?.querySelector(".control-row");
    if (modeRow) {
      const countLabel = document.createElement("label");
      countLabel.className = "round-count-control";
      countLabel.append(document.createTextNode("Rounds "));
      const countSelect = document.createElement("select");
      countSelect.setAttribute("aria-label", "Sample game round count");
      for (const optionValue of [3, 5, 7, 10]) {
        const option = document.createElement("option");
        option.value = String(optionValue);
        option.textContent = String(optionValue);
        if (optionValue === 5) option.selected = true;
        countSelect.append(option);
      }
      countSelect.addEventListener("change", () => {
        roundCount = Number(countSelect.value);
        roundNumber = 1;
        sessionScore = 0;
        modeSelection = selectionSelect.value;
        previousRandomMode = null;
        phase = "answering";
        lastAnswer = "";
        deadlineAt = new Date(Date.now() + 30_000).toISOString();
        render();
      });
      countLabel.append(countSelect);
      modeRow.append(countLabel);

      const selectionLabel = document.createElement("label");
      selectionLabel.className = "round-count-control";
      selectionLabel.append(document.createTextNode("Mode "));
      const selectionSelect = document.createElement("select");
      selectionSelect.setAttribute("aria-label", "Sample mode selection");
      for (const [value, text] of [["streamer", "Selected"], ["random", "Random"]]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        selectionSelect.append(option);
      }
      selectionSelect.addEventListener("change", () => {
        modeSelection = selectionSelect.value;
        previousRandomMode = modeSelection === "random" ? mode : null;
      });
      selectionLabel.append(selectionSelect);
      modeRow.append(selectionLabel);

      const visibilityLabel = document.createElement("label");
      visibilityLabel.className = "round-count-control";
      visibilityLabel.append(document.createTextNode("Streamer overlay "));
      const visibilityToggle = document.createElement("input");
      visibilityToggle.type = "checkbox";
      visibilityToggle.setAttribute("aria-label", "Streamer overlay enabled for viewers");
      visibilityToggle.checked = true;
      visibilityToggle.addEventListener("change", () => {
        streamerOverlayEnabled = visibilityToggle.checked;
        render();
      });
      visibilityLabel.append(visibilityToggle);
      modeRow.append(visibilityLabel);
    }

    const stateRow = controls?.querySelector(".state-controls");
    if (stateRow) {
      const closeButton = document.createElement("button");
      closeButton.className = "state-button";
      closeButton.type = "button";
      closeButton.textContent = "Close round";
      closeButton.addEventListener("click", closeRound);
      stateRow.append(closeButton);

      const advanceButton = document.createElement("button");
      advanceButton.className = "state-button";
      advanceButton.type = "button";
      advanceButton.textContent = "Advance";
      advanceButton.addEventListener("click", advanceRound);
      stateRow.append(advanceButton);

      const cancelButton = document.createElement("button");
      cancelButton.className = "state-button";
      cancelButton.type = "button";
      cancelButton.textContent = "Cancel round";
      cancelButton.addEventListener("click", cancelRound);
      stateRow.append(cancelButton);
    }
    render();
    setInterval(() => {
      if ((phase === "answering" || phase === "submitted") && Date.now() >= new Date(deadlineAt).getTime()) closeRound();
    }, 250);
  });
})();
