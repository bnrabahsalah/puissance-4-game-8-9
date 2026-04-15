class Connect4Web {
  EMPTY = ".";
  RED = "R";
  YELLOW = "Y";
  CONNECT_N = 4;

  COLOR_BG = "#2f1252";
  COLOR_HOLE = "#fef3c7";
  COLOR_RED = "#ff4d6d";
  COLOR_YELLOW = "#facc15";
  COLOR_WIN = "#22c55e";
  COLOR_HOVER_COL = "rgba(250,204,21,0.16)";
  LS_NAME_R = "c4_name_red";
  LS_NAME_Y = "c4_name_yellow";
  LS_HISTORY = "c4_history";
  LS_ONLINE_CODE = "c4_online_code";
  LS_ONLINE_SECRET = "c4_online_secret";
  LS_ONLINE_TOKEN = "c4_online_token";
  LS_ONLINE_NAME = "c4_online_name";
  LS_STARTING_COLOR = "c4_starting_color";
  LOCAL_DB_NAME = "c4_local_db";
  LOCAL_DB_VERSION = 1;
  LOCAL_GAMES_STORE = "saved_games";
  HISTORY_LIMIT = 120;

  constructor() {
    const cfg = this.loadConfig();
    this.rows = cfg.rows;
    this.cols = cfg.cols;
    this.startingColor = cfg.starting_color;

    this.board = null;
    this.current = this.startingColor;
    this.gameOver = false;
    this.winner = null;
    this.winningCells = [];
    this.gameIndex = 1;
    this.moves = [];
    this.viewIndex = 0;

    this.robotThinking = false;
    this.aiLock = false;
    this.pendingTimers = new Set();

    this.online = {
      enabled: false,
      code: null,
      secret: null,
      token: null,
      pollId: null,
      joinInFlight: false,
      createInFlight: false,
      moveInFlight: false,
      rematchInFlight: false,
      savingFinishedGame: false,
      autoSavedFinishedGame: false,
      players: [],
      spectators: 0,
      lastWinner: null,
      lastStatus: null,
    };

    this.lastDrawGeom = null;
    this.hoverCol = null;
    this.predictionReqId = 0;
    this._predictionAbortController = null;
    this._predictionTimer = null;
    this._predictionCacheKey = "";
    this._minimaxDeadline = null;
    this._localTT = new Map();
    this._localHistory = new Map();
    this._localKillerMoves = Array.from({ length: 64 }, () => [null, null]);
    this._localZobristTables = new Map();
    this._localDbPromise = null;
    this._lastPredictionText = "";
    this._scoresRenderToken = 0;
    this._aiActionToken = 0;
    this.paintMode = false;
    this.paintColor = this.EMPTY;
    this.runtime = {
      env: this.detectRuntimeEnv(),
      storage: this.detectRuntimeStorage(),
      hasDatabase: false,
    };

    this.el = {
      aiMode: document.getElementById("aiMode"),
      controlR: document.getElementById("controlR"),
      controlY: document.getElementById("controlY"),
      depth: document.getElementById("depth"),
      noDigits: document.getElementById("noDigits"),
      saveName: document.getElementById("saveName"),
      startColor: document.getElementById("startColor"),
      nameR: document.getElementById("nameR"),
      nameY: document.getElementById("nameY"),
      changeR: document.getElementById("changeR"),
      changeY: document.getElementById("changeY"),
      predictionText: document.getElementById("predictionText"),
      onlineName: document.getElementById("onlineName"),
      paintToggle: document.getElementById("paintToggle"),
      paintColor: document.getElementById("paintColor"),
      paintClear: document.getElementById("paintClear"),
      paintInfo: document.getElementById("paintInfo"),
      paintResume: document.getElementById("paintResume"),
      onlineCode: document.getElementById("onlineCode"),
      onlineCreate: document.getElementById("onlineCreate"),
      onlineJoin: document.getElementById("onlineJoin"),
      onlineLeave: document.getElementById("onlineLeave"),
      onlineBadge: document.getElementById("onlineBadge"),
      onlineCopyLink: document.getElementById("onlineCopyLink"),
      onlineRematch: document.getElementById("onlineRematch"),
      spectatorsInfo: document.getElementById("spectatorsInfo"),

      saveMenu: document.getElementById("saveMenu"),
      loadMenu: document.getElementById("loadMenu"),
      loadJson: document.getElementById("loadJson"),

      newGame: document.getElementById("newGame"),
      stop: document.getElementById("stop"),

      status: document.getElementById("status"),
      colHoverInfo: document.getElementById("colHoverInfo"),

      colLabels: document.getElementById("colLabels"),
      colButtons: document.getElementById("colButtons"),
      colScores: document.getElementById("colScores"),

      canvasWrap: document.getElementById("canvasWrap"),
      canvas: document.getElementById("board"),

      moveSlider: document.getElementById("moveSlider"),
      moveLabel: document.getElementById("moveLabel"),
      firstMove: document.getElementById("firstMove"),
      prevMove: document.getElementById("prevMove"),
      nextMove: document.getElementById("nextMove"),
      lastMove: document.getElementById("lastMove"),

      rowsVal: document.getElementById("rowsVal"),
      colsVal: document.getElementById("colsVal"),
      startVal: document.getElementById("startVal"),
      gameIndexVal: document.getElementById("gameIndexVal"),
      movesVal: document.getElementById("movesVal"),
      viewVal: document.getElementById("viewVal"),

      historyBody: document.getElementById("historyBody"),
      clearHistoryBtn: document.getElementById("clearHistory"),
    };

    this.ctx = this.el.canvas?.getContext?.("2d") || null;

    this.bindUI();

    if (this.el.startColor) this.el.startColor.value = this.startingColor;
    if (this.el.controlR && !this.el.controlR.value) this.el.controlR.value = "human";
    if (this.el.controlY && !this.el.controlY.value) this.el.controlY.value = "ai";

    this.ensurePlayerNames();
    this.ensureDefaultSaveName();
    this.renderHistory();

    if (this.el.paintColor) this.el.paintColor.value = this.EMPTY;
    this.updatePaintUI();

    this.resetGame(false);
    this.setupResponsiveCanvas();
    this.setOnlineBadge("Offline");
    this.updateSpectatorsInfo(0);

    if (this.el.onlineName) {
      const savedName = (localStorage.getItem(this.LS_ONLINE_NAME) || "").trim();
      if (savedName && !this.el.onlineName.value) this.el.onlineName.value = savedName;
    }

    const params = new URLSearchParams(location.search);
    const joinCode = (params.get("join") || "").trim().toUpperCase();

    const hadSession = this.onlineLoadSession();

    if (joinCode) {
      if (this.el.onlineCode) this.el.onlineCode.value = joinCode;

      if (hadSession && this.online.code === joinCode) {
        this.setOnlineEnabled(true);
        this.onlineStartPolling();
        this.cleanJoinUrl();
      } else {
        this.onlineJoinFlow(joinCode).catch((e) => {
          alert("❌ Join URL: " + (e?.message || e));
        });
      }
    } else if (hadSession) {
      if (this.el.onlineCode) this.el.onlineCode.value = this.online.code;
      this.setOnlineEnabled(true);
      this.onlineStartPolling();
    }
  }

  // ===== PAINT MODE
  updatePaintUI() {
    if (this.el.paintToggle) {
      this.el.paintToggle.textContent = this.paintMode ? "🎨 ON" : "🎨 OFF";
      this.el.paintToggle.classList.toggle("isActive", this.paintMode);
    }

    if (this.el.paintInfo) {
      this.el.paintInfo.hidden = !this.paintMode;
    }

    if (this.el.paintResume) {
      this.el.paintResume.hidden = !this.paintMode;
    }
  }

  inferCurrentPlayerFromBoard() {
    if (!this.board) return this.startingColor;

    let red = 0;
    let yellow = 0;

    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        if (this.board[r][c] === this.RED) red++;
        else if (this.board[r][c] === this.YELLOW) yellow++;
      }
    }

    const total = red + yellow;

    return total % 2 === 0
      ? this.startingColor
      : this.other(this.startingColor);
  }
  detectWinnerOnBoard() {
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const token = this.board[r][c];
        if (token === this.EMPTY) continue;

        const cells = this.checkWinCells(this.board, r, c, token);
        if (cells.length) {
          return { winner: token, cells };
        }
      }
    }
    return { winner: null, cells: [] };
  }

  applyPaintAt(row, col) {
    if (!this.board) return;
    if (row < 0 || row >= this.rows || col < 0 || col >= this.cols) return;
    if (this.online.enabled) return;

    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;

    this.board[row][col] = this.paintColor;

    this.moves = [];
    this.viewIndex = 0;

    const win = this.detectWinnerOnBoard();
    this.winningCells = win.cells;
    this.winner = win.winner;
    this.gameOver = !!win.winner;

    if (!this.gameOver) {
      this.current = this.inferCurrentPlayerFromBoard();
    }

    this.drawBoard();
    this.updateReplayUI();
    this.updateStatus();
    this.updateSidePanel();
    this.setButtonsState(true);
    this.updatePrediction();
  }

  resumeGameFromPaint() {
    if (!this.board || this.online.enabled) return;

    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;

    const win = this.detectWinnerOnBoard();
    this.winningCells = win.cells;
    this.winner = win.winner;
    this.gameOver = !!win.winner || this.isDraw(this.board);
    if (!win.winner && this.gameOver) this.winner = null;

    if (!this.gameOver) {
      this.current = this.inferCurrentPlayerFromBoard();
    }

    this.paintMode = false;
    this._aiActionToken++;
    this.updatePaintUI();
    this.afterStateChange(true);
  }

  clearPaintBoard() {
    if (!this.board || this.online.enabled) return;

    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;

    this.board = this.createBoard();
    this.moves = [];
    this.viewIndex = 0;
    this.current = this.startingColor;
    this.gameOver = false;
    this.winner = null;
    this.winningCells = [];

    this.afterStateChange(false);
    this.resizeCanvasReliable();
  }

  // ===== CONFIG
  loadConfig() {
    const savedStart = localStorage.getItem(this.LS_STARTING_COLOR);
    const starting_color = savedStart === this.YELLOW ? this.YELLOW : this.RED;

    return {
      rows: 9,
      cols: 9,
      starting_color,
    };
  }

  detectRuntimeEnv() {
    const host = (window.location.hostname || "").toLowerCase();
    if (window.location.protocol === "file:") return "local";
    if (host === "127.0.0.1" || host === "localhost") return "local";
    return "production";
  }

  detectRuntimeStorage() {
    return this.detectRuntimeEnv() === "local" ? "indexeddb" : "postgres";
  }

  async initializeRuntime() {
    try {
      const res = await this.apiFetch("/config", { method: "GET" });
      if (res?.env) this.runtime.env = String(res.env).toLowerCase();
      if (res?.storage) this.runtime.storage = String(res.storage).toLowerCase();
      this.runtime.hasDatabase = !!res?.has_database;
    } catch {
      this.runtime = {
        ...this.runtime,
        env: this.detectRuntimeEnv(),
        storage: this.detectRuntimeStorage(),
        hasDatabase: false,
      };
    }
  }

  isLocalPersistence() {
    return this.runtime.storage === "indexeddb";
  }

  apiBase() {
    const { protocol, hostname, port } = window.location;

    if (port === "8000") {
      return "/api";
    }

    if (hostname === "127.0.0.1" || hostname === "localhost") {
      return `${protocol}//${hostname}:8000/api`;
    }

    return "/api";
  }

  async apiFetch(path, opts = {}) {
    const url = `${this.apiBase()}${path}`;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });

    let payload = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }

    if (!res.ok) {
      if (res.status === 405 && path === "/ai/move" && (opts.method || "GET").toUpperCase() === "POST") {
        try {
          const body = opts.body ? JSON.parse(opts.body) : {};
          const params = new URLSearchParams({
            board: JSON.stringify(body.board || []),
            player: String(body.player || "R"),
            ai_mode: String(body.ai_mode || "minimax"),
            depth: String(body.depth || 4),
          });
          return await this.apiFetch(`/ai/move?${params.toString()}`, { method: "GET" });
        } catch { }
      }

      const msg =
        payload?.detail ||
        payload?.error ||
        payload?.message ||
        `HTTP ${res.status}`;
      throw new Error(msg);
    }

    return payload;
  }

  async requestPrediction(payload, signal = null) {
    const params = new URLSearchParams({
      board: JSON.stringify(payload.board || []),
      player: String(payload.player || "R"),
      depth: String(payload.depth || 8),
    });

    return await this.apiFetch(`/predict?${params.toString()}`, {
      method: "GET",
      signal,
    });
  }
  async requestAiMove(payload, signal = null) {
    return await this.apiFetch("/ai/move", {
      method: "POST",
      body: JSON.stringify({
        board: payload.board || [],
        player: String(payload.player || "R"),
        ai_mode: String(payload.ai_mode || "minimax"),
        depth: String(payload.depth || 4),
      }),
      signal,
    });
  }
  cleanJoinUrl() {
    try {
      const cleanUrl = `${location.origin}${location.pathname}`;
      window.history.replaceState({}, "", cleanUrl);
    } catch { }
  }

  other(t) {
    return t === this.RED ? this.YELLOW : this.RED;
  }

  clampInt(v, lo, hi, dflt) {
    const x = parseInt(v, 10);
    if (Number.isNaN(x)) return dflt;
    return Math.max(lo, Math.min(hi, x));
  }

  copyGrid(g) {
    return g.map((row) => row.slice());
  }

  tokenForMoveIndex(i) {
    return i % 2 === 0 ? this.startingColor : this.other(this.startingColor);
  }

  schedule(fn, ms) {
    const id = setTimeout(() => {
      this.pendingTimers.delete(id);
      fn();
    }, ms);
    this.pendingTimers.add(id);
    return id;
  }

  clearTimers() {
    for (const id of this.pendingTimers) clearTimeout(id);
    this.pendingTimers.clear();
  }

  escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  getControlRed() {
    return this.el.controlR?.value === "ai" ? "ai" : "human";
  }

  getControlYellow() {
    return this.el.controlY?.value === "human" ? "human" : "ai";
  }

  isHumanTurn(current) {
    if (this.online.enabled) return false;
    if (current === this.RED) return this.getControlRed() === "human";
    return this.getControlYellow() === "human";
  }

  getDerivedGameMode() {
    const r = this.getControlRed();
    const y = this.getControlYellow();

    if (r === "ai" && y === "ai") return 0;
    if (r === "human" && y === "human") return 2;
    return 1;
  }

  controlsFromLegacyMode(mode) {
    const m = Number(mode);
    if (m === 0) return { controlRed: "ai", controlYellow: "ai" };
    if (m === 2) return { controlRed: "human", controlYellow: "human" };
    return { controlRed: "human", controlYellow: "ai" };
  }

  applyControls(controlRed, controlYellow) {
    if (this.el.controlR) this.el.controlR.value = controlRed === "ai" ? "ai" : "human";
    if (this.el.controlY) this.el.controlY.value = controlYellow === "human" ? "human" : "ai";
  }

  // ===== ONLINE HELPERS
  setOnlineBadge(text) {
    if (!this.el.onlineBadge) return;
    this.el.onlineBadge.textContent = text;
  }

  updateSpectatorsInfo(count) {
    this.online.spectators = Number.isInteger(count) ? count : 0;
    if (this.el.spectatorsInfo) {
      this.el.spectatorsInfo.textContent = `👁 ${this.online.spectators}`;
    }
  }

  getOnlineName() {
    const a = (this.el.onlineName?.value || "").trim();
    if (a) {
      localStorage.setItem(this.LS_ONLINE_NAME, a);
      return a;
    }
    const b = (localStorage.getItem(this.LS_ONLINE_NAME) || "").trim();
    return b || "Joueur";
  }

  setOnlineEnabled(on) {
    this.online.enabled = !!on;

    if (this.online.enabled) {
      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;
      if (this.el.aiMode) this.el.aiMode.value = "random";
      this.setScoresBlank();
    }

    this.updateStatus();
    this.setButtonsState(true);
  }

  onlineSaveSession(code, secret, token) {
    this.online.code = code;
    this.online.secret = secret;
    this.online.token = token;
    localStorage.setItem(this.LS_ONLINE_CODE, code);
    localStorage.setItem(this.LS_ONLINE_SECRET, secret || "");
    localStorage.setItem(this.LS_ONLINE_TOKEN, token || "");
  }

  onlineLoadSession() {
    const code = (localStorage.getItem(this.LS_ONLINE_CODE) || "").trim();
    const secret = (localStorage.getItem(this.LS_ONLINE_SECRET) || "").trim();
    const token = (localStorage.getItem(this.LS_ONLINE_TOKEN) || "").trim();

    if (code && token) {
      this.online.code = code;
      this.online.secret = secret;
      this.online.token = token;
      return true;
    }
    return false;
  }

  onlineClearSession() {
    this.online.code = null;
    this.online.secret = null;
    this.online.token = null;
    this.online.players = [];
    this.online.spectators = 0;
    this.online.autoSavedFinishedGame = false;
    localStorage.removeItem(this.LS_ONLINE_CODE);
    localStorage.removeItem(this.LS_ONLINE_SECRET);
    localStorage.removeItem(this.LS_ONLINE_TOKEN);
  }

  onlineStartPolling() {
    this.onlineStopPolling();
    if (!this.online.code) return;

    const tick = async () => {
      if (!this.online.enabled || !this.online.code) return;

      try {
        const st = await this.apiFetch(`/online/${this.online.code}/state`, {
          method: "GET",
        });
        this.applyOnlineState(st);
      } catch (e) {
        this.setOnlineBadge(`Offline (${e?.message || "erreur"})`);
      } finally {
        this.online.pollId = setTimeout(tick, 800);
      }
    };

    tick();
  }

  onlineStopPolling() {
    if (this.online.pollId) clearTimeout(this.online.pollId);
    this.online.pollId = null;
  }

  async onlineCreateFlow() {
    if (this.online.createInFlight) return;
    this.online.createInFlight = true;
    if (this.el.onlineCreate) this.el.onlineCreate.disabled = true;

    try {
      const name = this.getOnlineName();
      const out = await this.apiFetch("/online/create", {
        method: "POST",
        body: JSON.stringify({
          player_name: name,
          rows: this.rows,
          cols: this.cols,
          starting_color: this.startingColor,
        }),
      });

      this.onlineSaveSession(out.code, out.player_secret, out.your_token);
      if (this.el.onlineCode) this.el.onlineCode.value = out.code;

      this.online.autoSavedFinishedGame = false;
      this.setOnlineEnabled(true);
      this.setOnlineBadge(`Online #${out.code} (${out.your_token})`);

      this.resetLocalBoardOnly();
      this.onlineStartPolling();

      alert(`✅ Partie online créée.\nCode: ${out.code}\nPartage: ${location.origin}/?join=${out.code}`);
    } finally {
      this.online.createInFlight = false;
      if (this.el.onlineCreate) this.el.onlineCreate.disabled = false;
    }
  }

  normalizePredictionWinner(value) {
    if (value === this.RED || value === "R" || value === "red" || value === "RED") {
      return this.RED;
    }
    if (value === this.YELLOW || value === "Y" || value === "yellow" || value === "YELLOW") {
      return this.YELLOW;
    }
    if (
      value === null ||
      value === undefined ||
      value === "draw" ||
      value === "DRAW" ||
      value === "D" ||
      value === "null"
    ) {
      return null;
    }
    return undefined;
  }
  localPredictPosition(board, player, maxDepth = 8, timeLimitMs = 1200) {
    if (!board) {
      return {
        winner: null,
        best_col: null,
        score: 0,
        exact: false,
        mateIn: null,
        moves: null,
      };
    }

    const terminal = this.terminalState(board);
    if (terminal.over) {
      return {
        winner: terminal.winner,
        best_col: null,
        score:
          terminal.winner === player
            ? 1000000000
            : terminal.winner === null
              ? 0
              : -1000000000,
        exact: true,
        mateIn: 0,
        moves: 0,
      };
    }

    const best = this.runLocalBestMove(this.copyGrid(board), player, maxDepth, timeLimitMs);
    const score = Number.isFinite(best?.score) ? Number(best.score) : 0;

    let winner = null;
    if (score > 900000) winner = player;
    else if (score < -900000) winner = this.other(player);

    const mateIn =
      best?.distance !== null &&
        best?.distance !== undefined &&
        Number.isFinite(Number(best.distance))
        ? Number(best.distance)
        : null;

    return {
      winner,
      best_col:
        best?.move !== null &&
          best?.move !== undefined &&
          Number.isInteger(Number(best.move))
          ? Number(best.move)
          : null,
      score,
      exact: Math.abs(score) > 900000 || score === 0,
      mateIn,
      moves: mateIn,
      depthReached: Number(best?.depthReached || 0),
    };
  }

  formatPredictionResult(data) {
    const winner = this.normalizePredictionWinner(data?.winner);

    const bestCol =
      data?.best_col !== null &&
        data?.best_col !== undefined &&
        Number.isFinite(Number(data.best_col))
        ? Number(data.best_col)
        : null;

    const mateIn =
      data?.mateIn !== null &&
        data?.mateIn !== undefined &&
        Number.isFinite(Number(data.mateIn))
        ? Number(data.mateIn)
        : null;

    const moves =
      data?.moves !== null &&
        data?.moves !== undefined &&
        Number.isFinite(Number(data.moves))
        ? Number(data.moves)
        : null;

    const score =
      data?.score !== null &&
        data?.score !== undefined &&
        Number.isFinite(Number(data.score))
        ? Number(data.score)
        : 0;

    const exact = !!data?.exact;

    const parts = [];

    if (bestCol !== null) {
      parts.push(`💡 Meilleur coup : colonne ${bestCol + 1}`);
    }

    if (winner === this.RED || winner === this.YELLOW) {
      const color = winner === this.RED ? "Rouge" : "Jaune";
      const n = mateIn ?? moves;

      if (n !== null) {
        parts.push(
          exact
            ? `🔥 ${color} gagne dans ${n} coup(s)`
            : `🔥 ${color} devrait gagner dans ${n} coup(s)`
        );
      } else {
        parts.push(
          exact
            ? `🔥 ${color} gagne`
            : `🔥 ${color} a l’avantage`
        );
      }
    } else {
      if (score >= 1000) {
        parts.push("🔴 Rouge a l’avantage");
      } else if (score <= -1000) {
        parts.push("🟡 Jaune a l’avantage");
      } else {
        parts.push("⚖️ Position équilibrée");
      }
    }

    return parts.length ? parts.join(" | ") : "Prédiction : indisponible";
  }

  formatScoreForDisplay(score, distance = null) {
    const s = Number(score);
    if (!Number.isFinite(s)) return "0";

    if (s >= 900000000) {
      return distance !== null ? `+M${distance}` : "+WIN";
    }
    if (s <= -900000000) {
      return distance !== null ? `-M${distance}` : "-WIN";
    }

    const safe = Math.max(-999999, Math.min(999999, Math.trunc(s)));
    return String(safe);
  }
  async updatePrediction() {
    if (!this.el.predictionText) return;

    if (!this.board) {
      this.setPredictionText("Prédiction : ...");
      return;
    }

    if (this.gameOver) {
      if (this.winner === this.RED) {
        this.setPredictionText("Partie terminée : Rouge a gagné");
      } else if (this.winner === this.YELLOW) {
        this.setPredictionText("Partie terminée : Jaune a gagné");
      } else {
        this.setPredictionText("Partie terminée : match nul");
      }
      return;
    }

    const depth = this.clampInt(this.el.depth?.value, 1, 8, 6);

    const cacheKey = JSON.stringify({
      board: this.board,
      player: this.current,
      depth,
    });

    if (cacheKey === this._predictionCacheKey) {
      return;
    }
    this._predictionCacheKey = cacheKey;

    if (this._predictionTimer) {
      clearTimeout(this._predictionTimer);
      this._predictionTimer = null;
    }

    if (this._predictionAbortController) {
      try {
        this._predictionAbortController.abort();
      } catch { }
    }

    const reqId = ++this.predictionReqId;

    this._predictionTimer = setTimeout(async () => {
      this.setPredictionText("Prédiction : analyse...");

      const controller = new AbortController();
      this._predictionAbortController = controller;

      const timeoutId = setTimeout(() => {
        try {
          controller.abort();
        } catch { }
      }, 2200);

      try {
        let data = null;

        try {
          data = await this.requestPrediction(
            {
              board: this.board,
              player: this.current,
              depth,
            },
            controller.signal
          );
        } catch {
          data = this.localPredictPosition(this.board, this.current, depth, 1200);
        }

        clearTimeout(timeoutId);

        if (reqId !== this.predictionReqId) return;
        if (!data || typeof data !== "object") {
          this.setPredictionText("Prédiction : indisponible");
          return;
        }

        this.setPredictionText(this.formatPredictionResult(data));
      } catch (e) {
        clearTimeout(timeoutId);
        if (reqId !== this.predictionReqId) return;

        try {
          const localData = this.localPredictPosition(this.board, this.current, depth, 1000);
          this.setPredictionText(this.formatPredictionResult(localData));
        } catch {
          this.setPredictionText("Prédiction : indisponible");
        }
      } finally {
        if (this._predictionAbortController === controller) {
          this._predictionAbortController = null;
        }
      }
    }, 120);
  }
  resetPredictionDisplay() {
    if (this._predictionTimer) {
      clearTimeout(this._predictionTimer);
      this._predictionTimer = null;
    }

    if (this._predictionAbortController) {
      try {
        this._predictionAbortController.abort();
      } catch { }
      this._predictionAbortController = null;
    }

    this.predictionReqId++;
    this._predictionCacheKey = "";
    this._lastPredictionText = "Prédiction : ...";
    this.setPredictionText("Prédiction : ...");
  }
  async onlineRematchFlow() {
    if (!this.online.enabled || !this.online.code) return;
    if (this.online.rematchInFlight) return;

    this.online.rematchInFlight = true;
    if (this.el.onlineRematch) this.el.onlineRematch.disabled = true;

    try {
      await this.apiFetch(`/online/${this.online.code}/rematch`, {
        method: "POST",
        body: JSON.stringify({ player_secret: this.online.secret }),
      });

      this.online.autoSavedFinishedGame = false;
      this.resetLocalBoardOnly();
      await new Promise((r) => setTimeout(r, 250));
      const st = await this.apiFetch(`/online/${this.online.code}/state`, { method: "GET" });
      this.applyOnlineState(st);
    } catch (e) {
      alert("❌ Revanche: " + (e?.message || e) + "\n\nSi cette route n'existe pas encore dans le backend, ajoute /api/online/{code}/rematch.");
    } finally {
      this.online.rematchInFlight = false;
      if (this.el.onlineRematch) this.el.onlineRematch.disabled = false;
    }
  }

  resetLocalBoardOnly() {
    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;

    this.board = this.createBoard();
    this.moves = [];
    this.viewIndex = 0;
    this.current = this.startingColor;
    this.gameOver = false;
    this.winner = null;
    this.winningCells = [];

    this.resetPredictionDisplay();

    this.rebuildColumnWidgets();
    this.afterStateChange(false);
    this.resizeCanvasReliable();
  }

  getOnlinePlayerNameByToken(token) {
    const p = Array.isArray(this.online.players)
      ? this.online.players.find((x) => x?.token === token)
      : null;

    if (p?.player_name?.trim()) return p.player_name.trim();

    if (token === this.RED) {
      return localStorage.getItem(this.LS_NAME_R) || "Joueur Rouge";
    }
    if (token === this.YELLOW) {
      return localStorage.getItem(this.LS_NAME_Y) || "Joueur Jaune";
    }
    return "Spectateur";
  }

  syncDisplayedPlayerNamesFromOnline() {
    if (!this.online.enabled) return;

    const redName = this.getOnlinePlayerNameByToken(this.RED);
    const yellowName = this.getOnlinePlayerNameByToken(this.YELLOW);

    if (this.el.nameR) this.el.nameR.textContent = redName;
    if (this.el.nameY) this.el.nameY.textContent = yellowName;
  }

  computeWinningCellsFromMoves() {
    const b = this.createBoard();
    let lastPos = null;
    let lastToken = null;

    for (let i = 0; i < this.moves.length; i++) {
      const col = this.moves[i];
      const token = this.tokenForMoveIndex(i);
      const pos = this.dropToken(b, col, token);
      if (!pos) break;
      lastPos = pos;
      lastToken = token;
    }

    if (!lastPos || !lastToken) return [];
    return this.checkWinCells(b, lastPos[0], lastPos[1], lastToken);
  }

  async autoSaveFinishedOnlineGame() {
    if (!this.online.enabled) return;
    if (!this.gameOver) return;
    if (this.online.savingFinishedGame) return;
    if (this.online.autoSavedFinishedGame) return;

    this.online.savingFinishedGame = true;

    try {
      const saveName = `online_${this.online.code || "game"}_${new Date().toISOString().replace(/[:.]/g, "-")}`;
      const payload = this.buildGamePayloadForDB(saveName);

      payload.status = "completed";
      payload.game_mode = 2;
      payload.ai_mode = "online";
      payload.ai_depth = 1;
      payload.player_red = this.getOnlinePlayerNameByToken(this.RED);
      payload.player_yellow = this.getOnlinePlayerNameByToken(this.YELLOW);

      if (this.winner === this.RED) payload.winner = "R";
      else if (this.winner === this.YELLOW) payload.winner = "Y";
      else payload.winner = "D";

      await this.apiFetch("/games", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      this.online.autoSavedFinishedGame = true;
    } catch (e) {
      console.warn("Auto-save online failed:", e);
    } finally {
      this.online.savingFinishedGame = false;
    }
  }

  applyOnlineState(st) {
    const movesArr = Array.isArray(st.moves) ? st.moves : [];
    const moveCols = movesArr
      .map((m) => Number(m.col))
      .filter((x) => Number.isInteger(x));

    const rows = Number(st.rows);
    const colsN = Number(st.cols);

    if (Number.isInteger(rows) && Number.isInteger(colsN)) {
      if (rows !== this.rows || colsN !== this.cols) {
        this.rows = rows;
        this.cols = colsN;
        this.rebuildColumnWidgets();
      }
    }

    this.startingColor = st.starting_color === this.YELLOW ? this.YELLOW : this.RED;
    this.moves = moveCols;
    this.viewIndex = this.moves.length;
    this.board = this.reconstructBoard(this.viewIndex);
    this.current = st.current_turn === this.YELLOW ? this.YELLOW : this.RED;

    this.online.players = Array.isArray(st.players) ? st.players : [];
    this.updateSpectatorsInfo(
      this.online.players.filter((p) => p?.token === "S").length
    );
    this.syncDisplayedPlayerNamesFromOnline();

    this.gameOver = st.status === "finished" || st.winner !== null;

    if (st.winner === "R") this.winner = this.RED;
    else if (st.winner === "Y") this.winner = this.YELLOW;
    else this.winner = null;

    if (st.status === "finished") {
      this.winningCells = this.winner ? this.computeWinningCellsFromMoves() : [];
      if (!this.online.autoSavedFinishedGame) {
        this.autoSaveFinishedOnlineGame();
      }
    } else {
      this.winningCells = [];
      this.online.autoSavedFinishedGame = false;
    }

    const currentSpectators = this.online.players.filter((p) => p?.token === "S").length;
    const t = this.online.token || "?";
    this.setOnlineBadge(`Online #${this.online.code} (${t}) • 👁 ${currentSpectators}`);

    this.drawBoard();
    this.updateReplayUI();
    this.updateStatus();
    this.updateSidePanel();
    this.setButtonsState(true);
    this.updatePrediction();
    this.online.lastWinner = st.winner;
    this.online.lastStatus = st.status;
  }

  // ===== NOMS
  getNameForToken(token) {
    if (this.online.enabled) {
      return this.getOnlinePlayerNameByToken(token);
    }
    if (token === this.RED) return localStorage.getItem(this.LS_NAME_R) || "Joueur Rouge";
    return localStorage.getItem(this.LS_NAME_Y) || "Joueur Jaune";
  }

  setNameForToken(token, name) {
    if (token === this.RED) localStorage.setItem(this.LS_NAME_R, name);
    else localStorage.setItem(this.LS_NAME_Y, name);
  }

  ensurePlayerNames() {
    let r = localStorage.getItem(this.LS_NAME_R) || "";
    let y = localStorage.getItem(this.LS_NAME_Y) || "";

    if (!r) {
      r = prompt("Nom du joueur Rouge :", "Joueur Rouge");
      if (r === null) r = "Joueur Rouge";
      r = String(r).trim() || "Joueur Rouge";
      localStorage.setItem(this.LS_NAME_R, r);
    }

    if (!y) {
      y = prompt("Nom du joueur Jaune :", "Joueur Jaune");
      if (y === null) y = "Joueur Jaune";
      y = String(y).trim() || "Joueur Jaune";
      localStorage.setItem(this.LS_NAME_Y, y);
    }

    if (this.el.nameR) this.el.nameR.textContent = r;
    if (this.el.nameY) this.el.nameY.textContent = y;
  }

  changePlayerName(token) {
    if (this.online.enabled) {
      alert("En mode online, le pseudo affiché vient des joueurs connectés.");
      return;
    }

    const current = this.getNameForToken(token);
    let name = prompt(`Nouveau nom (${token === this.RED ? "Rouge" : "Jaune"}) :`, current);
    if (name === null) return;
    name = String(name).trim();
    if (!name) return;

    this.setNameForToken(token, name);
    if (token === this.RED && this.el.nameR) this.el.nameR.textContent = name;
    else if (this.el.nameY) this.el.nameY.textContent = name;

    this.pushHistory({
      player: name,
      type: "rename",
      game: this.gameIndex,
      move: this.moves.length,
      col: "-",
      when: Date.now(),
    });
    this.renderHistory();
    this.updateStatus();
    this.updateSidePanel();
  }

  // ===== HISTORY
  loadHistory() {
    try {
      const raw = localStorage.getItem(this.LS_HISTORY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  }

  saveHistory(arr) {
    localStorage.setItem(this.LS_HISTORY, JSON.stringify(arr.slice(0, this.HISTORY_LIMIT)));
  }

  clearHistory() {
    localStorage.removeItem(this.LS_HISTORY);
    this.renderHistory();
  }

  fmtWhen(ts) {
    const d = new Date(ts);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  pushHistory({ player, type, game, move, col, when }) {
    const arr = this.loadHistory();
    arr.unshift({ player, type, game, move, col, when });
    this.saveHistory(arr);
  }

  renderHistory() {
    if (!this.el.historyBody) return;

    const arr = this.loadHistory();
    const niceType = (t) => {
      if (t === "move") return "coup";
      if (t === "rename") return "nom";
      if (t === "save") return "sauvegarde";
      if (t === "load") return "chargement";
      if (t === "new") return "nouvelle";
      return t || "-";
    };

    this.el.historyBody.innerHTML = arr.length
      ? arr
        .map(
          (x) => `
        <tr>
          <td>${this.escapeHtml(x.player)}</td>
          <td>${this.escapeHtml(niceType(x.type))}</td>
          <td>#${this.escapeHtml(String(x.game))}</td>
          <td>${this.escapeHtml(String(x.move))}</td>
          <td>${this.escapeHtml(String(x.col))}</td>
          <td>${this.escapeHtml(this.fmtWhen(x.when))}</td>
        </tr>
      `
        )
        .join("")
      : `<tr><td colspan="6" class="muted">Aucun historique.</td></tr>`;
  }

  // ===== SAVE NAME
  ensureDefaultSaveName() {
    if (!this.el.saveName) return;
    const pad = (n) => String(n).padStart(2, "0");
    const d = new Date();
    const def = `partie_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
    if (!this.el.saveName.value.trim()) this.el.saveName.value = def;
  }

  getSaveNameOrDefault() {
    const raw = (this.el.saveName?.value || "").trim();
    if (raw) return raw;
    this.ensureDefaultSaveName();
    return (this.el.saveName?.value || "partie").trim() || "partie";
  }

  // ===== UI
  bindUI() {
    this.el.newGame?.addEventListener("click", () => {
      if (this.online.enabled) {
        this.onlineRematchFlow();
      } else {
        this.resetGame(true);
      }
    });

    this.el.startColor?.addEventListener("change", () => {
      if (this.online.enabled) return;

      const v = this.el.startColor.value === this.YELLOW ? this.YELLOW : this.RED;
      localStorage.setItem(this.LS_STARTING_COLOR, v);
      this.startingColor = v;

      this.resetGame(true);
    });

    this.el.stop?.addEventListener("click", () => this.stopGame());

    this.el.aiMode?.addEventListener("change", () => {
      if (this.online.enabled) return;

      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;

      this.updateStatus();
      this.renderAiScores();
      this.setButtonsState(true);

      const humanTurn = this.isHumanTurn(this.current);
      if (!this.gameOver && this.viewIndex === this.moves.length && !humanTurn) {
        this.schedule(() => this.robotStep(), 140);
      }
    });

    this.el.depth?.addEventListener("change", () => {
      this.renderAiScores();
      this.updatePrediction();
    });

    this.el.noDigits?.addEventListener("change", () => this.applyNoDigitsMode());

    this.el.changeR?.addEventListener("click", () => this.changePlayerName(this.RED));
    this.el.changeY?.addEventListener("click", () => this.changePlayerName(this.YELLOW));

    this.el.controlR?.addEventListener("change", () => {
      if (this.online.enabled) return;

      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;

      this.updateStatus();
      this.renderAiScores();
      this.updateReplayUI();
      this.setButtonsState(true);

      const humanTurn = this.isHumanTurn(this.current);
      if (!this.gameOver && this.viewIndex === this.moves.length && !humanTurn) {
        this.schedule(() => this.robotStep(), 140);
      }
    });

    this.el.controlY?.addEventListener("change", () => {
      if (this.online.enabled) return;

      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;

      this.updateStatus();
      this.renderAiScores();
      this.updateReplayUI();
      this.setButtonsState(true);

      const humanTurn = this.isHumanTurn(this.current);
      if (!this.gameOver && this.viewIndex === this.moves.length && !humanTurn) {
        this.schedule(() => this.robotStep(), 140);
      }
    });

    this.el.paintToggle?.addEventListener("click", () => {
      if (this.online.enabled) {
        alert("Mode peinture indisponible en ligne.");
        return;
      }

      const wasPaintMode = this.paintMode;
      this.paintMode = !this.paintMode;

      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;
      this._aiActionToken++;

      this.updatePaintUI();

      if (wasPaintMode && !this.paintMode) {
        this.resumeGameFromPaint();
        return;
      }

      this.drawBoard();
      this.updateStatus();
      this.setButtonsState(true);
    });

    this.el.paintColor?.addEventListener("change", () => {
      this.paintColor = this.el.paintColor.value || this.EMPTY;
    });

    this.el.paintClear?.addEventListener("click", () => {
      if (this.online.enabled) {
        alert("Effacement indisponible en ligne.");
        return;
      }
      this.clearPaintBoard();
    });

    this.el.paintResume?.addEventListener("click", () => {
      if (this.online.enabled) return;
      this.resumeGameFromPaint();
    });

    this.el.saveMenu?.addEventListener("change", async () => {
      const v = this.el.saveMenu.value;
      this.el.saveMenu.value = "";
      if (!v) return;
      if (v === "json") this.saveJsonFlow();
      if (v === "db") await this.saveDbFlow();
    });

    this.el.loadMenu?.addEventListener("change", async () => {
      const v = this.el.loadMenu.value;
      this.el.loadMenu.value = "";
      if (!v) return;
      if (v === "json") this.el.loadJson?.click();
      if (v === "db") await this.loadDbFlow();
    });

    this.el.loadJson?.addEventListener("change", (e) => this.loadJsonFlow(e));
    this.el.clearHistoryBtn?.addEventListener("click", () => this.clearHistory());

    this.el.moveSlider?.addEventListener("input", () => {
      this.navigateTo(parseInt(this.el.moveSlider.value, 10));
    });
    this.el.firstMove?.addEventListener("click", () => this.navigateTo(0));
    this.el.prevMove?.addEventListener("click", () => this.navigateTo(this.viewIndex - 1));
    this.el.nextMove?.addEventListener("click", () => this.navigateTo(this.viewIndex + 1));
    this.el.lastMove?.addEventListener("click", () => this.navigateTo(this.moves.length));

    this.el.canvas?.addEventListener("mousemove", (ev) => this.onCanvasMove(ev));
    this.el.canvas?.addEventListener("mouseleave", () => {
      this.setHoverColumn(null);
      this.drawBoard();
    });
    this.el.canvas?.addEventListener("click", (ev) => this.onCanvasClick(ev));

    if (this.el.onlineCreate) {
      this.el.onlineCreate.addEventListener("click", async () => {
        try {
          await this.onlineCreateFlow();
        } catch (e) {
          alert("❌ Online create: " + (e?.message || e));
        }
      });
    }

    if (this.el.onlineJoin) {
      this.el.onlineJoin.addEventListener("click", async () => {
        if (this.online.enabled && this.online.code === (this.el.onlineCode?.value || "").trim().toUpperCase()) {
          return;
        }
        try {
          await this.onlineJoinFlow(this.el.onlineCode?.value || "");
        } catch (e) {
          alert("❌ Online join: " + (e?.message || e));
        }
      });
    }

    if (this.el.onlineLeave) {
      this.el.onlineLeave.addEventListener("click", () => this.onlineLeaveFlow());
    }

    if (this.el.onlineCopyLink) {
      this.el.onlineCopyLink.addEventListener("click", async () => {
        const code = this.online.code || (this.el.onlineCode?.value || "").trim().toUpperCase();
        if (!code) return alert("Pas de code.");
        const url = `${location.origin}/?join=${code}`;
        try {
          await navigator.clipboard.writeText(url);
          alert("✅ Lien copié:\n" + url);
        } catch {
          prompt("Copie le lien :", url);
        }
      });
    }

    if (this.el.onlineRematch) {
      this.el.onlineRematch.addEventListener("click", async () => {
        await this.onlineRematchFlow();
      });
    }
  }

  // ===== COLUMN UI
  rebuildColumnWidgets() {
    if (!this.el.colLabels || !this.el.colButtons || !this.el.colScores) return;

    this.el.colLabels.innerHTML = "";
    this.el.colButtons.innerHTML = "";
    this.el.colScores.innerHTML = "";
    this.colBtnEls = [];
    this.scoreEls = [];

    for (let c = 0; c < this.cols; c++) {
      const lab = document.createElement("div");
      lab.className = "lab";
      lab.textContent = String(c + 1);
      this.el.colLabels.appendChild(lab);

      const b = document.createElement("button");
      b.type = "button";
      b.textContent = String(c + 1);
      b.setAttribute("aria-label", `Colonne ${c + 1}`);

      b.addEventListener("click", () => this.onClick(c));
      b.addEventListener("mouseenter", () => this.setHoverColumn(c));
      b.addEventListener("mouseleave", () => this.setHoverColumn(null));
      b.addEventListener("focus", () => this.setHoverColumn(c));
      b.addEventListener("blur", () => this.setHoverColumn(null));

      this.el.colButtons.appendChild(b);
      this.colBtnEls.push(b);
    }

    for (let c = 0; c < this.cols; c++) {
      const s = document.createElement("div");
      s.className = "score";
      s.textContent = "";
      this.el.colScores.appendChild(s);
      this.scoreEls.push(s);
    }

    this.applyNoDigitsMode();
  }

  applyNoDigitsMode() {
    const on = !!this.el.noDigits?.checked;
    for (let c = 0; c < (this.colBtnEls?.length || 0); c++) {
      const b = this.colBtnEls[c];
      b.classList.toggle("noDigits", on);
      b.textContent = String(c + 1);
    }
  }

  setHoverColumn(col) {
    this.hoverCol = col === null || col === undefined ? null : col;

    for (let i = 0; i < (this.colBtnEls?.length || 0); i++) {
      this.colBtnEls[i].classList.toggle("isHover", this.hoverCol === i);
    }

    if (this.el.colHoverInfo) {
      this.el.colHoverInfo.textContent = this.hoverCol === null ? "—" : String(this.hoverCol + 1);
    }
  }

  setButtonsState(enabled) {
    if (!this.colBtnEls) return;

    if (this.online.enabled) {
      const can =
        enabled &&
        !this.gameOver &&
        !this.robotThinking &&
        !this.aiLock &&
        !this.online.moveInFlight &&
        this.viewIndex === this.moves.length &&
        this.online.token !== "S" &&
        this.online.token &&
        this.current === this.online.token;

      for (const b of this.colBtnEls) b.disabled = !can;
      return;
    }

    const can =
      enabled &&
      this.isHumanTurn(this.current) &&
      !this.robotThinking &&
      !this.aiLock &&
      !this.gameOver;

    for (const b of this.colBtnEls) b.disabled = !can;
  }

  // ===== REPLAY
  updateReplayUI() {
    if (!this.el.moveSlider || !this.el.moveLabel) return;

    const total = this.moves.length;
    this.el.moveSlider.max = String(total);
    this.el.moveSlider.value = String(this.viewIndex);
    this.el.moveLabel.textContent = `Coup ${this.viewIndex}/${total}`;

    if (this.el.firstMove) this.el.firstMove.disabled = this.viewIndex <= 0 || this.online.enabled;
    if (this.el.prevMove) this.el.prevMove.disabled = this.viewIndex <= 0 || this.online.enabled;
    if (this.el.nextMove) this.el.nextMove.disabled = this.viewIndex >= total || this.online.enabled;
    if (this.el.lastMove) this.el.lastMove.disabled = this.viewIndex >= total || this.online.enabled;
    if (this.el.moveSlider) this.el.moveSlider.disabled = this.online.enabled;
  }

  reconstructBoard(upToIndex) {
    const b = this.createBoard();
    for (let i = 0; i < Math.min(upToIndex, this.moves.length); i++) {
      const col = this.moves[i];
      const token = this.tokenForMoveIndex(i);
      this.dropToken(b, col, token);
    }
    return b;
  }

  navigateTo(index) {
    if (this.online.enabled) {
      alert("Online: replay désactivé (synchro en direct).");
      return;
    }

    const total = this.moves.length;
    index = Math.max(0, Math.min(total, index));
    this.viewIndex = index;

    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;

    this.board = this.reconstructBoard(this.viewIndex);
    this.current = this.inferCurrentPlayerFromBoard();

    this.winningCells = [];
    this.winner = null;
    this.gameOver = false;

    this.drawBoard();
    this.updateStatus();
    this.updateReplayUI();
    this.updatePrediction();
  }

  // ===== GAME CORE
  createBoard() {
    return Array.from({ length: this.rows }, () =>
      Array.from({ length: this.cols }, () => this.EMPTY)
    );
  }

  validColumns(board = this.board) {
    const out = [];
    for (let c = 0; c < this.cols; c++) if (board[0][c] === this.EMPTY) out.push(c);
    return out;
  }

  dropToken(board, col, token) {
    if (col < 0 || col >= this.cols) return null;
    if (board[0][col] !== this.EMPTY) return null;
    for (let r = this.rows - 1; r >= 0; r--) {
      if (board[r][col] === this.EMPTY) {
        board[r][col] = token;
        return [r, col];
      }
    }
    return null;
  }

  isDraw(board = this.board) {
    for (let c = 0; c < this.cols; c++) if (board[0][c] === this.EMPTY) return false;
    return true;
  }

  checkWinCells(board, lastRow, lastCol, token) {
    const dirs = [
      [0, 1],
      [1, 0],
      [1, 1],
      [1, -1],
    ];

    for (const [dr, dc] of dirs) {
      const cells = [[lastRow, lastCol]];

      let r = lastRow + dr;
      let c = lastCol + dc;
      while (
        0 <= r &&
        r < this.rows &&
        0 <= c &&
        c < this.cols &&
        board[r][c] === token
      ) {
        cells.push([r, c]);
        r += dr;
        c += dc;
      }

      r = lastRow - dr;
      c = lastCol - dc;
      while (
        0 <= r &&
        r < this.rows &&
        0 <= c &&
        c < this.cols &&
        board[r][c] === token
      ) {
        cells.unshift([r, c]);
        r -= dr;
        c -= dc;
      }

      if (cells.length >= this.CONNECT_N) return cells.slice(0, this.CONNECT_N);
    }

    return [];
  }

  // ===== CANVAS INPUT
  canvasToBoardCell(clientX, clientY) {
    if (!this.lastDrawGeom) return null;

    const wrapRect = this.el.canvasWrap.getBoundingClientRect();
    const x = clientX - wrapRect.left;
    const y = clientY - wrapRect.top;

    const { x0, y0, cell, boardW, boardH } = this.lastDrawGeom;
    if (x < x0 || x > x0 + boardW || y < y0 || y > y0 + boardH) return null;

    const col = Math.floor((x - x0) / cell);
    const row = Math.floor((y - y0) / cell);

    if (col < 0 || col >= this.cols || row < 0 || row >= this.rows) return null;

    return { row, col };
  }

  canvasToBoardCol(clientX, clientY) {
    const cell = this.canvasToBoardCell(clientX, clientY);
    return cell ? cell.col : null;
  }

  onCanvasMove(ev) {
    const col = this.canvasToBoardCol(ev.clientX, ev.clientY);
    this.setHoverColumn(col);
    this.drawBoard();
  }

  onCanvasClick(ev) {
    const cell = this.canvasToBoardCell(ev.clientX, ev.clientY);
    if (!cell) return;

    if (this.paintMode) {
      this.applyPaintAt(cell.row, cell.col);
      return;
    }

    this.onClick(cell.col);
  }

  // ===== RESPONSIVE CANVAS
  setupResponsiveCanvas() {
    try {
      this._resizeObserver?.disconnect?.();
    } catch { }

    const wrap = this.el.canvasWrap;
    if (!wrap) return;

    const onResize = () => this.resizeCanvasReliable();

    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver = new ResizeObserver(() => onResize());
      this._resizeObserver.observe(wrap);
    }

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("orientationchange", onResize, { passive: true });

    requestAnimationFrame(() => this.resizeCanvasReliable());
  }

  resizeCanvasReliable(retry = 0) {
    const wrap = this.el.canvasWrap;
    const canvas = this.el.canvas;
    if (!wrap || !canvas || !this.ctx) return;

    const rect = wrap.getBoundingClientRect();
    const cssW = Math.floor(rect.width);
    const cssH = Math.floor(rect.height);

    if ((cssW === 0 || cssH === 0) && retry < 30) {
      requestAnimationFrame(() => this.resizeCanvasReliable(retry + 1));
      return;
    }

    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const bufW = Math.max(1, Math.floor(cssW * dpr));
    const bufH = Math.max(1, Math.floor(cssH * dpr));

    if (canvas.width !== bufW) canvas.width = bufW;
    if (canvas.height !== bufH) canvas.height = bufH;

    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.drawBoard();
  }

  cellColor(v) {
    if (v === this.RED) return this.COLOR_RED;
    if (v === this.YELLOW) return this.COLOR_YELLOW;
    return this.COLOR_HOLE;
  }

  drawBoard() {
    if (!this.board || !this.ctx || !this.el.canvasWrap) return;

    const ctx = this.ctx;
    const rect = this.el.canvasWrap.getBoundingClientRect();
    const W = Math.max(320, rect.width);
    const H = Math.max(320, rect.height);

    ctx.clearRect(0, 0, W, H);

    const cell = Math.min(W / this.cols, H / this.rows);
    const pad = cell * 0.1;

    const boardW = cell * this.cols;
    const boardH = cell * this.rows;
    const x0 = (W - boardW) / 2;
    const y0 = (H - boardH) / 2;

    this.lastDrawGeom = { x0, y0, cell, boardW, boardH };

    if (this.hoverCol !== null) {
      ctx.fillStyle = this.COLOR_HOVER_COL;
      ctx.fillRect(x0 + this.hoverCol * cell, y0, cell, boardH);
    }

    ctx.fillStyle = this.COLOR_BG;
    ctx.fillRect(x0, y0, boardW, boardH);

    const winSet = new Set((this.winningCells || []).map(([r, c]) => `${r},${c}`));

    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const cx0 = x0 + c * cell + pad;
        const cy0 = y0 + r * cell + pad;
        const cx1 = x0 + (c + 1) * cell - pad;
        const cy1 = y0 + (r + 1) * cell - pad;

        ctx.beginPath();
        ctx.ellipse(
          (cx0 + cx1) / 2,
          (cy0 + cy1) / 2,
          (cx1 - cx0) / 2,
          (cy1 - cy0) / 2,
          0,
          0,
          Math.PI * 2
        );

        const v = this.board[r][c];
        if (v === this.RED) {
          ctx.shadowColor = "rgba(229,48,48,0.65)";
          ctx.shadowBlur = 14;
        } else if (v === this.YELLOW) {
          ctx.shadowColor = "rgba(245,158,11,0.55)";
          ctx.shadowBlur = 12;
        }

        if (winSet.has(`${r},${c}`)) {
          ctx.fillStyle = this.COLOR_WIN;
        } else {
          ctx.fillStyle = this.cellColor(v);
        }

        ctx.fill();
        ctx.shadowBlur = 0;

        if (winSet.has(`${r},${c}`)) {
          ctx.lineWidth = 4;
          ctx.strokeStyle = "#ffffff";
          ctx.shadowColor = this.COLOR_WIN;
          ctx.shadowBlur = 18;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
      }
    }
  }

  // ===== STATUS + INFOS
  updateSidePanel() {
    if (this.el.rowsVal) this.el.rowsVal.textContent = String(this.rows);
    if (this.el.colsVal) this.el.colsVal.textContent = String(this.cols);
    if (this.el.startVal) {
      this.el.startVal.textContent =
        this.startingColor === this.RED
          ? `Rouge (${this.getNameForToken(this.RED)})`
          : `Jaune (${this.getNameForToken(this.YELLOW)})`;
    }
    if (this.el.gameIndexVal) this.el.gameIndexVal.textContent = String(this.gameIndex);
    if (this.el.movesVal) this.el.movesVal.textContent = String(this.moves.length);
    if (this.el.viewVal) this.el.viewVal.textContent = String(this.viewIndex);
  }

  updateStatus() {
    if (!this.el.status) return;

    let msg = "";

    if (this.online.enabled) {
      const code = this.online.code || "—";
      const tok = this.online.token || "?";
      msg += `🌐 Online #${code} (${tok}) • 👁 ${this.online.spectators} — `;
    }

    if (this.gameOver) {
      if (this.winner === this.RED) {
        msg += `Partie #${this.gameIndex} — 🎉 Gagnant : Rouge (${this.getNameForToken(this.RED)})`;
      } else if (this.winner === this.YELLOW) {
        msg += `Partie #${this.gameIndex} — 🎉 Gagnant : Jaune (${this.getNameForToken(this.YELLOW)})`;
      } else {
        msg += `Partie #${this.gameIndex} — 🤝 Match nul`;
      }

      if (this.online.enabled) {
        msg += ` — clique sur "Nouvelle partie" pour relancer la room`;
      }
    } else {
      const who = this.current === this.RED ? "Rouge" : "Jaune";
      msg += `Partie #${this.gameIndex} — À jouer : ${who} (${this.getNameForToken(this.current)})`;
    }

    if (this.paintMode && !this.online.enabled) {
      const nextPlayer = this.current === this.RED ? "Rouge" : "Jaune";
      msg += ` — 🎨 Mode peinture actif • prochain joueur estimé : ${nextPlayer}`;
    }
    if (this.robotThinking) msg += " (IA réfléchit...)";

    this.el.status.textContent = msg;
    this.updateSidePanel();
  }

  setPredictionText(text) {
    if (!this.el.predictionText) return;
    this._lastPredictionText = String(text || "");
    this.el.predictionText.textContent = this._lastPredictionText;
  }
  // ===== AI SCORES
  setScoresBlank() {
    for (const s of this.scoreEls || []) s.textContent = "";
  }

  scorePosition(grid, player) {
    const opp = this.other(player);

    const scoreLine = (cells) => {
      let p = 0, o = 0, e = 0;
      for (const v of cells) {
        if (v === player) p++;
        else if (v === opp) o++;
        else e++;
      }
      if (p > 0 && o > 0) return 0;
      if (p === 4) return 1000000;
      if (o === 4) return -1000000;
      if (p === 3 && e === 1) return 200;
      if (p === 2 && e === 2) return 30;
      if (o === 3 && e === 1) return -220;
      if (o === 2 && e === 2) return -35;
      return 0;
    };

    let score = 0;
    const center = Math.floor(this.cols / 2);
    let centerCount = 0;
    for (let r = 0; r < this.rows; r++) if (grid[r][center] === player) centerCount++;
    score += centerCount * 10;

    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c <= this.cols - 4; c++) {
        score += scoreLine([grid[r][c], grid[r][c + 1], grid[r][c + 2], grid[r][c + 3]]);
      }
    }
    for (let c = 0; c < this.cols; c++) {
      for (let r = 0; r <= this.rows - 4; r++) {
        score += scoreLine([grid[r][c], grid[r + 1][c], grid[r + 2][c], grid[r + 3][c]]);
      }
    }
    for (let r = 3; r < this.rows; r++) {
      for (let c = 0; c <= this.cols - 4; c++) {
        score += scoreLine([grid[r][c], grid[r - 1][c + 1], grid[r - 2][c + 2], grid[r - 3][c + 3]]);
      }
    }
    for (let r = 0; r <= this.rows - 4; r++) {
      for (let c = 0; c <= this.cols - 4; c++) {
        score += scoreLine([grid[r][c], grid[r + 1][c + 1], grid[r + 2][c + 2], grid[r + 3][c + 3]]);
      }
    }

    return score;
  }

  terminalState(grid) {
    const checkToken = (t) => {
      for (let r = 0; r < this.rows; r++) {
        for (let c = 0; c <= this.cols - 4; c++) {
          if (grid[r][c] === t && grid[r][c + 1] === t && grid[r][c + 2] === t && grid[r][c + 3] === t) return true;
        }
      }
      for (let c = 0; c < this.cols; c++) {
        for (let r = 0; r <= this.rows - 4; r++) {
          if (grid[r][c] === t && grid[r + 1][c] === t && grid[r + 2][c] === t && grid[r + 3][c] === t) return true;
        }
      }
      for (let r = 0; r <= this.rows - 4; r++) {
        for (let c = 0; c <= this.cols - 4; c++) {
          if (grid[r][c] === t && grid[r + 1][c + 1] === t && grid[r + 2][c + 2] === t && grid[r + 3][c + 3] === t) return true;
        }
      }
      for (let r = 3; r < this.rows; r++) {
        for (let c = 0; c <= this.cols - 4; c++) {
          if (grid[r][c] === t && grid[r - 1][c + 1] === t && grid[r - 2][c + 2] === t && grid[r - 3][c + 3] === t) return true;
        }
      }
      return false;
    };

    if (checkToken(this.RED)) return { over: true, winner: this.RED };
    if (checkToken(this.YELLOW)) return { over: true, winner: this.YELLOW };

    for (let c = 0; c < this.cols; c++) if (grid[0][c] === this.EMPTY) return { over: false };
    return { over: true, winner: null };
  }

  getLocalZobristTable(rows, cols) {
    const key = `${rows}x${cols}`;
    if (this._localZobristTables.has(key)) return this._localZobristTables.get(key);

    let seed = 0x9e3779b97f4a7c15n;
    const nextRand = () => {
      seed ^= seed << 13n;
      seed ^= seed >> 7n;
      seed ^= seed << 17n;
      return seed & ((1n << 64n) - 1n);
    };

    const table = {
      R: Array.from({ length: rows }, () => Array.from({ length: cols }, () => nextRand())),
      Y: Array.from({ length: rows }, () => Array.from({ length: cols }, () => nextRand())),
      turn: { R: nextRand(), Y: nextRand() },
    };
    this._localZobristTables.set(key, table);
    return table;
  }

  localBoardHash(grid, currentPlayer) {
    const table = this.getLocalZobristTable(grid.length, grid[0].length);
    let hash = table.turn[currentPlayer];

    for (let r = 0; r < grid.length; r++) {
      for (let c = 0; c < grid[0].length; c++) {
        const token = grid[r][c];
        if (token === this.RED || token === this.YELLOW) {
          hash ^= table[token][r][c];
        }
      }
    }

    return hash.toString();
  }

  findImmediateWinningMove(grid, player) {
    for (const col of this.validColumns(grid)) {
      const next = this.copyGrid(grid);
      const pos = this.dropToken(next, col, player);
      if (pos && this.checkWinCells(next, pos[0], pos[1], player).length) return col;
    }
    return null;
  }

  countImmediateWins(grid, player) {
    let count = 0;
    for (const col of this.validColumns(grid)) {
      const next = this.copyGrid(grid);
      const pos = this.dropToken(next, col, player);
      if (pos && this.checkWinCells(next, pos[0], pos[1], player).length) count++;
    }
    return count;
  }

  givesOpponentImmediateWin(grid, player, col) {
    const next = this.copyGrid(grid);
    const pos = this.dropToken(next, col, player);
    if (!pos) return true;
    return this.findImmediateWinningMove(next, this.other(player)) !== null;
  }

  orderLocalMoves(grid, moves, currentPlayer, rootPlayer, ply = 0, ttMove = null) {
    const opponent = this.other(currentPlayer);
    const center = Math.floor(this.cols / 2);
    const immediateBlock = this.findImmediateWinningMove(grid, opponent);

    return moves
      .map((col) => {
        let score = (this.cols - Math.abs(col - center)) * 20;
        if (ttMove === col) score += 2_000_000;

        const killers = this._localKillerMoves[ply] || [];
        if (killers[0] === col) score += 500_000;
        else if (killers[1] === col) score += 300_000;

        score += this._localHistory.get(`${currentPlayer}:${col}`) || 0;

        const next = this.copyGrid(grid);
        const pos = this.dropToken(next, col, currentPlayer);
        if (!pos) return { col, score: -Infinity };

        if (this.checkWinCells(next, pos[0], pos[1], currentPlayer).length) score += 10_000_000;
        if (immediateBlock === col) score += 8_000_000;
        if (this.givesOpponentImmediateWin(grid, currentPlayer, col)) score -= 2_000_000;

        const myThreats = this.countImmediateWins(next, currentPlayer);
        const oppThreats = this.countImmediateWins(next, opponent);
        score += myThreats * 120_000;
        score -= oppThreats * 160_000;
        score += (currentPlayer === rootPlayer ? 1 : -1) * this.scorePosition(next, rootPlayer) * 0.02;

        return { col, score };
      })
      .sort((a, b) => b.score - a.score)
      .map((entry) => entry.col);
  }

  recordLocalCutoff(player, col, depth, ply) {
    const killers = this._localKillerMoves[ply] || [null, null];
    if (killers[0] !== col) this._localKillerMoves[ply] = [col, killers[0]];
    const key = `${player}:${col}`;
    this._localHistory.set(key, (this._localHistory.get(key) || 0) + depth * depth);
  }

  localNegamax(grid, depth, alpha, beta, currentPlayer, rootPlayer, ply = 0) {
    if (this._minimaxDeadline !== null && performance.now() >= this._minimaxDeadline) {
      throw { timeout: true };
    }

    const terminal = this.terminalState(grid);
    if (terminal.over) {
      if (terminal.winner === null) return { score: 0, move: null, distance: 0 };
      if (terminal.winner === currentPlayer) return { score: 1000000000 - ply, move: null, distance: 0 };
      return { score: -1000000000 + ply, move: null, distance: 0 };
    }

    if (depth === 0) {
      const evalScore = this.scorePosition(grid, rootPlayer);
      return {
        score: currentPlayer === rootPlayer ? evalScore : -evalScore,
        move: null,
        distance: null,
      };
    }

    const alphaOrig = alpha;
    const betaOrig = beta;
    const ttKey = `${this.localBoardHash(grid, currentPlayer)}:${depth}:${currentPlayer}`;
    const ttEntry = this._localTT.get(ttKey);
    if (ttEntry) {
      if (ttEntry.flag === "exact") return { score: ttEntry.score, move: ttEntry.move, distance: ttEntry.distance };
      if (ttEntry.flag === "lower") alpha = Math.max(alpha, ttEntry.score);
      if (ttEntry.flag === "upper") beta = Math.min(beta, ttEntry.score);
      if (alpha >= beta) return { score: ttEntry.score, move: ttEntry.move, distance: ttEntry.distance };
    }

    const moves = this.validColumns(grid);
    if (!moves.length) return { score: 0, move: null, distance: 0 };

    const orderedMoves = this.orderLocalMoves(grid, moves, currentPlayer, rootPlayer, ply, ttEntry?.move ?? null);
    const opponent = this.other(currentPlayer);
    let bestScore = -Infinity;
    let bestMove = orderedMoves[0] ?? null;
    let bestDistance = null;

    for (const col of orderedMoves) {
      const next = this.copyGrid(grid);
      const pos = this.dropToken(next, col, currentPlayer);
      if (!pos) continue;

      let score;
      let distance;

      if (this.checkWinCells(next, pos[0], pos[1], currentPlayer).length) {
        score = 1000000000 - (ply + 1);
        distance = 1;
      } else {
        const child = this.localNegamax(next, depth - 1, -beta, -alpha, opponent, rootPlayer, ply + 1);
        score = -child.score;
        distance = child.distance === null ? null : child.distance + 1;
      }

      const isBetter =
        score > bestScore ||
        (score === bestScore &&
          ((score > 900000 && (bestDistance === null || (distance !== null && distance < bestDistance))) ||
            (score < -900000 && (bestDistance === null || (distance !== null && distance > bestDistance)))));

      if (isBetter) {
        bestScore = score;
        bestMove = col;
        bestDistance = distance;
      }

      alpha = Math.max(alpha, bestScore);
      if (alpha >= beta) {
        this.recordLocalCutoff(currentPlayer, col, depth, ply);
        break;
      }
    }

    const flag = bestScore <= alphaOrig ? "upper" : bestScore >= betaOrig ? "lower" : "exact";
    this._localTT.set(ttKey, { score: bestScore, move: bestMove, distance: bestDistance, flag });
    return { score: bestScore, move: bestMove, distance: bestDistance };
  }

  runLocalBestMove(board, player, maxDepth, timeLimitMs = 1500) {
    const deadline = performance.now() + timeLimitMs;
    this._minimaxDeadline = deadline;
    this._localTT = new Map();
    this._localHistory = new Map();
    this._localKillerMoves = Array.from({ length: 64 }, () => [null, null]);

    const ordered = this.orderLocalMoves(board, this.validColumns(board), player, player, 0);
    let bestResult = {
      move: ordered[0] ?? null,
      score: 0,
      distance: null,
      depthReached: 0,
      winner: null,
      mateIn: null,
    };

    for (let d = 1; d <= maxDepth; d++) {
      if (performance.now() >= deadline - 20) break;
      try {
        const r = this.localNegamax(this.copyGrid(board), d, -Infinity, Infinity, player, player, 0);
        if (r && r.move !== null) {
          bestResult = {
            ...r,
            depthReached: d,
            winner: r.score > 900000 ? player : r.score < -900000 ? this.other(player) : null,
            mateIn: r.distance ?? null,
          };
        }
      } catch (_e) {
        break;
      }
    }

    this._minimaxDeadline = null;
    return bestResult;
  }

  minimax(grid, depth, alpha, beta, maximizingPlayer, aiPlayer, humanPlayer) {
    const currentPlayer = maximizingPlayer ? aiPlayer : humanPlayer;
    const result = this.localNegamax(grid, depth, alpha, beta, currentPlayer, aiPlayer, 0);
    return {
      score: currentPlayer === aiPlayer ? result.score : -result.score,
      move: result.move,
      distance: result.distance,
    };
  }

  renderAiScores() {
    const renderToken = ++this._scoresRenderToken;

    if (this.online.enabled) {
      this.setScoresBlank();
      return;
    }

    const aiMode = (this.el.aiMode?.value || "random").toLowerCase();

    if (aiMode !== "minimax" || this.paintMode) {
      this.setScoresBlank();
      return;
    }

    if (!this.isHumanTurn(this.current)) {
      this.setScoresBlank();
      return;
    }

    if (this.robotThinking || !this.board) return;

    const depth = this.clampInt(this.el.depth?.value, 1, 8, 4);
    const grid0 = this.copyGrid(this.board);
    const player = this.current;
    const opponent = this.other(player);
    const valids = new Set(this.validColumns(grid0));

    for (let c = 0; c < this.cols; c++) {
      if (this.scoreEls[c]) this.scoreEls[c].textContent = valids.has(c) ? "..." : "N/A";
    }

    const colsList = [...Array(this.cols).keys()];
    const step = (i = 0) => {
      if (renderToken !== this._scoresRenderToken) return;
      if ((this.el.aiMode?.value || "random").toLowerCase() !== "minimax") return;
      if (this.robotThinking || this.gameOver || this.paintMode) return;
      if (i >= colsList.length) return;

      const col = colsList[i];

      if (!valids.has(col)) {
        if (this.scoreEls[col]) this.scoreEls[col].textContent = "N/A";
      } else {
        const g2 = this.copyGrid(grid0);
        const pos = this.dropToken(g2, col, player);

        if (!pos) {
          if (this.scoreEls[col]) this.scoreEls[col].textContent = "N/A";
        } else {
          let rawScore = 0;
          let distance = null;

          const immediateWin = this.checkWinCells(g2, pos[0], pos[1], player).length > 0;

          if (immediateWin) {
            rawScore = 1000000000;
            distance = 1;
          } else {
            const result = this.minimax(g2, depth - 1, -1e18, 1e18, false, player, opponent);
            rawScore = Number.isFinite(Number(result?.score)) ? Number(result.score) : 0;
            distance =
              result?.distance !== null &&
                result?.distance !== undefined &&
                Number.isFinite(Number(result.distance))
                ? Number(result.distance) + 1
                : null;
          }

          if (this.scoreEls[col]) {
            this.scoreEls[col].textContent = this.formatScoreForDisplay(rawScore, distance);
          }
        }
      }

      this.schedule(() => step(i + 1), 0);
    };

    this.schedule(() => step(0), 0);
  }

  // ===== GAME FLOW
  playMove(col, token) {
    const pos = this.dropToken(this.board, col, token);
    if (!pos) return true;

    if (this.viewIndex < this.moves.length) this.moves.splice(this.viewIndex);
    this.moves.push(col);
    this.viewIndex = this.moves.length;

    this.pushHistory({
      player: this.getNameForToken(token),
      type: "move",
      game: this.gameIndex,
      move: this.moves.length,
      col: col + 1,
      when: Date.now(),
    });
    this.renderHistory();

    this.updateReplayUI();

    const [r, c] = pos;
    const cells = this.checkWinCells(this.board, r, c, token);
    if (cells.length) {
      this.winningCells = cells;
      this.gameOver = true;
      this.winner = token;
      this.afterStateChange(false);
      return false;
    }

    if (this.isDraw(this.board)) {
      this.winningCells = [];
      this.gameOver = true;
      this.winner = null;
      this.afterStateChange(false);
      return false;
    }

    this.current = this.other(this.current);
    this.afterStateChange(true);
    return true;
  }

  onClick(col) {
    if (this.gameOver || this.robotThinking || this.aiLock) return;

    if (this.online.enabled) {
      if (this.online.token === "S") {
        alert("Tu es spectateur sur cette partie.");
        return;
      }
      if (this.viewIndex !== this.moves.length) {
        alert("Online: tu ne peux pas jouer en mode replay.");
        return;
      }
      this.onlinePlay(col).catch((e) => alert("❌ Coup refusé: " + (e?.message || e)));
      return;
    }

    if (this.viewIndex !== this.moves.length) {
      alert("Tu es en replay. Va à la fin (⏭) pour reprendre.");
      return;
    }

    if (!this.isHumanTurn(this.current)) return;

    const cont = this.playMove(col, this.current);
    if (!cont) return;

    if (!this.isHumanTurn(this.current) && !this.gameOver) {
      this.clearTimers();
      this.schedule(() => this.robotStep(), 140);
    }
  }

  robotRandomColumn(board) {
    const cols = this.validColumns(board);
    if (!cols.length) return null;
    return cols[Math.floor(Math.random() * cols.length)];
  }

  async robotPlayBackendAsync(aiMode, depth) {
    if (this.online.enabled) {
      this.aiLock = false;
      return;
    }

    if (this.paintMode) {
      this.aiLock = false;
      this.robotThinking = false;
      return;
    }

    if (this.gameOver) {
      this.aiLock = false;
      return;
    }

    if (this.robotThinking) {
      this.aiLock = false;
      return;
    }

    this.robotThinking = true;
    this.updateStatus();
    this.setButtonsState(false);
    this.setScoresBlank();
    const actionToken = ++this._aiActionToken;

    try {
      const data = await this.requestAiMove({
        board: this.board,
        player: this.current,
        ai_mode: aiMode,
        depth: this.clampInt(depth, 1, 8, 4),
      });

      const col = Number.isInteger(data?.col) ? data.col : parseInt(data?.col, 10);

      this.robotThinking = false;
      this.updateStatus();

      if (actionToken !== this._aiActionToken || this.paintMode || this.gameOver) {
        this.aiLock = false;
        this.setButtonsState(true);
        return;
      }

      if (!Number.isInteger(col)) {
        this.aiLock = false;
        this.setButtonsState(true);
        return;
      }

      if (!this.validColumns(this.board).includes(col)) {
        console.error("Coup backend invalide :", col, data);
        this.aiLock = false;
        this.setButtonsState(true);
        return;
      }

      this.playMove(col, this.current);
      this.aiLock = false;

      if (!this.isHumanTurn(this.current) && !this.gameOver) {
        this.clearTimers();
        this.schedule(() => this.robotStep(), 10);
      } else {
        this.setButtonsState(true);
      }
    } catch (e) {
      console.error(`Erreur IA backend (${aiMode}) :`, e);
      this.robotThinking = false;

      if (actionToken !== this._aiActionToken || this.paintMode || this.gameOver) {
        this.aiLock = false;
        this.setButtonsState(true);
        return;
      }

      if (aiMode === "minimax" || aiMode === "hybrid" || aiMode === "trained") {
        console.warn(`Backend indisponible pour "${aiMode}", bascule sur minimax local.`);
        try {
          const maxDepth = this.clampInt(depth, 1, 8, 4);
          const best = this.runLocalBestMove(this.board, this.current, maxDepth, 1500);
          const col = best?.move;
          if (Number.isInteger(col) && this.validColumns(this.board).includes(col)) {
            this.playMove(col, this.current);
            this.aiLock = false;
            if (!this.isHumanTurn(this.current) && !this.gameOver) {
              this.clearTimers();
              this.schedule(() => this.robotStep(), 10);
            } else {
              this.setButtonsState(true);
            }
            return;
          }
        } catch (localErr) {
          console.error("Erreur minimax local :", localErr);
        }
      }

      this.aiLock = false;
      this.updateStatus();
      this.setButtonsState(true);
      alert(`❌ Erreur IA ${aiMode} : ${e?.message || e}`);
    }
  }

  async robotStep() {
    if (this.online.enabled) return;
    if (this.paintMode) {
      this.robotThinking = false;
      this.aiLock = false;
      this.setButtonsState(true);
      return;
    }
    if (this.gameOver) return;
    if (this.robotThinking || this.aiLock) return;
    if (this.viewIndex !== this.moves.length) return;

    if (this.isHumanTurn(this.current)) {
      this.setButtonsState(true);
      return;
    }

    this.aiLock = true;
    this.setButtonsState(false);

    const aiMode = (this.el.aiMode?.value || "random").toLowerCase();
    const depth = this.clampInt(this.el.depth?.value, 1, 8, 4);

    if (aiMode === "random") {
      const col = this.robotRandomColumn(this.board);
      if (col === null) {
        this.gameOver = true;
        this.winner = null;
        this.winningCells = [];
        this.aiLock = false;
        this.afterStateChange(false);
        return;
      }

      this.playMove(col, this.current);
      this.aiLock = false;

      if (!this.isHumanTurn(this.current) && !this.gameOver) {
        this.clearTimers();
        this.schedule(() => this.robotStep(), 10);
      } else {
        this.setButtonsState(true);
      }
      return;
    }

    if (aiMode === "minimax" || aiMode === "trained" || aiMode === "hybrid") {
      await this.robotPlayBackendAsync(aiMode, depth);
      return;
    }

    await this.robotPlayBackendAsync("minimax", depth);
  }

  afterStateChange(triggerRobot = true) {
    this.drawBoard();
    this.updateStatus();
    this.renderAiScores();
    this.updateReplayUI();
    this.updatePrediction();

    if (this.gameOver) {
      this.setButtonsState(false);
      return;
    }

    const humanTurn = this.isHumanTurn(this.current);

    if (this.paintMode) {
      this.setButtonsState(true);
      return;
    }

    this.setButtonsState(!this.robotThinking && !this.aiLock && humanTurn);

    if (this.online.enabled) return;

    if (triggerRobot && !this.robotThinking && !this.aiLock && !this.gameOver) {
      if (!humanTurn) {
        this.clearTimers();
        this.schedule(() => this.robotStep(), 140);
      }
    }
  }

  stopGame() {
    this.clearTimers();
    this.gameOver = true;
    this.robotThinking = false;
    this.aiLock = false;
    this.winner = null;
    this.winningCells = [];
    this.afterStateChange(false);
  }

  resetGame(newGame = true) {
    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;
    this.paintMode = false;
    this.paintColor = this.el.paintColor?.value || this.EMPTY;
    this.updatePaintUI();

    if (newGame) {
      this.clearHistory();
      this.ensureDefaultSaveName();
      this.pushHistory({
        player: "system",
        type: "new",
        game: this.gameIndex + 1,
        move: 0,
        col: "-",
        when: Date.now(),
      });
      this.renderHistory();
    }

    const cfg = this.loadConfig();
    this.rows = cfg.rows;
    this.cols = cfg.cols;
    this.startingColor = cfg.starting_color;

    if (newGame) this.gameIndex += 1;

    this.board = this.createBoard();
    this.current = this.startingColor;
    this.gameOver = false;
    this.winner = null;
    this.winningCells = [];

    this.moves = [];
    this.viewIndex = 0;

    this.resetPredictionDisplay();

    this.rebuildColumnWidgets();
    this.afterStateChange(true);
    this.resizeCanvasReliable();
  }

  // ===== JSON SAVE/LOAD
  buildSavePayload(saveName) {
    return {
      save_name: saveName,
      rows: this.rows,
      cols: this.cols,
      starting_color: this.startingColor,
      control_red: this.getControlRed(),
      control_yellow: this.getControlYellow(),
      game_index: this.gameIndex,
      moves: this.moves,
      view_index: this.viewIndex,
      ai_mode: this.el.aiMode?.value || "random",
      ai_depth: this.clampInt(this.el.depth?.value, 1, 8, 4),
      player_red: this.getNameForToken(this.RED),
      player_yellow: this.getNameForToken(this.YELLOW),
      last_prediction: this._lastPredictionText || null,
    };
  }

  saveJsonFlow() {
    const saveName = this.getSaveNameOrDefault();
    const data = this.buildSavePayload(saveName);

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${saveName}.json`;
    a.click();
    URL.revokeObjectURL(a.href);

    this.pushHistory({
      player: "system",
      type: "save",
      game: this.gameIndex,
      move: this.moves.length,
      col: "JSON",
      when: Date.now(),
    });
    this.renderHistory();
  }

  loadJsonFlow(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        this.applyLoadedPayload(data);
        alert("✅ Partie chargée (JSON) !");

        this.pushHistory({
          player: "system",
          type: "load",
          game: this.gameIndex,
          move: this.moves.length,
          col: "JSON",
          when: Date.now(),
        });
        this.renderHistory();
      } catch (err) {
        alert("Fichier invalide : " + err);
      } finally {
        if (this.el.loadJson) this.el.loadJson.value = "";
      }
    };
    reader.readAsText(file, "utf-8");
  }

  applyLoadedPayload(data) {
    if (this.online.enabled) {
      alert("Online: chargement local désactivé (quitte Online si tu veux charger).");
      return;
    }

    this.clearTimers();
    this.robotThinking = false;
    this.aiLock = false;

    const rows = data.rows;
    const cols = data.cols;
    const start = data.starting_color;
    const moves = data.moves ?? [];
    const viewIndex = data.view_index ?? 0;

    if (!Number.isInteger(rows) || rows < 4 || rows > 20) throw new Error("rows invalide");
    if (!Number.isInteger(cols) || cols < 4 || cols > 20) throw new Error("cols invalide");
    if (start !== this.RED && start !== this.YELLOW) throw new Error("starting_color invalide");
    if (!Array.isArray(moves) || moves.some((x) => !Number.isInteger(x))) throw new Error("moves invalide");
    if (!Number.isInteger(viewIndex) || viewIndex < 0 || viewIndex > moves.length) throw new Error("view_index invalide");

    if (typeof data.player_red === "string" && data.player_red.trim()) {
      this.setNameForToken(this.RED, data.player_red.trim());
      if (this.el.nameR) this.el.nameR.textContent = data.player_red.trim();
    }
    if (typeof data.player_yellow === "string" && data.player_yellow.trim()) {
      this.setNameForToken(this.YELLOW, data.player_yellow.trim());
      if (this.el.nameY) this.el.nameY.textContent = data.player_yellow.trim();
    }

    this.rows = rows;
    this.cols = cols;
    this.startingColor = start;
    if (this.el.startColor) {
      this.el.startColor.value = this.startingColor;
    }
    localStorage.setItem(this.LS_STARTING_COLOR, this.startingColor);

    let controlRed = data.control_red;
    let controlYellow = data.control_yellow;

    if (!controlRed || !controlYellow) {
      const legacy = this.controlsFromLegacyMode(data.mode);
      controlRed = controlRed || legacy.controlRed;
      controlYellow = controlYellow || legacy.controlYellow;
    }

    this.applyControls(controlRed, controlYellow);

    this.gameIndex = Number.isInteger(data.game_index) ? data.game_index : 1;
    if (this.el.aiMode) {
      const allowed = ["random", "minimax", "trained", "hybrid"];
      this.el.aiMode.value = allowed.includes(data.ai_mode) ? data.ai_mode : "random";
    }
    if (this.el.depth) this.el.depth.value = String(this.clampInt(data.ai_depth, 1, 8, 4));

    if (typeof data.last_prediction === "string" && data.last_prediction.trim()) {
      this._lastPredictionText = data.last_prediction.trim();
      if (this.el.predictionText) {
        this.el.predictionText.textContent = this._lastPredictionText;
      }
    }

    if (typeof data.save_name === "string" && data.save_name.trim()) {
      if (this.el.saveName) this.el.saveName.value = data.save_name.trim();
    } else {
      this.ensureDefaultSaveName();
    }

    this.moves = moves;
    this.viewIndex = viewIndex;

    this.board = this.createBoard();
    this.winningCells = [];
    this.gameOver = false;
    this.winner = null;

    let lastPos = null;
    let lastToken = null;

    for (let i = 0; i < this.viewIndex; i++) {
      const col = this.moves[i];
      const token = this.tokenForMoveIndex(i);
      lastToken = token;
      lastPos = this.dropToken(this.board, col, token);
      if (!lastPos) break;
    }

    this.current = this.inferCurrentPlayerFromBoard();

    if (lastPos && lastToken) {
      const [rr, cc] = lastPos;
      const cells = this.checkWinCells(this.board, rr, cc, lastToken);
      if (cells.length) {
        this.winningCells = cells;
        this.gameOver = true;
        this.winner = lastToken;
      } else if (this.isDraw(this.board)) {
        this.gameOver = true;
        this.winner = null;
      }
    }

    this.rebuildColumnWidgets();
    this.afterStateChange(true);
    this.resizeCanvasReliable();
  }

  // ===== DB SAVE/LOAD
  computeConfidence(controlRed, controlYellow, aiMode, aiDepth) {
    aiMode = (aiMode || "random").toLowerCase();
    aiDepth = this.clampInt(aiDepth, 1, 8, 4);

    const aiCount = (controlRed === "ai" ? 1 : 0) + (controlYellow === "ai" ? 1 : 0);

    if (aiCount === 0) return 5;
    if (aiMode === "random") return 1;
    if (aiMode === "minimax" || aiMode === "trained" || aiMode === "hybrid") {
      if (aiDepth <= 2) return 2;
      if (aiDepth <= 4) return 3;
      if (aiDepth <= 8) return 4;
      return 5;
    }
    if (aiMode === "online") return 5;
    return 1;
  }

  openLocalDb() {
    if (this._localDbPromise) return this._localDbPromise;

    this._localDbPromise = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB indisponible"));
        return;
      }

      const req = window.indexedDB.open(this.LOCAL_DB_NAME, this.LOCAL_DB_VERSION);

      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(this.LOCAL_GAMES_STORE)) {
          const store = db.createObjectStore(this.LOCAL_GAMES_STORE, { keyPath: "game_id" });
          store.createIndex("created_at", "created_at", { unique: false });
          store.createIndex("save_name", "save_name", { unique: false });
        }
      };

      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("Ouverture IndexedDB impossible"));
    });

    return this._localDbPromise;
  }

  async saveGameLocal(gameData) {
    const db = await this.openLocalDb();
    const now = new Date().toISOString();
    const payload = {
      ...gameData,
      game_id: gameData?.game_id || `local-${Date.now()}`,
      created_at: gameData?.created_at || now,
      total_moves: Array.isArray(gameData?.moves) ? gameData.moves.length : 0,
    };

    await new Promise((resolve, reject) => {
      const tx = db.transaction(this.LOCAL_GAMES_STORE, "readwrite");
      tx.objectStore(this.LOCAL_GAMES_STORE).put(payload);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error || new Error("Ecriture IndexedDB impossible"));
    });

    return { game_id: payload.game_id, storage: "indexeddb" };
  }

  async listLocalGames() {
    const db = await this.openLocalDb();
    const rows = await new Promise((resolve, reject) => {
      const tx = db.transaction(this.LOCAL_GAMES_STORE, "readonly");
      const req = tx.objectStore(this.LOCAL_GAMES_STORE).getAll();
      req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
      req.onerror = () => reject(req.error || new Error("Lecture IndexedDB impossible"));
    });

    return rows
      .slice()
      .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
      .map((g) => ({
        ...g,
        total_moves: g?.total_moves ?? (Array.isArray(g?.moves) ? g.moves.length : 0),
      }));
  }

  async getLocalGame(gameId) {
    const db = await this.openLocalDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(this.LOCAL_GAMES_STORE, "readonly");
      const req = tx.objectStore(this.LOCAL_GAMES_STORE).get(gameId);
      req.onsuccess = () => {
        if (!req.result) {
          reject(new Error("Partie introuvable"));
          return;
        }
        resolve(req.result);
      };
      req.onerror = () => reject(req.error || new Error("Lecture IndexedDB impossible"));
    });
  }

  async saveGame(gameData) {
    if (this.isLocalPersistence()) {
      return this.saveGameLocal(gameData);
    }

    return this.apiFetch("/games", {
      method: "POST",
      body: JSON.stringify(gameData),
    });
  }

  buildGamePayloadForDB(saveName) {
    const control_red = this.getControlRed();
    const control_yellow = this.getControlYellow();
    const game_mode = this.getDerivedGameMode();
    const ai_mode = (this.el.aiMode?.value || "random").toLowerCase();
    const ai_depth = this.clampInt(this.el.depth?.value, 1, 8, 4);
    const status = this.gameOver ? "completed" : "in_progress";

    let winner = null;
    if (this.gameOver) {
      if (this.winner === this.RED) winner = "R";
      else if (this.winner === this.YELLOW) winner = "Y";
      else winner = "D";
    }

    const distinct_cols = this.moves.length ? new Set(this.moves).size : 0;
    const confidence = this.computeConfidence(control_red, control_yellow, ai_mode, ai_depth);

    return {
      user_id: 1,
      save_name: saveName,
      game_index: this.gameIndex,
      rows_count: this.rows,
      cols_count: this.cols,
      starting_color: this.startingColor,
      control_red,
      control_yellow,
      ai_mode,
      ai_depth,
      game_mode,
      status,
      winner,
      view_index: this.viewIndex,
      moves: this.moves,
      confidence,
      distinct_cols,
      player_red: this.getNameForToken(this.RED),
      player_yellow: this.getNameForToken(this.YELLOW),
    };
  }

  async saveDbFlow() {
    if (this.online.enabled && !this.gameOver) {
      alert("Online: sauvegarde manuelle BD seulement en fin de partie ou hors ligne.");
      return;
    }

    const saveName = this.getSaveNameOrDefault();
    try {
      const payload = this.buildGamePayloadForDB(saveName);
      const out = await this.saveGame(payload);
      const gid = out?.game_id ?? out?.id ?? "(?)";
      const target = this.isLocalPersistence() ? "en local" : "en base";
      alert(`✅ Sauvegardé en base !\nID: ${gid}\nNom: ${saveName}`);
      this.pushHistory({
        player: "system",
        type: "save",
        game: this.gameIndex,
        move: this.moves.length,
        col: "BD",
        when: Date.now(),
      });
      this.renderHistory();
    } catch (e) {
      alert("❌ Sauvegarde BD impossible : " + (e?.message || e));
    }
  }

  async loadDbFlow() {
    if (this.online.enabled) {
      alert("Online: chargement BD désactivé (quitte Online si tu veux charger).");
      return;
    }

    try {
      const list = this.isLocalPersistence()
        ? await this.listLocalGames()
        : await this.apiFetch("/games", { method: "GET" });

      if (!Array.isArray(list) || list.length === 0) {
        alert("Base vide (aucune partie).");
        return;
      }

      const pickedId = await this.showDbLoadDialog(list);
      if (!pickedId) return;

      const g = this.isLocalPersistence()
        ? await this.getLocalGame(pickedId)
        : await this.apiFetch(`/games/${pickedId}`, { method: "GET" });

      let moves = g.moves;
      if (typeof moves === "string") {
        try {
          moves = JSON.parse(moves);
        } catch {
          moves = [];
        }
      }
      if (!Array.isArray(moves)) moves = [];

      const payload = {
        save_name: g.save_name,
        rows: Number(g.rows_count),
        cols: Number(g.cols_count),
        starting_color: g.starting_color,
        control_red: g.control_red,
        control_yellow: g.control_yellow,
        mode: Number(g.game_mode),
        game_index: Number(g.game_index || 1),
        moves,
        view_index: Number.isInteger(g.view_index) ? g.view_index : moves.length,
        ai_mode: g.ai_mode || "random",
        ai_depth: Number(g.ai_depth || 4),
        player_red: g.player_red,
        player_yellow: g.player_yellow,
      };

      this.applyLoadedPayload(payload);
      const source = this.isLocalPersistence() ? "le stockage local" : "la base";
      alert(`✅ Partie chargée depuis ${source} !\nID: ${pickedId}\nNom: ${g.save_name || ""}`);

      this.pushHistory({
        player: "system",
        type: "load",
        game: this.gameIndex,
        move: this.moves.length,
        col: "BD",
        when: Date.now(),
      });
      this.renderHistory();
    } catch (e) {
      alert("❌ Chargement BD impossible : " + (e?.message || e));
    }
  }

  showDbLoadDialog(list) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.style.position = "fixed";
      overlay.style.inset = "0";
      overlay.style.background = "rgba(0,0,0,0.55)";
      overlay.style.display = "flex";
      overlay.style.alignItems = "center";
      overlay.style.justifyContent = "center";
      overlay.style.zIndex = "99999";

      const modal = document.createElement("div");
      modal.style.width = "min(760px, 92vw)";
      modal.style.maxHeight = "80vh";
      modal.style.overflow = "hidden";
      modal.style.background = "#1c1338";
      modal.style.border = "1px solid rgba(255,255,255,0.12)";
      modal.style.borderRadius = "16px";
      modal.style.boxShadow = "0 20px 60px rgba(0,0,0,0.45)";
      modal.style.color = "#fff";
      modal.style.padding = "18px";
      modal.style.fontFamily = "DM Sans, Arial, sans-serif";

      const title = document.createElement("div");
      title.textContent = this.isLocalPersistence()
        ? "Charger une partie locale"
        : "Charger une partie depuis la base";
      title.style.fontSize = "22px";
      title.style.fontWeight = "700";
      title.style.marginBottom = "12px";

      const search = document.createElement("input");
      search.type = "text";
      search.placeholder = "Rechercher par ID, nom, joueurs, mode, taille...";
      search.style.width = "100%";
      search.style.padding = "12px 14px";
      search.style.borderRadius = "10px";
      search.style.border = "1px solid rgba(255,255,255,0.15)";
      search.style.background = "#120b29";
      search.style.color = "#fff";
      search.style.outline = "none";
      search.style.marginBottom = "12px";

      const select = document.createElement("select");
      select.size = 12;
      select.style.width = "100%";
      select.style.padding = "10px";
      select.style.borderRadius = "10px";
      select.style.border = "1px solid rgba(255,255,255,0.15)";
      select.style.background = "#120b29";
      select.style.color = "#fff";
      select.style.marginBottom = "14px";

      const footer = document.createElement("div");
      footer.style.display = "flex";
      footer.style.justifyContent = "flex-end";
      footer.style.gap = "10px";

      const btnCancel = document.createElement("button");
      btnCancel.type = "button";
      btnCancel.textContent = "Annuler";
      btnCancel.style.padding = "10px 16px";
      btnCancel.style.borderRadius = "10px";
      btnCancel.style.border = "1px solid rgba(255,255,255,0.15)";
      btnCancel.style.background = "#2a214a";
      btnCancel.style.color = "#fff";
      btnCancel.style.cursor = "pointer";

      const btnLoad = document.createElement("button");
      btnLoad.type = "button";
      btnLoad.textContent = "Charger";
      btnLoad.style.padding = "10px 16px";
      btnLoad.style.borderRadius = "10px";
      btnLoad.style.border = "none";
      btnLoad.style.background = "#0ea5e9";
      btnLoad.style.color = "#fff";
      btnLoad.style.fontWeight = "700";
      btnLoad.style.cursor = "pointer";

      const normalizeGame = (g) => {
        const id = g.game_id ?? g.id ?? "";
        const saveName = g.save_name || "(sans nom)";
        const size = `${g.rows_count ?? "?"}x${g.cols_count ?? "?"}`;
        const modeMap = { 0: "IA vs IA", 1: "Humain vs IA", 2: "Humain vs Humain" };
        const mode = modeMap[g.game_mode] ?? `mode=${g.game_mode ?? "?"}`;
        const ai = `${g.ai_mode ?? "?"}/${g.ai_depth ?? "?"}`;
        const totalMoves = g.total_moves ?? (Array.isArray(g.moves) ? g.moves.length : "?");
        const red = g.player_red || "Rouge";
        const yellow = g.player_yellow || "Jaune";
        const created = g.created_at ? new Date(g.created_at).toLocaleString() : "";

        return {
          raw: g,
          id,
          label: `#${id} | ${saveName} | ${size} | ${mode} | ${ai} | coups=${totalMoves} | ${red} vs ${yellow} | ${created}`,
          haystack: `${id} ${saveName} ${size} ${mode} ${ai} ${totalMoves} ${red} ${yellow} ${created}`.toLowerCase(),
        };
      };

      const normalized = list.map(normalizeGame);

      const renderOptions = (query = "") => {
        const q = query.trim().toLowerCase();
        const filtered = q ? normalized.filter((x) => x.haystack.includes(q)) : normalized;
        select.innerHTML = "";
        for (const item of filtered) {
          const opt = document.createElement("option");
          opt.value = String(item.id);
          opt.textContent = item.label;
          select.appendChild(opt);
        }
        if (select.options.length > 0) select.selectedIndex = 0;
      };

      const close = (value = null) => {
        overlay.remove();
        resolve(value);
      };

      search.addEventListener("input", () => renderOptions(search.value));
      btnCancel.addEventListener("click", () => close(null));

      btnLoad.addEventListener("click", () => {
        const val = select.value || null;
        if (!val) return;
        close(val);
      });

      select.addEventListener("dblclick", () => {
        const val = select.value || null;
        if (!val) return;
        close(val);
      });

      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) close(null);
      });

      document.addEventListener(
        "keydown",
        function escHandler(e) {
          if (e.key === "Escape") {
            document.removeEventListener("keydown", escHandler);
            close(null);
          }
        },
        { once: true }
      );

      renderOptions();
      footer.appendChild(btnCancel);
      footer.appendChild(btnLoad);
      modal.appendChild(title);
      modal.appendChild(search);
      modal.appendChild(select);
      modal.appendChild(footer);
      overlay.appendChild(modal);
      document.body.appendChild(overlay);
      search.focus();
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const app = new Connect4Web();
  app.initializeRuntime().catch(() => { });
  requestAnimationFrame(() => requestAnimationFrame(() => app.resizeCanvasReliable()));
});