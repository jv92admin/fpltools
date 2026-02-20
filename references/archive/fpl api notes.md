Where the “documentation” effectively lives

Since there’s no canonical official docs, most usable “docs” are:

The API itself (inspect responses; start with bootstrap-static) 
Fantasy Premier League
+1

Community endpoint guides and Postman collections 
oliverlooney.com
+2
Postman
+2

Wrapper library docs (Python/R/TS) that cite the underlying endpoints 
fpl.readthedocs.io
+2
fpl.readthedocs.io
+2

Core concept: bootstrap-static is your “schema anchor”

This endpoint is the backbone: it gives you the lookup tables and most “current snapshot” player metadata. It contains (among other sections) events (gameweeks), teams, element_types (positions), elements (players), and game configuration. 
Fantasy Premier League
+1

Because most other endpoints refer to entities by numeric IDs, you typically:

Pull bootstrap-static

Build dimension tables (players/teams/positions/events)

Use those IDs to join against fixtures, live GW data, picks, transfers, league standings, etc. 
Fantasy Premier League
+1

Practical endpoint map (what’s available)
1) Global / Season metadata
GET https://fantasy.premierleague.com/api/bootstrap-static/
  - events (GW deadlines, average/highest scores, chips usage counts, etc.)
  - teams (team IDs, names, strength ratings)
  - elements (player “catalog”: price, points, minutes, status, selected_by_percent, transfers*, etc.)
  - element_types (GK/DEF/MID/FWD)
  - game_settings, phases, etc.

GET https://fantasy.premierleague.com/api/event-status/
  - processing status for the current GW (e.g., bonus/league updates)

GET https://fantasy.premierleague.com/api/dream-team/{event_id}/
  - dream team for a GW

GET https://fantasy.premierleague.com/api/team/set-piece-notes/
  - set-piece taker notes by PL team


Fantasy Premier League
+2
oliverlooney.com
+2

Ownership (global): elements[].selected_by_percent in bootstrap-static is the canonical “overall ownership” snapshot exposed by the site API. 
Fantasy Premier League
+1

2) Fixtures and match-level stats
GET https://fantasy.premierleague.com/api/fixtures/
GET https://fantasy.premierleague.com/api/fixtures/?event={event_id}
  - per-fixture objects; for completed fixtures includes stats payloads


oliverlooney.com
+1

3) Player data (deep dives)
GET https://fantasy.premierleague.com/api/element-summary/{element_id}/
  - fixtures (player’s upcoming fixtures)
  - history (GW-by-GW performance this season)
  - history_past (previous seasons)


oliverlooney.com
+1

4) Gameweek “live” player performance
GET https://fantasy.premierleague.com/api/event/{event_id}/live/
  - stats for every player for that GW (live scoring source)


oliverlooney.com
+1

5) Manager (entry) data: profile, roster/picks, transfers
GET https://fantasy.premierleague.com/api/entry/{manager_id}/
  - manager summary (name, region, favourite team, leagues joined, etc.)

GET https://fantasy.premierleague.com/api/entry/{manager_id}/history/
  - current (GW results), past (prior seasons), chips usage

GET https://fantasy.premierleague.com/api/entry/{manager_id}/event/{event_id}/picks/
  - roster for that GW (starting XI/bench, captain/vice, chip, etc.)

GET https://fantasy.premierleague.com/api/entry/{manager_id}/transfers/
  - all transfers for the manager this season

GET https://fantasy.premierleague.com/api/entry/{manager_id}/transfers-latest/
  - transfers for the most recently completed GW (often requires auth/session)


oliverlooney.com
+1

Roster data (your “team”): if you want the current squad state (bank, team value, free transfers, etc.), that is typically under an authenticated endpoint (below). 
fpl.readthedocs.io
+1

6) Mini-leagues: standings + (H2H) matchups
GET https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/
  - classic mini-league standings (paginated)
  - query params commonly used: page_new_entries, page_standings, phase

GET https://fantasy.premierleague.com/api/leagues-h2h/{league_id}/standings/
  - head-to-head league standings (community-discovered; may vary)

GET https://fantasy.premierleague.com/api/leagues-h2h-matches/league/{league_id}/?page=1
  - head-to-head fixtures/matchups (paginated)

GET https://fantasy.premierleague.com/api/league/{league_id}/cup-status/
  - cup status for a league


oliverlooney.com
+2
fpl.readthedocs.io
+2

7) Authenticated (“private”) endpoints you should expect

These are commonly referenced by wrappers/guides as requiring an FPL session/cookie, and are used for “my account” views:

GET https://fantasy.premierleague.com/api/my-team/{manager_id}/
  - current team state (requires authentication)

GET https://fantasy.premierleague.com/api/me/
  - logged-in user data (requires authentication)


oliverlooney.com
+1

How to think about “ownership” beyond global ownership

Global ownership: bootstrap-static -> elements[].selected_by_percent 
Fantasy Premier League
+1

Mini-league ownership: not typically a single endpoint. The usual pattern is:

Pull league standings to get the list of entry (manager) IDs

For each entry, pull .../event/{GW}/picks/

Aggregate picks into counts / percentages (and compute “effective ownership” yourself if you want captain multipliers) 
oliverlooney.com
+2
fpl.readthedocs.io
+2

Operational notes (important in real apps)

Many developers report the FPL API has CORS constraints (meaning you generally call it from a backend/service, not directly from a browser frontend). 
oliverlooney.com

Rate limiting isn’t formally published by FPL, but third-party connectors document throttles (example: 100 calls / 60 seconds per connection in one connector). In practice: cache aggressively (bootstrap-static especially), and paginate leagues carefully. 
Microsoft Learn

Use wrapper libraries as living “type hints” when building quickly (e.g., TS wrapper projects that track response shapes; Python libs that document which endpoints require login). 
GitHub
+2
fpl.readthedocs.io
+2

If you’re building a data model: a clean starting schema

Dimensions (slow-changing):

teams (from bootstrap-static)

players (from bootstrap-static.elements)

positions (from bootstrap-static.element_types)

events/gameweeks (from bootstrap-static.events)

Facts (high-volume / time-series):

fixtures (from fixtures/)

gw_live_player_stats (from event/{GW}/live/)

player_gw_history (either from element-summary/{id} or derived from live)

entry_gw_picks (from entry/{id}/event/{GW}/picks/)

entry_transfers (from entry/{id}/transfers/)

league_standings_snapshots (from leagues-classic/.../standings/)