"""
bga_scraper_ui.py
=================================================================
Interface de scraping BGA — Mission 4.1

Fonctionnalités :
  • Entrer un numéro de table BGA
  • Scraper le /gamereview via Selenium (sans headless → tu restes connecté)
  • Importer automatiquement en DB PostgreSQL (anti-doublon inclus)
  • Visualiser la partie pas-à-pas sur un vrai plateau Puissance 4
  • Lancer game.py avec la partie chargée (bouton "Ouvrir dans le jeu")
=================================================================
"""

import json
import re
import threading
import time
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ── Selenium (optionnel : si absent on désactive le scrape) ─────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import os
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

# ── psycopg2 (optionnel : si absent on désactive l'import DB) ───────────────
try:
    import psycopg2

    PSYCOPG2_OK = True
except ImportError:
    PSYCOPG2_OK = False

# =================================================================
# CONFIG DB  (même que game.py / bga_import.py)
# =================================================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "puissance4_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", "5432")),
}

BGA_BASE = "https://boardgamearena.com"

# Fichier de tracking (même que bga_to_db.py)
SCRAPED_TABLES_FILE = Path(__file__).resolve().parent / "scraped_tables.json"

# =================================================================
# COULEURS UI
# =================================================================
COLOR_BG_BOARD = "#00478e"
COLOR_EMPTY = "#e3f2fd"
COLOR_RED = "#d32f2f"
COLOR_YELLOW = "#fbc02d"
COLOR_WIN = "#00c853"
COLOR_LAST_MOVE = "#ffffff"  # contour blanc = dernier coup


# =================================================================
# HELPERS DB
# =================================================================


def db_ensure_table(conn):
    """Crée / patche saved_games si besoin."""
    sql = """
    CREATE TABLE IF NOT EXISTS saved_games (
        id SERIAL PRIMARY KEY,
        save_name VARCHAR(100),
        rows INTEGER NOT NULL DEFAULT 9,
        cols INTEGER NOT NULL DEFAULT 9,
        starting_color CHAR(1) NOT NULL DEFAULT 'R'
            CHECK (starting_color IN ('R','Y')),
        mode INTEGER NOT NULL DEFAULT 2
            CHECK (mode IN (0,1,2)),
        game_index INTEGER NOT NULL DEFAULT 1,
        moves JSONB NOT NULL DEFAULT '[]'::jsonb,
        view_index INTEGER NOT NULL DEFAULT 0,
        ai_mode VARCHAR(20) NOT NULL DEFAULT 'bga',
        ai_depth INTEGER NOT NULL DEFAULT 4,
        save_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    ALTER TABLE saved_games
        ADD COLUMN IF NOT EXISTS confidence INTEGER NOT NULL DEFAULT 1
        CHECK (confidence BETWEEN 0 AND 5);
    ALTER TABLE saved_games
        ADD COLUMN IF NOT EXISTS distinct_cols INTEGER NOT NULL DEFAULT 0
        CHECK (distinct_cols BETWEEN 0 AND 20);
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def db_insert_game(
    conn, table_id: str, moves_0: list[int], rows: int, cols: int
) -> tuple[int, bool]:
    """
    Insère la partie dans saved_games.
    Retourne (id, is_new).
    is_new=False si doublon détecté (mêmes moves+taille).
    """
    moves_json = json.dumps(moves_0)
    save_name = f"BGA_{table_id}"
    distinct = len(set(moves_0))

    # anti-doublon
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM saved_games WHERE rows=%s AND cols=%s AND moves=%s::jsonb LIMIT 1",
            (rows, cols, moves_json),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), False

        cur.execute(
            """
            INSERT INTO saved_games
              (save_name, rows, cols, starting_color, mode, game_index,
               moves, view_index, ai_mode, ai_depth, confidence, distinct_cols, save_date)
            VALUES (%s,%s,%s,'R',2,1, %s::jsonb, %s,'bga',4,3,%s, NOW())
            RETURNING id
            """,
            (save_name, rows, cols, moves_json, len(moves_0), distinct),
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    return int(new_id), True


# =================================================================
# HELPERS SCRAPING
# =================================================================


def load_scraped_tracking() -> dict:
    if SCRAPED_TABLES_FILE.exists():
        try:
            d = json.loads(SCRAPED_TABLES_FILE.read_text("utf-8"))
            d.setdefault("scraped", [])
            d.setdefault("imported", [])
            d.setdefault("failed", {})
            return d
        except Exception:
            pass
    return {"scraped": [], "imported": [], "failed": {}}


def save_scraped_tracking(data: dict):
    try:
        SCRAPED_TABLES_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), "utf-8"
        )
    except Exception:
        pass


def make_driver() -> "webdriver.Chrome":
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(60)
    return drv


SIZE_RE = re.compile(r"(\d{1,2})\s*[x×]\s*(\d{1,2})", re.IGNORECASE)


def detect_size(text: str) -> tuple[int, int] | None:
    if not text:
        return None
    lo = text.lower()
    if "9x9" in lo or "9×9" in lo:
        return (9, 9)
    for line in text.splitlines():
        ll = line.lower()
        if any(
            k in ll for k in ("board size", "taille plateau", "grid size", "grille")
        ):
            m = SIZE_RE.search(line)
            if m:
                r, c = int(m.group(1)), int(m.group(2))
                if 4 <= r <= 20 and 4 <= c <= 20:
                    return (r, c)
    return None


def scrape_gamereview(driver, table_id: str, log_fn) -> tuple[list[int], int, int]:
    """
    Scrape /gamereview et retourne (moves_0based, rows, cols).
    moves_0based : liste d'entiers 0-indexed.
    """
    url = f"{BGA_BASE}/gamereview?table={table_id}"
    log_fn(f"🌐 Ouverture de {url}")
    driver.get(url)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(2)

    page_text = driver.find_element(By.TAG_NAME, "body").text
    size = detect_size(page_text)
    rows, cols = size if size else (9, 9)
    log_fn(f"📏 Taille plateau détectée : {rows}×{cols}")

    # Pattern FR : "Joueur place un pion dans la colonne N"
    pattern = re.compile(
        r"^.+?\s+place[zr]?\s+un\s+pion\s+dans\s+la\s+colonne\s+(\d+)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    raw_cols = [int(m.group(1)) for m in pattern.finditer(page_text)]

    if not raw_cols:
        log_fn("⚠️  Pattern FR non trouvé — tentative EN…")
        pattern_en = re.compile(
            r"^.+?\s+drops?\s+(?:a\s+)?(?:piece|token|disc)\s+(?:in(?:to)?\s+)?(?:column\s+)?(\d+)\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        raw_cols = [int(m.group(1)) for m in pattern_en.finditer(page_text)]

    if not raw_cols:
        raise ValueError("Aucun coup trouvé dans la page gamereview.")

    # Normalisation → 0-based
    mn, mx = min(raw_cols), max(raw_cols)
    if mn >= 1 and mx <= cols:
        moves_0 = [c - 1 for c in raw_cols]
        log_fn(f"🔢 Colonnes 1-based → converties en 0-based")
    else:
        moves_0 = raw_cols
        log_fn(f"🔢 Colonnes déjà 0-based")

    log_fn(f"✅ {len(moves_0)} coups extraits")
    return moves_0, rows, cols


# =================================================================
# LOGIQUE PLATEAU (pour visualisation — autonome, pas d'import game.py)
# =================================================================
EMPTY = "."
RED = "R"
YELLOW = "Y"


def make_board(rows, cols):
    return [[EMPTY] * cols for _ in range(rows)]


def drop(board, col, token):
    rows = len(board)
    for r in range(rows - 1, -1, -1):
        if board[r][col] == EMPTY:
            board[r][col] = token
            return (r, col)
    return None


def check_win_cells(board, r0, c0, token):
    rows, cols = len(board), len(board[0])
    for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
        cells = [(r0, c0)]
        r, c = r0 + dr, c0 + dc
        while 0 <= r < rows and 0 <= c < cols and board[r][c] == token:
            cells.append((r, c))
            r += dr
            c += dc
        r, c = r0 - dr, c0 - dc
        while 0 <= r < rows and 0 <= c < cols and board[r][c] == token:
            cells.insert(0, (r, c))
            r -= dr
            c -= dc
        if len(cells) >= 4:
            return cells[:4]
    return []


def compute_board_at(moves_0, step, rows, cols, starting_color="R"):
    """Retourne (board, last_pos, last_token, win_cells)."""
    board = make_board(rows, cols)
    last_pos = None
    last_token = None
    win_cells = []
    current = starting_color
    for i in range(step):
        col = moves_0[i]
        last_pos = drop(board, col, current)
        last_token = current
        current = YELLOW if current == RED else RED
    if last_pos and last_token:
        win_cells = check_win_cells(board, last_pos[0], last_pos[1], last_token)
    return board, last_pos, last_token, win_cells


# =================================================================
# FENÊTRE PRINCIPALE
# =================================================================


class BGAScraperUI(tk.Tk):

    CELL_SIZE = 56  # px par cellule (canvas)
    PAD = 18

    def __init__(self):
        super().__init__()
        self.title("🔍 BGA Scraper — Puissance 4")
        self.geometry("1050x760")
        self.resizable(True, True)
        self.configure(bg="#1a1a2e")

        # État courant
        self.moves_0: list[int] = []
        self.rows: int = 9
        self.cols: int = 9
        self.step: int = 0  # coup affiché (0 = plateau vide)
        self.db_game_id: int | None = None
        self.driver = None
        self._driver_lock = threading.Lock()
        self._chrome_ready = False  # True une fois connecté à BGA

        self._build_ui()
        self._render_board()

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#1a1a2e")
        style.configure(
            "TLabel", background="#1a1a2e", foreground="#e0e0e0", font=("Segoe UI", 10)
        )
        style.configure(
            "Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#64b5f6"
        )
        style.configure(
            "Status.TLabel", font=("Segoe UI", 10, "italic"), foreground="#a5d6a7"
        )
        style.configure(
            "Warn.TLabel", font=("Segoe UI", 10, "italic"), foreground="#ef9a9a"
        )
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        # ── TOP BAR ────────────────────────────────────────────────────
        top = ttk.Frame(self, padding=(14, 10, 14, 6))
        top.pack(fill=tk.X)

        ttk.Label(top, text="🔍  BGA Scraper", style="Title.TLabel").pack(side=tk.LEFT)

        # numéro de table
        ttk.Label(top, text="   Table BGA :").pack(side=tk.LEFT)
        self.table_var = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.table_var, width=16, font=("Segoe UI", 12))
        e.pack(side=tk.LEFT, padx=(4, 8))
        e.bind("<Return>", lambda _: self._start_scrape())

        self.btn_scrape = ttk.Button(
            top,
            text="⬇  Scraper & Importer",
            command=self._start_scrape,
            style="Accent.TButton",
        )
        self.btn_scrape.pack(side=tk.LEFT, padx=4)

        self.btn_connect = ttk.Button(
            top, text="🔐 Ouvrir Chrome / Se connecter", command=self._confirm_connected
        )
        self.btn_connect.pack(side=tk.LEFT, padx=4)

        self.btn_open = ttk.Button(
            top,
            text="🎮  Ouvrir dans le jeu",
            command=self._open_in_game,
            state=tk.DISABLED,
        )
        self.btn_open.pack(side=tk.LEFT, padx=4)

        self.btn_quit = ttk.Button(top, text="✖ Fermer", command=self._on_close)
        self.btn_quit.pack(side=tk.RIGHT, padx=4)

        # ── STATUS ─────────────────────────────────────────────────────
        sf = ttk.Frame(self, padding=(14, 0))
        sf.pack(fill=tk.X)
        self.status_var = tk.StringVar(
            value="Entrez un numéro de table BGA et cliquez « Scraper »."
        )
        self.status_lbl = ttk.Label(
            sf, textvariable=self.status_var, style="Status.TLabel"
        )
        self.status_lbl.pack(side=tk.LEFT)

        # ── BODY (plateau gauche + log droite) ─────────────────────────
        body = ttk.Frame(self, padding=(14, 6))
        body.pack(fill=tk.BOTH, expand=True)

        # ---- Plateau ----
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Timeline
        tl = ttk.Frame(left)
        tl.pack(fill=tk.X)

        self.tl_var = tk.StringVar(value="Coup : 0 / 0")
        ttk.Label(tl, textvariable=self.tl_var, width=14).pack(side=tk.LEFT)

        self.slider = ttk.Scale(
            tl, from_=0, to=0, orient=tk.HORIZONTAL, command=self._on_slider
        )
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        ttk.Button(tl, text="⏮", width=3, command=self._step_first).pack(side=tk.LEFT)
        ttk.Button(tl, text="◀", width=3, command=self._step_prev).pack(side=tk.LEFT)
        ttk.Button(tl, text="▶", width=3, command=self._step_next).pack(side=tk.LEFT)
        ttk.Button(tl, text="⏭", width=3, command=self._step_last).pack(side=tk.LEFT)

        self.btn_autoplay = ttk.Button(
            tl, text="▶▶ Auto", width=8, command=self._toggle_autoplay
        )
        self.btn_autoplay.pack(side=tk.LEFT, padx=(6, 0))
        self._autoplay_running = False

        # Canvas plateau
        self.canvas = tk.Canvas(left, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.canvas.bind("<Configure>", lambda _e: self._render_board())

        # Info partie
        self.info_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.info_var, style="Status.TLabel").pack(
            anchor="w"
        )

        # ---- Log ----
        right = ttk.Frame(body, padding=(12, 0, 0, 0))
        right.pack(side=tk.RIGHT, fill=tk.BOTH)

        ttk.Label(right, text="📋 Journal", style="Title.TLabel").pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(
            right,
            width=38,
            height=28,
            font=("Courier New", 9),
            bg="#0d0d1a",
            fg="#b0bec5",
            insertbackground="white",
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(right, text="🗑 Vider le journal", command=self._clear_log).pack(
            anchor="e", pady=(4, 0)
        )

    # ------------------------------------------------------------------
    # LOG
    # ------------------------------------------------------------------

    def _log(self, msg: str, level: str = "INFO"):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        print(f"[{level}] {msg}")

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_status(self, msg: str, warn=False):
        self.status_var.set(msg)
        style = "Warn.TLabel" if warn else "Status.TLabel"
        self.status_lbl.configure(style=style)

    # ------------------------------------------------------------------
    # SCRAPING (thread séparé pour ne pas geler l'UI)
    # ------------------------------------------------------------------

    def _start_scrape(self):
        tid = self.table_var.get().strip()
        if not tid.isdigit():
            messagebox.showerror("Erreur", "Le numéro de table doit être un entier.")
            return
        if not SELENIUM_OK:
            messagebox.showerror(
                "Dépendance manquante",
                "selenium n'est pas installé.\npip install selenium",
            )
            return

        self.btn_scrape.configure(state=tk.DISABLED)
        self.btn_connect.configure(state=tk.DISABLED)
        self._log(f"=== SCRAPE table {tid} ===")

        # Si Chrome n'est pas encore ouvert et connecté, on ouvre d'abord
        if not self._chrome_ready:
            self._set_status(
                "Ouverture de Chrome — connecte-toi à BGA puis clique « Prêt »"
            )
            t = threading.Thread(target=self._open_chrome_thread, daemon=True)
            t.start()
        else:
            # Chrome déjà ouvert et connecté → scrape direct
            self._set_status(f"Scraping de la table {tid}…")
            t = threading.Thread(target=self._scrape_thread, args=(tid,), daemon=True)
            t.start()

    def _open_chrome_thread(self):
        """Ouvre Chrome sur BGA et attend que l'utilisateur se connecte."""
        try:
            self._log("🚀 Lancement de Chrome…")
            with self._driver_lock:
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                self.driver = make_driver()

            self.driver.get(f"{BGA_BASE}/account")
            self._log("🔐 Connecte-toi à BGA dans la fenêtre Chrome.")
            self._log("   Puis clique le bouton  ✅ Prêt  dans cette interface.")

            # Active le bouton "Prêt" dans le thread principal
            self.after(
                0,
                lambda: self.btn_connect.configure(
                    state=tk.NORMAL, text="✅ Connecté — Scraper maintenant"
                ),
            )
            self.after(0, lambda: self.btn_scrape.configure(state=tk.NORMAL))
            self.after(
                0,
                lambda: self._set_status(
                    "Connecte-toi à BGA dans Chrome, puis clique « ✅ Connecté »"
                ),
            )
        except Exception as e:
            self._log(f"❌ Erreur Chrome : {e}")
            self.after(0, lambda: self.btn_scrape.configure(state=tk.NORMAL))
            self.after(0, lambda: self.btn_connect.configure(state=tk.NORMAL))

    def _confirm_connected(self):
        """Appele quand l'utilisateur clique Connecte."""
        tid = self.table_var.get().strip()
        if not tid.isdigit():
            messagebox.showerror("Erreur", "Rentre un numero de table BGA.")
            return

        # Verifie si connecte via cookies ou URL
        connected = False
        if self.driver:
            try:
                cookies = {c["name"]: c["value"] for c in self.driver.get_cookies()}
                connected = any(
                    k in cookies
                    for k in ("TBNSSUserCookie", "account_id", "user_id", "bga_uid")
                )
                if not connected:
                    url = self.driver.current_url
                    connected = "boardgamearena.com" in url and "/account" not in url
                if not connected:
                    try:
                        body_text = self.driver.find_element(By.TAG_NAME, "body").text
                        connected = any(
                            k in body_text.lower()
                            for k in (
                                "my profile",
                                "mon profil",
                                "logout",
                                "se deconnecter",
                                "my account",
                            )
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        if not connected:
            ans = messagebox.askyesno(
                "Connexion non detectee",
                "La connexion BGA n'a pas pu etre verifiee.\n\n"
                "Es-tu bien connecte dans la fenetre Chrome ?\n\n"
                "Oui = Scraper quand meme\n"
                "Non = Annuler",
            )
            if not ans:
                return

        self._chrome_ready = True
        self.btn_connect.configure(state=tk.DISABLED, text="Connecte")
        self._set_status(f"Scraping de la table {tid}...")
        self._log(f"Connexion confirmee - lancement du scrape pour table {tid}")
        t = threading.Thread(target=self._scrape_thread, args=(tid,), daemon=True)
        t.start()

    def _scrape_thread(self, tid: str):
        """Tourne dans un thread secondaire."""
        tracking = load_scraped_tracking()

        try:
            # ── 1. Vérif doublon tracking ────────────────────────────
            if tid in tracking["scraped"]:
                self._log(f"ℹ️  Table {tid} déjà dans le tracking — vérification DB…")
                # Essaie de charger depuis la DB en priorité
                loaded = self._try_load_from_db_by_name(f"BGA_{tid}", tid)
                if loaded:
                    # Trouvée en DB : pas besoin de re-scraper
                    self.after(0, lambda: self.btn_scrape.configure(state=tk.NORMAL))
                    return
                # Absente de la DB malgré le tracking → on re-scrape
                self._log(f"⚠️  Absente de la DB — re-scrape forcé pour la table {tid}.")

            # ── 2. Scrape gamereview (Chrome déjà ouvert et connecté) ──
            moves_0, rows, cols = scrape_gamereview(self.driver, tid, self._log)

            # ── 5. Marquer dans tracking ─────────────────────────────
            if tid not in tracking["scraped"]:
                tracking["scraped"].append(tid)
            save_scraped_tracking(tracking)

            # ── 6. Import DB ─────────────────────────────────────────
            db_id = None
            is_new = False
            if PSYCOPG2_OK:
                try:
                    self._log("💾 Connexion PostgreSQL…")
                    conn = psycopg2.connect(**DB_CONFIG)
                    db_ensure_table(conn)
                    db_id, is_new = db_insert_game(conn, tid, moves_0, rows, cols)
                    conn.close()
                    if is_new:
                        self._log(f"✅ Partie importée en DB  (id={db_id})")
                        tracking["imported"].append(tid)
                    else:
                        self._log(f"♻️  Doublon DB détecté — id existant = {db_id}")
                    save_scraped_tracking(tracking)
                except Exception as e:
                    self._log(f"❌ Erreur DB : {e}")
            else:
                self._log("⚠️  psycopg2 non disponible — import DB ignoré.")

            # ── 7. Mise à jour de l'UI (thread principal) ────────────
            def _update_ui():
                self.moves_0 = moves_0
                self.rows = rows
                self.cols = cols
                self.step = len(moves_0)  # affiche la partie terminée par défaut
                self.db_game_id = db_id
                # Met à jour le slider AVANT le rendu
                self.slider.configure(from_=0, to=len(moves_0))
                self.slider.set(len(moves_0))
                self._sync_timeline_label()
                self.btn_open.configure(state=tk.NORMAL)
                lbl = f"Table {tid} — {rows}×{cols} — {len(moves_0)} coups"
                if db_id:
                    lbl += f"  |  DB id={db_id}" + (" ✨" if is_new else " (doublon)")
                self.info_var.set(lbl)
                self._set_status(f"✅ Table {tid} chargée ({len(moves_0)} coups).")
                self.btn_scrape.configure(state=tk.NORMAL)
                # Force le redimensionnement du canvas PUIS redessine
                self.update_idletasks()
                self._render_board()
                messagebox.showinfo(
                    "Succès",
                    f"Table BGA {tid} chargée !\n"
                    f"  Taille : {rows}×{cols}\n"
                    f"  Coups  : {len(moves_0)}\n"
                    f"  DB id  : {db_id if db_id else 'N/A'}"
                    + ("\n  (déjà présente)" if not is_new and db_id else ""),
                )

            self.after(0, _update_ui)

        except Exception as exc:
            err = str(exc)
            self._log(f"❌ Erreur scraping : {err}")
            tracking["failed"][tid] = err
            save_scraped_tracking(tracking)
            self.after(0, lambda: self._set_status(f"Erreur : {err}", warn=True))
            self.after(0, lambda: messagebox.showerror("Erreur scraping", err))
            self.after(0, lambda: self.btn_scrape.configure(state=tk.NORMAL))

    def _try_load_from_db_by_name(self, save_name: str, tid: str) -> bool:
        """
        Charge une partie deja en DB (par save_name) pour la visualiser.
        Retourne True si trouvee et chargee, False sinon.
        """
        if not PSYCOPG2_OK:
            return False
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                # Essaie d'abord avec le schéma rows/cols (game.py local)
                try:
                    cur.execute(
                        "SELECT id, rows, cols, moves FROM saved_games "
                        "WHERE save_name=%s ORDER BY save_date DESC LIMIT 1",
                        (save_name,),
                    )
                except Exception:
                    # Fallback schéma rows_count/cols_count (app.py Render)
                    cur.execute(
                        "SELECT game_id, rows_count, cols_count, moves FROM saved_games "
                        "WHERE save_name=%s ORDER BY created_at DESC LIMIT 1",
                        (save_name,),
                    )
                row = cur.fetchone()
            conn.close()
            if not row:
                return False
            db_id, rows, cols, moves_raw = row
            moves_0 = (
                json.loads(moves_raw) if isinstance(moves_raw, str) else list(moves_raw)
            )
            self._log(f"OK Table {tid} trouvee en DB (id={db_id}) — chargement direct.")

            def _update():
                self.moves_0 = moves_0
                self.rows = rows
                self.cols = cols
                self.step = len(moves_0)  # affiche la partie terminée par défaut
                self.db_game_id = db_id
                self.slider.configure(from_=0, to=len(moves_0))
                self.slider.set(len(moves_0))
                self._sync_timeline_label()
                self.btn_open.configure(state=tk.NORMAL)
                self.info_var.set(
                    f"Table {tid} — {rows}x{cols} — {len(moves_0)} coups | DB id={db_id}"
                )
                self._set_status(f"Table {tid} rechargee depuis la DB.")
                self.update_idletasks()
                self._render_board()

            self.after(0, _update)
            return True

        except Exception as e:
            self._log(f"Erreur Lecture DB : {e}")
            return False

    # ------------------------------------------------------------------
    # TIMELINE / NAVIGATION
    # ------------------------------------------------------------------

    def _sync_timeline_label(self):
        total = len(self.moves_0)
        self.tl_var.set(f"Coup : {self.step} / {total}")

    def _on_slider(self, v):
        try:
            idx = int(float(v) + 0.5)
        except Exception:
            return
        idx = max(0, min(len(self.moves_0), idx))
        if idx != self.step:
            self.step = idx
            self._sync_timeline_label()
            self._render_board()

    def _step_first(self):
        self._go_to(0)

    def _step_prev(self):
        self._go_to(max(0, self.step - 1))

    def _step_next(self):
        self._go_to(min(len(self.moves_0), self.step + 1))

    def _step_last(self):
        self._go_to(len(self.moves_0))

    def _go_to(self, idx: int):
        self.step = max(0, min(len(self.moves_0), idx))
        self.slider.set(self.step)
        self._sync_timeline_label()
        self._render_board()

    # ── Autoplay ─────────────────────────────────────────────────────

    def _toggle_autoplay(self):
        if self._autoplay_running:
            self._autoplay_running = False
            self.btn_autoplay.configure(text="▶▶ Auto")
        else:
            if not self.moves_0:
                return
            if self.step >= len(self.moves_0):
                self._go_to(0)
            self._autoplay_running = True
            self.btn_autoplay.configure(text="⏸ Pause")
            self._autoplay_tick()

    def _autoplay_tick(self):
        if not self._autoplay_running:
            return
        if self.step >= len(self.moves_0):
            self._autoplay_running = False
            self.btn_autoplay.configure(text="▶▶ Auto")
            return
        self._go_to(self.step + 1)
        self.after(600, self._autoplay_tick)

    # ------------------------------------------------------------------
    # DESSIN DU PLATEAU
    # ------------------------------------------------------------------

    def _render_board(self):
        cv = self.canvas
        cv.delete("all")

        if not self.moves_0:
            # Placeholder
            cv.create_text(
                cv.winfo_width() // 2 or 400,
                cv.winfo_height() // 2 or 300,
                text="Scrape une table BGA pour voir la partie ici",
                fill="#546e7a",
                font=("Segoe UI", 13, "italic"),
                anchor="center",
            )
            return

        rows, cols = self.rows, self.cols
        board, last_pos, last_token, win_cells = compute_board_at(
            self.moves_0, self.step, rows, cols
        )

        # Calcul taille cellule dynamique
        w = cv.winfo_width() or 500
        h = cv.winfo_height() or 450
        cell = min((w - 2 * self.PAD) // cols, (h - 2 * self.PAD) // rows, 68)
        pad_x = (w - cell * cols) // 2
        pad_y = (h - cell * rows) // 2

        # Fond bleu plateau
        cv.create_rectangle(
            pad_x - 4,
            pad_y - 4,
            pad_x + cols * cell + 4,
            pad_y + rows * cell + 4,
            fill=COLOR_BG_BOARD,
            outline="#003a77",
            width=2,
        )

        radius = cell // 2 - 4
        win_set = set(map(tuple, win_cells))

        for r in range(rows):
            for c in range(cols):
                cx = pad_x + c * cell + cell // 2
                cy = pad_y + r * cell + cell // 2

                token = board[r][c]

                if (r, c) in win_set:
                    fill = COLOR_WIN
                elif token == RED:
                    fill = COLOR_RED
                elif token == YELLOW:
                    fill = COLOR_YELLOW
                else:
                    fill = COLOR_EMPTY

                # Contour spécial = dernier coup joué
                outline_color = (
                    COLOR_LAST_MOVE if (last_pos and (r, c) == last_pos) else "#003a77"
                )
                outline_width = 3 if (last_pos and (r, c) == last_pos) else 1

                cv.create_oval(
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius,
                    fill=fill,
                    outline=outline_color,
                    width=outline_width,
                )

        # Légende du coup en cours
        if self.step > 0 and self.step <= len(self.moves_0):
            token_played = RED if ((self.step - 1) % 2 == 0) else YELLOW
            col_played = self.moves_0[self.step - 1]
            legend = f"Coup {self.step} — {'🔴 Rouge' if token_played==RED else '🟡 Jaune'} — Col. {col_played+1}"
            if win_cells:
                legend += "  🏆 VICTOIRE"
            cv.create_text(
                w // 2,
                pad_y + rows * cell + 16,
                text=legend,
                fill="#e0e0e0",
                font=("Segoe UI", 10, "bold"),
                anchor="n",
            )

    # ------------------------------------------------------------------
    # OUVRIR DANS LE JEU (game.py)
    # ------------------------------------------------------------------

    def _open_in_game(self):
        if not self.moves_0:
            messagebox.showwarning("Aucune partie", "Charge d'abord une table BGA.")
            return

        # On écrit un fichier JSON temporaire que game.py peut charger
        payload = {
            "save_name": f"BGA_{self.table_var.get().strip()}",
            "rows": self.rows,
            "cols": self.cols,
            "starting_color": "R",
            "mode": 2,
            "game_index": 1,
            "moves": self.moves_0,
            "view_index": self.step,
            "ai_mode": "bga",
            "ai_depth": 4,
        }

        tmp_path = Path(__file__).resolve().parent / "_bga_tmp_game.json"
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self._log(f"📂 Partie écrite dans {tmp_path}")
        self._log("🎮 Lancement de game.py…")

        try:
            subprocess.Popen(
                ["python", "game.py", "--load", str(tmp_path)],
                cwd=str(Path(__file__).resolve().parent),
            )
        except FileNotFoundError:
            # Essai avec python3
            try:
                subprocess.Popen(
                    ["python3", "game.py", "--load", str(tmp_path)],
                    cwd=str(Path(__file__).resolve().parent),
                )
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de lancer game.py :\n{e}")
                return

        messagebox.showinfo(
            "game.py lancé",
            "game.py a démarré.\n\n"
            "Dans le jeu :\n"
            "  📂 Charger → Charger depuis un fichier JSON\n"
            f"  → sélectionne  _bga_tmp_game.json\n\n"
            "(ou utilise le chargement DB si la partie a bien été importée)",
        )

    # ------------------------------------------------------------------
    # FERMETURE
    # ------------------------------------------------------------------

    def _on_close(self):
        self._autoplay_running = False
        with self._driver_lock:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
        self.destroy()


# =================================================================
# POINT D'ENTRÉE
# =================================================================

if __name__ == "__main__":
    app = BGAScraperUI()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
