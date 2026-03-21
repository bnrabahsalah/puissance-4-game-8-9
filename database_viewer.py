"""
OUTIL DE VISUALISATION DE LA BASE DE DONNÉES PUISSANCE 4
Version compatible avec l'application game.py (table saved_games uniquement)

✅ AJOUT :
- Afficher confidence/confiance
- Afficher distinct_cols (nombre de colonnes distinctes utilisées)

✅ MISSION 3 :
- Informations de la partie dynamiques (position, prochain joueur)
- Détails de la position dynamiques (dernier coup, cases occupées, colonnes jouables, hash)
- Navigation fonctionnelle (ne réécrase plus view_index)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import psycopg2
import json
import hashlib
import os
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


class DatabaseViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Visualisateur Base de Données Puissance 4")
        self.geometry("1400x800")

        self.conn = None
        self.connect_to_db()

        self.current_game_id = None
        self.moves = []
        self.view_index = 0
        self.board_rows = 8
        self.board_cols = 9
        self.starting_color = "R"

        # ✅ NEW: meta statique de la partie (pour mise à jour dynamique sans SQL)
        self.game_meta = {}

        self.search_var = tk.StringVar()

        self.COLORS = {
            "bg": "#00478e",
            "hole": "#e3f2fd",
            "red": "#d32f2f",
            "yellow": "#fbc02d",
            "win": "#00c853",
            "grid": "#1e88e5",
        }

        self.EMPTY = "."
        self.RED = "R"
        self.YELLOW = "Y"

        self.build_ui()
        self.load_games_list()

    def connect_to_db(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            print("✅ Connecté à la base de données")
        except Exception as e:
            messagebox.showerror(
                "Erreur de connexion",
                f"Impossible de se connecter à la base:\n{str(e)}\n\n"
                f"Assurez-vous que PostgreSQL tourne et que la table 'saved_games' existe.",
            )
            self.destroy()

    def execute_query(self, query, params=None, fetch=True):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                self.conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"❌ Erreur requête: {e}")
            messagebox.showerror("Erreur SQL", str(e))
            return None

    def column_exists(self, table_name: str, column_name: str) -> bool:
        q = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=%s
              AND column_name=%s
        )
        """
        r = self.execute_query(q, (table_name, column_name))
        return bool(r and r[0] and r[0][0])

    def build_ui(self):
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="🔍 Recherche:", font=("Arial", 10)).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<Return>", lambda e: self.load_games_list())

        ttk.Button(top_frame, text="Rechercher", command=self.load_games_list).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(top_frame, text="Actualiser", command=self.refresh_all).pack(
            side=tk.LEFT, padx=5
        )

        self.count_var = tk.StringVar(value="")
        ttk.Label(
            top_frame, textvariable=self.count_var, font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=15)

        action_frame = ttk.Frame(top_frame)
        action_frame.pack(side=tk.RIGHT)

        ttk.Button(
            action_frame, text="📤 Importer JSON", command=self.import_json
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="📊 Statistiques", command=self.show_stats).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(
            action_frame, text="🗑 Supprimer", command=self.delete_selected_game
        ).pack(side=tk.LEFT, padx=2)

        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        left_panel = ttk.Frame(main_container, width=520)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)

        list_frame = ttk.LabelFrame(left_panel, text="Parties sauvegardées", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = (
            "ID",
            "Nom",
            "Taille",
            "Mode",
            "IA",
            "Confiance",
            "ColsUsed",
            "Coups",
            "Date",
        )
        self.games_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=20
        )

        col_config = [
            ("ID", 50, "center"),
            ("Nom", 170, "w"),
            ("Taille", 70, "center"),
            ("Mode", 110, "center"),
            ("IA", 120, "center"),
            ("Confiance", 80, "center"),
            ("ColsUsed", 80, "center"),
            ("Coups", 70, "center"),
            ("Date", 120, "center"),
        ]
        for col, width, anchor in col_config:
            self.games_tree.heading(col, text=col)
            self.games_tree.column(col, width=width, anchor=anchor)

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.games_tree.yview
        )
        self.games_tree.configure(yscrollcommand=scrollbar.set)

        self.games_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.games_tree.bind("<<TreeviewSelect>>", self.on_game_select)

        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        info_frame = ttk.LabelFrame(
            right_panel, text="Informations de la partie", padding=10
        )
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.info_text = tk.Text(info_frame, height=8, width=60, font=("Courier", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)

        canvas_frame = ttk.LabelFrame(
            right_panel, text="Visualisation du plateau", padding=10
        )
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        nav_frame = ttk.Frame(right_panel)
        nav_frame.pack(fill=tk.X, pady=10)

        ttk.Button(nav_frame, text="⏮ Début", command=lambda: self.navigate_to(0)).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(nav_frame, text="◀ Précédent", command=self.prev_move).pack(
            side=tk.LEFT, padx=2
        )

        self.nav_label = ttk.Label(nav_frame, text="Coup 0/0", font=("Arial", 10))
        self.nav_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(nav_frame, text="Suivant ▶", command=self.next_move).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(nav_frame, text="Fin ⏭", command=self.go_to_end).pack(
            side=tk.LEFT, padx=2
        )

        self.nav_scale = tk.Scale(
            nav_frame,
            from_=0,
            to=0,
            orient="horizontal",
            showvalue=True,
            command=self.on_scale_move,
            length=300,
        )
        self.nav_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        bottom_frame = ttk.LabelFrame(
            right_panel, text="Détails de la position", padding=10
        )
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        self.pos_info_text = tk.Text(
            bottom_frame, height=6, width=60, font=("Courier", 9)
        )
        self.pos_info_text.pack(fill=tk.BOTH, expand=True)

    # =======================
    # LIST + DETAILS
    # =======================
    def load_games_list(self):
        self.games_tree.delete(*self.games_tree.get_children())

        has_confidence = self.column_exists("saved_games", "confidence")
        has_confiance = self.column_exists("saved_games", "confiance")
        has_distinct = self.column_exists("saved_games", "distinct_cols")

        conf_expr = "1"
        if has_confidence:
            conf_expr = "COALESCE(confidence, 1)"
        elif has_confiance:
            conf_expr = "COALESCE(confiance, 1)"

        distinct_expr = """
        (
          SELECT COUNT(DISTINCT (x)::int)
          FROM jsonb_array_elements_text(moves) AS x
        )
        """
        if has_distinct:
            distinct_expr = f"COALESCE(distinct_cols, {distinct_expr})"

        query = f"""
        SELECT 
            id,
            save_name,
            CONCAT(rows, 'x', cols) as taille,
            CASE mode
                WHEN 0 THEN 'IA vs IA'
                WHEN 1 THEN 'Humain vs IA'
                WHEN 2 THEN 'Humain vs Humain'
                ELSE 'Inconnu'
            END as mode_jeu,
            CONCAT(ai_mode, ' (', ai_depth, ')') as ia,
            {conf_expr} as confiance,
            {distinct_expr} as distinct_cols,
            jsonb_array_length(moves) as nb_coups,
            TO_CHAR(save_date, 'DD/MM HH24:MI') as date_save
        FROM saved_games
        WHERE 1=1
        """

        params = []
        search_text = self.search_var.get().strip()
        if search_text:
            query += " AND (save_name ILIKE %s OR id::TEXT LIKE %s)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])

        query += " ORDER BY save_date DESC LIMIT 100"

        games = self.execute_query(query, params)
        if games:
            for game in games:
                self.games_tree.insert("", "end", values=game)

        # Compteur total (toutes parties, sans filtre de recherche)
        count_result = self.execute_query("SELECT COUNT(*) FROM saved_games")
        total = count_result[0][0] if count_result else 0
        shown = len(games) if games else 0
        if search_text:
            self.count_var.set(f"🗃  {shown} résultat(s)  /  {total} partie(s) en base")
        else:
            self.count_var.set(f"🗃  {total} partie(s) en base")

    def on_game_select(self, event):
        selection = self.games_tree.selection()
        if not selection:
            return
        item = self.games_tree.item(selection[0])
        self.current_game_id = item["values"][0]
        self.load_game_details(self.current_game_id)

    def load_game_details(self, game_id):
        has_confidence = self.column_exists("saved_games", "confidence")
        has_confiance = self.column_exists("saved_games", "confiance")
        has_distinct = self.column_exists("saved_games", "distinct_cols")

        conf_expr = "1"
        if has_confidence:
            conf_expr = "COALESCE(confidence, 1)"
        elif has_confiance:
            conf_expr = "COALESCE(confiance, 1)"

        distinct_expr = "0"
        if has_distinct:
            distinct_expr = "COALESCE(distinct_cols, 0)"

        query = f"""
        SELECT 
            id, save_name, rows, cols, starting_color,
            mode, game_index, ai_mode, ai_depth,
            moves, view_index, save_date,
            {conf_expr} as confiance,
            {distinct_expr} as distinct_cols
        FROM saved_games
        WHERE id = %s
        """

        result = self.execute_query(query, (game_id,))
        if not result or not result[0]:
            return

        game_data = result[0]

        moves_json = game_data[9]
        if moves_json:
            self.moves = (
                json.loads(moves_json)
                if isinstance(moves_json, str)
                else list(moves_json)
            )
        else:
            self.moves = []

        self.board_rows = game_data[2]
        self.board_cols = game_data[3]
        self.starting_color = game_data[4]
        self.view_index = int(game_data[10]) if game_data[10] is not None else 0

        # clamp au cas où
        self.view_index = max(0, min(self.view_index, len(self.moves)))

        confiance = int(game_data[12]) if game_data[12] is not None else 1
        distinct_cols = (
            int(game_data[13])
            if (has_distinct and game_data[13] is not None)
            else (len(set(self.moves)) if self.moves else 0)
        )

        # ✅ stock meta statique (pour update dynamique sans SQL)
        self.game_meta = {
            "id": game_data[0],
            "save_name": game_data[1],
            "mode": game_data[5],
            "game_index": game_data[6],
            "ai_mode": game_data[7],
            "ai_depth": game_data[8],
            "confiance": confiance,
            "distinct_cols": distinct_cols,
            "save_date": game_data[11],
        }

        self.update_game_info_panel()
        self.update_navigation()
        self.display_current_position()

    def update_game_info_panel(self):
        """Met à jour le panneau 'Informations de la partie' selon self.view_index, sans requête SQL."""
        if not self.game_meta:
            return

        total_moves = len(self.moves)
        next_player = (
            "Rouge" if self.get_player_at_index(self.view_index) == "R" else "Jaune"
        )

        info = f"""
╔══════════════════════════════════════════════════════════════╗
║ PARTIE: {self.game_meta['save_name']} (ID: {self.game_meta['id']})
╠══════════════════════════════════════════════════════════════╣
║ • Taille: {self.board_rows}x{self.board_cols}
║ • Premier joueur: {'Rouge' if self.starting_color == 'R' else 'Jaune'}
║ • Mode: {self.get_mode_name(self.game_meta['mode'])}
║ • Index partie: {self.game_meta['game_index']}
║ • IA: {self.game_meta['ai_mode']} (profondeur: {self.game_meta['ai_depth']})
║ • Confiance: {self.game_meta['confiance']}
║ • Colonnes utilisées: {self.game_meta['distinct_cols']}
║ • Coups joués: {total_moves}
║ • Position actuelle: {self.view_index}/{total_moves}
║ • Prochain joueur: {next_player}
║ • Sauvegardée: {self.game_meta['save_date'].strftime('%d/%m/%Y %H:%M:%S')}
╚══════════════════════════════════════════════════════════════╝
"""

        self.info_text.config(state="normal")
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)
        self.info_text.config(state="disabled")

    # =======================
    # BOARD VIEW
    # =======================
    def display_current_position(self):
        board = self.reconstruct_board(self.view_index)
        self.draw_board(board)

        # Joueur "à jouer" sur la position courante
        to_play = self.get_player_at_index(self.view_index)

        # Dernier coup = coup qui vient d'être joué (si view_index > 0)
        last_col = self.moves[self.view_index - 1] if self.view_index > 0 else None

        move_info = {
            "index": self.view_index,
            "last_col": last_col,
            "to_play": to_play,
            "board": board,
        }
        self.display_position_info(move_info)

    def reconstruct_board(self, up_to_index):
        board = [
            [self.EMPTY for _ in range(self.board_cols)] for _ in range(self.board_rows)
        ]
        current_color = self.starting_color

        for i in range(min(up_to_index, len(self.moves))):
            col = self.moves[i]
            for row in range(self.board_rows - 1, -1, -1):
                if board[row][col] == self.EMPTY:
                    board[row][col] = current_color
                    break
            current_color = self.YELLOW if current_color == self.RED else self.RED

        return board

    def get_player_at_index(self, move_index):
        # joueur qui DOIT jouer au coup move_index
        if move_index == 0:
            return self.starting_color
        # si starting_color = R, alors coup 1 joué par R, coup 2 par Y, etc.
        # joueur à jouer au move_index = inverse du dernier joueur joué
        last_player = (
            self.starting_color
            if (move_index - 1) % 2 == 0
            else (self.YELLOW if self.starting_color == self.RED else self.RED)
        )
        return self.YELLOW if last_player == self.RED else self.RED

    def draw_board(self, board):
        self.canvas.delete("all")
        if not board:
            return

        rows = len(board)
        cols = len(board[0])

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 10 or canvas_height < 10:
            canvas_width = 500
            canvas_height = 500

        cell_size = min(canvas_width / cols, canvas_height / rows) * 0.8
        margin_x = (canvas_width - cols * cell_size) / 2
        margin_y = (canvas_height - rows * cell_size) / 2

        self.canvas.create_rectangle(
            margin_x,
            margin_y,
            margin_x + cols * cell_size,
            margin_y + rows * cell_size,
            fill=self.COLORS["bg"],
            outline="",
        )

        hole_radius = cell_size * 0.4
        for r in range(rows):
            for c in range(cols):
                center_x = margin_x + c * cell_size + cell_size / 2
                center_y = margin_y + r * cell_size + cell_size / 2

                if board[r][c] == self.RED:
                    color = self.COLORS["red"]
                elif board[r][c] == self.YELLOW:
                    color = self.COLORS["yellow"]
                else:
                    color = self.COLORS["hole"]

                self.canvas.create_oval(
                    center_x - hole_radius,
                    center_y - hole_radius,
                    center_x + hole_radius,
                    center_y + hole_radius,
                    fill=color,
                    outline=self.COLORS["grid"],
                    width=2,
                )

        for c in range(cols):
            x = margin_x + c * cell_size + cell_size / 2
            y = margin_y + rows * cell_size + 20
            self.canvas.create_text(
                x, y, text=str(c + 1), fill="white", font=("Arial", 12, "bold")
            )

    # =======================
    # POSITION DETAILS (DYNAMIQUE)
    # =======================
    def count_legal_columns(self, board):
        """Nombre de colonnes jouables = cases vides sur la première ligne."""
        if not board:
            return 0
        legal = 0
        for col in range(self.board_cols):
            if board[0][col] == self.EMPTY:
                legal += 1
        return legal

    def display_position_info(self, move):
        board = move["board"] if move else None
        if not board:
            board = [
                [self.EMPTY for _ in range(self.board_cols)]
                for _ in range(self.board_rows)
            ]

        # dernier coup
        if move and move["last_col"] is not None and move["index"] > 0:
            last_move = f"Colonne {move['last_col'] + 1}"
        else:
            last_move = "Aucun"

        # joueur à jouer (position courante)
        to_play = move["to_play"] if move else self.starting_color
        player_name = "Rouge" if to_play == "R" else "Jaune"

        filled_cells = sum(row.count("R") + row.count("Y") for row in board)
        legal_cols = self.count_legal_columns(board)
        board_hash = self.calculate_board_hash(board)[:16]

        title = (
            "POSITION INITIALE - Coup 0"
            if (move and move["index"] == 0)
            else f"POSITION - Coup {move['index'] if move else 0}"
        )

        info = f"""
╔══════════════════════════════════════════════════════════════╗
║ {title}
╠══════════════════════════════════════════════════════════════╣
║ • Dernier coup: {last_move}
║ • Joueur actuel (à jouer): {player_name}
║ • Cases occupées: {filled_cells}
║ • Colonnes jouables: {legal_cols}
║ • Hash position: {board_hash}...
╚══════════════════════════════════════════════════════════════╝
"""

        self.pos_info_text.config(state="normal")
        self.pos_info_text.delete(1.0, tk.END)
        self.pos_info_text.insert(1.0, info)
        self.pos_info_text.config(state="disabled")

    # =======================
    # NAVIGATION
    # =======================
    def update_navigation(self):
        total = len(self.moves)
        self.nav_scale.config(to=max(0, total))
        self.nav_scale.set(self.view_index)
        self.nav_label.config(text=f"Coup {self.view_index}/{total}")

    def navigate_to(self, index):
        if 0 <= index <= len(self.moves):
            self.view_index = index
            self.update_navigation()
            self.display_current_position()
            self.update_game_info_panel()

    def prev_move(self):
        if self.view_index > 0:
            self.navigate_to(self.view_index - 1)

    def next_move(self):
        if self.view_index < len(self.moves):
            self.navigate_to(self.view_index + 1)

    def go_to_end(self):
        if self.moves:
            self.navigate_to(len(self.moves))
        else:
            self.navigate_to(0)

    def on_scale_move(self, value):
        try:
            index = int(float(value))
            self.navigate_to(index)
        except Exception:
            pass

    # =======================
    # ADVANCED
    # =======================
    def import_json(self):
        filepath = filedialog.askopenfilename(
            title="Importer une partie JSON",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
        )
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                game_data = json.load(f)

            required_fields = ["rows", "cols", "starting_color", "moves"]
            for field in required_fields:
                if field not in game_data:
                    raise ValueError(f"Champ manquant: {field}")

            query = "SELECT id FROM saved_games WHERE save_name = %s"
            existing = self.execute_query(
                query, (os.path.basename(filepath).replace(".json", ""),)
            )
            if existing:
                messagebox.showinfo(
                    "Partie existante",
                    f"Une partie avec ce nom existe déjà (ID: {existing[0][0]})",
                )
                return

            query = """
            INSERT INTO saved_games 
            (save_name, rows, cols, starting_color, mode, game_index, moves, view_index, ai_mode, ai_depth)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            save_name = os.path.basename(filepath).replace(".json", "")
            params = (
                save_name,
                game_data["rows"],
                game_data["cols"],
                game_data["starting_color"],
                game_data.get("mode", 2),
                game_data.get("game_index", 1),
                json.dumps(game_data["moves"]),
                game_data.get("view_index", 0),
                game_data.get("ai_mode", "random"),
                game_data.get("ai_depth", 4),
            )

            result = self.execute_query(query, params, fetch=False)
            if result:
                new_game_id = self.execute_query("SELECT LASTVAL()")[0][0]
                messagebox.showinfo(
                    "Succès", f"Partie importée avec succès! ID: {new_game_id}"
                )
                self.load_games_list()
            else:
                messagebox.showerror("Erreur", "Échec de l'importation")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'import: {str(e)}")

    def show_stats(self):
        query = """
        SELECT 
            COUNT(*) as total_games,
            COUNT(DISTINCT moves) as unique_games,
            AVG(jsonb_array_length(moves))::INTEGER as avg_moves,
            MIN(jsonb_array_length(moves)) as min_moves,
            MAX(jsonb_array_length(moves)) as max_moves,
            COUNT(DISTINCT rows || 'x' || cols) as different_sizes,
            MODE() WITHIN GROUP (ORDER BY ai_mode) as most_common_ai
        FROM saved_games
        """
        stats = self.execute_query(query)
        if stats and stats[0]:
            s = stats[0]
            stats_text = f"""
╔══════════════════════════════════════════════════════════════╗
║ STATISTIQUES GÉNÉRALES
╠══════════════════════════════════════════════════════════════╣
║ • Parties totales: {s[0] or 0}
║ • Parties uniques: {s[1] or 0}
║ • Coups moyens par partie: {s[2] or 0}
║ • Coups minimum: {s[3] or 0}
║ • Coups maximum: {s[4] or 0}
║ • Tailles différentes: {s[5] or 0}
║ • IA la plus utilisée: {s[6] or 'N/A'}
╚══════════════════════════════════════════════════════════════╝
            """
            messagebox.showinfo("Statistiques", stats_text)
        else:
            messagebox.showinfo("Statistiques", "Aucune donnée disponible")

    def delete_selected_game(self):
        selection = self.games_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Aucune sélection", "Veuillez sélectionner une partie à supprimer"
            )
            return

        item = self.games_tree.item(selection[0])
        game_id = item["values"][0]
        game_name = item["values"][1]

        confirm = messagebox.askyesno(
            "Confirmer suppression",
            f"Voulez-vous vraiment supprimer la partie '{game_name}' (ID: {game_id}) ?\n\n"
            "Cette action est irréversible.",
        )
        if confirm:
            try:
                query = "DELETE FROM saved_games WHERE id = %s"
                result = self.execute_query(query, (game_id,), fetch=False)
                if result:
                    messagebox.showinfo("Succès", "Partie supprimée avec succès")
                    self.load_games_list()
                    self.current_game_id = None
                    self.moves = []
                    self.view_index = 0
                    self.game_meta = {}
                    self.canvas.delete("all")
                    self.info_text.delete(1.0, tk.END)
                    self.pos_info_text.delete(1.0, tk.END)
                    self.update_navigation()
                else:
                    messagebox.showerror("Erreur", "Échec de la suppression")
            except Exception as e:
                messagebox.showerror(
                    "Erreur", f"Erreur lors de la suppression: {str(e)}"
                )

    def calculate_board_hash(self, board):
        if not board:
            return "N/A"
        board_str = json.dumps(board)
        return hashlib.sha256(board_str.encode()).hexdigest()

    def get_mode_name(self, mode_code):
        modes = {0: "IA vs IA", 1: "Humain vs IA", 2: "Humain vs Humain"}
        return modes.get(mode_code, f"Mode {mode_code}")

    def refresh_all(self):
        self.load_games_list()
        if self.current_game_id:
            self.load_game_details(self.current_game_id)

    def __del__(self):
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    try:
        import psycopg2  # noqa
    except ImportError:
        print(
            "❌ psycopg2 n'est pas installé. Installez-le avec: pip install psycopg2-binary"
        )
        raise SystemExit(1)

    app = DatabaseViewer()
    app.mainloop()
