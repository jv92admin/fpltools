-- ============================================================================
-- FPL Tools - Initial Database Schema
-- ============================================================================
-- Run this in your Supabase SQL Editor to create the initial tables.
-- 
-- Schema Design:
--   - dim_* tables: Dimension tables (slowly changing reference data)
--   - fact_* tables: Fact tables (time-series / event data)
-- ============================================================================


-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- Teams (20 Premier League clubs)
CREATE TABLE IF NOT EXISTS dim_teams (
    fpl_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    code INTEGER,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Positions (GK, DEF, MID, FWD)
CREATE TABLE IF NOT EXISTS dim_positions (
    fpl_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert standard positions
INSERT INTO dim_positions (fpl_id, name, short_name) VALUES
    (1, 'Goalkeeper', 'GKP'),
    (2, 'Defender', 'DEF'),
    (3, 'Midfielder', 'MID'),
    (4, 'Forward', 'FWD')
ON CONFLICT (fpl_id) DO NOTHING;

-- Gameweeks (38 per season)
CREATE TABLE IF NOT EXISTS dim_gameweeks (
    fpl_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    deadline_time TIMESTAMPTZ,
    is_current BOOLEAN DEFAULT FALSE,
    is_next BOOLEAN DEFAULT FALSE,
    finished BOOLEAN DEFAULT FALSE,
    
    -- Aggregate stats (updated after GW finishes)
    average_score INTEGER,
    highest_score INTEGER,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Players (~700 per season)
CREATE TABLE IF NOT EXISTS dim_players (
    fpl_id INTEGER PRIMARY KEY,
    web_name TEXT NOT NULL,
    first_name TEXT,
    second_name TEXT,
    
    -- Current team/position
    team_id INTEGER REFERENCES dim_teams(fpl_id),
    position_id INTEGER REFERENCES dim_positions(fpl_id),
    
    -- Current price (in millions, e.g., 10.5)
    price DECIMAL(4, 1),
    
    -- Cumulative stats (updated with each bootstrap pull)
    total_points INTEGER DEFAULT 0,
    selected_by_percent DECIMAL(5, 2) DEFAULT 0,
    
    -- Status
    status TEXT,  -- 'a' = available, 'i' = injured, 'd' = doubtful, etc.
    news TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- FACT TABLES
-- ============================================================================

-- Player stats per gameweek
CREATE TABLE IF NOT EXISTS fact_player_gw (
    id BIGSERIAL PRIMARY KEY,
    
    fpl_player_id INTEGER NOT NULL REFERENCES dim_players(fpl_id),
    gameweek INTEGER NOT NULL REFERENCES dim_gameweeks(fpl_id),
    
    -- Core stats
    minutes INTEGER DEFAULT 0,
    goals_scored INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    clean_sheets INTEGER DEFAULT 0,
    goals_conceded INTEGER DEFAULT 0,
    own_goals INTEGER DEFAULT 0,
    penalties_saved INTEGER DEFAULT 0,
    penalties_missed INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_cards INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    bonus INTEGER DEFAULT 0,
    bps INTEGER DEFAULT 0,  -- Bonus Points System raw score
    
    -- Points
    total_points INTEGER DEFAULT 0,
    
    -- Value at time of GW
    value DECIMAL(4, 1),
    
    -- Metadata
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(fpl_player_id, gameweek)
);

-- Fixtures
CREATE TABLE IF NOT EXISTS fact_fixtures (
    fpl_id INTEGER PRIMARY KEY,
    gameweek INTEGER REFERENCES dim_gameweeks(fpl_id),
    
    home_team_id INTEGER REFERENCES dim_teams(fpl_id),
    away_team_id INTEGER REFERENCES dim_teams(fpl_id),
    
    home_score INTEGER,
    away_score INTEGER,
    
    kickoff_time TIMESTAMPTZ,
    finished BOOLEAN DEFAULT FALSE,
    
    -- Difficulty ratings (1-5)
    home_difficulty INTEGER,
    away_difficulty INTEGER,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Manager picks per gameweek
CREATE TABLE IF NOT EXISTS fact_manager_picks (
    id BIGSERIAL PRIMARY KEY,
    
    manager_id INTEGER NOT NULL,
    gameweek INTEGER NOT NULL REFERENCES dim_gameweeks(fpl_id),
    fpl_player_id INTEGER NOT NULL REFERENCES dim_players(fpl_id),
    
    -- Pick details
    position INTEGER,  -- 1-15 (1-11 = starting, 12-15 = bench)
    multiplier INTEGER DEFAULT 1,  -- 0=bench auto, 1=normal, 2=captain, 3=triple captain
    is_captain BOOLEAN DEFAULT FALSE,
    is_vice_captain BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(gameweek, manager_id, fpl_player_id)
);

-- League standings snapshots
CREATE TABLE IF NOT EXISTS fact_league_standings (
    id BIGSERIAL PRIMARY KEY,
    
    league_id INTEGER NOT NULL,
    gameweek INTEGER NOT NULL REFERENCES dim_gameweeks(fpl_id),
    manager_id INTEGER NOT NULL,
    
    -- Manager info (denormalized for convenience)
    manager_name TEXT,
    team_name TEXT,
    
    -- Standing
    rank INTEGER,
    last_rank INTEGER,
    
    -- Points
    total_points INTEGER DEFAULT 0,
    event_points INTEGER DEFAULT 0,
    
    -- Metadata
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(league_id, gameweek, manager_id)
);


-- ============================================================================
-- INDEXES
-- ============================================================================

-- Player lookups
CREATE INDEX IF NOT EXISTS idx_players_team ON dim_players(team_id);
CREATE INDEX IF NOT EXISTS idx_players_position ON dim_players(position_id);

-- Fact table lookups
CREATE INDEX IF NOT EXISTS idx_player_gw_gameweek ON fact_player_gw(gameweek);
CREATE INDEX IF NOT EXISTS idx_player_gw_player ON fact_player_gw(fpl_player_id);

CREATE INDEX IF NOT EXISTS idx_fixtures_gameweek ON fact_fixtures(gameweek);
CREATE INDEX IF NOT EXISTS idx_fixtures_home_team ON fact_fixtures(home_team_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_away_team ON fact_fixtures(away_team_id);

CREATE INDEX IF NOT EXISTS idx_manager_picks_gw ON fact_manager_picks(gameweek);
CREATE INDEX IF NOT EXISTS idx_manager_picks_manager ON fact_manager_picks(manager_id);

CREATE INDEX IF NOT EXISTS idx_standings_league_gw ON fact_league_standings(league_id, gameweek);


-- ============================================================================
-- ROW LEVEL SECURITY (Optional - enable if needed)
-- ============================================================================

-- For now, we'll leave RLS disabled since this is internal data
-- ALTER TABLE dim_players ENABLE ROW LEVEL SECURITY;
-- etc.


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to dimension tables
CREATE TRIGGER update_dim_teams_updated_at
    BEFORE UPDATE ON dim_teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_dim_gameweeks_updated_at
    BEFORE UPDATE ON dim_gameweeks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_dim_players_updated_at
    BEFORE UPDATE ON dim_players
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_fact_fixtures_updated_at
    BEFORE UPDATE ON fact_fixtures
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

