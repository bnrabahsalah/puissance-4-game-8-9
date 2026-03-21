import os
import sys
import json
import secrets
import re as _re
import urllib.request as _req2
from datetime import datetime, timezone
from typing import Optional, List

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

from ia_engine import (
    best_move,
    check_win_cells,
    valid_columns,
    drop_in_grid,
    copy_grid,
    EMPTY,
    RED,
    YELLOW,
    other,
    reload_model,
)

# ══════════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════════


def db_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL manquant")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Render / cloud
    if "render.com" in url or "amazonaws.com" in url:
        return psycopg2.connect(url, sslmode="require")

    # Local
    return psycopg2.connect(url)


INIT_SQL = """
CREATE TABLE IF NOT EXISTS saved_games (
  game_id        SERIAL PRIMARY KEY,
  save_name      TEXT,
  rows_count     INT  NOT NULL DEFAULT 9 CHECK (rows_count BETWEEN 4 AND 20),
  cols_count     INT  NOT NULL DEFAULT 9 CHECK (cols_count BETWEEN 4 AND 20),
  starting_color CHAR(1) NOT NULL DEFAULT 'R' CHECK (starting_color IN ('R','Y')),
  ai_mode        TEXT NOT NULL DEFAULT 'random',
  ai_depth       INT  NOT NULL DEFAULT 4 CHECK (ai_depth BETWEEN 1 AND 8),
  game_mode      INT  NOT NULL DEFAULT 2 CHECK (game_mode IN (0,1,2)),
  status         TEXT NOT NULL DEFAULT 'in_progress',
  winner         CHAR(1),
  view_index     INT  NOT NULL DEFAULT 0,
  moves          JSONB NOT NULL DEFAULT '[]'::jsonb,
  player_red     TEXT,
  player_yellow  TEXT,
  confidence     INT  NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 5),
  distinct_cols  INT  NOT NULL DEFAULT 0 CHECK (distinct_cols BETWEEN 0 AND 20),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS online_games (
  id             SERIAL PRIMARY KEY,
  code           TEXT UNIQUE NOT NULL,
  rows           INT  NOT NULL DEFAULT 8 CHECK (rows BETWEEN 4 AND 20),
  cols           INT  NOT NULL DEFAULT 9 CHECK (cols BETWEEN 4 AND 20),
  starting_color CHAR(1) NOT NULL DEFAULT 'R' CHECK (starting_color IN ('R','Y')),
  current_turn   CHAR(1) NOT NULL DEFAULT 'R' CHECK (current_turn IN ('R','Y')),
  status         TEXT NOT NULL DEFAULT 'waiting',
  winner         CHAR(1),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS online_players (
  id          SERIAL PRIMARY KEY,
  game_id     INT NOT NULL REFERENCES online_games(id) ON DELETE CASCADE,
  player_name TEXT NOT NULL,
  token       CHAR(1) NOT NULL,
  secret      TEXT NOT NULL,
  joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(game_id, token)
);

CREATE TABLE IF NOT EXISTS online_moves (
  id          SERIAL PRIMARY KEY,
  game_id     INT NOT NULL REFERENCES online_games(id) ON DELETE CASCADE,
  move_index  INT NOT NULL,
  token       CHAR(1) NOT NULL,
  col         INT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(game_id, move_index)
);

CREATE INDEX IF NOT EXISTS idx_saved_games_created_at ON saved_games(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_online_games_code ON online_games(code);
CREATE INDEX IF NOT EXISTS idx_online_moves_game_id ON online_moves(game_id);
"""


def init_db():
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL manquante, init_db ignoré")
        return

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(INIT_SQL)
        conn.commit()


# ══════════════════════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════════════════════

app = FastAPI(title="Puissance 4 Web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre plus tard si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    if os.environ.get("DATABASE_URL"):
        init_db()
        print("Base de données initialisée")
    else:
        print("DATABASE_URL absente : démarrage sans base de données")


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════
# IA
# ══════════════════════════════════════════════════════════════


class AIMoveReq(BaseModel):
    board: List[List[str]]
    player: str = "R"
    ai_mode: str = "minimax"
    depth: int = 4


@app.post("/api/ai/move")
def ai_move(req: AIMoveReq):
    player = req.player if req.player in (RED, YELLOW) else RED
    depth = max(1, min(8, req.depth))

    result = best_move(req.board, player, depth, req.ai_mode)

    return {
        "col": result.get("col"),
        "scores": result.get("scores", []),
        "player": player,
        "ai_mode": req.ai_mode,
        "depth": depth,
    }


@app.post("/api/ai/reload")
def ai_reload():
    ok = reload_model()
    return {"loaded": ok}


# ══════════════════════════════════════════════════════════════
# SAVED GAMES
# ══════════════════════════════════════════════════════════════


class SaveReq(BaseModel):
    save_name: Optional[str] = None
    rows_count: int
    cols_count: int
    starting_color: str = "R"
    ai_mode: str = "random"
    ai_depth: int = 4
    game_mode: int = 2
    status: str = "in_progress"
    winner: Optional[str] = None
    view_index: int = 0
    moves: List[int] = []
    player_red: Optional[str] = None
    player_yellow: Optional[str] = None
    confidence: int = 1


@app.post("/api/games")
def save_game(req: SaveReq):
    if req.starting_color not in (RED, YELLOW):
        raise HTTPException(400, "starting_color invalide")

    if req.winner not in (None, RED, YELLOW, "D"):
        raise HTTPException(400, "winner invalide")

    if not (4 <= req.rows_count <= 20 and 4 <= req.cols_count <= 20):
        raise HTTPException(400, "taille invalide")

    if not (1 <= req.ai_depth <= 8):
        raise HTTPException(400, "ai_depth invalide")

    if req.game_mode not in (0, 1, 2):
        raise HTTPException(400, "game_mode invalide")

    if req.status not in ("in_progress", "completed", "aborted"):
        raise HTTPException(400, "status invalide")

    for m in req.moves:
        if not isinstance(m, int) or m < 0 or m >= req.cols_count:
            raise HTTPException(400, f"move invalide: {m}")

    distinct = len(set(req.moves)) if req.moves else 0
    confidence = max(0, min(5, req.confidence))

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO saved_games
                (
                    save_name, rows_count, cols_count, starting_color,
                    ai_mode, ai_depth, game_mode, status, winner,
                    view_index, moves, player_red, player_yellow,
                    confidence, distinct_cols
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING game_id
                """,
                (
                    req.save_name,
                    req.rows_count,
                    req.cols_count,
                    req.starting_color,
                    req.ai_mode,
                    req.ai_depth,
                    req.game_mode,
                    req.status,
                    req.winner,
                    req.view_index,
                    json.dumps(req.moves),
                    req.player_red,
                    req.player_yellow,
                    confidence,
                    distinct,
                ),
            )
            gid = cur.fetchone()["game_id"]
        conn.commit()

    return {"game_id": gid}


@app.get("/api/games")
def list_games():
    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    game_id,
                    save_name,
                    rows_count,
                    cols_count,
                    starting_color,
                    ai_mode,
                    ai_depth,
                    game_mode,
                    status,
                    winner,
                    view_index,
                    COALESCE(confidence,1) AS confidence,
                    COALESCE(distinct_cols,0) AS distinct_cols,
                    jsonb_array_length(moves) AS total_moves,
                    created_at,
                    player_red,
                    player_yellow
                FROM saved_games
                ORDER BY created_at DESC
                LIMIT 200
                """
            )
            return cur.fetchall()


@app.get("/api/games/stats")
def games_stats():
    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    ROUND(AVG(jsonb_array_length(moves)), 1) AS avg_moves,
                    MIN(jsonb_array_length(moves)) AS min_moves,
                    MAX(jsonb_array_length(moves)) AS max_moves
                FROM saved_games
                """
            )
            return cur.fetchone()


@app.get("/api/games/{game_id}")
def get_game(game_id: int):
    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM saved_games WHERE game_id=%s", (game_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Partie introuvable")
            return row


@app.delete("/api/games/{game_id}")
def delete_game(game_id: int):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM saved_games WHERE game_id=%s RETURNING game_id",
                (game_id,),
            )
            deleted = cur.fetchone()
            if not deleted:
                raise HTTPException(404, "Partie introuvable")
        conn.commit()

    return {"deleted": game_id}


@app.post("/api/games/position")
def game_position(req: dict):
    game_id = req.get("game_id")
    view_index = req.get("view_index", 0)

    if not isinstance(game_id, int):
        raise HTTPException(400, "game_id invalide")

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT rows_count, cols_count, starting_color, moves FROM saved_games WHERE game_id=%s",
                (game_id,),
            )
            g = cur.fetchone()

    if not g:
        raise HTTPException(404, "Partie introuvable")

    rows = g["rows_count"]
    cols = g["cols_count"]
    start = g["starting_color"]
    moves = (
        g["moves"] if isinstance(g["moves"], list) else json.loads(g["moves"] or "[]")
    )

    vi = max(0, min(int(view_index), len(moves)))
    board = [[EMPTY] * cols for _ in range(rows)]

    current = start
    last_r = -1
    last_c = -1

    for i in range(vi):
        col = moves[i]
        for r in range(rows - 1, -1, -1):
            if board[r][col] == EMPTY:
                board[r][col] = current
                if i == vi - 1:
                    last_r, last_c = r, col
                break
        current = YELLOW if current == RED else RED

    win_cells = []
    winner = None
    if last_r >= 0:
        cells = check_win_cells(board, last_r, last_c, board[last_r][last_c])
        if cells:
            win_cells = cells
            winner = board[last_r][last_c]

    return {
        "board": board,
        "view_index": vi,
        "total_moves": len(moves),
        "to_play": current,
        "last_col": last_c if vi > 0 else None,
        "winner": winner,
        "win_cells": win_cells,
        "filled_cells": sum(1 for row in board for cell in row if cell != EMPTY),
        "legal_cols": sum(1 for c in range(cols) if board[0][c] == EMPTY),
    }


# ══════════════════════════════════════════════════════════════
# BGA IMPORT
# ══════════════════════════════════════════════════════════════


class BGAReq(BaseModel):
    table_id: str


@app.post("/api/bga/import")
def bga_import(req: BGAReq):
    tid = req.table_id.strip()
    if not tid.isdigit():
        raise HTTPException(400, "Numéro invalide")

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT game_id, rows_count, cols_count, moves FROM saved_games WHERE save_name=%s LIMIT 1",
                (f"BGA_{tid}",),
            )
            existing = cur.fetchone()

    if existing:
        moves = (
            existing["moves"]
            if isinstance(existing["moves"], list)
            else json.loads(existing["moves"] or "[]")
        )
        return {
            "game_id": existing["game_id"],
            "rows": existing["rows_count"],
            "cols": existing["cols_count"],
            "moves": moves,
            "cached": True,
        }

    try:
        rq = _req2.Request(
            f"https://boardgamearena.com/gamereview?table={tid}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; P4Bot/1.0)"},
        )
        with _req2.urlopen(rq, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(502, f"Impossible de contacter BGA : {e}")

    moves = []
    for pat in (
        _re.compile(r"place[rz]?\s+un\s+pion\s+dans\s+la\s+colonne\s+(\d+)", _re.I),
        _re.compile(
            r"(?:drops?\s+(?:a\s+)?(?:piece|token|disc)\s+(?:in(?:to)?\s+)?(?:column\s+)?|column\s+)(\d+)",
            _re.I,
        ),
    ):
        found = [int(m.group(1)) for m in pat.finditer(html)]
        if found:
            moves = found
            break

    if not moves:
        raise HTTPException(404, "Aucun coup trouvé — partie privée ?")

    if min(moves) >= 1 and max(moves) <= 20:
        moves = [c - 1 for c in moves]

    rows, cols = 9, 9
    sm = _re.search(r"(\d{1,2})\s*[x×]\s*(\d{1,2})", html, _re.I)
    if sm:
        rr, cc = int(sm.group(1)), int(sm.group(2))
        if 4 <= rr <= 20 and 4 <= cc <= 20:
            rows, cols = rr, cc

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO saved_games
                (
                    save_name, rows_count, cols_count, starting_color,
                    ai_mode, ai_depth, game_mode, status, view_index,
                    moves, distinct_cols
                )
                VALUES (%s,%s,%s,'R','bga',4,2,'completed',%s,%s,%s)
                RETURNING game_id
                """,
                (
                    f"BGA_{tid}",
                    rows,
                    cols,
                    len(moves),
                    json.dumps(moves),
                    len(set(moves)),
                ),
            )
            gid = cur.fetchone()["game_id"]
        conn.commit()

    return {
        "game_id": gid,
        "rows": rows,
        "cols": cols,
        "moves": moves,
        "cached": False,
    }


# ══════════════════════════════════════════════════════════════
# ONLINE MULTIPLAYER
# ══════════════════════════════════════════════════════════════


def _mk(rows, cols):
    return [[EMPTY] * cols for _ in range(rows)]


def _drop(board, col, token):
    for r in range(len(board) - 1, -1, -1):
        if board[r][col] == EMPTY:
            board[r][col] = token
            return r
    raise ValueError("colonne pleine")


def _win(board):
    rows, cols = len(board), len(board[0])

    for r in range(rows):
        for c in range(cols):
            t = board[r][c]
            if t not in (RED, YELLOW):
                continue
            for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                ok = True
                for k in range(1, 4):
                    nr, nc = r + dr * k, c + dc * k
                    if not (0 <= nr < rows and 0 <= nc < cols) or board[nr][nc] != t:
                        ok = False
                        break
                if ok:
                    return t

    if all(board[0][c] != EMPTY for c in range(cols)):
        return "D"

    return None


def _rebuild(rows, cols, moves):
    board = _mk(rows, cols)
    for m in moves:
        _drop(board, m["col"], m["token"])
    return board


def _code():
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()


class CreateOnlineReq(BaseModel):
    player_name: str = Field(min_length=1, max_length=40)
    rows: int = 8
    cols: int = 9
    starting_color: str = "R"


class JoinOnlineReq(BaseModel):
    code: str = Field(min_length=4, max_length=16)
    player_name: str = Field(min_length=1, max_length=40)


class MoveReq(BaseModel):
    player_secret: str = Field(min_length=10, max_length=200)
    col: int


@app.post("/api/online/create")
def online_create(req: CreateOnlineReq):
    code = _code()
    secret = secrets.token_urlsafe(24)
    rows = max(4, min(20, req.rows))
    cols = max(4, min(20, req.cols))
    start = req.starting_color if req.starting_color in (RED, YELLOW) else RED

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO online_games(code, rows, cols, starting_color, current_turn, status)
                VALUES(%s,%s,%s,%s,%s,'waiting')
                RETURNING id, code, rows, cols, starting_color
                """,
                (code, rows, cols, start, start),
            )
            g = cur.fetchone()

            cur.execute(
                """
                INSERT INTO online_players(game_id, player_name, token, secret)
                VALUES(%s,%s,%s,%s)
                RETURNING token
                """,
                (g["id"], req.player_name.strip(), g["starting_color"], secret),
            )
            pl = cur.fetchone()

        conn.commit()

    return {
        "code": g["code"],
        "rows": g["rows"],
        "cols": g["cols"],
        "starting_color": g["starting_color"],
        "your_token": pl["token"],
        "player_secret": secret,
        "share_url": f"/?join={g['code']}",
    }


@app.post("/api/online/join")
def online_join(req: JoinOnlineReq):
    code = req.code.strip().upper()
    secret = secrets.token_urlsafe(24)

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM online_games WHERE code=%s", (code,))
            g = cur.fetchone()
            if not g:
                raise HTTPException(404, "Code introuvable")

            cur.execute("SELECT token FROM online_players WHERE game_id=%s", (g["id"],))
            tokens = {r["token"] for r in cur.fetchall()}

            token = "R" if "R" not in tokens else ("Y" if "Y" not in tokens else "S")

            cur.execute(
                """
                INSERT INTO online_players(game_id, player_name, token, secret)
                VALUES(%s,%s,%s,%s)
                RETURNING token
                """,
                (g["id"], req.player_name.strip(), token, secret),
            )
            pl = cur.fetchone()

            if token in (RED, YELLOW):
                cur.execute(
                    "SELECT COUNT(*) AS c FROM online_players WHERE game_id=%s AND token IN('R','Y')",
                    (g["id"],),
                )
                if cur.fetchone()["c"] == 2 and g["status"] == "waiting":
                    cur.execute(
                        "UPDATE online_games SET status='playing' WHERE id=%s",
                        (g["id"],),
                    )

        conn.commit()

    return {
        "code": code,
        "rows": g["rows"],
        "cols": g["cols"],
        "starting_color": g["starting_color"],
        "your_token": pl["token"],
        "player_secret": secret,
    }


@app.get("/api/online/{code}/state")
def online_state(code: str):
    code = code.strip().upper()

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM online_games WHERE code=%s", (code,))
            g = cur.fetchone()
            if not g:
                raise HTTPException(404, "Partie introuvable")

            cur.execute(
                "SELECT move_index, token, col FROM online_moves WHERE game_id=%s ORDER BY move_index",
                (g["id"],),
            )
            moves = cur.fetchall()

            cur.execute(
                "SELECT token, player_name FROM online_players WHERE game_id=%s ORDER BY id",
                (g["id"],),
            )
            players = cur.fetchall()

    return {
        "code": code,
        "rows": g["rows"],
        "cols": g["cols"],
        "starting_color": g["starting_color"],
        "current_turn": g["current_turn"],
        "status": g["status"],
        "winner": g["winner"],
        "moves": [
            {"move_index": m["move_index"], "token": m["token"], "col": m["col"]}
            for m in moves
        ],
        "players": players,
    }


@app.post("/api/online/{code}/move")
def online_move(code: str, req: MoveReq):
    code = code.strip().upper()

    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM online_games WHERE code=%s FOR UPDATE", (code,))
            g = cur.fetchone()
            if not g:
                raise HTTPException(404, "Partie introuvable")

            if g["status"] == "finished":
                raise HTTPException(409, "Partie terminée")

            cur.execute(
                "SELECT * FROM online_players WHERE game_id=%s AND secret=%s",
                (g["id"], req.player_secret),
            )
            p = cur.fetchone()
            if not p:
                raise HTTPException(401, "Joueur non reconnu")

            token = p["token"]
            if token not in (RED, YELLOW):
                raise HTTPException(403, "Spectateur")

            if token != g["current_turn"]:
                raise HTTPException(409, "Pas ton tour")

            cur.execute(
                "SELECT move_index, token, col FROM online_moves WHERE game_id=%s ORDER BY move_index",
                (g["id"],),
            )
            mvs = cur.fetchall()

            board = _rebuild(g["rows"], g["cols"], mvs)

            try:
                _drop(board, req.col, token)
            except ValueError as e:
                raise HTTPException(409, str(e))

            cur.execute(
                "INSERT INTO online_moves(game_id, move_index, token, col) VALUES(%s,%s,%s,%s)",
                (g["id"], len(mvs), token, req.col),
            )

            w = _win(board)
            if w:
                cur.execute(
                    "UPDATE online_games SET status='finished', winner=%s WHERE id=%s",
                    (w, g["id"]),
                )
                next_turn = g["current_turn"]
            else:
                next_turn = YELLOW if token == RED else RED
                cur.execute(
                    "UPDATE online_games SET current_turn=%s, status='playing' WHERE id=%s",
                    (next_turn, g["id"]),
                )

        conn.commit()

    return {"ok": True, "next_turn": next_turn}


# ══════════════════════════════════════════════════════════════
# STATIC FILES
# ══════════════════════════════════════════════════════════════

PUBLIC_DIR = os.path.join(BASE_DIR, "public")
if os.path.isdir(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
