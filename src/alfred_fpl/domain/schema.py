"""FPL schema definitions, field enums, semantic notes, and subdomain registry.

This is the contract the LLM codes against. Fallback schemas are LOAD-BEARING:
our Supabase instance does not have the get_table_columns RPC, so these schemas
are the only way Act prompts know what columns exist. Every column name, type,
and comment here directly affects whether the LLM writes correct queries and
correct Python code in ANALYZE steps.
"""

# ---------------------------------------------------------------------------
# Fallback schemas — the LLM's view of the database
#
# Format: table_name → human-readable column listing
# These are injected into Act prompts when the LLM needs to construct queries
# or write Python code. Include column semantics (not just types) because the
# LLM writing pandas code needs to know "price is in millions" not just
# "price is decimal".
# ---------------------------------------------------------------------------

FALLBACK_SCHEMAS: dict[str, str] = {
    # --- Dimension tables ---
    "positions": (
        "id (uuid PK), fpl_id (int, FPL API position ID), "
        "name (text, e.g. 'Goalkeeper'), short_name (text, e.g. 'GKP')"
    ),
    "teams": (
        "id (uuid PK), fpl_id (int, FPL API team ID), "
        "name (text, full name e.g. 'Arsenal'), "
        "short_name (text, 3-letter code e.g. 'ARS'), "
        "code (int, FPL internal code)"
    ),
    "gameweeks": (
        "id (uuid PK), fpl_id (int, GW number 1-38), "
        "name (text, e.g. 'Gameweek 25'), "
        "deadline_time (timestamptz, transfer deadline), "
        "is_current (bool), is_next (bool), finished (bool), "
        "average_score (int, GW average points), "
        "highest_score (int, GW top score)"
    ),
    "leagues": (
        "id (uuid PK), fpl_id (int, FPL API league ID), "
        "name (text, mini-league name)"
    ),
    "players": (
        "id (uuid PK), fpl_id (int, FPL API element ID), "
        "web_name (text, display name e.g. 'Salah'), "
        "first_name (text), second_name (text), "
        "team_id (uuid FK → teams.id), "
        "position_id (uuid FK → positions.id), "
        "price (decimal, current price in millions e.g. 13.2), "
        "total_points (int, season total), "
        "selected_by_percent (decimal, ownership % e.g. 45.2), "
        "status (text, one of: a=available, i=injured, d=doubtful, s=suspended, u=unavailable), "
        "news (text, injury/suspension details), "
        "form (decimal, recent form rating), "
        "points_per_game (decimal, season avg PPG), "
        "minutes (int, total minutes played), "
        "goals_scored (int), assists (int), "
        "clean_sheets (int), bonus (int, total bonus points)"
    ),
    # --- Fact / reference tables ---
    "fixtures": (
        "id (uuid PK), fpl_id (int), "
        "gameweek (int, GW number — NULL if unscheduled), "
        "home_team_id (uuid FK → teams.id), "
        "away_team_id (uuid FK → teams.id), "
        "home_score (int, NULL if not played), "
        "away_score (int, NULL if not played), "
        "kickoff_time (timestamptz), "
        "finished (bool), "
        "home_difficulty (int, FDR 1-5 where 1=easiest), "
        "away_difficulty (int, FDR 1-5 where 1=easiest)"
    ),
    "player_gameweeks": (
        "id (uuid PK), "
        "player_id (uuid FK → players.id), "
        "gameweek (int, GW number), "
        "minutes (int), goals_scored (int), assists (int), "
        "clean_sheets (int), goals_conceded (int), saves (int), "
        "bonus (int, 0-3), bps (int, raw bonus points system score), "
        "influence (decimal), creativity (decimal), threat (decimal), "
        "ict_index (decimal, composite ICT), "
        "expected_goals (decimal, xG), expected_assists (decimal, xA), "
        "expected_goal_involvements (decimal, xGI), "
        "expected_goals_conceded (decimal, xGC), "
        "total_points (int, points scored this GW), "
        "in_dreamteam (bool), "
        "value (decimal, player price at that GW in millions)"
    ),
    "player_snapshots": (
        "id (uuid PK), "
        "player_id (uuid FK → players.id), "
        "snapshot_time (timestamptz), "
        "gameweek (int), "
        "transfers_in_event (int, transfers in this GW), "
        "transfers_out_event (int, transfers out this GW), "
        "selected_by_percent (decimal, ownership %), "
        "price (decimal, price in millions), "
        "form (decimal), points_per_game (decimal)"
    ),
    # --- Manager subview tables (integer manager_id, not UUID) ---
    "squads": (
        "id (uuid PK), "
        "manager_id (int, FPL manager ID — NOT a UUID), "
        "manager_name (text), "
        "gameweek (int), "
        "player_id (uuid FK → players.id), "
        "slot (int, 1-11=starting XI, 12-15=bench), "
        "multiplier (int, 0=benched 1=playing 2=captain 3=triple-captain), "
        "is_captain (bool), is_vice_captain (bool)"
    ),
    "transfers": (
        "id (uuid PK), "
        "manager_id (int, FPL manager ID — NOT a UUID), "
        "manager_name (text), "
        "gameweek (int), "
        "player_in_id (uuid FK → players.id), "
        "player_out_id (uuid FK → players.id), "
        "price_in (decimal, millions), price_out (decimal, millions), "
        "transfer_time (timestamptz)"
    ),
    "manager_seasons": (
        "id (uuid PK), "
        "manager_id (int, FPL manager ID — NOT a UUID), "
        "manager_name (text), "
        "gameweek (int), "
        "points (int, GW points), total_points (int, cumulative), "
        "rank (int, GW rank), overall_rank (int), percentile_rank (int), "
        "bank (decimal, transfer budget in millions), "
        "team_value (decimal, squad value in millions), "
        "transfers_made (int), transfers_cost (int, hit points taken), "
        "points_on_bench (int), "
        "chip_used (text, NULL or one of: wildcard/bboost/3xc/freehit)"
    ),
    "league_standings": (
        "id (uuid PK), "
        "league_id (int, FPL league ID — NOT a UUID), "
        "league_name (text), "
        "gameweek (int), "
        "manager_id (int, FPL manager ID — NOT a UUID), "
        "manager_name (text), team_name (text), "
        "rank (int), last_rank (int, previous GW rank), "
        "total_points (int), event_points (int, this GW only)"
    ),
    # --- User-owned tables (RLS-protected) ---
    "manager_links": (
        "id (uuid PK), "
        "user_id (uuid FK → auth.users, auto-scoped by RLS), "
        "fpl_manager_id (int, the FPL API manager ID), "
        "is_primary (bool, true = this is the user's own team), "
        "label (text, display name e.g. 'Vinay' or 'My Team'), "
        "league_id (int, optional league association)"
    ),
    "watchlist": (
        "id (uuid PK), "
        "user_id (uuid FK → auth.users, auto-scoped by RLS), "
        "player_id (uuid FK → players.id), "
        "notes (text, user's notes on this player), "
        "created_at (timestamptz)"
    ),
    "transfer_plans": (
        "id (uuid PK), "
        "user_id (uuid FK → auth.users, auto-scoped by RLS), "
        "manager_id (int, FPL manager ID), "
        "gameweek (int, planned GW for transfer), "
        "player_in_id (uuid FK → players.id), "
        "player_out_id (uuid FK → players.id), "
        "price_in (decimal, millions), price_out (decimal, millions), "
        "created_at (timestamptz)"
    ),
}


# ---------------------------------------------------------------------------
# Subdomain registry — maps subdomains to their accessible tables
# ---------------------------------------------------------------------------

SUBDOMAIN_REGISTRY: dict[str, dict] = {
    "squad": {
        "tables": [
            "squads", "players", "teams", "positions",
            "gameweeks", "manager_seasons", "manager_links",
        ],
    },
    "scouting": {
        "tables": [
            "players", "teams", "positions", "player_gameweeks",
            "player_snapshots", "fixtures", "gameweeks", "watchlist",
        ],
    },
    "market": {
        "tables": [
            "player_snapshots", "players", "teams", "transfers",
            "transfer_plans", "manager_seasons",
        ],
    },
    "league": {
        "tables": [
            "league_standings", "leagues", "squads", "manager_seasons",
            "players", "teams", "gameweeks", "manager_links",
        ],
    },
    "live": {
        "tables": [
            "player_gameweeks", "squads", "players", "teams",
            "fixtures", "gameweeks", "manager_links",
        ],
    },
    "fixtures": {
        "tables": ["fixtures", "teams", "gameweeks"],
    },
}


# ---------------------------------------------------------------------------
# Subdomain examples — routing hints for Understand/Think
# ---------------------------------------------------------------------------

SUBDOMAIN_EXAMPLES: dict[str, str] = {
    "squad": (
        '## Squad examples\n'
        'User: "show my team" → db_read on squads, filter manager_id + current GW\n'
        'User: "who\'s my captain?" → db_read on squads, filter is_captain eq true\n'
        'User: "show my bench" → db_read on squads, filter slot gte 12'
    ),
    "scouting": (
        '## Scouting examples\n'
        'User: "cheap midfielders under 6m" → db_read on players, '
        'filter position_id eq <MID>, price lte 6.0, order total_points desc, limit 20\n'
        'User: "compare Salah and Saka" → db_read players by web_name, '
        'then db_read player_gameweeks for recent GWs, then ANALYZE to compare\n'
        'User: "add Salah to watchlist" → db_create on watchlist with player_id'
    ),
    "market": (
        '## Market examples\n'
        'User: "what transfers has Vinay made?" → db_read on transfers, '
        'filter manager_id (resolve Vinay via manager_links or league_standings)\n'
        'User: "who should I transfer in for Haaland?" → db_read squad + players + fixtures, '
        'ANALYZE to rank replacements by form + fixtures + value'
    ),
    "league": (
        '## League examples\n'
        'User: "show the league table" → db_read league_standings, '
        'filter league_id + current GW, order rank asc\n'
        'User: "how am I doing vs Vinay?" → multi-step: '
        'READ standings for both, READ squads for both, READ fixtures, '
        'ANALYZE differentials + fixture advantage'
    ),
    "live": (
        '## Live examples\n'
        'User: "how\'s this week going?" → db_read player_gameweeks + squads '
        'for current GW, cross-reference picks with points\n'
        'User: "what\'s the GW average?" → db_read gameweeks where is_current'
    ),
    "fixtures": (
        '## Fixture examples\n'
        'User: "which defenders have good fixtures?" → db_read fixtures '
        'next 3-5 GWs, filter low FDR, then db_read players DEF on those teams\n'
        'User: "Arsenal fixtures" → db_read fixtures where home_team_id or '
        'away_team_id matches Arsenal, order by gameweek'
    ),
}


# ---------------------------------------------------------------------------
# Field enums — categorical fields with valid values (all strings)
# ---------------------------------------------------------------------------

FIELD_ENUMS: dict[str, dict[str, list[str]]] = {
    "scouting": {
        "status": ["a", "i", "d", "s", "u"],
        "position": ["GKP", "DEF", "MID", "FWD"],
    },
    "squad": {
        "multiplier": ["0", "1", "2", "3"],
        "is_captain": ["true", "false"],
        "is_vice_captain": ["true", "false"],
        "position": ["GKP", "DEF", "MID", "FWD"],
    },
    "market": {
        "chip_used": ["wildcard", "bboost", "3xc", "freehit"],
    },
    "live": {
        "in_dreamteam": ["true", "false"],
    },
}


# ---------------------------------------------------------------------------
# Semantic notes — domain rules keyed by subdomain
# ---------------------------------------------------------------------------

SEMANTIC_NOTES: dict[str, str] = {
    "squad": (
        "A squad has exactly 15 players: 2 GKP, 5 DEF, 5 MID, 3 FWD. "
        "Max 3 from any single team. Slots 1-11 are the starting XI, "
        "12-15 are bench (ordered by auto-sub priority). "
        "multiplier: 0=not playing, 1=playing, 2=captain (2x points), "
        "3=triple captain (3x points, chip). "
        "manager_id is an INTEGER from the FPL API, not a UUID."
    ),
    "scouting": (
        "Player status: a=available, i=injured, d=doubtful, s=suspended, "
        "u=unavailable. price is in millions (6.0 = 6.0m). "
        "form is a rolling average over recent GWs. "
        "ICT = Influence + Creativity + Threat (composite index). "
        "xG = expected goals, xA = expected assists, xGI = xG + xA. "
        "When comparing players, always consider: form, fixtures, price, "
        "ownership, and minutes played (flag rotation risks under 60 mins/GW avg)."
    ),
    "market": (
        "Each manager gets 1 free transfer per GW (max 5 banked under 2024/25 rules). "
        "Extra transfers cost 4 points each. "
        "Selling price = purchase price + floor(50% of profit). "
        "Wildcard allows unlimited free transfers for one GW. "
        "Free Hit lets you make unlimited transfers for one GW but squad resets after. "
        "Bench Boost scores bench players for one GW. "
        "Triple Captain triples captain points for one GW. "
        "transfers_in_event / transfers_out_event show transfer velocity — "
        "high net transfers in = likely price rise."
    ),
    "league": (
        "Classic scoring: total points accumulated across all GWs. "
        "rank = position within the mini-league. "
        "event_points = points scored that single GW. "
        "last_rank = rank from previous GW (track movement). "
        "A 'differential' is a player owned by one manager but not another. "
        "manager_id and league_id are INTEGERS from the FPL API, not UUIDs. "
        "Resolve human names (e.g. 'Vinay') via manager_links.label or "
        "league_standings.manager_name using ilike."
    ),
    "live": (
        "bonus column = final bonus points (0-3) after BPS calculation. "
        "bps = raw Bonus Points System score before conversion to bonus. "
        "in_dreamteam = true if player was in the highest-scoring XI of the GW. "
        "Points come from player_gameweeks.total_points. "
        "Cross-reference squads (who did the manager pick) with "
        "player_gameweeks (how did those picks score) to compute live total."
    ),
    "fixtures": (
        "home_difficulty and away_difficulty are FDR ratings 1-5 "
        "(1=easiest, 5=hardest). These are from the perspective of the team "
        "being rated: home_difficulty is how hard it is for the HOME team. "
        "gameweek=NULL means the fixture is unscheduled. "
        "finished=true means the final score is available. "
        "For fixture planning, think in runs of 3-5 GWs. "
        "A team's fixture run = average FDR over the window."
    ),
}


# ---------------------------------------------------------------------------
# Empty responses — per-subdomain messages when queries return nothing
# ---------------------------------------------------------------------------

EMPTY_RESPONSES: dict[str, str] = {
    "squad": (
        "No squad found for this gameweek. The squad data may not have been "
        "synced yet — try running the pipeline for this GW."
    ),
    "scouting": (
        "No players found matching those criteria. Try broadening your "
        "filters — increase the price ceiling, remove the position filter, "
        "or check that player data has been synced."
    ),
    "market": (
        "No transfer activity found. This manager may not have made "
        "transfers this gameweek, or transfer data hasn't been synced."
    ),
    "league": (
        "No league standings found. Make sure the league has been synced "
        "and gameweek data is available."
    ),
    "live": (
        "No live data for this gameweek yet. Points appear after "
        "matches kick off and the pipeline syncs."
    ),
    "fixtures": (
        "No fixtures found for that range. Check that fixture data "
        "has been synced, or try a different gameweek range."
    ),
}


# ---------------------------------------------------------------------------
# Position lookup
# ---------------------------------------------------------------------------

POSITIONS: dict[str, int] = {
    "GKP": 1,
    "DEF": 2,
    "MID": 3,
    "FWD": 4,
}
