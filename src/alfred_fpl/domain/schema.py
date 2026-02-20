"""FPL schema definitions, field enums, semantic notes, and subdomain registry.

This is the contract the LLM codes against. Fallback schemas are LOAD-BEARING:
our Supabase instance does not have the get_table_columns RPC, so these schemas
are the only way Act prompts know what columns exist. Every column name, type,
and comment here directly affects whether the LLM writes correct queries and
correct Python code in ANALYZE steps.

CRITICAL: FALLBACK_SCHEMAS must be keyed by SUBDOMAIN name (not table name).
Alfred-core calls `get_fallback_schemas().get(subdomain)` — if keys are table
names, the lookup returns None and the LLM gets "*Schema unavailable*" for
every table.
"""

# ---------------------------------------------------------------------------
# Fallback schemas — the LLM's view of the database
#
# Format: subdomain_name → full markdown with table schemas for that subdomain.
# Alfred-core calls get_fallback_schemas().get(subdomain) in
# alfred.tools.schema.get_schema_with_fallback().
#
# Each subdomain includes all tables from SUBDOMAIN_REGISTRY[subdomain].
# Use markdown tables (| Column | Type | Notes |) for LLM readability.
# ---------------------------------------------------------------------------

# -- Shared table blocks (reused across subdomains) --

_PLAYERS_SCHEMA = """\
### players
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| fpl_id | integer | FPL API element ID |
| web_name | text | Display name e.g. 'Salah' |
| first_name | text | |
| second_name | text | |
| team_id | uuid | FK → teams.id |
| position_id | uuid | FK → positions.id |
| price | decimal | Current price in **millions** (13.2 = £13.2m) |
| total_points | integer | Season total |
| selected_by_percent | decimal | Ownership % (45.2 = 45.2%) |
| status | text | a=available, i=injured, d=doubtful, s=suspended, u=unavailable |
| news | text | Injury/suspension details |
| form | decimal | Recent form rating (rolling avg) |
| points_per_game | decimal | Season average PPG |
| minutes | integer | Total minutes played |
| goals_scored | integer | |
| assists | integer | |
| clean_sheets | integer | |
| bonus | integer | Total bonus points |"""

_TEAMS_SCHEMA = """\
### teams
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| fpl_id | integer | FPL API team ID |
| name | text | Full name e.g. 'Arsenal' |
| short_name | text | 3-letter code e.g. 'ARS' |
| code | integer | FPL internal code |"""

_POSITIONS_SCHEMA = """\
### positions
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| fpl_id | integer | FPL API position ID |
| name | text | e.g. 'Goalkeeper' |
| short_name | text | GKP, DEF, MID, FWD |"""

_GAMEWEEKS_SCHEMA = """\
### gameweeks
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| fpl_id | integer | GW number 1-38 |
| name | text | e.g. 'Gameweek 25' |
| deadline_time | timestamptz | Transfer deadline |
| is_current | boolean | |
| is_next | boolean | |
| finished | boolean | |
| average_score | integer | GW average points |
| highest_score | integer | GW top score |"""

_FIXTURES_SCHEMA = """\
### fixtures
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| fpl_id | integer | |
| gameweek | integer | GW number (NULL if unscheduled) |
| home_team_id | uuid | FK → teams.id |
| away_team_id | uuid | FK → teams.id |
| home_score | integer | NULL if not played |
| away_score | integer | NULL if not played |
| kickoff_time | timestamptz | |
| finished | boolean | |
| home_difficulty | integer | FDR 1-5 (1=easiest for home team) |
| away_difficulty | integer | FDR 1-5 (1=easiest for away team) |"""

_SQUADS_SCHEMA = """\
### squads
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| manager_id | integer | FPL manager ID (NOT a UUID) |
| manager_name | text | |
| gameweek | integer | |
| player_id | uuid | FK → players.id |
| slot | integer | 1-11=starting XI, 12-15=bench |
| multiplier | integer | 0=benched, 1=playing, 2=captain, 3=triple-captain |
| is_captain | boolean | |
| is_vice_captain | boolean | |"""

_PLAYER_GAMEWEEKS_SCHEMA = """\
### player_gameweeks
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| player_id | uuid | FK → players.id |
| gameweek | integer | GW number |
| minutes | integer | |
| goals_scored | integer | |
| assists | integer | |
| clean_sheets | integer | |
| goals_conceded | integer | |
| saves | integer | |
| bonus | integer | 0-3 |
| bps | integer | Raw Bonus Points System score |
| influence | decimal | |
| creativity | decimal | |
| threat | decimal | |
| ict_index | decimal | Composite ICT |
| expected_goals | decimal | xG |
| expected_assists | decimal | xA |
| expected_goal_involvements | decimal | xGI = xG + xA |
| expected_goals_conceded | decimal | xGC |
| total_points | integer | Points scored this GW |
| in_dreamteam | boolean | |
| value | decimal | Player price at that GW in millions |"""

_PLAYER_SNAPSHOTS_SCHEMA = """\
### player_snapshots
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| player_id | uuid | FK → players.id |
| snapshot_time | timestamptz | |
| gameweek | integer | GW number |
| transfers_in_event | integer | Transfers in this GW |
| transfers_out_event | integer | Transfers out this GW |
| selected_by_percent | decimal | Ownership % |
| price | decimal | Price in millions |
| form | decimal | |
| points_per_game | decimal | |"""

_MANAGER_SEASONS_SCHEMA = """\
### manager_seasons
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| manager_id | integer | FPL manager ID (NOT a UUID) |
| manager_name | text | |
| gameweek | integer | |
| points | integer | GW points |
| total_points | integer | Cumulative |
| rank | integer | GW rank |
| overall_rank | integer | |
| percentile_rank | integer | |
| bank | decimal | Transfer budget in millions |
| team_value | decimal | Squad value in millions |
| transfers_made | integer | |
| transfers_cost | integer | Hit points taken |
| points_on_bench | integer | |
| chip_used | text | NULL or: wildcard, bboost, 3xc, freehit |"""

_MANAGER_LINKS_SCHEMA = """\
### manager_links
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK → auth.users (auto-scoped by RLS) |
| fpl_manager_id | integer | The FPL API manager ID |
| is_primary | boolean | true = user's own team |
| label | text | Display name e.g. 'Vinay' or 'My Team' |
| league_id | integer | Optional league association |"""

_LEAGUE_STANDINGS_SCHEMA = """\
### league_standings
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| league_id | integer | FPL league ID (NOT a UUID) |
| league_name | text | |
| gameweek | integer | |
| manager_id | integer | FPL manager ID (NOT a UUID) |
| manager_name | text | |
| team_name | text | |
| rank | integer | |
| last_rank | integer | Previous GW rank |
| total_points | integer | |
| event_points | integer | This GW only |"""

_LEAGUES_SCHEMA = """\
### leagues
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| fpl_id | integer | FPL API league ID |
| name | text | Mini-league name |"""

_TRANSFERS_SCHEMA = """\
### transfers
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| manager_id | integer | FPL manager ID (NOT a UUID) |
| manager_name | text | |
| gameweek | integer | |
| player_in_id | uuid | FK → players.id |
| player_out_id | uuid | FK → players.id |
| price_in | decimal | Millions |
| price_out | decimal | Millions |
| transfer_time | timestamptz | |"""

_WATCHLIST_SCHEMA = """\
### watchlist
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK → auth.users (auto-scoped by RLS) |
| player_id | uuid | FK → players.id |
| notes | text | User's notes on this player |
| created_at | timestamptz | |"""

_TRANSFER_PLANS_SCHEMA = """\
### transfer_plans
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK → auth.users (auto-scoped by RLS) |
| manager_id | integer | FPL manager ID |
| gameweek | integer | Planned GW for transfer |
| player_in_id | uuid | FK → players.id |
| player_out_id | uuid | FK → players.id |
| price_in | decimal | Millions |
| price_out | decimal | Millions |
| created_at | timestamptz | |"""


# -- Subdomain-keyed fallback schemas --

FALLBACK_SCHEMAS: dict[str, str] = {
    "squad": f"""## Available Tables (subdomain: squad)

{_SQUADS_SCHEMA}

{_PLAYERS_SCHEMA}

{_TEAMS_SCHEMA}

{_POSITIONS_SCHEMA}

{_GAMEWEEKS_SCHEMA}

{_MANAGER_SEASONS_SCHEMA}
""",

    "scouting": f"""## Available Tables (subdomain: scouting)

{_PLAYERS_SCHEMA}

{_TEAMS_SCHEMA}

{_POSITIONS_SCHEMA}

{_PLAYER_GAMEWEEKS_SCHEMA}

{_PLAYER_SNAPSHOTS_SCHEMA}

{_FIXTURES_SCHEMA}

{_GAMEWEEKS_SCHEMA}

{_WATCHLIST_SCHEMA}
""",

    "market": f"""## Available Tables (subdomain: market)

{_PLAYER_SNAPSHOTS_SCHEMA}

{_PLAYERS_SCHEMA}

{_TEAMS_SCHEMA}

{_TRANSFERS_SCHEMA}

{_TRANSFER_PLANS_SCHEMA}

{_MANAGER_SEASONS_SCHEMA}
""",

    "league": f"""## Available Tables (subdomain: league)

{_LEAGUE_STANDINGS_SCHEMA}

{_LEAGUES_SCHEMA}

{_SQUADS_SCHEMA}

{_MANAGER_SEASONS_SCHEMA}

{_PLAYERS_SCHEMA}

{_TEAMS_SCHEMA}

{_GAMEWEEKS_SCHEMA}
""",

    "live": f"""## Available Tables (subdomain: live)

{_PLAYER_GAMEWEEKS_SCHEMA}

{_SQUADS_SCHEMA}

{_PLAYERS_SCHEMA}

{_TEAMS_SCHEMA}

{_FIXTURES_SCHEMA}

{_GAMEWEEKS_SCHEMA}
""",

    "fixtures": f"""## Available Tables (subdomain: fixtures)

{_FIXTURES_SCHEMA}

{_TEAMS_SCHEMA}

{_GAMEWEEKS_SCHEMA}
""",
}


# ---------------------------------------------------------------------------
# Subdomain registry — maps subdomains to their accessible tables
# ---------------------------------------------------------------------------

SUBDOMAIN_REGISTRY: dict[str, dict] = {
    "squad": {
        "tables": [
            "squads", "players", "teams", "positions",
            "gameweeks", "manager_seasons",
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
            "players", "teams", "gameweeks",
        ],
    },
    "live": {
        "tables": [
            "player_gameweeks", "squads", "players", "teams",
            "fixtures", "gameweeks",
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
        '**Note:** Middleware auto-injects manager_id on squads reads. '
        'Just read squads directly — do NOT query manager_links first.\n\n'
        'User: "show my team" → db_read on squads (middleware adds manager_id automatically)\n'
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
        '**Note:** Transfer velocity (most transferred-in/out) is in the '
        '`player_snapshots` table (transfers_in_event, transfers_out_event columns). '
        'There is NO `player_transfers` table.\n\n'
        'User: "most transferred-in players" → db_read on player_snapshots, '
        'filter gameweek eq current, order transfers_in_event desc, limit 10\n'
        'User: "what transfers has Vinay made?" → db_read on transfers, '
        'filter manager_id\n'
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
