class Connect4Web {
  EMPTY = ".";
  RED = "R";
  YELLOW = "Y";
  CONNECT_N = 4;

  COLOR_BG = "#170c38";
  COLOR_HOLE = "#ede5ff";
  COLOR_RED = "#e53030";
  COLOR_YELLOW = "#f59e0b";
  COLOR_WIN = "#22c55e";
  COLOR_HOVER_COL = "rgba(124,82,232,0.18)";

  LS_NAME_R = "c4_name_red";
  LS_NAME_Y = "c4_name_yellow";
  LS_HISTORY = "c4_history";
  HISTORY_LIMIT = 120;

  // ===== ONLINE (multijoueur)
  LS_ONLINE_CODE = "c4_online_code";
  LS_ONLINE_SECRET = "c4_online_secret";
  LS_ONLINE_TOKEN = "c4_online_token";
  LS_ONLINE_NAME = "c4_online_name";
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
      title.textContent = "Charger une partie depuis la base";
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
        const filtered = q
          ? normalized.filter((x) => x.haystack.includes(q))
          : normalized;

        select.innerHTML = "";

        for (const item of filtered) {
          const opt = document.createElement("option");
          opt.value = String(item.id);
          opt.textContent = item.label;
          select.appendChild(opt);
        }

        if (select.options.length > 0) {
          select.selectedIndex = 0;
        }
      };

      const close = (value = null) => {
        overlay.remove();
        resolve(value);
      };

      search.addEventListener("input", () => renderOptions(search.value));

      btnCancel.addEventListener("click", () => close(null));

      btnLoad.addEventListener("click", () => {
        const val = select.value ? parseInt(select.value, 10) : null;
        if (!val) return;
        close(val);
      });

      select.addEventListener("dblclick", () => {
        const val = select.value ? parseInt(select.value, 10) : null;
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

    // ✅ FIX minimax multi-coups
    this.robotThinking = false;
    this.aiLock = false;
    this.pendingTimers = new Set();

    // Online state
    this.online = {
      enabled: false,
      code: null,
      secret: null,
      token: null, // "R" | "Y" | "S"
      pollId: null,
      lastMovesLen: 0,
    };

    // Hover
    this.lastDrawGeom = null;
    this.hoverCol = null;

    // DOM
    this.el = {
      mode: document.getElementById("mode"),
      aiMode: document.getElementById("aiMode"),
      depth: document.getElementById("depth"),
      noDigits: document.getElementById("noDigits"),
      saveName: document.getElementById("saveName"),

      nameR: document.getElementById("nameR"),
      nameY: document.getElementById("nameY"),
      changeR: document.getElementById("changeR"),
      changeY: document.getElementById("changeY"),

      // Online
      onlineName: document.getElementById("onlineName"),
      onlineCode: document.getElementById("onlineCode"),
      onlineCreate: document.getElementById("onlineCreate"),
      onlineJoin: document.getElementById("onlineJoin"),
      onlineLeave: document.getElementById("onlineLeave"),
      onlineBadge: document.getElementById("onlineBadge"),
      onlineCopyLink: document.getElementById("onlineCopyLink"),

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

    this.ctx = this.el.canvas.getContext("2d");

    this.bindUI();
    this.ensurePlayerNames();
    this.ensureDefaultSaveName();

    // Log + render history
    this.renderHistory();

    this.resetGame(false);

    // ✅ Responsive canvas (PC + mobile)
    this.setupResponsiveCanvas();

    // ✅ ONLINE: restore session or join via URL
    this.setOnlineBadge("Offline");

    if (this.el.onlineName) {
      const savedName = (localStorage.getItem(this.LS_ONLINE_NAME) || "").trim();
      if (savedName && !this.el.onlineName.value) this.el.onlineName.value = savedName;
    }

    const params = new URLSearchParams(location.search);
    const joinCode = (params.get("join") || "").trim().toUpperCase();

    if (joinCode) {
      if (this.el.onlineCode) this.el.onlineCode.value = joinCode;
      this.onlineJoinFlow(joinCode).catch((e) => alert("❌ Join URL: " + (e?.message || e)));
    } else if (this.onlineLoadSession()) {
      if (this.el.onlineCode) this.el.onlineCode.value = this.online.code;
      this.setOnlineEnabled(true);
      this.onlineStartPolling();
    }
  }

  // ===== CONFIG
  loadConfig() {
    return { rows: 8, cols: 9, starting_color: "R" };
  }

  // ===== HELPERS
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

  // ===== API (backend optionnel)
  apiBase() {
    return "/api";
  }

  async apiFetch(path, opts = {}) {
    const res = await fetch(`${this.apiBase()}${path}`, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });

    let payload = null;
    try {
      payload = await res.json();
    } catch { }

    if (!res.ok) {
      const msg = payload?.error || payload?.message || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return payload;
  }

  // ===== ONLINE HELPERS
  setOnlineBadge(text) {
    if (!this.el.onlineBadge) return;
    this.el.onlineBadge.textContent = text;
  }

  getOnlineName() {
    const a = (this.el.onlineName?.value || "").trim();
    if (a) {
      localStorage.setItem(this.LS_ONLINE_NAME, a);
      return a;
    }
    const b = (localStorage.getItem(this.LS_ONLINE_NAME) || "").trim();
    return b || this.getNameForToken(this.RED);
  }

  setOnlineEnabled(on) {
    this.online.enabled = !!on;

    if (this.online.enabled) {
      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;

      // Forcer humain vs humain en online (sinon IA spam des coups locaux)
      this.el.mode.value = "2";
      this.el.aiMode.value = "random";
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
    localStorage.setItem(this.LS_ONLINE_SECRET, secret);
    localStorage.setItem(this.LS_ONLINE_TOKEN, token);
  }

  onlineLoadSession() {
    const code = (localStorage.getItem(this.LS_ONLINE_CODE) || "").trim();
    const secret = (localStorage.getItem(this.LS_ONLINE_SECRET) || "").trim();
    const token = (localStorage.getItem(this.LS_ONLINE_TOKEN) || "").trim();
    if (code && secret && token) {
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
        const st = await this.apiFetch(`/online/${this.online.code}/state`, { method: "GET" });
        this.applyOnlineState(st);
      } catch {
        this.setOnlineBadge("Offline");
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

    this.setOnlineEnabled(true);
    this.setOnlineBadge(`Online #${out.code} (${out.your_token})`);

    this.resetLocalBoardOnly();
    this.onlineStartPolling();

    alert(`✅ Partie online créée.\nCode: ${out.code}\nPartage: ${location.origin}/?join=${out.code}`);
  }

  async onlineJoinFlow(codeRaw) {
    const code = (codeRaw || "").trim().toUpperCase();
    if (!code) throw new Error("Code manquant.");

    const name = this.getOnlineName();
    const out = await this.apiFetch("/online/join", {
      method: "POST",
      body: JSON.stringify({ code, player_name: name }),
    });

    this.onlineSaveSession(out.code, out.player_secret, out.your_token);
    if (this.el.onlineCode) this.el.onlineCode.value = out.code;

    this.setOnlineEnabled(true);
    this.setOnlineBadge(`Online #${out.code} (${out.your_token})`);

    this.resetLocalBoardOnly();
    this.onlineStartPolling();
  }

  onlineLeaveFlow() {
    this.onlineStopPolling();
    this.setOnlineEnabled(false);
    this.onlineClearSession();
    this.setOnlineBadge("Offline");
  }

  async onlinePlay(col) {
    if (!this.online.enabled || !this.online.code || !this.online.secret) return;
    await this.apiFetch(`/online/${this.online.code}/move`, {
      method: "POST",
      body: JSON.stringify({ player_secret: this.online.secret, col }),
    });
    // pas de play local : on attend /state
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

    this.rebuildColumnWidgets();
    this.afterStateChange(false);
    this.resizeCanvasReliable();
  }

  applyOnlineState(st) {
    const movesArr = Array.isArray(st.moves) ? st.moves : [];
    const cols = movesArr
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

    this.moves = cols;
    this.viewIndex = this.moves.length;
    this.board = this.reconstructBoard(this.viewIndex);

    this.current = st.current_turn === this.YELLOW ? this.YELLOW : this.RED;

    this.gameOver = st.status === "finished" || st.winner !== null;
    if (st.winner === "R") this.winner = this.RED;
    else if (st.winner === "Y") this.winner = this.YELLOW;
    else if (st.winner === "D") this.winner = null;
    else this.winner = null;

    if (this.online.enabled && this.online.code) {
      const t = this.online.token || "?";
      this.setOnlineBadge(`Online #${this.online.code} (${t})`);
    }

    this.winningCells = [];
    this.drawBoard();
    this.updateReplayUI();
    this.updateStatus();
    this.updateSidePanel();

    this.setButtonsState(true);
  }

  // ===== NOMS
  getNameForToken(token) {
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

    this.el.nameR.textContent = r;
    this.el.nameY.textContent = y;
  }

  changePlayerName(token) {
    const current = this.getNameForToken(token);
    let name = prompt(`Nouveau nom (${token === this.RED ? "Rouge" : "Jaune"}) :`, current);
    if (name === null) return;
    name = String(name).trim();
    if (!name) return;

    this.setNameForToken(token, name);
    if (token === this.RED) this.el.nameR.textContent = name;
    else this.el.nameY.textContent = name;

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

  escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  pushHistory({ player, type, game, move, col, when }) {
    const arr = this.loadHistory();
    arr.unshift({ player, type, game, move, col, when });
    this.saveHistory(arr);
  }

  renderHistory() {
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
    const pad = (n) => String(n).padStart(2, "0");
    const d = new Date();
    const def = `partie_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}${pad(
      d.getMinutes()
    )}`;
    if (!this.el.saveName.value.trim()) this.el.saveName.value = def;
  }

  getSaveNameOrDefault() {
    const raw = (this.el.saveName.value || "").trim();
    if (raw) return raw;
    this.ensureDefaultSaveName();
    return (this.el.saveName.value || "partie").trim() || "partie";
  }

  // ===== UI
  bindUI() {
    this.el.newGame.addEventListener("click", () => this.resetGame(true));
    this.el.stop.addEventListener("click", () => this.stopGame());

    this.el.mode.addEventListener("change", () => {
      if (this.online.enabled) return;

      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;

      this.updateStatus();
      this.renderAiScores();
      this.updateReplayUI();
      this.setButtonsState(true);

      const mode = parseInt(this.el.mode.value, 10);

      if (!this.gameOver && this.viewIndex === this.moves.length && !this.isHumanTurn(mode, this.current)) {
        this.schedule(() => this.robotStep(), 140);
      }
    });
    this.el.aiMode.addEventListener("change", () => {
      if (this.online.enabled) return;

      this.clearTimers();
      this.robotThinking = false;
      this.aiLock = false;

      this.updateStatus();
      this.renderAiScores();
      this.setButtonsState(true);

      const mode = parseInt(this.el.mode.value, 10);
      if (!this.gameOver && this.viewIndex === this.moves.length && !this.isHumanTurn(mode, this.current)) {
        this.schedule(() => this.robotStep(), 140);
      }
    });
    this.el.depth.addEventListener("change", () => this.renderAiScores());
    this.el.noDigits.addEventListener("change", () => this.applyNoDigitsMode());

    this.el.changeR.addEventListener("click", () => this.changePlayerName(this.RED));
    this.el.changeY.addEventListener("click", () => this.changePlayerName(this.YELLOW));

    // Dropdown save/load only
    this.el.saveMenu.addEventListener("change", async () => {
      const v = this.el.saveMenu.value;
      this.el.saveMenu.value = "";
      if (!v) return;
      if (v === "json") this.saveJsonFlow();
      if (v === "db") await this.saveDbFlow();
    });

    this.el.loadMenu.addEventListener("change", async () => {
      const v = this.el.loadMenu.value;
      this.el.loadMenu.value = "";
      if (!v) return;
      if (v === "json") this.el.loadJson.click();
      if (v === "db") await this.loadDbFlow();
    });

    this.el.loadJson.addEventListener("change", (e) => this.loadJsonFlow(e));
    this.el.clearHistoryBtn.addEventListener("click", () => this.clearHistory());

    // Replay
    this.el.moveSlider.addEventListener("input", () => {
      this.navigateTo(parseInt(this.el.moveSlider.value, 10));
    });
    this.el.firstMove.addEventListener("click", () => this.navigateTo(0));
    this.el.prevMove.addEventListener("click", () => this.navigateTo(this.viewIndex - 1));
    this.el.nextMove.addEventListener("click", () => this.navigateTo(this.viewIndex + 1));
    this.el.lastMove.addEventListener("click", () => this.navigateTo(this.moves.length));

    // Canvas interactions
    this.el.canvas.addEventListener("mousemove", (ev) => this.onCanvasMove(ev));
    this.el.canvas.addEventListener("mouseleave", () => {
      this.setHoverColumn(null);
      this.drawBoard();
    });
    this.el.canvas.addEventListener("click", (ev) => this.onCanvasClick(ev));

    // ===== ONLINE buttons
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
  }

  // ===== COLUMN UI
  rebuildColumnWidgets() {
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
    const on = !!this.el.noDigits.checked;
    for (let c = 0; c < this.colBtnEls.length; c++) {
      const b = this.colBtnEls[c];
      b.classList.toggle("noDigits", on);
      b.textContent = String(c + 1);
    }
  }

  setHoverColumn(col) {
    this.hoverCol = col === null || col === undefined ? null : col;

    for (let i = 0; i < this.colBtnEls.length; i++) {
      this.colBtnEls[i].classList.toggle("isHover", this.hoverCol === i);
    }

    this.el.colHoverInfo.textContent = this.hoverCol === null ? "—" : String(this.hoverCol + 1);
  }

  setButtonsState(enabled) {
    // ONLINE: bouton actif seulement si c'est ton tour et que tu n'es pas spectateur
    if (this.online.enabled) {
      const can =
        enabled &&
        !this.gameOver &&
        !this.robotThinking &&
        !this.aiLock &&
        this.viewIndex === this.moves.length &&
        this.online.token !== "S" &&
        this.online.token &&
        this.current === this.online.token;

      for (const b of this.colBtnEls) b.disabled = !can;
      return;
    }

    const mode = parseInt(this.el.mode.value, 10);
    const can =
      enabled &&
      this.isHumanTurn(mode, this.current) &&
      !this.robotThinking &&
      !this.aiLock &&
      !this.gameOver;

    for (const b of this.colBtnEls) b.disabled = !can;
  }

  // ===== REPLAY
  updateReplayUI() {
    const total = this.moves.length;
    this.el.moveSlider.max = String(total);
    this.el.moveSlider.value = String(this.viewIndex);
    this.el.moveLabel.textContent = `Coup ${this.viewIndex}/${total}`;

    this.el.firstMove.disabled = this.viewIndex <= 0;
    this.el.prevMove.disabled = this.viewIndex <= 0;
    this.el.nextMove.disabled = this.viewIndex >= total;
    this.el.lastMove.disabled = this.viewIndex >= total;
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
    this.current = this.tokenForMoveIndex(this.viewIndex);

    this.winningCells = [];
    this.winner = null;
    this.gameOver = false;

    this.drawBoard();
    this.updateStatus();
    this.updateReplayUI();
  }

  // ===== GAME CORE
  createBoard() {
    return Array.from({ length: this.rows }, () => Array.from({ length: this.cols }, () => this.EMPTY));
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

  isHumanTurn(mode, current) {
    mode = parseInt(mode, 10);
    if (mode === 2) return true;
    if (mode === 0) return false;
    return current === this.RED;
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

      let r = lastRow + dr,
        c = lastCol + dc;
      while (0 <= r && r < this.rows && 0 <= c && c < this.cols && board[r][c] === token) {
        cells.push([r, c]);
        r += dr;
        c += dc;
      }

      r = lastRow - dr;
      c = lastCol - dc;
      while (0 <= r && r < this.rows && 0 <= c && c < this.cols && board[r][c] === token) {
        cells.unshift([r, c]);
        r -= dr;
        c -= dc;
      }

      if (cells.length >= this.CONNECT_N) return cells.slice(0, this.CONNECT_N);
    }
    return [];
  }

  // ===== CANVAS INPUT
  canvasToBoardCol(clientX, clientY) {
    if (!this.lastDrawGeom) return null;
    const wrapRect = this.el.canvasWrap.getBoundingClientRect();
    const x = clientX - wrapRect.left;
    const y = clientY - wrapRect.top;

    const { x0, y0, cell, boardW, boardH } = this.lastDrawGeom;
    if (x < x0 || x > x0 + boardW || y < y0 || y > y0 + boardH) return null;

    const col = Math.floor((x - x0) / cell);
    if (col < 0 || col >= this.cols) return null;
    return col;
  }

  onCanvasMove(ev) {
    const col = this.canvasToBoardCol(ev.clientX, ev.clientY);
    this.setHoverColumn(col);
    this.drawBoard();
  }

  onCanvasClick(ev) {
    const col = this.canvasToBoardCol(ev.clientX, ev.clientY);
    if (col === null) return;
    this.onClick(col);
  }

  // ===== CANVAS RESIZE (RESPONSIVE) ✅
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
    if (!wrap) return;

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

    if (this.el.canvas.width !== bufW) this.el.canvas.width = bufW;
    if (this.el.canvas.height !== bufH) this.el.canvas.height = bufH;

    // draw in CSS pixels
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    this.drawBoard();
  }

  cellColor(v) {
    if (v === this.RED) return this.COLOR_RED;
    if (v === this.YELLOW) return this.COLOR_YELLOW;
    return this.COLOR_HOLE;
  }

  drawBoard() {
    if (!this.board) return;

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

    // hover column highlight
    if (this.hoverCol !== null) {
      ctx.fillStyle = this.COLOR_HOVER_COL;
      ctx.fillRect(x0 + this.hoverCol * cell, y0, cell, boardH);
    }

    // board background
    ctx.fillStyle = this.COLOR_BG;
    ctx.fillRect(x0, y0, boardW, boardH);

    const winSet = new Set(this.winningCells.map(([r, c]) => `${r},${c}`));

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
        const _cv = this.board[r][c];
        if (_cv === this.RED) {
          ctx.shadowColor = "rgba(229,48,48,0.65)";
          ctx.shadowBlur = 14;
        } else if (_cv === this.YELLOW) {
          ctx.shadowColor = "rgba(245,158,11,0.55)";
          ctx.shadowBlur = 12;
        }
        ctx.fillStyle = this.cellColor(_cv);
        ctx.fill();
        ctx.shadowBlur = 0;

        if (winSet.has(`${r},${c}`)) {
          ctx.lineWidth = 4;
          ctx.strokeStyle = this.COLOR_WIN;
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
    this.el.rowsVal.textContent = String(this.rows);
    this.el.colsVal.textContent = String(this.cols);
    this.el.startVal.textContent =
      this.startingColor === this.RED
        ? `Rouge (${this.getNameForToken(this.RED)})`
        : `Jaune (${this.getNameForToken(this.YELLOW)})`;
    this.el.gameIndexVal.textContent = String(this.gameIndex);
    this.el.movesVal.textContent = String(this.moves.length);
    this.el.viewVal.textContent = String(this.viewIndex);
  }

  updateStatus() {
    let msg = "";

    if (this.online.enabled) {
      const code = this.online.code || "—";
      const tok = this.online.token || "?";
      msg += `🌐 Online #${code} (${tok}) — `;
    }

    if (this.gameOver) {
      if (this.winner === this.RED)
        msg += `Partie #${this.gameIndex} — 🎉 Gagnant : Rouge (${this.getNameForToken(this.RED)})`;
      else if (this.winner === this.YELLOW)
        msg += `Partie #${this.gameIndex} — 🎉 Gagnant : Jaune (${this.getNameForToken(this.YELLOW)})`;
      else msg += `Partie #${this.gameIndex} — 🤝 Match nul`;
    } else {
      const who = this.current === this.RED ? "Rouge" : "Jaune";
      msg += `Partie #${this.gameIndex} — À jouer : ${who} (${this.getNameForToken(this.current)})`;
    }

    if (this.robotThinking) msg += " (IA réfléchit...)";
    this.el.status.textContent = msg;
    this.updateSidePanel();
  }

  // ===== AI SCORES
  setScoresBlank() {
    for (const s of this.scoreEls) s.textContent = "";
  }

  dropInGrid(grid, col, token) {
    if (grid[0][col] !== this.EMPTY) return null;
    for (let r = this.rows - 1; r >= 0; r--) {
      if (grid[r][col] === this.EMPTY) {
        grid[r][col] = token;
        return [r, col];
      }
    }
    return null;
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
  findBestMove(grid, depth, aiPlayer, humanPlayer) {
    const moves = this.validColumns(grid);
    if (!moves.length) return null;

    // 1) gagner immédiatement
    for (const col of moves) {
      const g2 = this.copyGrid(grid);
      const pos = this.dropInGrid(g2, col, aiPlayer);
      if (!pos) continue;

      const winCells = this.checkWinCells(g2, pos[0], pos[1], aiPlayer);
      if (winCells.length) return col;
    }

    // 2) bloquer une victoire immédiate adverse
    const opponentWinningMoves = [];
    for (const col of moves) {
      const g2 = this.copyGrid(grid);
      const pos = this.dropInGrid(g2, col, humanPlayer);
      if (!pos) continue;

      const winCells = this.checkWinCells(g2, pos[0], pos[1], humanPlayer);
      if (winCells.length) opponentWinningMoves.push(col);
    }

    if (opponentWinningMoves.length === 1) {
      return opponentWinningMoves[0];
    }

    // S'il y a plusieurs menaces immédiates adverses, on essaye au moins
    // d'en bloquer une. Le minimax départagera ensuite si besoin.
    if (opponentWinningMoves.length > 1) {
      return opponentWinningMoves[0];
    }

    // 3) sinon minimax
    const result = this.minimax(grid, depth, -Infinity, Infinity, true, aiPlayer, humanPlayer);
    return result.move;
  }
  countImmediateWins(grid, player) {
    let count = 0;
    const moves = this.validColumns(grid);

    for (const col of moves) {
      const g2 = this.copyGrid(grid);
      const pos = this.dropInGrid(g2, col, player);
      if (!pos) continue;

      const winCells = this.checkWinCells(g2, pos[0], pos[1], player);
      if (winCells.length) count++;
    }

    return count;
  }
  heuristicScore(grid, aiPlayer, humanPlayer) {
    let score = 0;
    const centerCol = Math.floor(this.cols / 2);

    // contrôle du centre
    let centerAI = 0;
    let centerHuman = 0;
    for (let r = 0; r < this.rows; r++) {
      if (grid[r][centerCol] === aiPlayer) centerAI++;
      if (grid[r][centerCol] === humanPlayer) centerHuman++;
    }
    score += centerAI * 12;
    score -= centerHuman * 12;

    // horizontales
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c <= this.cols - 4; c++) {
        const window = [grid[r][c], grid[r][c + 1], grid[r][c + 2], grid[r][c + 3]];
        score += this.evaluateWindow(window, aiPlayer, humanPlayer);
      }
    }

    // verticales
    for (let c = 0; c < this.cols; c++) {
      for (let r = 0; r <= this.rows - 4; r++) {
        const window = [grid[r][c], grid[r + 1][c], grid[r + 2][c], grid[r + 3][c]];
        score += this.evaluateWindow(window, aiPlayer, humanPlayer);
      }
    }

    // diagonales \
    for (let r = 0; r <= this.rows - 4; r++) {
      for (let c = 0; c <= this.cols - 4; c++) {
        const window = [grid[r][c], grid[r + 1][c + 1], grid[r + 2][c + 2], grid[r + 3][c + 3]];
        score += this.evaluateWindow(window, aiPlayer, humanPlayer);
      }
    }

    // diagonales /
    for (let r = 3; r < this.rows; r++) {
      for (let c = 0; c <= this.cols - 4; c++) {
        const window = [grid[r][c], grid[r - 1][c + 1], grid[r - 2][c + 2], grid[r - 3][c + 3]];
        score += this.evaluateWindow(window, aiPlayer, humanPlayer);
      }
    }

    return score;
  }
  minimax(grid, depth, alpha, beta, maximizingPlayer, aiPlayer, humanPlayer) {
    const terminal = this.terminalState(grid);

    if (terminal.over) {
      if (terminal.winner === aiPlayer) {
        return { score: 1000000000 + depth, move: null };
      }
      if (terminal.winner === humanPlayer) {
        return { score: -1000000000 - depth, move: null };
      }
      return { score: 0, move: null };
    }

    if (depth === 0) {
      return { score: this.scorePosition(grid, aiPlayer), move: null };
    }

    let moves = this.validColumns(grid);
    const center = Math.floor(this.cols / 2);

    moves.sort((a, b) => Math.abs(a - center) - Math.abs(b - center));

    let bestMove = moves.length ? moves[0] : null;

    if (maximizingPlayer) {
      let maxEval = -Infinity;

      for (const col of moves) {
        const nextGrid = this.copyGrid(grid);
        const pos = this.dropInGrid(nextGrid, col, aiPlayer);
        if (!pos) continue;

        let result;

        const aiWin = this.checkWinCells(nextGrid, pos[0], pos[1], aiPlayer);
        if (aiWin.length) {
          result = { score: 1000000000 + depth, move: col };
        } else {
          let oppCanWin = false;
          const oppMoves = this.validColumns(nextGrid);

          for (const oppCol of oppMoves) {
            const testGrid = this.copyGrid(nextGrid);
            const oppPos = this.dropInGrid(testGrid, oppCol, humanPlayer);
            if (!oppPos) continue;

            const oppWin = this.checkWinCells(testGrid, oppPos[0], oppPos[1], humanPlayer);
            if (oppWin.length) {
              oppCanWin = true;
              break;
            }
          }

          if (oppCanWin) {
            result = { score: -999999999, move: col };
          } else {
            result = this.minimax(nextGrid, depth - 1, alpha, beta, false, aiPlayer, humanPlayer);
          }
        }

        if (result.score > maxEval) {
          maxEval = result.score;
          bestMove = col;
        }

        alpha = Math.max(alpha, maxEval);
        if (beta <= alpha) break;
      }

      return { score: maxEval, move: bestMove };
    } else {
      let minEval = Infinity;

      for (const col of moves) {
        const nextGrid = this.copyGrid(grid);
        const pos = this.dropInGrid(nextGrid, col, humanPlayer);
        if (!pos) continue;

        let result;

        const humanWin = this.checkWinCells(nextGrid, pos[0], pos[1], humanPlayer);
        if (humanWin.length) {
          result = { score: -1000000000 - depth, move: col };
        } else {
          let aiCanWin = false;
          const aiMoves = this.validColumns(nextGrid);

          for (const aiCol of aiMoves) {
            const testGrid = this.copyGrid(nextGrid);
            const aiPos = this.dropInGrid(testGrid, aiCol, aiPlayer);
            if (!aiPos) continue;

            const aiWin = this.checkWinCells(testGrid, aiPos[0], aiPos[1], aiPlayer);
            if (aiWin.length) {
              aiCanWin = true;
              break;
            }
          }

          if (aiCanWin) {
            result = { score: 999999999, move: col };
          } else {
            result = this.minimax(nextGrid, depth - 1, alpha, beta, true, aiPlayer, humanPlayer);
          }
        }

        if (result.score < minEval) {
          minEval = result.score;
          bestMove = col;
        }

        beta = Math.min(beta, minEval);
        if (beta <= alpha) break;
      }

      return { score: minEval, move: bestMove };
    }
  }
  hasImmediateWinningMove(grid, player) {
    const moves = this.validColumns(grid);

    for (const col of moves) {
      const g2 = this.copyGrid(grid);
      const pos = this.dropInGrid(g2, col, player);
      if (!pos) continue;

      const winCells = this.checkWinCells(g2, pos[0], pos[1], player);
      if (winCells.length) return true;
    }

    return false;
  }

  findImmediateBestMove(grid, player) {
    const opponent = this.other(player);
    const moves = this.validColumns(grid);

    // 1. gagner tout de suite
    for (const col of moves) {
      const g = this.copyGrid(grid);
      const pos = this.dropInGrid(g, col, player);
      if (!pos) continue;
      if (this.checkWinCells(g, pos[0], pos[1], player).length) {
        return col;
      }
    }

    // 2. bloquer l'adversaire s'il gagne au prochain coup
    for (const col of moves) {
      const g = this.copyGrid(grid);
      const pos = this.dropInGrid(g, col, opponent);
      if (!pos) continue;
      if (this.checkWinCells(g, pos[0], pos[1], opponent).length) {
        return col;
      }
    }

    return null;
  }
  renderAiScores() {
    if (this.online.enabled) {
      this.setScoresBlank();
      return;
    }

    if (this.el.aiMode.value !== "minimax") {
      this.setScoresBlank();
      return;
    }

    if (this.robotThinking || !this.board) return;

    const depth = this.clampInt(this.el.depth.value, 1, 8, 4);
    const grid0 = this.copyGrid(this.board);
    const player = this.current;
    const opponent = this.other(player);
    const valids = new Set(this.validColumns(grid0));

    for (let c = 0; c < this.cols; c++) {
      this.scoreEls[c].textContent = valids.has(c) ? "..." : "N/A";
    }

    const colsList = [...Array(this.cols).keys()];
    const step = (i = 0) => {
      if (this.el.aiMode.value !== "minimax") return;
      if (this.robotThinking || this.gameOver) return;
      if (i >= colsList.length) return;

      const col = colsList[i];

      if (!valids.has(col)) {
        this.scoreEls[col].textContent = "N/A";
      } else {
        const g2 = this.copyGrid(grid0);
        const pos = this.dropInGrid(g2, col, player);

        if (!pos) {
          this.scoreEls[col].textContent = "N/A";
        } else {
          const immediateWin = this.checkWinCells(g2, pos[0], pos[1], player).length > 0;

          if (immediateWin) {
            this.scoreEls[col].textContent = "1000000000";
          } else {
            const result = this.minimax(g2, depth - 1, -1e18, 1e18, false, player, opponent);
            this.scoreEls[col].textContent = String(Math.trunc(result.score));
          }
        }
      }

      this.schedule(() => step(i + 1), 30);
    };

    step(0);
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

    // ✅ ONLINE: on envoie le coup au serveur
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

    const mode = parseInt(this.el.mode.value, 10);
    if (!this.isHumanTurn(mode, this.current)) return;

    const cont = this.playMove(col, this.current);
    if (!cont) return;

    if ((mode === 0 || mode === 1) && !this.isHumanTurn(mode, this.current) && !this.gameOver) {
      this.clearTimers();
      this.schedule(() => this.robotStep(), 140);
    }
  }

  robotRandomColumn(board) {
    const cols = this.validColumns(board);
    if (!cols.length) return null;
    return cols[Math.floor(Math.random() * cols.length)];
  }

  robotStep() {
    if (this.online.enabled) return;
    if (this.gameOver) return;
    if (this.robotThinking || this.aiLock) return;

    const mode = parseInt(this.el.mode.value, 10);
    if (this.viewIndex !== this.moves.length) return;

    if (this.isHumanTurn(mode, this.current)) {
      this.setButtonsState(true);
      return;
    }

    this.aiLock = true;
    this.setButtonsState(false);

    if (this.el.aiMode.value === "random") {
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

      if (mode === 0 && !this.gameOver) {
        this.clearTimers();
        this.schedule(() => this.robotStep(), 250);
      } else {
        this.setButtonsState(true);
      }
      return;
    }

    const depth = this.clampInt(this.el.depth.value, 1, 8, 4);
    this.robotPlayMinimaxAsync(depth);
  }

  robotPlayMinimaxAsync(depth) {
    if (this.online.enabled) {
      this.aiLock = false;
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

    const grid0 = this.copyGrid(this.board);
    const player = this.current;
    const opponent = this.other(player);
    const valids = new Set(this.validColumns(grid0));

    for (let c = 0; c < this.cols; c++) {
      this.scoreEls[c].textContent = valids.has(c) ? "..." : "N/A";
    }

    const center = Math.floor(this.cols / 2);
    const colList = [...Array(this.cols).keys()].sort((a, b) => Math.abs(a - center) - Math.abs(b - center));
    const state = { bestCol: null, bestVal: -1e18 };

    const step = (i = 0) => {
      if (this.gameOver) {
        this.robotThinking = false;
        this.aiLock = false;
        this.updateStatus();
        return;
      }

      if (i >= colList.length) {
        let bestCol = state.bestCol;
        const validArr = [...valids];

        if (bestCol === null && validArr.length) {
          bestCol = validArr[Math.floor(Math.random() * validArr.length)];
        }

        this.robotThinking = false;
        this.updateStatus();

        if (bestCol !== null) {
          this.playMove(bestCol, player);
        }

        this.aiLock = false;

        const mode = parseInt(this.el.mode.value, 10);
        if (mode === 0 && !this.gameOver) {
          this.clearTimers();
          this.schedule(() => this.robotStep(), 250);
        } else {
          this.setButtonsState(true);
        }
        return;
      }

      const col = colList[i];

      if (!valids.has(col)) {
        this.scoreEls[col].textContent = "N/A";
        this.schedule(() => step(i + 1), 18);
        return;
      }

      const g2 = this.copyGrid(grid0);
      const pos = this.dropInGrid(g2, col, player);

      let val = -1e18;

      if (pos) {
        const immediateWin = this.checkWinCells(g2, pos[0], pos[1], player).length > 0;

        if (immediateWin) {
          val = 1000000000;
        } else {
          const result = this.minimax(g2, depth - 1, -1e18, 1e18, false, player, opponent);
          val = result.score;
        }
      }

      this.scoreEls[col].textContent = String(Math.trunc(val));

      if (val > state.bestVal) {
        state.bestVal = val;
        state.bestCol = col;
      }

      this.schedule(() => step(i + 1), 26);
    };

    this.clearTimers();
    step(0);
  }
  afterStateChange(triggerRobot = true) {
    this.drawBoard();
    this.updateStatus();
    this.renderAiScores();
    this.updateReplayUI();

    if (this.gameOver) {
      this.setButtonsState(false);
      return;
    }

    const mode = parseInt(this.el.mode.value, 10);
    this.setButtonsState(!this.robotThinking && !this.aiLock && this.isHumanTurn(mode, this.current));

    if (this.online.enabled) return;

    if (triggerRobot && !this.robotThinking && !this.aiLock && !this.gameOver) {
      if (!this.isHumanTurn(mode, this.current)) {
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

    this.rebuildColumnWidgets();
    this.afterStateChange(true);
    this.resizeCanvasReliable();
  }

  // ===== SAVE/LOAD JSON
  buildSavePayload(saveName) {
    return {
      save_name: saveName,
      rows: this.rows,
      cols: this.cols,
      starting_color: this.startingColor,
      mode: parseInt(this.el.mode.value, 10),
      game_index: this.gameIndex,
      moves: this.moves,
      view_index: this.viewIndex,
      ai_mode: this.el.aiMode.value,
      ai_depth: this.clampInt(this.el.depth.value, 1, 8, 4),
      player_red: this.getNameForToken(this.RED),
      player_yellow: this.getNameForToken(this.YELLOW),
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
        this.el.loadJson.value = "";
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

    const rows = data.rows,
      cols = data.cols,
      start = data.starting_color;
    const moves = data.moves ?? [];
    const viewIndex = data.view_index ?? 0;

    if (!Number.isInteger(rows) || rows < 4 || rows > 20) throw new Error("rows invalide");
    if (!Number.isInteger(cols) || cols < 4 || cols > 20) throw new Error("cols invalide");
    if (start !== this.RED && start !== this.YELLOW) throw new Error("starting_color invalide");
    if (!Array.isArray(moves) || moves.some((x) => !Number.isInteger(x))) throw new Error("moves invalide");
    if (!Number.isInteger(viewIndex) || viewIndex < 0 || viewIndex > moves.length) throw new Error("view_index invalide");

    if (typeof data.player_red === "string" && data.player_red.trim()) {
      this.setNameForToken(this.RED, data.player_red.trim());
      this.el.nameR.textContent = data.player_red.trim();
    }
    if (typeof data.player_yellow === "string" && data.player_yellow.trim()) {
      this.setNameForToken(this.YELLOW, data.player_yellow.trim());
      this.el.nameY.textContent = data.player_yellow.trim();
    }

    this.rows = rows;
    this.cols = cols;
    this.startingColor = start;

    this.el.mode.value = String(Number.isInteger(data.mode) ? data.mode : 2);
    this.gameIndex = Number.isInteger(data.game_index) ? data.game_index : 1;
    this.el.aiMode.value = data.ai_mode === "minimax" ? "minimax" : "random";
    this.el.depth.value = String(this.clampInt(data.ai_depth, 1, 8, 4));

    if (typeof data.save_name === "string" && data.save_name.trim()) {
      this.el.saveName.value = data.save_name.trim();
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

    this.current = this.tokenForMoveIndex(this.viewIndex);

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

  // ===== DB save/load (optionnel)
  computeConfidence(mode, aiMode, aiDepth) {
    mode = this.clampInt(mode, 0, 2, 2);
    aiMode = (aiMode || "random").toLowerCase();
    aiDepth = this.clampInt(aiDepth, 1, 8, 4);

    if (mode === 2) return 5;
    if (aiMode === "random") return 1;
    if (aiMode === "minimax") {
      if (aiDepth <= 2) return 2;
      if (aiDepth <= 4) return 3;
      if (aiDepth <= 6) return 4;
      return 5;
    }
    return 1;
  }

  buildGamePayloadForDB(saveName) {
    const game_mode = parseInt(this.el.mode.value, 10);
    const ai_mode = (this.el.aiMode.value || "random").toLowerCase();
    const ai_depth = this.clampInt(this.el.depth.value, 1, 8, 4);
    const status = this.gameOver ? "completed" : "in_progress";

    let winner = null;
    if (this.gameOver) {
      if (this.winner === this.RED) winner = "R";
      else if (this.winner === this.YELLOW) winner = "Y";
      else winner = "D";
    }

    const distinct_cols = this.moves.length ? new Set(this.moves).size : 0;
    const confidence = this.computeConfidence(game_mode, ai_mode, ai_depth);

    return {
      user_id: 1,
      save_name: saveName,
      game_index: this.gameIndex,
      rows_count: this.rows,
      cols_count: this.cols,
      starting_color: this.startingColor,
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
    if (this.online.enabled) {
      alert("Online: sauvegarde BD désactivée (quitte Online si tu veux sauvegarder).");
      return;
    }

    const saveName = this.getSaveNameOrDefault();
    try {
      const payload = this.buildGamePayloadForDB(saveName);
      const out = await this.apiFetch("/games", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const gid = out?.game_id ?? out?.id ?? "(?)";
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
      const list = await this.apiFetch("/games", { method: "GET" });

      if (!Array.isArray(list) || list.length === 0) {
        alert("Base vide (aucune partie).");
        return;
      }

      const pickedId = await this.showDbLoadDialog(list);
      if (!pickedId) return;

      const g = await this.apiFetch(`/games/${pickedId}`, { method: "GET" });

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
      alert(`✅ Partie chargée depuis la base !\nID: ${pickedId}\nNom: ${g.save_name || ""}`);

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
}

// BOOT
window.addEventListener("DOMContentLoaded", () => {
  const app = new Connect4Web();
  requestAnimationFrame(() => requestAnimationFrame(() => app.resizeCanvasReliable()));
});