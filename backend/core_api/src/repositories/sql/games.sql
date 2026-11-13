-- Additive, idempotent migration for both existing and new Core API databases.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    login VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    balance INT NOT NULL DEFAULT 10000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS games (
    owner TEXT NOT NULL,
    id UUID NOT NULL,
    state JSONB NOT NULL,
    clock_at TIMESTAMPTZ NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (owner, id)
);

CREATE INDEX IF NOT EXISTS games_owner_saved_idx ON games (owner, saved_at DESC);

CREATE TABLE IF NOT EXISTS game_actions (
    owner TEXT NOT NULL,
    game_id UUID NOT NULL,
    request_id UUID NOT NULL,
    fingerprint TEXT NOT NULL,
    PRIMARY KEY (owner, game_id, request_id),
    FOREIGN KEY (owner, game_id) REFERENCES games (owner, id) ON DELETE CASCADE
);
