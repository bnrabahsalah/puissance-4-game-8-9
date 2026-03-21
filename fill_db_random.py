import random
import json
import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "puissance4_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", "5432")),
}


EMPTY = "."
RED = "R"
YELLOW = "Y"
CONNECT_N = 4

ROWS = 9
COLS = 9


def other(token):
    return YELLOW if token == RED else RED


def create_board():
    return [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]


def valid_columns(board):
    return [c for c in range(COLS) if board[0][c] == EMPTY]


def drop_token(board, col, token):
    if col < 0 or col >= COLS:
        return None
    if board[0][col] != EMPTY:
        return None
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] == EMPTY:
            board[r][col] = token
            return (r, col)
    return None


def is_draw(board):
    return all(board[0][c] != EMPTY for c in range(COLS))


def check_win(board, last_row, last_col, token):
    dirs = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in dirs:
        count = 1
        # forward
        r, c = last_row + dr, last_col + dc
        while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == token:
            count += 1
            r += dr
            c += dc
        # backward
        r, c = last_row - dr, last_col - dc
        while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == token:
            count += 1
            r -= dr
            c -= dc
        if count >= CONNECT_N:
            return True
    return False


def compute_confidence(ai_mode: str, ai_depth: int, mode: int) -> int:
    """
    Même logique que ton game.py :
    - 1 : random
    - 2..5 : minimax selon profondeur
    - 0 : lose (si tu ajoutes ce mode)
    - mode=2 (humain vs humain) : 5
    """
    ai_mode = (ai_mode or "random").lower()
    ai_depth = max(1, min(8, int(ai_depth)))
    mode = int(mode)

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


def play_random_game(starting_color=RED, max_moves=ROWS * COLS):
    board = create_board()
    moves = []
    current = starting_color

    for _ in range(max_moves):
        cols = valid_columns(board)
        if not cols:
            break

        col = random.choice(cols)
        pos = drop_token(board, col, current)
        if pos is None:
            break

        moves.append(col)
        r, c = pos
        if check_win(board, r, c, current):
            # victoire
            return moves, current  # winner token

        if is_draw(board):
            return moves, None  # draw

        current = other(current)

    return moves, None


def ensure_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
        ALTER TABLE saved_games
            ALTER COLUMN rows SET DEFAULT 9;
        """
        )
        cur.execute(
            """
        ALTER TABLE saved_games
            ALTER COLUMN cols SET DEFAULT 9;
        """
        )
        cur.execute(
            """
        ALTER TABLE saved_games
            ADD COLUMN IF NOT EXISTS confidence INTEGER NOT NULL DEFAULT 1
            CHECK (confidence BETWEEN 0 AND 5);
        """
        )
        cur.execute(
            """
        ALTER TABLE saved_games
            ADD COLUMN IF NOT EXISTS distinct_cols INTEGER NOT NULL DEFAULT 0
            CHECK (distinct_cols BETWEEN 0 AND 20);
        """
        )
    conn.commit()


def insert_game(
    conn,
    save_name,
    rows,
    cols,
    starting_color,
    mode,
    game_index,
    moves,
    view_index,
    ai_mode,
    ai_depth,
    confidence,
    distinct_cols,
):
    with conn.cursor() as cur:
        cur.execute(
            """
        INSERT INTO saved_games
          (save_name, rows, cols, starting_color, mode, game_index,
           moves, view_index, ai_mode, ai_depth, confidence, distinct_cols, save_date)
        VALUES
          (%s, %s, %s, %s, %s, %s,
           %s::jsonb, %s, %s, %s, %s, %s, NOW())
        """,
            (
                save_name,
                rows,
                cols,
                starting_color,
                mode,
                game_index,
                json.dumps(moves),
                view_index,
                ai_mode,
                ai_depth,
                confidence,
                distinct_cols,
            ),
        )
    conn.commit()


def main(n_games=200):
    with psycopg2.connect(**DB_CONFIG) as conn:
        ensure_columns(conn)

        for i in range(1, n_games + 1):
            # Ici tu peux varier les “algos” :
            # - random => confidence=1
            # - minimax => confidence dépend depth (même si on simule en random ici)
            ai_mode = random.choice(["random", "minimax"])
            ai_depth = random.choice([2, 4, 6, 8])
            mode = random.choice([0, 1])  # on simule des parties avec IA impliquée
            starting_color = random.choice([RED, YELLOW])

            moves, winner = play_random_game(starting_color=starting_color)
            distinct_cols = len(set(moves)) if moves else 0
            confidence = compute_confidence(ai_mode, ai_depth, mode)

            save_name = f"auto_{ROWS}x{COLS}_{ai_mode}_d{ai_depth}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"

            insert_game(
                conn=conn,
                save_name=save_name,
                rows=ROWS,
                cols=COLS,
                starting_color=starting_color,
                mode=mode,
                game_index=i,
                moves=moves,
                view_index=len(moves),
                ai_mode=ai_mode,
                ai_depth=ai_depth,
                confidence=confidence,
                distinct_cols=distinct_cols,
            )

            if i % 25 == 0:
                print(f"✅ {i}/{n_games} parties insérées...")

    print("✅ Remplissage terminé.")


if __name__ == "__main__":
    main(n_games=300)
