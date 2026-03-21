import os
import re
import time
import random
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ──────────────────────────────────────────────────────────────
# Logique de jeu (minimax avec alpha-beta)
# ──────────────────────────────────────────────────────────────
def other(token: str) -> str:
    return YELLOW if token == RED else RED


def create_board() -> List[List[str]]:
    return [[EMPTY] * COLS for _ in range(ROWS)]


def copy_grid(grid: List[List[str]]) -> List[List[str]]:
    return [row[:] for row in grid]


def valid_columns(board: List[List[str]]) -> List[int]:
    return [c for c in range(COLS) if board[0][c] == EMPTY]


def drop_token(
    board: List[List[str]], col: int, token: str
) -> Optional[Tuple[int, int]]:
    if col < 0 or col >= COLS:
        return None
    if board[0][col] != EMPTY:
        return None
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] == EMPTY:
            board[r][col] = token
            return (r, col)
    return None


def is_draw(board: List[List[str]]) -> bool:
    return all(board[0][c] != EMPTY for c in range(COLS))


def check_win_cells(
    board: List[List[str]], last_row: int, last_col: int, token: str
) -> List[Tuple[int, int]]:
    dirs = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in dirs:
        cells = [(last_row, last_col)]
        r, c = last_row + dr, last_col + dc
        while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == token:
            cells.append((r, c))
            r += dr
            c += dc
        r, c = last_row - dr, last_col - dc
        while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == token:
            cells.insert(0, (r, c))
            r -= dr
            c -= dc
        if len(cells) >= CONNECT_N:
            return cells[:CONNECT_N]
    return []


def terminal_state(grid: List[List[str]]) -> Tuple[bool, Optional[str]]:
    for r in range(ROWS):
        for c in range(COLS):
            p = grid[r][c]
            if p == EMPTY:
                continue
            if c + 3 < COLS and all(grid[r][c + i] == p for i in range(4)):
                return True, p
            if r + 3 < ROWS and all(grid[r + i][c] == p for i in range(4)):
                return True, p
            if (
                r + 3 < ROWS
                and c + 3 < COLS
                and all(grid[r + i][c + i] == p for i in range(4))
            ):
                return True, p
            if (
                r + 3 < ROWS
                and c + 3 < COLS
                and all(grid[r + 3 - i][c + i] == p for i in range(4))
            ):
                return True, p
    if is_draw(grid):
        return True, None
    return False, None


def evaluate_window(window: List[str], player: str) -> int:
    opp = other(player)
    cp = window.count(player)
    co = window.count(opp)
    ce = window.count(EMPTY)

    if cp == 4:
        return 100000
    if co == 4:
        return -100000

    score = 0
    if cp == 3 and ce == 1:
        score += 50
    elif cp == 2 and ce == 2:
        score += 10
    if co == 3 and ce == 1:
        score -= 80
    elif co == 2 and ce == 2:
        score -= 10
    return score


def heuristic_score(grid: List[List[str]], player: str) -> int:
    score = 0
    center = COLS // 2
    score += sum(1 for r in range(ROWS) if grid[r][center] == player) * 6

    for r in range(ROWS):
        for c in range(COLS - 3):
            score += evaluate_window([grid[r][c + i] for i in range(4)], player)

    for c in range(COLS):
        for r in range(ROWS - 3):
            score += evaluate_window([grid[r + i][c] for i in range(4)], player)

    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            score += evaluate_window([grid[r + i][c + i] for i in range(4)], player)

    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            score += evaluate_window([grid[r + 3 - i][c + i] for i in range(4)], player)

    return score


def minimax(
    grid: List[List[str]],
    depth: int,
    alpha: float,
    beta: float,
    maximizing: bool,
    player: str,
) -> float:
    term, winner = terminal_state(grid)
    if term:
        if winner == player:
            return 1_000_000
        if winner == other(player):
            return -1_000_000
        return 0
    if depth == 0:
        return heuristic_score(grid, player)

    moves = valid_columns(grid)
    center = COLS // 2
    moves.sort(key=lambda c: abs(c - center))

    if maximizing:
        best = -(10**18)
        for col in moves:
            g2 = copy_grid(grid)
            _drop_in_grid(g2, col, player)
            val = minimax(g2, depth - 1, alpha, beta, False, player)
            best = max(best, val)
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    else:
        opp = other(player)
        best = 10**18
        for col in moves:
            g2 = copy_grid(grid)
            _drop_in_grid(g2, col, opp)
            val = minimax(g2, depth - 1, alpha, beta, True, player)
            best = min(best, val)
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best


def _drop_in_grid(
    grid: List[List[str]], col: int, token: str
) -> Optional[Tuple[int, int]]:
    for r in range(ROWS - 1, -1, -1):
        if grid[r][col] == EMPTY:
            grid[r][col] = token
            return (r, col)
    return None


def get_winning_move(board: List[List[str]], player: str) -> Optional[int]:
    """
    Vérifie s'il y a un coup gagnant immédiat pour le joueur.
    Retourne la colonne si oui, sinon None.
    """
    for col in valid_columns(board):
        g2 = copy_grid(board)
        pos = _drop_in_grid(g2, col, player)
        if pos and check_win_cells(g2, pos[0], pos[1], player):
            return col
    return None


def choose_move_minimax(
    board: List[List[str]],
    current: str,
    depth: int,
) -> Optional[int]:
    cols = valid_columns(board)
    if not cols:
        return None

    # 1. Priorité : coup gagnant immédiat
    win_col = get_winning_move(board, current)
    if win_col is not None:
        return win_col

    # 2. Bloquer le coup gagnant adverse
    opp = other(current)
    block_col = get_winning_move(board, opp)
    if block_col is not None:
        return block_col

    # 3. Sinon, minimax
    center = COLS // 2
    cols_sorted = sorted(cols, key=lambda c: abs(c - center))
    best_col = cols_sorted[0]
    best_val = -(10**18)
    for col in cols_sorted:
        g2 = copy_grid(board)
        _drop_in_grid(g2, col, current)
        val = minimax(g2, depth - 1, -(10**18), 10**18, False, current)
        if val > best_val:
            best_val = val
            best_col = col
    return best_col


def get_board_from_dom(driver) -> Optional[List[List[str]]]:
    """
    Extrait l'état du plateau depuis le DOM.
    Suppose que les cases sont dans #board .square, avec classes 'red' ou 'yellow'.
    Suppose ordre : rangées de haut en bas, colonnes de gauche à droite.
    """
    js = r"""
    try {
        const squares = document.querySelectorAll('#board .square');
        if (squares.length !== 42) return null;  // 6*7=42
        const grid = Array(6).fill().map(() => Array(7).fill('.'));
        let index = 0;
        for (let r = 0; r < 6; r++) {
            for (let c = 0; c < 7; c++) {
                const square = squares[index++];
                if (square.classList.contains('red')) grid[r][c] = 'R';
                else if (square.classList.contains('yellow')) grid[r][c] = 'Y';
                else grid[r][c] = '.';
            }
        }
        return grid;
    } catch(e) {
        return null;
    }
    """
    try:
        grid = driver.execute_script(js)
        return grid if grid else None
    except Exception:
        return None


# =========================
# DB LAYER (SQLite simple)
# =========================
class DBWriter:
    """
    DB minimaliste pour enregistrer des parties + coups.
    Tu peux remplacer cette classe par ton code (bga_to_db.py) plus tard.
    """

    def __init__(self, db_path="connect4.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games_live (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bga_table_id TEXT,
                game_name TEXT NOT NULL,
                started_at_utc TEXT NOT NULL,
                ended_at_utc TEXT,
                status TEXT NOT NULL DEFAULT 'IN_PROGRESS'
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS moves_live (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                move_index INTEGER NOT NULL,
                player TEXT,              -- "ME" / "OPP" / "UNKNOWN"
                col INTEGER,              -- 0..6 si détecté
                raw TEXT,                 -- dump brut (fallback)
                created_at_utc TEXT NOT NULL,
                UNIQUE(game_id, move_index),
                FOREIGN KEY(game_id) REFERENCES games_live(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    def start_game(self, game_name: str, bga_table_id: str | None):
        started = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO games_live (bga_table_id, game_name, started_at_utc) VALUES (?, ?, ?)",
            (bga_table_id, game_name, started),
        )
        self.conn.commit()
        return cur.lastrowid

    def end_game(self, game_id: int, status: str = "FINISHED"):
        ended = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE games_live SET ended_at_utc=?, status=? WHERE id=?",
            (ended, status, game_id),
        )
        self.conn.commit()

    def insert_move(
        self,
        game_id: int,
        move_index: int,
        player: str,
        col: int | None,
        raw: str | None,
    ):
        created = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO moves_live (game_id, move_index, player, col, raw, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (game_id, move_index, player, col, raw, created),
        )
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


# =========================
# HELPERS (DOM/JS extraction)
# =========================
def extract_table_id_from_url(url: str) -> str | None:
    # Exemples possibles: ...table=123456789 ; .../table?table=...
    m = re.search(r"[?&]table=(\d+)", url)
    return m.group(1) if m else None


def infer_col_from_square_element(el) -> int | None:
    """
    Essaie de déduire la colonne cliquée depuis l'élément DOM.
    Comme les jeux BGA changent souvent, on tente plusieurs patterns.
    """
    try:
        # attributs courants possibles
        for attr in ["data-col", "data-column", "data-x"]:
            v = el.get_attribute(attr)
            if v is not None and str(v).strip().isdigit():
                return int(v)

        cls = el.get_attribute("class") or ""
        # patterns du type col_3 / col3 / column-3
        for pat in [r"col[_-]?(\d+)", r"column[_-]?(\d+)", r"x[_-]?(\d+)"]:
            m = re.search(pat, cls)
            if m:
                return int(m.group(1))

        # parfois l'ID contient la colonne
        _id = el.get_attribute("id") or ""
        for pat in [r"col[_-]?(\d+)", r"column[_-]?(\d+)", r"x[_-]?(\d+)"]:
            m = re.search(pat, _id)
            if m:
                return int(m.group(1))
    except Exception:
        return None

    return None


def try_get_moves_from_bga_js(driver) -> list[dict] | None:
    """
    BGA stocke souvent des infos dans `gameui` (dojo) mais ça dépend du jeu.
    On tente plusieurs chemins possibles.
    Retour attendu: liste de dicts (au minimum {move_index, col, player})
    """
    js = r"""
    try {
        // 1) parfois les coups sont gardés dans une structure interne
        // (ceci dépend complètement de l'implémentation du jeu)
        const cand = [];

        function safePushMove(mi, col, player, raw) {
            if (mi == null) return;
            cand.push({move_index: mi, col: col ?? null, player: player ?? "UNKNOWN", raw: raw ?? null});
        }

        // ---- Tentative A: notifications buffered (rare mais possible)
        if (window.gameui && window.gameui.notifqueue && window.gameui.notifqueue.queue) {
            const q = window.gameui.notifqueue.queue;
            let idx = 0;
            for (const it of q) {
                // it: {type, args, ...} varie beaucoup
                if (it && it.args) {
                    // connectfour: on tente des clés fréquentes
                    const col = (it.args.col ?? it.args.column ?? it.args.x);
                    if (col !== undefined) safePushMove(idx, Number(col), it.args.player ?? "UNKNOWN", JSON.stringify(it.args));
                }
                idx++;
            }
            if (cand.length > 0) return cand;
        }

        // ---- Tentative B: gamedatas (rarement "moves", mais parfois)
        if (window.gameui && window.gameui.gamedatas) {
            const gd = window.gameui.gamedatas;

            if (gd.moves && Array.isArray(gd.moves)) {
                let i = 0;
                for (const mv of gd.moves) {
                    safePushMove(i, Number(mv.col ?? mv.column ?? mv.x), mv.player ?? mv.player_id ?? "UNKNOWN", JSON.stringify(mv));
                    i++;
                }
                if (cand.length > 0) return cand;
            }

            // ---- Tentative C: history/log (encore plus rare)
            if (gd.log && Array.isArray(gd.log)) {
                let i = 0;
                for (const row of gd.log) {
                    // on tente d'extraire "col" d'un texte
                    const s = JSON.stringify(row);
                    const m = s.match(/col[^0-9]*([0-9]+)/i) || s.match(/column[^0-9]*([0-9]+)/i);
                    const col = m ? Number(m[1]) : null;
                    safePushMove(i, col, "UNKNOWN", s);
                    i++;
                }
                if (cand.length > 0) return cand;
            }
        }

        return null;
    } catch(e) {
        return null;
    }
    """
    try:
        res = driver.execute_script(js)
        if isinstance(res, list) and len(res) > 0:
            # normalise
            out = []
            for it in res:
                if not isinstance(it, dict):
                    continue
                mi = it.get("move_index")
                if mi is None:
                    continue
                out.append(
                    {
                        "move_index": int(mi),
                        "col": None if it.get("col") is None else int(it.get("col")),
                        "player": str(it.get("player") or "UNKNOWN"),
                        "raw": it.get("raw"),
                    }
                )
            return out if out else None
    except Exception:
        pass
    return None


# =========================
# BOT
# =========================
class BGABot:
    def __init__(self, chrome_version=144, db_path="connect4.db"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        user_data_path = os.path.join(script_dir, "profile")

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={user_data_path}")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--start-maximized")

        print(f"Launching Chrome v{chrome_version}...")
        self.driver = uc.Chrome(options=options, version_main=chrome_version)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 20)

        self.db = DBWriter(db_path=db_path)
        self.current_game_id = None
        self.current_table_id = None
        self.local_move_index = (
            0  # fallback: index incrémental (au moins pour tes moves)
        )

        # anti-dup insertion quand on lit via JS
        self.last_js_move_index_saved = -1

    def login(self):
        print("Opening BGA... Please log in manually if prompted.")
        self.driver.get("https://en.boardgamearena.com/account")
        login_wait = WebDriverWait(self.driver, 600)
        login_wait.until(lambda d: "account" not in d.current_url)
        print("\n--- LOGIN DETECTED ---")
        time.sleep(2)

    def navigate_to_game(self, game_name="connectfour"):
        url = f"https://boardgamearena.com/gamepanel?game={game_name}"
        print(f"Navigating to: {url}")
        self.driver.get(url)

    def clear_popups(self):
        try:
            popups = self.driver.find_elements(
                By.CSS_SELECTOR, "div[id^='continue_btn_']"
            )
            for popup in popups:
                if popup.is_displayed():
                    print("🏆 Trophy popup detected! Clearing...")
                    self.driver.execute_script("arguments[0].click();", popup)
                    time.sleep(1)
                    self.clear_popups()
        except Exception:
            pass

    def select_realtime_mode(self):
        print("🔄 Entrée dans la boucle de sélection du mode...")
        while True:
            try:
                dropdown_button = self.wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            ".panel-block--buttons__mode-select .bga-dropdown-button",
                        )
                    )
                )

                current_mode_text = (dropdown_button.text or "").upper()
                if (
                    "TEMPS RÉEL" in current_mode_text
                    or "REAL-TIME" in current_mode_text
                ):
                    print("✅ Mode Temps Réel confirmé.")
                    return True

                print(
                    f"🧐 Mode actuel : '{current_mode_text}'. Tentative de basculement..."
                )
                self.driver.execute_script("arguments[0].click();", dropdown_button)
                time.sleep(1.5)

                realtime_option = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, ".bga-dropdown-option-realtime")
                    )
                )
                self.driver.execute_script("arguments[0].click();", realtime_option)
                print("🖱️ Clic sur l'option 'Temps Réel' effectué.")
                time.sleep(2)

            except Exception:
                print("⌛ Échec de la sélection, nouvelle tentative dans 2s...")
                time.sleep(2)

    def start_table(self):
        print("🔍 Monitoring table state (Waiting for Start or Accept)...")
        start_xpath = "//a[contains(@class, 'bga-button')]//div[contains(text(), 'Démarrer') or contains(text(), 'Start')]"
        accept_id = "ags_start_game_accept"
        board_id = "board"

        while True:
            self.clear_popups()

            try:
                board_elements = self.driver.find_elements(By.ID, board_id)
                if board_elements and board_elements[0].is_displayed():
                    print("✅ Game board detected! Transitioning to play loop.")
                    return True

                accept_btns = self.driver.find_elements(By.ID, accept_id)
                if accept_btns and accept_btns[0].is_displayed():
                    print("✅ Opponent found! Clicking 'Accept'...")
                    self.driver.execute_script("arguments[0].click();", accept_btns[0])
                    time.sleep(2)
                    continue

                start_btns = self.driver.find_elements(By.XPATH, start_xpath)
                if start_btns and start_btns[0].is_displayed():
                    print("✅ Clicking 'Start' to open the table...")
                    self.driver.execute_script("arguments[0].click();", start_btns[0])
                    time.sleep(2)
                    continue

                body_class = self.driver.find_element(
                    By.TAG_NAME, "body"
                ).get_attribute("class")
                if "current_player_is_active" in body_class:
                    print("✅ Active turn detected via body class. Let's go!")
                    return True

                time.sleep(2)

            except WebDriverException as e:
                print(f"⌛ Connection unstable, retrying... ({e})")
                time.sleep(2)
            except Exception:
                time.sleep(2)

    def _ensure_game_started_in_db(self):
        # table id depuis l'url courante (si dispo)
        self.current_table_id = extract_table_id_from_url(self.driver.current_url)
        self.local_move_index = 0
        self.last_js_move_index_saved = -1
        self.current_game_id = self.db.start_game(
            game_name="connectfour", bga_table_id=self.current_table_id
        )
        print(
            f"🗄️ DB: game started (game_id={self.current_game_id}, table_id={self.current_table_id})"
        )

    def _sync_moves_from_js_if_possible(self):
        """
        Essaye de récupérer la liste des coups via JS et de les persister.
        Si ça marche => on récupère aussi les coups adverses.
        """
        if self.current_game_id is None:
            return

        moves = try_get_moves_from_bga_js(self.driver)
        if not moves:
            return

        # On enregistre tout ce qui est nouveau
        for mv in moves:
            mi = mv["move_index"]
            if mi <= self.last_js_move_index_saved:
                continue
            self.db.insert_move(
                game_id=self.current_game_id,
                move_index=mi,
                player=mv["player"],
                col=mv["col"],
                raw=mv.get("raw"),
            )
            self.last_js_move_index_saved = mi

        # ⚠️ On ne force pas local_move_index ici, car le fallback sert surtout pour TES coups
        # si JS n’est pas dispo.

    def play_random_move(self):
        try:
            # 0) sync JS (si possible) pour récupérer aussi les coups adverses
            self._sync_moves_from_js_if_possible()

            # 1) Check end game
            title_text = self.driver.find_element(By.ID, "pagemaintitletext").text
            if (
                "Fin de la partie" in title_text
                or "Victoire" in title_text
                or "End of game" in title_text
                or "Game over" in title_text
                or "Victory" in title_text
                or "Defeat" in title_text
                or "You win" in title_text
                or "You lose" in title_text
            ):
                print(f"🏁 Game Over Detected: {title_text}")
                return "GAME_OVER"

            # 2) Turn detection
            is_active = self.driver.find_elements(
                By.CSS_SELECTOR, "body.current_player_is_active"
            )
            if not is_active:
                return "WAITING"

            print("🎲 My turn! Playing...")
            clickable_squares = self.driver.find_elements(
                By.CSS_SELECTOR, "#board .square.possibleMove"
            )

            if clickable_squares:
                target = random.choice(clickable_squares)

                # essayer de déduire la colonne AVANT le clic
                col = infer_col_from_square_element(target)

                self.driver.execute_script("arguments[0].click();", target)
                time.sleep(2.5)

                # fallback: on log au moins ton coup même si JS ne donne rien
                if self.current_game_id is not None:
                    self.db.insert_move(
                        game_id=self.current_game_id,
                        move_index=self.local_move_index,
                        player="ME",
                        col=col,
                        raw=f"clicked_square col={col}",
                    )
                    self.local_move_index += 1

                return "MOVED"

            return "WAITING"

        except Exception:
            print(f"⌛ Polling game state...")
            return "WAITING"

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass
        print("\nBot terminé. Appuyez sur Entrée pour fermer.")
        input()
        try:
            self.driver.quit()
        except Exception:
            pass


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    bot = BGABot(chrome_version=146, db_path="connect4.db")
    counter = 0

    try:
        bot.login()

        while True:
            print("\n🚀 Starting a new session...")
            bot.navigate_to_game("connectfour")
            bot.select_realtime_mode()

            if bot.start_table():
                counter += 1
                print(
                    f"------------------------ we are playing game number {counter} -----------------------------\n"
                )

                bot._ensure_game_started_in_db()

                game_in_progress = True
                while game_in_progress:
                    status = bot.play_random_move()

                    if status == "GAME_OVER":
                        if bot.current_game_id is not None:
                            bot.db.end_game(bot.current_game_id, status="FINISHED")
                            print(f"🗄️ DB: game ended (game_id={bot.current_game_id})")
                            bot.current_game_id = None
                        print(
                            "♻️ Game ended. Preparing to start a new one in 10 seconds..."
                        )
                        time.sleep(10)
                        game_in_progress = False

                    time.sleep(3)

    except Exception as main_error:
        print(f"Fatal Error: {main_error}")
        # si crash en plein match, on marque le game comme ABORTED
        try:
            if bot.current_game_id is not None:
                bot.db.end_game(bot.current_game_id, status="ABORTED")
        except Exception:
            pass
    finally:
        bot.close()
