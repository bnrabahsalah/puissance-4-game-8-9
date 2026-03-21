# -*- coding: utf-8 -*-
"""
bga_import.py
Import de parties Connect4 scrapées sur BGA vers PostgreSQL
"""

import json
import hashlib
from typing import Any, Dict, List, Optional

import psycopg2
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


def db_connect():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("UTF8")
    return conn


def ensure_saved_games_table():
    create_sql = """
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

    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
        conn.commit()


def _extract_cols_from_moves(moves: List[Dict[str, Any]]) -> List[int]:
    cols = []
    for m in moves or []:
        if isinstance(m, dict) and "col" in m:
            try:
                cols.append(int(m["col"]))
            except Exception:
                pass
    return cols


def _normalize_cols(cols_raw: List[int], cols_count: int) -> List[int]:
    if not cols_raw:
        return []

    mn = min(cols_raw)
    mx = max(cols_raw)

    if mn == 0 and mx <= cols_count - 1:
        return cols_raw

    if mn >= 1 and mx <= cols_count:
        return [c - 1 for c in cols_raw]

    if mn >= 0 and mx <= cols_count - 1:
        return cols_raw

    raise ValueError(
        f"Inconsistent columns: min={mn}, max={mx}, cols_count={cols_count}"
    )


def _moves_signature(cols_0_based: List[int]) -> str:
    payload = json.dumps(
        cols_0_based, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def import_bga_moves(
    moves: List[Dict[str, Any]],
    rows: int = 9,
    cols: int = 9,
    confiance: int = 3,
    save_name: Optional[str] = None,
    starting_color: str = "R",
) -> int:
    ensure_saved_games_table()

    if starting_color not in ("R", "Y"):
        starting_color = "R"

    cols_raw = _extract_cols_from_moves(moves)
    cols_0 = _normalize_cols(cols_raw, cols_count=cols)

    if not cols_0:
        raise ValueError("No valid move to import.")

    distinct_cols = len(set(cols_0))
    signature = _moves_signature(cols_0)
    moves_json = json.dumps(cols_0, ensure_ascii=False)

    if not save_name:
        save_name = f"BGA_{rows}x{cols}_{signature[:12]}"

    select_dup = """
    SELECT id
    FROM saved_games
    WHERE rows = %s AND cols = %s AND moves = %s::jsonb
    LIMIT 1;
    """

    insert_sql = """
    INSERT INTO saved_games
      (
        save_name, rows, cols, starting_color, mode, game_index,
        moves, view_index, ai_mode, ai_depth, confidence, distinct_cols, save_date
      )
    VALUES
      (
        %s, %s, %s, %s, %s, %s,
        %s::jsonb, %s, %s, %s, %s, %s, NOW()
      )
    RETURNING id;
    """

    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(select_dup, (int(rows), int(cols), moves_json))
            row = cur.fetchone()
            if row:
                return int(row[0])

            cur.execute(
                insert_sql,
                (
                    save_name,
                    int(rows),
                    int(cols),
                    starting_color,
                    2,
                    1,
                    moves_json,
                    0,
                    "bga",
                    4,
                    int(confiance),
                    int(distinct_cols),
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    return int(new_id)
