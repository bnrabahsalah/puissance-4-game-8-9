-- =======================
-- BASE DE DONNÉES PUISSANCE 4 - VERSION AMÉLIORÉE
-- =======================

-- Extension nécessaire pour digest()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des parties (table principale)
CREATE TABLE IF NOT EXISTS games (
    game_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    game_index INTEGER NOT NULL,
    rows_count INTEGER NOT NULL CHECK (rows_count BETWEEN 4 AND 20),
    cols_count INTEGER NOT NULL CHECK (cols_count BETWEEN 4 AND 20),
    starting_color CHAR(1) CHECK (starting_color IN ('R', 'Y')),
    ai_mode VARCHAR(20) DEFAULT 'random',
    ai_depth INTEGER DEFAULT 4 CHECK (ai_depth BETWEEN 1 AND 8),
    game_mode INTEGER CHECK (game_mode IN (0, 1, 2)),
    status VARCHAR(20) DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'aborted')),
    winner CHAR(1) CHECK (winner IN ('R', 'Y', 'D')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    board_hash VARCHAR(64),
    moves_hash VARCHAR(64),
    save_name VARCHAR(100),
    view_index INTEGER DEFAULT 0,
    moves JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (moves_hash)  -- Empêche les doublons
);

-- Table des coups
CREATE TABLE IF NOT EXISTS moves (
    move_id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(game_id) ON DELETE CASCADE,
    move_index INTEGER NOT NULL,
    column_played INTEGER NOT NULL CHECK (column_played >= 0),
    player CHAR(1) CHECK (player IN ('R', 'Y')),
    board_state TEXT,
    evaluation_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (game_id, move_index)
);

-- Table des positions (centralisée)
CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    board_hash VARCHAR(64) UNIQUE NOT NULL,
    board_state TEXT NOT NULL,
    rows_count INTEGER NOT NULL,
    cols_count INTEGER NOT NULL,
    next_player CHAR(1) CHECK (next_player IN ('R', 'Y')),
    terminal BOOLEAN DEFAULT FALSE,
    winner CHAR(1) CHECK (winner IN ('R', 'Y', 'D')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour performances
CREATE INDEX IF NOT EXISTS idx_board_hash ON positions(board_hash);
CREATE INDEX IF NOT EXISTS idx_terminal ON positions(terminal);
CREATE INDEX IF NOT EXISTS idx_games_moves_hash ON games(moves_hash);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);

-- Table de liaison parties-positions
CREATE TABLE IF NOT EXISTS game_positions (
    game_id INTEGER REFERENCES games(game_id) ON DELETE CASCADE,
    position_id INTEGER REFERENCES positions(position_id) ON DELETE CASCADE,
    move_index INTEGER NOT NULL,
    PRIMARY KEY (game_id, position_id)
);

-- Table des symétries (améliorée)
CREATE TABLE IF NOT EXISTS symmetries (
    symmetry_id SERIAL PRIMARY KEY,
    original_hash VARCHAR(64) NOT NULL,
    symmetric_hash VARCHAR(64) NOT NULL,
    symmetry_type VARCHAR(20)
        CHECK (symmetry_type IN (
            'horizontal', 'vertical',
            'rotate180', 'rotate90', 'rotate270',
            'identity'
        )),
    transformation TEXT, -- Description de la transformation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (original_hash, symmetric_hash, symmetry_type)
);

-- Statistiques des positions
CREATE TABLE IF NOT EXISTS position_stats (
    position_id INTEGER PRIMARY KEY REFERENCES positions(position_id),
    times_played INTEGER DEFAULT 0,
    red_wins INTEGER DEFAULT 0,
    yellow_wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    avg_evaluation_score FLOAT,
    last_played TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vue d'analyse des parties (améliorée)
CREATE OR REPLACE VIEW game_details AS
SELECT
    g.game_id,
    g.save_name,
    g.game_index,
    g.rows_count,
    g.cols_count,
    g.starting_color,
    g.ai_mode,
    g.ai_depth,
    g.game_mode,
    g.status,
    g.winner,
    g.created_at,
    g.completed_at,
    g.view_index,
    jsonb_array_length(g.moves) as total_moves,
    u.username,
    g.moves_hash
FROM games g
LEFT JOIN users u ON g.user_id = u.user_id
ORDER BY g.created_at DESC;

-- Vue pour les symétries (nouvelle)
CREATE OR REPLACE VIEW symmetry_view AS
SELECT
    s.symmetry_id,
    s.original_hash,
    s.symmetric_hash,
    s.symmetry_type,
    s.transformation,
    p1.board_state as original_board,
    p2.board_state as symmetric_board,
    p1.rows_count,
    p1.cols_count,
    s.created_at
FROM symmetries s
JOIN positions p1 ON s.original_hash = p1.board_hash
JOIN positions p2 ON s.symmetric_hash = p2.board_hash;

-- Fonction de hachage du plateau
CREATE OR REPLACE FUNCTION calculate_board_hash(board_state TEXT)
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN encode(digest(board_state, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql;

-- Fonction pour calculer le hash des mouvements
CREATE OR REPLACE FUNCTION calculate_moves_hash(moves_array JSONB)
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN encode(digest(moves_array::text, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql;

-- Fonction pour vérifier si une partie existe déjà
CREATE OR REPLACE FUNCTION game_exists(moves_array JSONB)
RETURNS INTEGER AS $$
DECLARE
    existing_id INTEGER;
    moves_hash VARCHAR(64);
BEGIN
    moves_hash := calculate_moves_hash(moves_array);
    
    SELECT game_id INTO existing_id 
    FROM games 
    WHERE moves_hash = game_exists.moves_hash
    LIMIT 1;
    
    RETURN COALESCE(existing_id, -1);
END;
$$ LANGUAGE plpgsql;

-- Fonction pour générer toutes les symétries d'une position
CREATE OR REPLACE FUNCTION generate_symmetries(board_hash VARCHAR(64))
RETURNS TABLE(
    symmetric_hash VARCHAR(64),
    symmetry_type VARCHAR(20),
    transformation TEXT
) AS $$
DECLARE
    board_state TEXT;
    rows_count INTEGER;
    cols_count INTEGER;
BEGIN
    -- Récupérer la position originale
    SELECT p.board_state, p.rows_count, p.cols_count
    INTO board_state, rows_count, cols_count
    FROM positions p
    WHERE p.board_hash = generate_symmetries.board_hash;
    
    IF NOT FOUND THEN
        RETURN;
    END IF;
    
    -- Symétrie identité (original)
    symmetric_hash := board_hash;
    symmetry_type := 'identity';
    transformation := 'No transformation';
    RETURN NEXT;
    
    -- Générer les autres symétries ici (logique simplifiée)
    -- Dans une version complète, on implémenterait les transformations réelles
    
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour mettre à jour automatiquement moves_hash
CREATE OR REPLACE FUNCTION update_moves_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.moves_hash := calculate_moves_hash(NEW.moves);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_moves_hash
BEFORE INSERT OR UPDATE ON games
FOR EACH ROW
EXECUTE FUNCTION update_moves_hash();

-- Trigger pour détecter les parties en double
CREATE OR REPLACE FUNCTION prevent_duplicate_games()
RETURNS TRIGGER AS $$
BEGIN
    IF game_exists(NEW.moves) != -1 THEN
        RAISE EXCEPTION 'Cette partie existe déjà dans la base de données (mouvements identiques)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_prevent_duplicate_games
BEFORE INSERT ON games
FOR EACH ROW
EXECUTE FUNCTION prevent_duplicate_games();

-- =======================
-- DONNÉES DE TEST
-- =======================

-- Insertion d'un utilisateur par défaut
INSERT INTO users (username) VALUES ('default_user')
ON CONFLICT (username) DO NOTHING;

-- Insertion d'une partie de test (suite 3131313)
INSERT INTO games (
    user_id,
    game_index,
    rows_count,
    cols_count,
    starting_color,
    ai_mode,
    ai_depth,
    game_mode,
    status,
    winner,
    save_name,
    moves
) VALUES (
    1, -- user_id
    1, -- game_index
    6, -- rows_count
    7, -- cols_count
    'R', -- starting_color
    'minimax', -- ai_mode
    4, -- ai_depth
    1, -- game_mode (Humain vs IA)
    'completed', -- status
    'R', -- winner
    'partie_test_3131313', -- save_name
    '[3,1,3,1,3,1,3]'::jsonb -- moves (suite 3131313)
) ON CONFLICT (moves_hash) DO NOTHING;
ALTER TABLE saved_games ALTER COLUMN rows SET DEFAULT 9;
ALTER TABLE saved_games ALTER COLUMN cols SET DEFAULT 9;
ALTER TABLE games ALTER COLUMN rows_count SET DEFAULT 9;
ALTER TABLE games ALTER COLUMN cols_count SET DEFAULT 9;
ALTER TABLE saved_games
ADD COLUMN IF NOT EXISTS confidence INTEGER NOT NULL DEFAULT 1
CHECK (confidence BETWEEN 0 AND 5);
ALTER TABLE games
ADD COLUMN IF NOT EXISTS confidence INTEGER NOT NULL DEFAULT 1
CHECK (confidence BETWEEN 0 AND 5);
UPDATE saved_games SET confidence = 1 WHERE confidence IS NULL;
-- ou
UPDATE games SET confidence = 1 WHERE confidence IS NULL;
ALTER TABLE saved_games
ADD COLUMN IF NOT EXISTS distinct_cols INTEGER NOT NULL DEFAULT 0
CHECK (distinct_cols BETWEEN 0 AND 20);
ALTER TABLE games
ADD COLUMN IF NOT EXISTS distinct_cols INTEGER NOT NULL DEFAULT 0
CHECK (distinct_cols BETWEEN 0 AND 20);
UPDATE saved_games SET confidence = 1 WHERE confidence IS NULL;
UPDATE saved_games SET distinct_cols = 0 WHERE distinct_cols IS NULL;
ALTER TABLE saved_games
ADD COLUMN IF NOT EXISTS confiance INTEGER DEFAULT 1 CHECK (confiance >= 0);

ALTER TABLE saved_games
RENAME COLUMN confiance TO confidence;
-- Copier les valeurs si besoin
UPDATE saved_games
SET confidence = COALESCE(confidence, confiance);

-- Supprimer la colonne en trop
ALTER TABLE saved_games
DROP COLUMN confiance;
