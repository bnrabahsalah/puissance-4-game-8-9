# game.py — Application desktop Puissance 4
# L'IA est maintenant dans ia_engine.py (partagée avec le site web)
# ═══════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import os
from datetime import datetime
import os
from dotenv import load_dotenv

import psycopg2
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ia_engine import *

# ── IA partagée avec le site web ────────────────────────────
from ia_engine import (
    best_move,
    check_win_cells,
    valid_columns,
    drop_in_grid,
    copy_grid,
    is_draw,
    terminal_state,
    other,
    EMPTY,
    RED,
    YELLOW,
    reload_model,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "puissance4_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", "5432")),
}


class Connect4App(tk.Tk):
    EMPTY = EMPTY
    RED = RED
    YELLOW = YELLOW
    CONNECT_N = 4

    CONFIG_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "donnees", "config.json"
    )

    COLOR_BG = "#00478e"
    COLOR_HOLE = "#e3f2fd"
    COLOR_RED = "#d32f2f"
    COLOR_YELLOW = "#fbc02d"
    COLOR_WIN = "#00c853"

    def __init__(self):
        super().__init__()
        self.title("Puissance 4+ — IA partagée (ia_engine.py)")
        self.minsize(1050, 700)

        cfg = self.load_config()
        self.rows = cfg["rows"]
        self.cols = cfg["cols"]
        self.starting_color = cfg["starting_color"]

        self.board = None
        self.current = self.starting_color
        self.game_over = False
        self.winner = None
        self.winning_cells = []
        self.game_index = 1
        self.moves = []
        self.view_index = 0
        self.robot_thinking = False
        self.pending_after = None

        self.mode_var = tk.StringVar(value="2")
        self.ai_var = tk.StringVar(value="random")
        self.depth_var = tk.StringVar(value="4")
        self.starting_var = tk.StringVar(value=self.starting_color)
        self.status_var = tk.StringVar(value="")

        self.col_buttons = []
        self.score_labels = []
        self.timeline_var = tk.IntVar(value=0)

        self._build_ui()
        self.reset_game(new_game=False)

    # ── helpers ──────────────────────────────────────────────
    def clamp_int(self, v, lo, hi, default):
        try:
            return max(lo, min(hi, int(v)))
        except:
            return default

    def is_replay_view(self):
        return self.view_index < len(self.moves)

    def mirror_col(self, col):
        return (self.cols - 1) - int(col)

    def mirror_moves(self, moves):
        return [self.mirror_col(c) for c in moves]

    def canonical_moves(self, moves):
        m1 = list(moves)
        m2 = self.mirror_moves(m1)
        return m1 if m1 < m2 else m2

    # ── config ───────────────────────────────────────────────
    def load_config(self, path=None):
        path = path or self.CONFIG_PATH
        default = {"rows": 8, "cols": 9, "starting_color": self.RED}
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return default
        rows = data.get("rows", default["rows"])
        cols = data.get("cols", default["cols"])
        start = data.get("starting_color", default["starting_color"])
        if not isinstance(rows, int) or not (4 <= rows <= 20):
            rows = default["rows"]
        if not isinstance(cols, int) or not (4 <= cols <= 20):
            cols = default["cols"]
        if start not in (self.RED, self.YELLOW):
            start = default["starting_color"]
        return {"rows": rows, "cols": cols, "starting_color": start}

    def save_starting_color(self):
        new_start = self.starting_var.get()
        if new_start in (self.RED, self.YELLOW):
            cfg = self.load_config()
            cfg["starting_color"] = new_start
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            self.starting_color = new_start
            self.reset_game(new_game=False)

    # ── DB ───────────────────────────────────────────────────
    def db_connect(self):
        return psycopg2.connect(**DB_CONFIG)

    def ensure_saved_games_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS saved_games (
            id SERIAL PRIMARY KEY,
            save_name VARCHAR(100),
            rows INTEGER NOT NULL DEFAULT 9,
            cols INTEGER NOT NULL DEFAULT 9,
            starting_color CHAR(1) NOT NULL CHECK (starting_color IN ('R','Y')),
            mode INTEGER NOT NULL CHECK (mode IN (0,1,2)),
            game_index INTEGER NOT NULL DEFAULT 1,
            moves JSONB NOT NULL DEFAULT '[]'::jsonb,
            view_index INTEGER NOT NULL DEFAULT 0,
            ai_mode VARCHAR(20) NOT NULL DEFAULT 'random',
            ai_depth INTEGER NOT NULL DEFAULT 4,
            save_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE saved_games ADD COLUMN IF NOT EXISTS confidence   INTEGER NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 5);
        ALTER TABLE saved_games ADD COLUMN IF NOT EXISTS distinct_cols INTEGER NOT NULL DEFAULT 0 CHECK (distinct_cols BETWEEN 0 AND 20);
        """
        with self.db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    def compute_confidence(self, mode, ai_mode, ai_depth):
        try:
            mode = int(mode)
        except:
            mode = 2
        ai_mode = (ai_mode or "random").lower()
        ai_depth = self.clamp_int(ai_depth, 1, 8, 4)
        if mode == 2:
            return 5
        if ai_mode == "lose":
            return 0
        if ai_mode == "random":
            return 1
        if ai_mode == "trained":
            return 4
        if ai_mode == "minimax":
            if ai_depth <= 2:
                return 2
            if ai_depth <= 4:
                return 3
            if ai_depth <= 6:
                return 4
            return 5
        return 1

    def upsert_game_to_postgres(self, save_name):
        self.ensure_saved_games_table()
        mode = int(self.mode_var.get())
        ai_mode = self.ai_var.get()
        ai_depth = self.clamp_int(self.depth_var.get(), 1, 8, 4)
        confidence = self.compute_confidence(mode, ai_mode, ai_depth)
        moves_canon = self.canonical_moves(self.moves)
        distinct_cols = len(set(moves_canon)) if moves_canon else 0

        # check doublon
        with self.db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM saved_games WHERE save_name=%s OR (rows=%s AND cols=%s AND moves=%s::jsonb) ORDER BY save_date DESC LIMIT 1",
                    (save_name, self.rows, self.cols, json.dumps(moves_canon)),
                )
                row = cur.fetchone()

        if row:
            ok = messagebox.askyesno(
                "Doublon",
                f"Une partie similaire existe (id={row[0]}).\nÉcraser ?",
                parent=self,
            )
            if not ok:
                return None, "cancel"
            with self.db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE saved_games SET save_name=%s,rows=%s,cols=%s,starting_color=%s,mode=%s,game_index=%s,moves=%s::jsonb,view_index=%s,ai_mode=%s,ai_depth=%s,confidence=%s,distinct_cols=%s,save_date=NOW() WHERE id=%s RETURNING id",
                        (
                            save_name,
                            self.rows,
                            self.cols,
                            self.starting_color,
                            mode,
                            self.game_index,
                            json.dumps(moves_canon),
                            self.view_index,
                            ai_mode,
                            ai_depth,
                            confidence,
                            distinct_cols,
                            row[0],
                        ),
                    )
                    gid = cur.fetchone()[0]
                conn.commit()
            return int(gid), "update"

        with self.db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO saved_games (save_name,rows,cols,starting_color,mode,game_index,moves,view_index,ai_mode,ai_depth,confidence,distinct_cols,save_date) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,NOW()) RETURNING id",
                    (
                        save_name,
                        self.rows,
                        self.cols,
                        self.starting_color,
                        mode,
                        self.game_index,
                        json.dumps(moves_canon),
                        self.view_index,
                        ai_mode,
                        ai_depth,
                        confidence,
                        distinct_cols,
                    ),
                )
                gid = cur.fetchone()[0]
            conn.commit()
        return int(gid), "insert"

    def fetch_saved_games_list(self):
        self.ensure_saved_games_table()
        with self.db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id,save_name,rows,cols,mode,ai_mode,ai_depth,COALESCE(confidence,1),COALESCE(distinct_cols,0),jsonb_array_length(moves),save_date FROM saved_games ORDER BY save_date DESC LIMIT 200"
                )
                return cur.fetchall()

    def fetch_saved_game_by_id(self, gid):
        self.ensure_saved_games_table()
        with self.db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id,save_name,rows,cols,starting_color,mode,game_index,moves,view_index,ai_mode,ai_depth FROM saved_games WHERE id=%s LIMIT 1",
                    (gid,),
                )
                return cur.fetchone()

    # ── jeu ──────────────────────────────────────────────────
    def create_board(self):
        return [[self.EMPTY] * self.cols for _ in range(self.rows)]

    def valid_columns_local(self, board=None):
        b = board if board is not None else self.board
        return valid_columns(b)

    def drop_token(self, board, col, token):
        if col < 0 or col >= self.cols or board[0][col] != self.EMPTY:
            return None
        for r in range(self.rows - 1, -1, -1):
            if board[r][col] == self.EMPTY:
                board[r][col] = token
                return (r, col)
        return None

    def is_draw_local(self, board=None):
        return is_draw(board if board is not None else self.board)

    def is_human_turn(self, mode, current):
        mode = int(mode)
        if mode == 2:
            return True
        if mode == 0:
            return False
        return current == self.RED

    def token_for_move_index(self, i):
        return self.starting_color if i % 2 == 0 else other(self.starting_color)

    def play_move(self, col, token):
        pos = self.drop_token(self.board, col, token)
        if pos is None:
            return True
        if self.view_index < len(self.moves):
            del self.moves[self.view_index :]
        self.moves.append(col)
        self.view_index = len(self.moves)
        r, c = pos
        cells = check_win_cells(self.board, r, c, token)
        if cells:
            self.winning_cells = cells
            self.game_over = True
            self.winner = token
            self._after_state_change(trigger_robot=False)
            return False
        if self.is_draw_local():
            self.winning_cells = []
            self.game_over = True
            self.winner = None
            self._after_state_change(trigger_robot=False)
            return False
        self.current = other(self.current)
        self._after_state_change(trigger_robot=True)
        return True

    def on_click(self, col):
        if self.is_replay_view() or self.game_over or self.robot_thinking:
            return
        mode = int(self.mode_var.get())
        if not self.is_human_turn(mode, self.current):
            return
        # play_move appelle _after_state_change(trigger_robot=True)
        # qui schedule déjà robot_step — ne pas l'appeler une 2e fois ici
        self.play_move(col, self.current)

    def on_canvas_click(self, event):
        if self.is_replay_view() or self.game_over or self.robot_thinking:
            return
        mode = int(self.mode_var.get())
        if not self.is_human_turn(mode, self.current):
            return
        W = self.canvas.winfo_width()
        H = self.canvas.winfo_height()
        cell = min(W / self.cols, H / self.rows)
        board_w = cell * self.cols
        x0 = (W - board_w) / 2
        x = event.x - x0
        if x < 0 or x >= board_w:
            return
        col = int(x // cell)
        if 0 <= col < self.cols:
            self.on_click(col)

    # ── ROBOT — utilise ia_engine.best_move ──────────────────
    def robot_step(self):
        if self.game_over or self.is_replay_view():
            return
        mode = int(self.mode_var.get())
        if self.is_human_turn(mode, self.current):
            self.set_buttons_state(True)
            return
        self.set_buttons_state(False)
        ai_mode = self.ai_var.get()
        depth = self.clamp_int(self.depth_var.get(), 1, 8, 4)

        if ai_mode == "random":
            result = best_move(self.board, self.current, depth, "random")
            col = result["col"]
            if col is None:
                self.game_over = True
                self._after_state_change(trigger_robot=False)
                return
            cont = self.play_move(col, self.current)
            if not cont:
                return
            if mode == 0 and not self.game_over:
                self.after(250, self.robot_step)
            else:
                self.set_buttons_state(True)
        else:
            # minimax ou trained — async pour ne pas geler l'UI
            self.robot_play_async(depth, ai_mode)

    def robot_play_async(self, depth, ai_mode):
        if self.game_over or self.is_replay_view():
            return
        # Vérifier qu'un calcul n'est pas déjà en cours
        if self.robot_thinking:
            return
        self.robot_thinking = True
        self.update_status()
        self.set_buttons_state(False)

        board_copy = copy_grid(self.board)
        player = self.current
        mode = int(self.mode_var.get())

        def compute():
            # Tourne dans after() pour ne pas geler l'UI
            if self.game_over or self.is_replay_view():
                self.robot_thinking = False
                self.update_status()
                return

            result = best_move(board_copy, player, depth, ai_mode)
            best_col = result["col"]

            # Afficher les scores sous les colonnes
            for c, v in result.get("scores", {}).items():
                if c < len(self.score_labels):
                    disp = "✓" if v > 900000 else ("✗" if v < -900000 else str(int(v)))
                    self.score_labels[c].set(disp)

            self.robot_thinking = False
            self.update_status()

            if best_col is None or self.game_over:
                self.set_buttons_state(True)
                return

            # Jouer le coup — play_move gère _after_state_change
            # NE PAS appeler robot_step ici, _after_state_change le fera
            self.play_move(best_col, player)

            # Mode IA vs IA : relancer après un délai
            if mode == 0 and not self.game_over:
                self.pending_after = self.after(300, self.robot_step)

        self.pending_after = self.after(10, compute)

    def render_ai_scores(self):
        if self.is_replay_view() or self.ai_var.get() != "minimax":
            return
        if self.robot_thinking or self.board is None:
            return
        depth = self.clamp_int(self.depth_var.get(), 1, 8, 4)
        grid0 = copy_grid(self.board)
        player = self.current
        valids = valid_columns(grid0)

        def step(i=0):
            if (
                self.ai_var.get() != "minimax"
                or self.robot_thinking
                or self.game_over
                or self.is_replay_view()
            ):
                return
            if i >= self.cols:
                return
            c = i
            if c not in valids:
                self.score_labels[c].set("N/A")
            else:
                from ia_engine import minimax

                g2 = copy_grid(grid0)
                drop_in_grid(g2, c, player)
                val = minimax(g2, depth - 1, -(10**18), 10**18, False, player)
                self.score_labels[c].set(str(int(val)))
            self.pending_after = self.after(40, lambda: step(i + 1))

        step(0)

    # ── dessin ───────────────────────────────────────────────
    def draw_board(self):
        if self.board is None:
            return
        self.canvas.delete("all")
        W = max(300, self.canvas.winfo_width())
        H = max(300, self.canvas.winfo_height())
        cell = min(W / self.cols, H / self.rows)
        pad = cell * 0.10
        bw = cell * self.cols
        bh = cell * self.rows
        x0 = (W - bw) / 2
        y0 = (H - bh) / 2
        self.canvas.create_rectangle(
            x0, y0, x0 + bw, y0 + bh, fill=self.COLOR_BG, outline=""
        )
        win_set = set(map(tuple, self.winning_cells))
        for r in range(self.rows):
            for c in range(self.cols):
                cx0 = x0 + c * cell + pad
                cy0 = y0 + r * cell + pad
                cx1 = x0 + (c + 1) * cell - pad
                cy1 = y0 + (r + 1) * cell - pad
                val = self.board[r][c]
                fill = (
                    self.COLOR_RED
                    if val == self.RED
                    else self.COLOR_YELLOW if val == self.YELLOW else self.COLOR_HOLE
                )
                outline = self.COLOR_WIN if (r, c) in win_set else ""
                width = 4 if (r, c) in win_set else 1
                self.canvas.create_oval(
                    cx0, cy0, cx1, cy1, fill=fill, outline=outline, width=width
                )

    def update_status(self):
        replay = (
            f"   (replay: coup {self.view_index}/{len(self.moves)})"
            if self.is_replay_view()
            else ""
        )
        if self.game_over:
            if self.winner == self.RED:
                msg = f"Partie #{self.game_index} — 🎉 Rouge gagne"
            elif self.winner == self.YELLOW:
                msg = f"Partie #{self.game_index} — 🎉 Jaune gagne"
            else:
                msg = f"Partie #{self.game_index} — 🤝 Match nul"
        else:
            name = "Rouge" if self.current == self.RED else "Jaune"
            msg = f"Partie #{self.game_index} — À jouer : {name}"
        if self.robot_thinking:
            msg += "   (IA réfléchit…)"
        self.status_var.set(msg + replay)

    def set_buttons_state(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in self.col_buttons:
            b.config(state=state)

    def _after_state_change(self, trigger_robot=True):
        self.draw_board()
        self.update_status()
        self.render_ai_scores()
        self._sync_timeline_ui()
        if self.is_replay_view():
            self.set_buttons_state(False)
            return
        if self.game_over:
            self.set_buttons_state(False)
            return
        mode = int(self.mode_var.get())
        self.set_buttons_state(
            (not self.robot_thinking) and self.is_human_turn(mode, self.current)
        )
        if trigger_robot and not self.robot_thinking and not self.game_over:
            if not self.is_human_turn(mode, self.current):
                self.after(120, self.robot_step)

    # ── timeline ─────────────────────────────────────────────
    def _sync_timeline_ui(self):
        try:
            maxv = len(self.moves)
            self.timeline_scale.configure(to=maxv)
            self.timeline_scale.set(self.view_index)
            self.tl_label_var.set(f"Coups: {self.view_index}/{maxv}")
        except Exception:
            pass

    def _timeline_prev(self):
        self.set_view_index(self.view_index - 1) if self.view_index > 0 else None

    def _timeline_next(self):
        (
            self.set_view_index(self.view_index + 1)
            if self.view_index < len(self.moves)
            else None
        )

    def _timeline_end(self):
        self.set_view_index(len(self.moves))

    def _on_timeline_scale(self, v):
        try:
            idx = max(0, min(len(self.moves), int(float(v) + 0.5)))
            if idx != self.view_index:
                self.set_view_index(idx)
        except Exception:
            pass

    def set_view_index(self, idx):
        if self.pending_after:
            try:
                self.after_cancel(self.pending_after)
            except:
                pass
            self.pending_after = None
        self.robot_thinking = False
        self.view_index = max(0, min(len(self.moves), int(idx)))
        self.board = self.create_board()
        self.winning_cells = []
        self.game_over = False
        self.winner = None
        last_pos = last_token = None
        for i in range(self.view_index):
            token = self.token_for_move_index(i)
            last_token = token
            last_pos = self.drop_token(self.board, self.moves[i], token)
        self.current = self.token_for_move_index(self.view_index)
        if self.view_index == len(self.moves) and last_pos and last_token:
            rr, cc = last_pos
            cells = check_win_cells(self.board, rr, cc, last_token)
            if cells:
                self.winning_cells = cells
                self.game_over = True
                self.winner = last_token
            elif self.is_draw_local():
                self.game_over = True
        self._after_state_change(trigger_robot=False)

    # ── reset ────────────────────────────────────────────────
    def stop_game(self):
        if self.pending_after:
            try:
                self.after_cancel(self.pending_after)
            except:
                pass
            self.pending_after = None
        self.game_over = True
        self.robot_thinking = False
        self.winner = None
        self.winning_cells = []
        self._after_state_change(trigger_robot=False)

    def reset_game(self, new_game=True):
        if self.pending_after:
            try:
                self.after_cancel(self.pending_after)
            except:
                pass
            self.pending_after = None
        self.robot_thinking = False
        cfg = self.load_config()
        self.rows = cfg["rows"]
        self.cols = cfg["cols"]
        self.starting_color = cfg["starting_color"]
        if new_game:
            self.game_index += 1
        self.board = self.create_board()
        self.current = self.starting_color
        self.game_over = False
        self.winner = None
        self.winning_cells = []
        self.moves = []
        self.view_index = 0
        self.rebuild_column_widgets()
        self._after_state_change(trigger_robot=True)

    # ── widgets ──────────────────────────────────────────────
    def rebuild_column_widgets(self):
        for w in self.btn_frame.winfo_children():
            w.destroy()
        self.col_buttons = []
        self.score_labels = []
        row_btn = ttk.Frame(self.btn_frame)
        row_btn.pack()
        row_scores = ttk.Frame(self.btn_frame)
        row_scores.pack()
        for c in range(self.cols):
            b = ttk.Button(
                row_btn,
                text=str(c + 1),
                width=4,
                command=lambda cc=c: self.on_click(cc),
            )
            b.pack(side=tk.LEFT, padx=3, pady=2)
            self.col_buttons.append(b)
        for c in range(self.cols):
            v = tk.StringVar(value="")
            ttk.Label(row_scores, textvariable=v, width=7, anchor="center").pack(
                side=tk.LEFT, padx=3
            )
            self.score_labels.append(v)

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Mode:").pack(side=tk.LEFT)
        mc = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=["0", "1", "2"],
            width=4,
            state="readonly",
        )
        mc.pack(side=tk.LEFT, padx=(6, 14))
        mc.bind("<<ComboboxSelected>>", lambda e: self.reset_game(new_game=True))

        ttk.Label(top, text="IA:").pack(side=tk.LEFT)
        ac = ttk.Combobox(
            top,
            textvariable=self.ai_var,
            values=["random", "minimax", "trained"],
            width=10,
            state="readonly",
        )
        ac.pack(side=tk.LEFT, padx=(6, 10))
        ac.bind("<<ComboboxSelected>>", lambda e: self._after_state_change(True))

        ttk.Label(top, text="Profondeur:").pack(side=tk.LEFT)
        ttk.Spinbox(
            top,
            from_=1,
            to=8,
            width=5,
            textvariable=self.depth_var,
            command=self.render_ai_scores,
        ).pack(side=tk.LEFT, padx=(6, 14))

        ttk.Label(top, text="Commence:").pack(side=tk.LEFT)
        sc = ttk.Combobox(
            top,
            textvariable=self.starting_var,
            values=["R", "Y"],
            width=4,
            state="readonly",
        )
        sc.pack(side=tk.LEFT, padx=(6, 14))
        sc.bind("<<ComboboxSelected>>", lambda e: self.save_starting_color())

        ttk.Button(
            top, text="Nouvelle partie", command=lambda: self.reset_game(True)
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Stop", command=self.stop_game).pack(side=tk.LEFT, padx=6)

        # Bouton recharger modèle IA
        ttk.Button(top, text="🔄 Recharger IA", command=self._reload_ia).pack(
            side=tk.LEFT, padx=6
        )

        save_mb = tk.Menubutton(top, text="💾 Sauvegarder ▾", relief="raised")
        save_menu = tk.Menu(save_mb, tearoff=0)
        save_menu.add_command(label="PostgreSQL", command=self.save_game_db_flow)
        save_menu.add_command(label="Fichier JSON", command=self.save_game_json_flow)
        save_mb.configure(menu=save_menu)
        save_mb.pack(side=tk.LEFT, padx=6)

        load_mb = tk.Menubutton(top, text="📂 Charger ▾", relief="raised")
        load_menu = tk.Menu(load_mb, tearoff=0)
        load_menu.add_command(label="PostgreSQL", command=self.load_game_db_flow)
        load_menu.add_command(label="Fichier JSON", command=self.load_game_json_flow)
        load_mb.configure(menu=load_menu)
        load_mb.pack(side=tk.LEFT, padx=6)

        ttk.Label(self, textvariable=self.status_var, font=("Segoe UI", 12)).pack(
            side=tk.TOP, anchor="w", padx=10, pady=6
        )

        tl = ttk.Frame(self, padding=(10, 0))
        tl.pack(side=tk.TOP, fill=tk.X)
        self.tl_label_var = tk.StringVar(value="Coups: 0/0")
        ttk.Label(tl, textvariable=self.tl_label_var).pack(side=tk.LEFT)
        self.timeline_scale = ttk.Scale(
            tl, from_=0, to=0, orient="horizontal", command=self._on_timeline_scale
        )
        self.timeline_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        ttk.Button(tl, text="⏮", width=3, command=self._timeline_prev).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(tl, text="⏭", width=3, command=self._timeline_next).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(tl, text="Fin", width=5, command=self._timeline_end).pack(
            side=tk.LEFT
        )

        body = ttk.Frame(self, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.btn_frame = ttk.Frame(left)
        self.btn_frame.pack(fill=tk.X)
        self.canvas = tk.Canvas(left, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.canvas.bind("<Configure>", lambda e: self.draw_board())
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    def _reload_ia(self):
        ok = reload_model()
        if ok:
            messagebox.showinfo("IA", "Modèle entraîné rechargé depuis ia_model.pkl")
        else:
            messagebox.showinfo(
                "IA", "Aucun modèle ia_model.pkl trouvé — minimax utilisé"
            )

    # ── save/load flows ──────────────────────────────────────
    def ask_save_name(self):
        default = (
            f'partie_{self.rows}x{self.cols}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )
        name = simpledialog.askstring(
            "Nom", "Nom de la partie :", initialvalue=default, parent=self
        )
        return name.strip() if name and name.strip() else None

    def save_game_db_flow(self):
        name = self.ask_save_name()
        if not name:
            return
        try:
            gid, action = self.upsert_game_to_postgres(name)
            if action == "cancel":
                return
            messagebox.showinfo(
                "Sauvegarde",
                f'✅ {"Écrasé" if action == "update" else "Sauvegardé"} (id={gid})',
            )
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def save_game_json_flow(self):
        name = self.ask_save_name()
        if not name:
            return
        data = {
            "save_name": name,
            "rows": self.rows,
            "cols": self.cols,
            "starting_color": self.starting_color,
            "mode": int(self.mode_var.get()),
            "game_index": self.game_index,
            "moves": self.canonical_moves(self.moves),
            "view_index": self.view_index,
            "ai_mode": self.ai_var.get(),
            "ai_depth": self.clamp_int(self.depth_var.get(), 1, 8, 4),
        }
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=f"{name}.json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Sauvegarde", "✅ Fichier JSON sauvegardé")

    def load_game_json_flow(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_loaded_payload(data)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def load_game_db_flow(self):
        try:
            games = self.fetch_saved_games_list()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        if not games:
            messagebox.showinfo("Base vide", "Aucune partie sauvegardée.")
            return

        win = tk.Toplevel(self)
        win.title("Charger")
        win.geometry("900x420")
        win.transient(self)
        win.grab_set()
        cols = (
            "ID",
            "Nom",
            "Taille",
            "Mode",
            "IA",
            "Conf",
            "ColsUsed",
            "Coups",
            "Date",
        )
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=90)
        for g in games:
            gid, name, r, c, mode, ai_mode, ai_depth, conf, cols_used, nb, date = g
            date_str = (
                date.strftime("%d/%m %H:%M") if hasattr(date, "strftime") else str(date)
            )
            mode_name = {0: "IA/IA", 1: "Hum/IA", 2: "Hum/Hum"}.get(
                int(mode), str(mode)
            )
            tree.insert(
                "",
                "end",
                values=(
                    gid,
                    name or "",
                    f"{r}x{c}",
                    mode_name,
                    f"{ai_mode}({ai_depth})",
                    conf,
                    cols_used,
                    nb,
                    date_str,
                ),
            )
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def do_load():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Sélection", "Sélectionne une partie.")
                return
            gid = int(tree.item(sel[0])["values"][0])
            data = self.fetch_saved_game_by_id(gid)
            if not data:
                return
            moves_raw = data[7]
            payload = {
                "save_name": data[1],
                "rows": int(data[2]),
                "cols": int(data[3]),
                "starting_color": data[4],
                "mode": int(data[5]),
                "game_index": int(data[6]),
                "moves": (
                    json.loads(moves_raw)
                    if isinstance(moves_raw, str)
                    else list(moves_raw)
                ),
                "view_index": int(data[8]),
                "ai_mode": data[9],
                "ai_depth": int(data[10]),
            }
            self._apply_loaded_payload(payload)
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Charger", command=do_load).pack(side=tk.LEFT)
        ttk.Button(btns, text="Annuler", command=win.destroy).pack(side=tk.RIGHT)

    def _apply_loaded_payload(self, data):
        if self.pending_after:
            try:
                self.after_cancel(self.pending_after)
            except:
                pass
            self.pending_after = None
        self.robot_thinking = False
        rows = data.get("rows")
        cols = data.get("cols")
        start = data.get("starting_color")
        moves = data.get("moves", [])
        vi = data.get("view_index", 0)
        if not isinstance(rows, int) or not (4 <= rows <= 20):
            return messagebox.showerror("Erreur", "rows invalide")
        if not isinstance(cols, int) or not (4 <= cols <= 20):
            return messagebox.showerror("Erreur", "cols invalide")
        if start not in (self.RED, self.YELLOW):
            return messagebox.showerror("Erreur", "starting_color invalide")
        if not isinstance(moves, list):
            return messagebox.showerror("Erreur", "moves invalide")
        if not isinstance(vi, int) or not (0 <= vi <= len(moves)):
            vi = len(moves)
        self.rows = rows
        self.cols = cols
        self.starting_color = start
        self.mode_var.set(str(int(data.get("mode", 2))))
        self.game_index = int(data.get("game_index", 1))
        self.ai_var.set(data.get("ai_mode", "random"))
        self.depth_var.set(str(self.clamp_int(data.get("ai_depth", 4), 1, 8, 4)))
        self.moves = moves
        self.view_index = vi
        self.board = self.create_board()
        self.winning_cells = []
        self.game_over = False
        self.winner = None
        last_pos = last_token = None
        for i in range(vi):
            token = self.token_for_move_index(i)
            last_token = token
            last_pos = self.drop_token(self.board, moves[i], token)
        self.current = self.token_for_move_index(vi)
        if vi == len(moves) and last_pos and last_token:
            rr, cc = last_pos
            cells = check_win_cells(self.board, rr, cc, last_token)
            if cells:
                self.winning_cells = cells
                self.game_over = True
                self.winner = last_token
            elif self.is_draw_local():
                self.game_over = True
        self.rebuild_column_widgets()
        self._after_state_change(trigger_robot=True)


if __name__ == "__main__":
    Connect4App().mainloop()
