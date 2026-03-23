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

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "puissance4_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", "5432")),
}

ROWS = 9
COLS = 9
MIN_MOVES = 8


def create_board(rows=ROWS, cols=COLS):
    return [[0 for _ in range(cols)] for _ in range(rows)]


def valid_columns(board):
    return [c for c in range(len(board[0])) if board[0][c] == 0]


def drop_piece(board, col, player):
    for r in range(len(board) - 1, -1, -1):
        if board[r][col] == 0:
            board[r][col] = player
            return True
    return False


def board_to_features(board, current_player):
    """
    Représentation améliorée:
    - canal 1: cases du joueur courant
    - canal 2: cases de l'adversaire
    - canal 3: cases vides
    """
    current = []
    opponent = []
    empty = []

    for row in board:
        for cell in row:
            current.append(1 if cell == current_player else 0)
            opponent.append(1 if cell == -current_player else 0)
            empty.append(1 if cell == 0 else 0)

    return current + opponent + empty


def fetch_games():
    query = """
    SELECT id, rows, cols, starting_color, moves
    FROM saved_games
    WHERE rows = %s
      AND cols = %s
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


def build_dataset(games):
    X, y = [], []
    skipped_invalid = 0
    skipped_short = 0

    for game in games:
        game_id, rows_count, cols_count, starting_color, moves = game

        if isinstance(moves, str):
            moves = json.loads(moves)

        if not isinstance(moves, list) or len(moves) < MIN_MOVES:
            skipped_short += 1
            continue

        board = create_board(rows_count, cols_count)
        current_player = 1 if starting_color == "R" else -1
        ok_game = True

        for move in moves:
            if not isinstance(move, int):
                ok_game = False
                break

            if move < 0 or move >= cols_count:
                ok_game = False
                break

            if move not in valid_columns(board):
                ok_game = False
                break

            X.append(board_to_features(board, current_player))
            y.append(move)

            if not drop_piece(board, move, current_player):
                ok_game = False
                break

            current_player *= -1

        if not ok_game:
            skipped_invalid += 1

    print("Positions générées :", len(X))
    print("Parties ignorées (invalides) :", skipped_invalid)
    print("Parties ignorées (trop courtes) :", skipped_short)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)


def show_label_distribution(y):
    counter = Counter(y.tolist())
    print("Distribution des colonnes :")
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
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    model = MLPClassifier(
        hidden_layer_sizes=(512, 256, 128),
        activation="relu",
        solver="adam",
        alpha=0.0001,
        batch_size=256,
        learning_rate_init=0.001,
        max_iter=300,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=15,
        random_state=42,
        verbose=True
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print("\nAccuracy :", acc)
    print("\nClassification report :")
    print(classification_report(y_test, y_pred))

    return model, scaler


def main():
    games = fetch_games()
    print("Parties récupérées :", len(games))

    X, y = build_dataset(games)
    print("Shape X :", X.shape)
    print("Shape y :", y.shape)

    if len(X) == 0 or len(y) == 0:
        print("Aucune donnée trouvée pour l'entraînement.")
        return

    model, scaler = train_model(X, y)

    joblib.dump(model, "connect4_policy_9x9.pkl")
    joblib.dump(scaler, "connect4_policy_9x9_scaler.pkl")

    print("\nModèle sauvegardé : connect4_policy_9x9.pkl")
    print("Scaler sauvegardé : connect4_policy_9x9_scaler.pkl")


if __name__ == "__main__":
    main()