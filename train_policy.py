import json
import os
import joblib
import psycopg2
import numpy as np

from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
from collections import Counter

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "puissance4_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", "5432")),
}

ROWS = 9
COLS = 9
CONNECT_N = 4
MIN_MOVES = 8

# Seuils de qualité
MIN_POSITION_CONFIDENCE = 0.45   # on garde seulement les coups au-dessus de ce score
MIN_GAME_CONFIDENCE = 0.55       # on ignore les parties globalement trop faibles
MAX_SAMPLES_PER_GAME = None      # ex: 40 pour limiter le volume, ou None
RANDOM_STATE = 42

MODEL_PATH = "connect4_policy_9x9.pkl"
SCALER_PATH = "connect4_policy_9x9_scaler.pkl"


# ══════════════════════════════════════════════════════════════
# BOARD HELPERS
# ══════════════════════════════════════════════════════════════

def create_board(rows=ROWS, cols=COLS):
    return [[0 for _ in range(cols)] for _ in range(rows)]


def copy_board(board):
    return [row[:] for row in board]


def valid_columns(board):
    return [c for c in range(len(board[0])) if board[0][c] == 0]


def drop_piece(board, col, player):
    for r in range(len(board) - 1, -1, -1):
        if board[r][col] == 0:
            board[r][col] = player
            return r
    return -1


def board_full(board):
    return all(board[0][c] != 0 for c in range(len(board[0])))


def count_pieces(board):
    return sum(1 for row in board for cell in row if cell != 0)


def inside(board, r, c):
    return 0 <= r < len(board) and 0 <= c < len(board[0])


def check_winner(board, player, connect_n=CONNECT_N):
    rows = len(board)
    cols = len(board[0])

    directions = [
        (0, 1),   # horizontal
        (1, 0),   # vertical
        (1, 1),   # diag down-right
        (1, -1),  # diag down-left
    ]

    for r in range(rows):
        for c in range(cols):
            if board[r][c] != player:
                continue

            for dr, dc in directions:
                ok = True
                for k in range(1, connect_n):
                    rr = r + dr * k
                    cc = c + dc * k
                    if not inside(board, rr, cc) or board[rr][cc] != player:
                        ok = False
                        break
                if ok:
                    return True
    return False


def winning_columns(board, player):
    wins = []
    for col in valid_columns(board):
        tmp = copy_board(board)
        row = drop_piece(tmp, col, player)
        if row != -1 and check_winner(tmp, player):
            wins.append(col)
    return wins


def center_preference(col, cols):
    center = (cols - 1) / 2.0
    dist = abs(col - center)
    max_dist = center if center > 0 else 1
    return 1.0 - (dist / max_dist)


def board_to_features(board, current_player):
    """
    Encodage 3 canaux :
    - cases du joueur courant
    - cases de l'adversaire
    - cases vides
    + features globales simples
    """
    current = []
    opponent = []
    empty = []

    for row in board:
        for cell in row:
            current.append(1 if cell == current_player else 0)
            opponent.append(1 if cell == -current_player else 0)
            empty.append(1 if cell == 0 else 0)

    # Features globales
    moves_played = count_pieces(board)
    progress = moves_played / float(len(board) * len(board[0]))

    current_immediate_wins = len(winning_columns(board, current_player)) / float(len(board[0]))
    opp_immediate_wins = len(winning_columns(board, -current_player)) / float(len(board[0]))
    valid_count = len(valid_columns(board)) / float(len(board[0]))

    extra = [progress, current_immediate_wins, opp_immediate_wins, valid_count]

    return current + opponent + empty + extra


# ══════════════════════════════════════════════════════════════
# CONFIDENCE / QUALITY HEURISTICS
# ══════════════════════════════════════════════════════════════

def evaluate_move_confidence(board_before, move, current_player):
    """
    Retourne un score de confiance entre 0 et 1 pour le coup joué.

    Heuristiques utilisées :
    - jouer un coup gagnant immédiat => très fort
    - bloquer un gain immédiat adverse => fort
    - rater un coup gagnant immédiat => très mauvais
    - laisser un gain immédiat adverse après son coup => très mauvais
    - préférence légère pour le centre
    """

    valid = valid_columns(board_before)
    if move not in valid:
        return 0.0

    own_wins_before = winning_columns(board_before, current_player)
    opp_wins_before = winning_columns(board_before, -current_player)

    score = 0.50  # base neutre

    # 1) Si le joueur pouvait gagner tout de suite
    if own_wins_before:
        if move in own_wins_before:
            score += 0.40
        else:
            score -= 0.45

    # 2) Si l'adversaire avait un gain immédiat, bloquer est important
    if opp_wins_before:
        if move in opp_wins_before:
            score += 0.25
        else:
            score -= 0.30

    # 3) Simuler le coup
    after = copy_board(board_before)
    row = drop_piece(after, move, current_player)
    if row == -1:
        return 0.0

    # 4) Coup gagnant maintenant
    if check_winner(after, current_player):
        score += 0.35

    # 5) Est-ce qu'on donne un gain immédiat à l'adversaire ?
    opp_wins_after = winning_columns(after, -current_player)
    if opp_wins_after:
        score -= 0.35

    # 6) Léger bonus positionnel au centre
    score += 0.08 * center_preference(move, len(board_before[0]))

    # 7) Un petit bonus quand la partie avance, car les coups sont
    # souvent plus "informatifs" tactiquement
    progress = count_pieces(board_before) / float(len(board_before) * len(board_before[0]))
    score += 0.07 * progress

    # Clamp
    score = max(0.0, min(1.0, score))
    return score


def compute_game_confidence(position_confidences):
    if not position_confidences:
        return 0.0

    arr = np.array(position_confidences, dtype=np.float32)

    # Moyenne + pénalité si trop de très mauvais coups
    mean_conf = float(arr.mean())
    low_ratio = float((arr < 0.35).mean())
    game_conf = mean_conf - 0.35 * low_ratio

    return max(0.0, min(1.0, game_conf))


# ══════════════════════════════════════════════════════════════
# DATA FETCH
# ══════════════════════════════════════════════════════════════

def fetch_games():
    query = """
    SELECT id, rows, cols, starting_color, moves
    FROM saved_games
    WHERE rows = %s
      AND cols = %s
      AND moves IS NOT NULL
      AND jsonb_typeof(moves) = 'array'
      AND jsonb_array_length(moves) > 0
    ORDER BY id;
    """

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(query, (ROWS, COLS))
    games = cur.fetchall()
    cur.close()
    conn.close()
    return games


# ══════════════════════════════════════════════════════════════
# DATASET BUILD
# ══════════════════════════════════════════════════════════════

def build_dataset(games):
    X, y = [], []

    skipped_invalid = 0
    skipped_short = 0
    skipped_low_conf_games = 0

    kept_games = 0
    total_positions = 0
    kept_positions = 0

    for game in games:
        game_id, rows_count, cols_count, starting_color, moves = game

        if isinstance(moves, str):
            try:
                moves = json.loads(moves)
            except Exception:
                skipped_invalid += 1
                continue

        if not isinstance(moves, list) or len(moves) < MIN_MOVES:
            skipped_short += 1
            continue

        board = create_board(rows_count, cols_count)
        current_player = 1 if starting_color == "R" else -1

        ok_game = True
        game_samples_X = []
        game_samples_y = []
        game_position_confidences = []

        for move in moves:
            total_positions += 1

            # Validation basique
            if not isinstance(move, int):
                ok_game = False
                break

            if move < 0 or move >= cols_count:
                ok_game = False
                break

            if move not in valid_columns(board):
                ok_game = False
                break

            features = board_to_features(board, current_player)
            conf = evaluate_move_confidence(board, move, current_player)

            # On garde seulement les positions suffisamment fiables
            if conf >= MIN_POSITION_CONFIDENCE:
                game_samples_X.append(features)
                game_samples_y.append(move)
                game_position_confidences.append(conf)
                kept_positions += 1

            # On joue le coup pour continuer l'analyse
            if drop_piece(board, move, current_player) == -1:
                ok_game = False
                break

            # Si quelqu'un a gagné, on s'arrête proprement
            if check_winner(board, current_player):
                current_player *= -1
                break

            if board_full(board):
                current_player *= -1
                break

            current_player *= -1

        if not ok_game:
            skipped_invalid += 1
            continue

        game_conf = compute_game_confidence(game_position_confidences)

        if game_conf < MIN_GAME_CONFIDENCE or len(game_samples_X) == 0:
            skipped_low_conf_games += 1
            continue

        kept_games += 1

        if MAX_SAMPLES_PER_GAME is not None and len(game_samples_X) > MAX_SAMPLES_PER_GAME:
            # garde les positions les plus confiantes
            idx_sorted = np.argsort(game_position_confidences)[::-1][:MAX_SAMPLES_PER_GAME]
            idx_sorted = sorted(idx_sorted.tolist())
            for idx in idx_sorted:
                X.append(game_samples_X[idx])
                y.append(game_samples_y[idx])
        else:
            X.extend(game_samples_X)
            y.extend(game_samples_y)

    print("Positions totales analysées :", total_positions)
    print("Positions retenues :", len(X))
    print("Parties retenues :", kept_games)
    print("Parties ignorées (invalides) :", skipped_invalid)
    print("Parties ignorées (trop courtes) :", skipped_short)
    print("Parties ignorées (faible confiance) :", skipped_low_conf_games)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)


# ══════════════════════════════════════════════════════════════
# TRAINING
# ══════════════════════════════════════════════════════════════

def show_label_distribution(y):
    counter = Counter(y.tolist())
    print("\nDistribution des colonnes :")
    for col in range(COLS):
        print(f"Colonne {col} : {counter.get(col, 0)}")


def train_model(X, y):
    if len(X) == 0 or len(y) == 0:
        raise ValueError("Dataset vide.")

    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        raise ValueError("Pas assez de colonnes différentes dans y pour entraîner le modèle.")

    show_label_distribution(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=y
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    model = MLPClassifier(
        hidden_layer_sizes=(512, 256, 128),
        activation="relu",
        solver="adam",
        alpha=0.0003,
        batch_size=256,
        learning_rate_init=0.001,
        max_iter=300,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=15,
        random_state=RANDOM_STATE,
        verbose=True
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print("\nAccuracy :", acc)
    print("\nClassification report :")
    print(classification_report(y_test, y_pred))

    return model, scaler


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    print("Connexion DB...")
    games = fetch_games()
    print("Parties récupérées :", len(games))

    X, y = build_dataset(games)
    print("Shape X :", X.shape)
    print("Shape y :", y.shape)

    if len(X) == 0 or len(y) == 0:
        print("Aucune donnée exploitable trouvée pour l'entraînement.")
        return

    model, scaler = train_model(X, y)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    print(f"\nModèle sauvegardé : {MODEL_PATH}")
    print(f"Scaler sauvegardé : {SCALER_PATH}")


if __name__ == "__main__":
    main()