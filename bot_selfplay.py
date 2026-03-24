# -*- coding: utf-8 -*-
"""
bot_selfplay.py
───────────────
Bot autonome : joue des parties Puissance-4 (9×9) IA vs IA
et les insère dans la table saved_games de PostgreSQL.

Version :
- minimax vs minimax uniquement
- choix aléatoire parmi les meilleurs coups minimax
- pas de symétrie canonique pour éviter trop de doublons

Usage :
    python bot_selfplay.py
    python bot_selfplay.py --red-depth 4 --yellow-depth 4
    python bot_selfplay.py --red-depth 6 --yellow-depth 4
    python bot_selfplay.py --start alt
    python bot_selfplay.py --no-skip-duplicates
"""

import argparse
import json
import random
import os
from typing import List, Optional, Tuple

import psycopg2
from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(__file__), "..", ".env"),
    encoding="utf-8"
)

DB_CONFIG = {
    "host": "localhost",
    "database": "puissance4_db",
    "user": "postgres",
    "password": "admin123",
    "port": 5432,
}

# ──────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────
EMPTY = "."
RED = "R"
YELLOW = "Y"
CONNECT_N = 4
ROWS = 9
COLS = 9


# ──────────────────────────────────────────────────────────────
# Logique de jeu
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


# ──────────────────────────────────────────────────────────────
# Minimax
# ──────────────────────────────────────────────────────────────
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


def _drop_in_grid(
    grid: List[List[str]], col: int, token: str
) -> Optional[Tuple[int, int]]:
    for r in range(ROWS - 1, -1, -1):
        if grid[r][col] == EMPTY:
            grid[r][col] = token
            return (r, col)
    return None


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


# ──────────────────────────────────────────────────────────────
# Choix de coup
# ──────────────────────────────────────────────────────────────
def choose_move(
    board: List[List[str]],
    current: str,
    ai_mode: str,
    depth: int,
) -> Optional[int]:
    cols = valid_columns(board)
    if not cols:
        return None

    if ai_mode == "random":
        return random.choice(cols)

    if ai_mode == "minimax":
        center = COLS // 2
        cols_sorted = sorted(cols, key=lambda c: abs(c - center))

        best_val = -(10**18)
        best_cols = []

        for col in cols_sorted:
            g2 = copy_grid(board)
            _drop_in_grid(g2, col, current)
            val = minimax(g2, depth - 1, -(10**18), 10**18, False, current)

            if val > best_val:
                best_val = val
                best_cols = [col]
            elif val == best_val:
                best_cols.append(col)

        return random.choice(best_cols)

    return random.choice(cols)


# ──────────────────────────────────────────────────────────────
# Symétrie / doublons
# ──────────────────────────────────────────────────────────────
def mirror_col(col: int) -> int:
    return (COLS - 1) - col


def canonical_moves(moves: List[int]) -> List[int]:
    if not moves:
        return []
    m1 = list(moves)
    m2 = [mirror_col(c) for c in m1]
    return m1 if m1 < m2 else m2


# ──────────────────────────────────────────────────────────────
# Confidence
# ──────────────────────────────────────────────────────────────
def compute_confidence(mode: int, ai_mode: str, ai_depth: int) -> int:
    ai_mode = (ai_mode or "random").lower()
    ai_depth = max(1, min(8, int(ai_depth)))

    if mode == 2:
        return 5
    if ai_mode == "lose":
        return 0
    if ai_mode == "random":
        return 1
    if ai_mode == "minimax":
        if ai_depth <= 2:
            return 2
        if ai_depth <= 4:
            return 3
        if ai_depth <= 6:
            return 4
        return 5

    return 1


# ──────────────────────────────────────────────────────────────
# Jouer une partie complète
# ──────────────────────────────────────────────────────────────
def play_game(
    starting_color: str = RED,
    red_ai: str = "minimax",
    red_depth: int = 4,
    yellow_ai: str = "minimax",
    yellow_depth: int = 4,
) -> Tuple[List[int], Optional[str]]:
    board = create_board()
    moves: List[int] = []
    current = starting_color

    while True:
        cols = valid_columns(board)
        if not cols:
            return moves, None

        if current == RED:
            col = choose_move(board, current, red_ai, red_depth)
        else:
            col = choose_move(board, current, yellow_ai, yellow_depth)

        if col is None:
            return moves, None

        pos = drop_token(board, col, current)
        if pos is None:
            return moves, None

        moves.append(col)
        r, c = pos

        cells = check_win_cells(board, r, c, current)
        if cells:
            return moves, current

        if is_draw(board):
            return moves, None

        current = other(current)


# ──────────────────────────────────────────────────────────────
# Base de données
# ──────────────────────────────────────────────────────────────
def db_connect():
    print("DB_CONFIG =", repr(DB_CONFIG))
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("UTF8")
    return conn


def ensure_table(conn):
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
        confidence INTEGER NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 5),
        distinct_cols INTEGER NOT NULL DEFAULT 0 CHECK (distinct_cols BETWEEN 0 AND 20),
        save_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        for col_def in [
            "ADD COLUMN IF NOT EXISTS confidence INTEGER NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 5)",
            "ADD COLUMN IF NOT EXISTS distinct_cols INTEGER NOT NULL DEFAULT 0 CHECK (distinct_cols BETWEEN 0 AND 20)",
        ]:
            try:
                cur.execute(f"ALTER TABLE saved_games {col_def}")
            except Exception:
                pass
    conn.commit()


def is_duplicate(conn, moves_to_store: List[int]) -> bool:
    sql = """
    SELECT 1 FROM saved_games
    WHERE rows = %s AND cols = %s AND moves = %s::jsonb
    LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (ROWS, COLS, json.dumps(moves_to_store)))
        return cur.fetchone() is not None


def insert_game(
    conn,
    save_name: str,
    starting_color: str,
    moves_to_store: List[int],
    ai_mode_red: str,
    ai_depth_red: int,
    ai_mode_yellow: str,
    ai_depth_yellow: int,
    game_index: int,
    winner: Optional[str],
) -> int:
    moves_str = json.dumps(moves_to_store)
    distinct_cols = len(set(moves_to_store)) if moves_to_store else 0

    conf_red = compute_confidence(0, ai_mode_red, ai_depth_red)
    conf_yellow = compute_confidence(0, ai_mode_yellow, ai_depth_yellow)
    confidence = max(conf_red, conf_yellow)

    insert_sql = """
    INSERT INTO saved_games
      (save_name, rows, cols, starting_color, mode, game_index,
       moves, view_index, ai_mode, ai_depth, confidence, distinct_cols, save_date)
    VALUES
      (%s, %s, %s, %s, %s, %s,
       %s::jsonb, %s, %s, %s, %s, %s, NOW())
    RETURNING id;
    """
    with conn.cursor() as cur:
        cur.execute(
            insert_sql,
            (
                save_name,
                ROWS,
                COLS,
                starting_color,
                2,
                game_index,
                moves_str,
                len(moves_to_store),
                "bga",
                max(ai_depth_red, ai_depth_yellow),
                confidence,
                distinct_cols,
            ),
        )
        new_id = cur.fetchone()[0]

    conn.commit()
    return int(new_id)


# ──────────────────────────────────────────────────────────────
# Boucle principale
# ──────────────────────────────────────────────────────────────
def run_bot(
    red_depth: int = 4,
    yellow_depth: int = 4,
    starting_color: str = RED,
    skip_duplicates: bool = True,
    verbose: bool = True,
):
    conn = db_connect()
    ensure_table(conn)

    stats = {"inserted": 0, "skipped": 0, "R": 0, "Y": 0, "draw": 0}

    if verbose:
        print("\n🤖  Bot selfplay — boucle infinie (Ctrl+C pour arrêter)")
        print(f"    Rouge  : minimax depth={red_depth}")
        print(f"    Jaune  : minimax depth={yellow_depth}")
        print(f"    Taille : {ROWS}×{COLS}  |  Départ : {starting_color}\n")

    i = 0
    try:
        while True:
            i += 1

            start = (
                starting_color
                if starting_color in (RED, YELLOW)
                else (RED if i % 2 else YELLOW)
            )

            cur_red_ai, cur_red_depth = "minimax", red_depth
            cur_yellow_ai, cur_yellow_depth = "minimax", yellow_depth

            moves, winner = play_game(
                starting_color=start,
                red_ai=cur_red_ai,
                red_depth=cur_red_depth,
                yellow_ai=cur_yellow_ai,
                yellow_depth=cur_yellow_depth,
            )

            # On garde les coups tels quels pour éviter que les parties miroir
            # soient considérées comme doublons
            moves_to_store = moves

            if skip_duplicates and is_duplicate(conn, moves_to_store):
                stats["skipped"] += 1
                if verbose:
                    print(f"  [#{i:>5}]  ⏭  doublon ignoré")
                continue

            stats["R" if winner == RED else "Y" if winner == YELLOW else "draw"] += 1

            id1 = random.randint(100_000_000, 999_999_999)
            id2 = random.randint(100_000_000, 999_999_999)
            save_name = f"BGA_{id1}_{id2}_{ROWS}x{COLS}"

            gid = insert_game(
                conn=conn,
                save_name=save_name,
                starting_color=start,
                moves_to_store=moves_to_store,
                ai_mode_red=cur_red_ai,
                ai_depth_red=cur_red_depth,
                ai_mode_yellow=cur_yellow_ai,
                ai_depth_yellow=cur_yellow_depth,
                game_index=i,
                winner=winner,
            )
            stats["inserted"] += 1

            if verbose:
                winner_label = (
                    "🔴 Rouge"
                    if winner == RED
                    else "🟡 Jaune" if winner == YELLOW else "🤝 Nul"
                )
                print(
                    f"  [#{i:>5}]  ✅  id={gid:<6}  coups={len(moves_to_store):<4}"
                    f"  🔴minimax({cur_red_depth}) vs 🟡minimax({cur_yellow_depth})"
                    f"  →  {winner_label}"
                )

    except KeyboardInterrupt:
        if verbose:
            print(f"\n\n⛔  Arrêté par l'utilisateur après {i} parties.")

    finally:
        conn.close()
        if verbose:
            print(f"\n{'─'*50}")
            print(f"  Parties insérées : {stats['inserted']}")
            print(f"  Doublons ignorés : {stats['skipped']}")
            print(f"  Rouge gagne      : {stats['R']}")
            print(f"  Jaune gagne      : {stats['Y']}")
            print(f"  Nuls             : {stats['draw']}")
            print(f"{'─'*50}\n")

    return stats


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="Bot selfplay Puissance-4 9×9 — minimax vs minimax uniquement"
    )
    p.add_argument(
        "--red-depth",
        type=int,
        default=4,
        help="Profondeur minimax Rouge (défaut: 4)",
    )
    p.add_argument(
        "--yellow-depth",
        type=int,
        default=4,
        help="Profondeur minimax Jaune (défaut: 4)",
    )
    p.add_argument(
        "--start",
        default="alt",
        choices=["R", "Y", "alt"],
        help="Couleur de départ : R, Y, ou alt (alternance, défaut: alt)",
    )
    p.add_argument(
        "--no-skip-duplicates",
        action="store_true",
        help="Insère même si les coups existent déjà en base",
    )
    p.add_argument("--quiet", action="store_true", help="Mode silencieux")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    starting = args.start if args.start in (RED, YELLOW) else RED

    run_bot(
        red_depth=args.red_depth,
        yellow_depth=args.yellow_depth,
        starting_color=starting,
        skip_duplicates=not args.no_skip_duplicates,
        verbose=not args.quiet,
    )
