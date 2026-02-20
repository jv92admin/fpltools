-- ============================================================================
-- FPL Tools — Complete Schema (Fresh Start)
-- ============================================================================
-- Run this in your Supabase SQL Editor.
--
-- This replaces the previous dim_/fact_ schema with the target architecture
-- from the domain spec (fpl-domain-spec.md section 10):
--   - UUID primary keys on all tables
--   - Clean table names (no dim_/fact_ prefixes)
--   - UUID FK columns for entity enrichment
--   - Integer manager_id/league_id with denormalized name columns
--   - RLS on user-owned tables
--
-- IMPORTANT: This drops all existing tables. Re-sync from FPL API after.
-- ============================================================================


-- ============================================================================
-- DROP EXISTING TABLES
-- ============================================================================

-- Old schema (dim_/fact_ convention)
DROP TABLE IF EXISTS fact_player_snapshot CASCADE;
DROP TABLE IF EXISTS fact_manager_gw CASCADE;
DROP TABLE IF EXISTS fact_league_standings CASCADE;
DROP TABLE IF EXISTS fact_manager_picks CASCADE;
DROP TABLE IF EXISTS fact_player_gw CASCADE;
DROP TABLE IF EXISTS fact_fixtures CASCADE;
DROP TABLE IF EXISTS dim_players CASCADE;
DROP TABLE IF EXISTS dim_gameweeks CASCADE;
DROP TABLE IF EXISTS dim_positions CASCADE;
DROP TABLE IF EXISTS dim_teams CASCADE;

-- Tables from 002_new_tables.sql (if they exist)
DROP TABLE IF EXISTS transfer_plans CASCADE;
DROP TABLE IF EXISTS watchlist CASCADE;
DROP TABLE IF EXISTS manager_links CASCADE;
DROP TABLE IF EXISTS transfers CASCADE;
DROP TABLE IF EXISTS leagues CASCADE;

-- New schema tables (in case re-running this script)
DROP TABLE IF EXISTS player_gameweeks CASCADE;
DROP TABLE IF EXISTS player_snapshots CASCADE;
DROP TABLE IF EXISTS squads CASCADE;
DROP TABLE IF EXISTS manager_seasons CASCADE;
DROP TABLE IF EXISTS league_standings CASCADE;
DROP TABLE IF EXISTS fixtures CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS positions CASCADE;
DROP TABLE IF EXISTS teams CASCADE;
DROP TABLE IF EXISTS gameweeks CASCADE;

-- Old trigger function
DROP FUNCTION IF EXISTS update_updated_at() CASCADE;


-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- Positions (GKP, DEF, MID, FWD)
CREATE TABLE positions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fpl_id      INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    short_name  TEXT NOT NULL
);

-- Seed positions (pipeline will upsert these too)
INSERT INTO positions (fpl_id, name, short_name) VALUES
    (1, 'Goalkeeper', 'GKP'),
    (2, 'Defender', 'DEF'),
    (3, 'Midfielder', 'MID'),
    (4, 'Forward', 'FWD');

-- Teams (20 Premier League clubs)
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fpl_id      INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    short_name  TEXT NOT NULL,
    code        INTEGER
);

-- Gameweeks (38 per season)
CREATE TABLE gameweeks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fpl_id          INTEGER NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    deadline_time   TIMESTAMPTZ,
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,
    is_next         BOOLEAN NOT NULL DEFAULT FALSE,
    finished        BOOLEAN NOT NULL DEFAULT FALSE,
    average_score   INTEGER,
    highest_score   INTEGER
);

-- Leagues (mini-leagues the user participates in)
CREATE TABLE leagues (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fpl_id  INTEGER NOT NULL UNIQUE,
    name    TEXT NOT NULL
);

-- Players (~700 per season)
CREATE TABLE players (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fpl_id                  INTEGER NOT NULL UNIQUE,
    web_name                TEXT NOT NULL,
    first_name              TEXT,
    second_name             TEXT,
    team_id                 UUID NOT NULL REFERENCES teams(id),
    position_id             UUID NOT NULL REFERENCES positions(id),
    price                   DECIMAL(4, 1),
    total_points            INTEGER NOT NULL DEFAULT 0,
    selected_by_percent     DECIMAL(5, 2),
    status                  TEXT,
    news                    TEXT,
    form                    DECIMAL(3, 1),
    points_per_game         DECIMAL(3, 1),
    minutes                 INTEGER,
    goals_scored            INTEGER,
    assists                 INTEGER,
    clean_sheets            INTEGER,
    bonus                   INTEGER
);


-- ============================================================================
-- REFERENCE / FACT TABLES
-- ============================================================================

-- Fixtures (all season matches)
CREATE TABLE fixtures (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fpl_id          INTEGER NOT NULL UNIQUE,
    gameweek        INTEGER,
    home_team_id    UUID NOT NULL REFERENCES teams(id),
    away_team_id    UUID NOT NULL REFERENCES teams(id),
    home_score      INTEGER,
    away_score      INTEGER,
    kickoff_time    TIMESTAMPTZ,
    finished        BOOLEAN NOT NULL DEFAULT FALSE,
    home_difficulty INTEGER,
    away_difficulty INTEGER
);

-- Player per-gameweek stats
CREATE TABLE player_gameweeks (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id                   UUID NOT NULL REFERENCES players(id),
    gameweek                    INTEGER NOT NULL,
    minutes                     INTEGER NOT NULL DEFAULT 0,
    goals_scored                INTEGER NOT NULL DEFAULT 0,
    assists                     INTEGER NOT NULL DEFAULT 0,
    clean_sheets                INTEGER NOT NULL DEFAULT 0,
    goals_conceded              INTEGER NOT NULL DEFAULT 0,
    saves                       INTEGER NOT NULL DEFAULT 0,
    bonus                       INTEGER NOT NULL DEFAULT 0,
    bps                         INTEGER NOT NULL DEFAULT 0,
    influence                   DECIMAL(6, 1),
    creativity                  DECIMAL(6, 1),
    threat                      DECIMAL(6, 1),
    ict_index                   DECIMAL(6, 1),
    expected_goals              DECIMAL(5, 2),
    expected_assists            DECIMAL(5, 2),
    expected_goal_involvements  DECIMAL(5, 2),
    expected_goals_conceded     DECIMAL(5, 2),
    total_points                INTEGER NOT NULL DEFAULT 0,
    in_dreamteam                BOOLEAN NOT NULL DEFAULT FALSE,
    value                       DECIMAL(4, 1),

    UNIQUE(player_id, gameweek)
);

-- Player price/ownership snapshots (time series)
CREATE TABLE player_snapshots (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id               UUID NOT NULL REFERENCES players(id),
    snapshot_time           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gameweek                INTEGER,
    transfers_in_event      INTEGER NOT NULL DEFAULT 0,
    transfers_out_event     INTEGER NOT NULL DEFAULT 0,
    selected_by_percent     DECIMAL(5, 2),
    price                   DECIMAL(4, 1),
    form                    DECIMAL(3, 1),
    points_per_game         DECIMAL(3, 1),

    UNIQUE(player_id, snapshot_time)
);


-- ============================================================================
-- MANAGER SUBVIEW TABLES (public data, scoped by integer manager_id)
-- ============================================================================

-- Squads (manager picks per gameweek)
CREATE TABLE squads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id      INTEGER NOT NULL,
    manager_name    TEXT,
    gameweek        INTEGER NOT NULL,
    player_id       UUID NOT NULL REFERENCES players(id),
    slot            INTEGER,
    multiplier      INTEGER NOT NULL DEFAULT 1,
    is_captain      BOOLEAN NOT NULL DEFAULT FALSE,
    is_vice_captain BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE(manager_id, gameweek, player_id)
);

-- Manager transfer history (from FPL API)
CREATE TABLE transfers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id      INTEGER NOT NULL,
    manager_name    TEXT,
    gameweek        INTEGER NOT NULL,
    player_in_id    UUID NOT NULL REFERENCES players(id),
    player_out_id   UUID NOT NULL REFERENCES players(id),
    price_in        DECIMAL(4, 1),
    price_out       DECIMAL(4, 1),
    transfer_time   TIMESTAMPTZ,

    UNIQUE(manager_id, gameweek, player_in_id, player_out_id)
);

-- Manager season history (one row per GW per manager)
CREATE TABLE manager_seasons (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id      INTEGER NOT NULL,
    manager_name    TEXT,
    gameweek        INTEGER NOT NULL,
    points          INTEGER NOT NULL DEFAULT 0,
    total_points    INTEGER NOT NULL DEFAULT 0,
    rank            INTEGER,
    overall_rank    INTEGER,
    percentile_rank INTEGER,
    bank            DECIMAL(4, 1) NOT NULL DEFAULT 0,
    team_value      DECIMAL(5, 1) NOT NULL DEFAULT 0,
    transfers_made  INTEGER NOT NULL DEFAULT 0,
    transfers_cost  INTEGER NOT NULL DEFAULT 0,
    points_on_bench INTEGER NOT NULL DEFAULT 0,
    chip_used       TEXT,

    UNIQUE(manager_id, gameweek)
);

-- League standings snapshots
CREATE TABLE league_standings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id       INTEGER NOT NULL,
    league_name     TEXT,
    gameweek        INTEGER NOT NULL,
    manager_id      INTEGER NOT NULL,
    manager_name    TEXT,
    team_name       TEXT,
    rank            INTEGER,
    last_rank       INTEGER,
    total_points    INTEGER NOT NULL DEFAULT 0,
    event_points    INTEGER NOT NULL DEFAULT 0,

    UNIQUE(league_id, gameweek, manager_id)
);


-- ============================================================================
-- USER-OWNED TABLES (private to Alfred user, scoped by auth.uid())
-- ============================================================================

-- Manager links (which FPL managers does this user track?)
CREATE TABLE manager_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    fpl_manager_id  INTEGER NOT NULL,
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    label           TEXT,
    league_id       INTEGER,

    UNIQUE(user_id, fpl_manager_id)
);

-- Watchlist (players the user is scouting)
CREATE TABLE watchlist (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id),
    player_id   UUID NOT NULL REFERENCES players(id),
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, player_id)
);

-- Transfer plans (user's planned transfers)
CREATE TABLE transfer_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    manager_id      INTEGER NOT NULL,
    gameweek        INTEGER NOT NULL,
    player_in_id    UUID NOT NULL REFERENCES players(id),
    player_out_id   UUID NOT NULL REFERENCES players(id),
    price_in        DECIMAL(4, 1),
    price_out       DECIMAL(4, 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, gameweek, player_in_id, player_out_id)
);


-- ============================================================================
-- INDEXES
-- ============================================================================

-- Players
CREATE INDEX idx_players_team ON players(team_id);
CREATE INDEX idx_players_position ON players(position_id);

-- Fixtures
CREATE INDEX idx_fixtures_gameweek ON fixtures(gameweek);
CREATE INDEX idx_fixtures_home_team ON fixtures(home_team_id);
CREATE INDEX idx_fixtures_away_team ON fixtures(away_team_id);

-- Player gameweeks
CREATE INDEX idx_player_gw_player ON player_gameweeks(player_id);
CREATE INDEX idx_player_gw_gameweek ON player_gameweeks(gameweek);

-- Player snapshots
CREATE INDEX idx_player_snap_player ON player_snapshots(player_id);
CREATE INDEX idx_player_snap_time ON player_snapshots(snapshot_time);
CREATE INDEX idx_player_snap_gameweek ON player_snapshots(gameweek);

-- Squads
CREATE INDEX idx_squads_manager ON squads(manager_id);
CREATE INDEX idx_squads_gameweek ON squads(gameweek);
CREATE INDEX idx_squads_player ON squads(player_id);

-- Transfers
CREATE INDEX idx_transfers_manager ON transfers(manager_id);
CREATE INDEX idx_transfers_gameweek ON transfers(gameweek);

-- Manager seasons
CREATE INDEX idx_manager_seasons_manager ON manager_seasons(manager_id);
CREATE INDEX idx_manager_seasons_gameweek ON manager_seasons(gameweek);

-- League standings
CREATE INDEX idx_standings_league_gw ON league_standings(league_id, gameweek);
CREATE INDEX idx_standings_manager ON league_standings(manager_id);

-- Manager links
CREATE INDEX idx_manager_links_user ON manager_links(user_id);

-- Watchlist
CREATE INDEX idx_watchlist_user ON watchlist(user_id);
CREATE INDEX idx_watchlist_player ON watchlist(player_id);

-- Transfer plans
CREATE INDEX idx_transfer_plans_user ON transfer_plans(user_id);


-- ============================================================================
-- ROW LEVEL SECURITY — User-Owned Tables
-- ============================================================================
-- User-owned tables: full CRUD scoped by auth.uid().
-- Reference tables: RLS not enabled here — pipeline writes with anon/service key.
-- For production, enable RLS on reference tables with SELECT-only policies.

-- manager_links
ALTER TABLE manager_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own manager_links"
    ON manager_links FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own manager_links"
    ON manager_links FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own manager_links"
    ON manager_links FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own manager_links"
    ON manager_links FOR DELETE USING (auth.uid() = user_id);

-- watchlist
ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own watchlist"
    ON watchlist FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own watchlist"
    ON watchlist FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own watchlist"
    ON watchlist FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own watchlist"
    ON watchlist FOR DELETE USING (auth.uid() = user_id);

-- transfer_plans
ALTER TABLE transfer_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own transfer_plans"
    ON transfer_plans FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own transfer_plans"
    ON transfer_plans FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own transfer_plans"
    ON transfer_plans FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own transfer_plans"
    ON transfer_plans FOR DELETE USING (auth.uid() = user_id);
