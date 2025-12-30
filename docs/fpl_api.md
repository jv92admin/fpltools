# FPL API Documentation

> **Note**: The FPL API has no official documentation. This is based on community discovery and direct API inspection as of December 2025.

## Base URL

```
https://fantasy.premierleague.com/api/
```

## Rate Limits & Caching

| Concern | Recommendation |
|---------|----------------|
| **Rate limit** | ~100 requests/minute (unofficial) |
| **CORS** | Blocked from browser; use backend/proxy |
| **Caching** | `bootstrap-static` for hours; live data for minutes |

---

## Endpoints

### 1. Bootstrap Static (Core Data)

```
GET /bootstrap-static/
```

The backbone endpoint — contains all reference data. **Cache this aggressively.**

#### Response Structure

```json
{
  "chips": [...],           // 8 chip types
  "events": [...],          // 38 gameweeks
  "game_settings": {...},   // League size limits, etc.
  "game_config": {...},     // Settings, rules, scoring
  "phases": [...],          // 11 phases (months)
  "teams": [...],           // 20 Premier League teams
  "total_players": 12620800,
  "element_stats": [...],   // 26 stat definitions
  "element_types": [...],   // 4 positions (GK/DEF/MID/FWD)
  "elements": [...]         // 775 players
}
```

#### Player Object (`elements[]`) — 102 Fields

Key fields:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `id` | int | `1` | Unique player ID |
| `web_name` | str | `"Raya"` | Display name |
| `first_name` | str | `"David"` | First name |
| `second_name` | str | `"Raya Martín"` | Surname |
| `team` | int | `1` | Team ID (→ teams[]) |
| `element_type` | int | `1` | Position ID (1=GK, 2=DEF, 3=MID, 4=FWD) |
| `now_cost` | int | `60` | Price in £0.1m (divide by 10) |
| `total_points` | int | `77` | Season total points |
| `selected_by_percent` | str | `"35.5"` | Global ownership % |
| `status` | str | `"a"` | Availability: a=available, i=injured, d=doubtful, s=suspended, u=unavailable |
| `news` | str | `""` | Injury/news text |
| `minutes` | int | `1620` | Total minutes played |
| `goals_scored` | int | `0` | Season goals |
| `assists` | int | `0` | Season assists |
| `clean_sheets` | int | `9` | Season clean sheets |
| `bonus` | int | `4` | Season bonus points |
| `bps` | int | `314` | Bonus Points System score |
| `form` | str | `"3.7"` | Recent form rating |
| `points_per_game` | str | `"4.3"` | Average PPG |

#### Team Object (`teams[]`)

```json
{
  "id": 1,
  "code": 3,
  "name": "Arsenal",
  "short_name": "ARS",
  "strength": 5,
  "strength_overall_home": 1300,
  "strength_overall_away": 1375,
  "strength_attack_home": 1340,
  "strength_attack_away": 1400,
  "strength_defence_home": 1260,
  "strength_defence_away": 1350,
  "pulse_id": 1
}
```

#### Gameweek Object (`events[]`)

```json
{
  "id": 1,
  "name": "Gameweek 1",
  "deadline_time": "2025-08-15T17:30:00Z",
  "deadline_time_epoch": 1755279000,
  "finished": true,
  "is_current": false,
  "is_next": false,
  "is_previous": false,
  "average_entry_score": 54,
  "highest_score": 127,
  "highest_scoring_entry": 3772644,
  "ranked_count": 9469118,
  "chip_plays": [
    {"chip_name": "bboost", "num_played": 342779},
    {"chip_name": "3xc", "num_played": 272642}
  ],
  "most_selected": 235,
  "most_captained": 381,
  "most_vice_captained": 235,
  "most_transferred_in": 1,
  "top_element": 531,
  "top_element_info": {"id": 531, "points": 17}
}
```

---

### 2. Manager Profile

```
GET /entry/{manager_id}/
```

#### Response

```json
{
  "id": 6578679,
  "name": "Kiseki no sedai",
  "player_first_name": "Vignesh",
  "player_last_name": "Jeyaraman",
  "player_region_name": "USA",
  "player_region_iso_code_short": "US",
  "joined_time": "2025-08-13T15:38:32.968798Z",
  "started_event": 1,
  "years_active": 13,
  "summary_overall_points": 1043,
  "summary_overall_rank": 1226651,
  "summary_event_points": 41,
  "summary_event_rank": 7766178,
  "current_event": 18,
  "last_deadline_bank": 14,
  "last_deadline_value": 1010,
  "last_deadline_total_transfers": 22,
  "favourite_team": null,
  "leagues": {
    "classic": [...],  // Array of classic leagues
    "h2h": [...],      // Array of H2H leagues
    "cup": {...},      // Cup status
    "cup_matches": [...] // Cup match history
  },
  "entered_events": [1, 2, 3, ...]  // GWs participated in
}
```

---

### 3. Manager History

```
GET /entry/{manager_id}/history/
```

#### Response

```json
{
  "current": [
    {
      "event": 18,
      "points": 41,
      "total_points": 1043,
      "rank": 7766178,
      "rank_sort": 7810628,
      "overall_rank": 1226651,
      "percentile_rank": 65,
      "bank": 14,
      "value": 1010,
      "event_transfers": 1,
      "event_transfers_cost": 0,
      "points_on_bench": 11
    }
  ],
  "past": [
    {"season_name": "2024/25", "total_points": 2100, "rank": 500000},
    // ... more seasons
  ],
  "chips": [
    {"name": "wildcard", "event": 6, "time": "2025-09-27T02:20:46.247838Z"},
    {"name": "bboost", "event": 7, "time": "2025-10-02T21:28:17.606870Z"},
    {"name": "3xc", "event": 13, "time": "2025-11-26T06:00:44.851849Z"}
  ]
}
```

---

### 4. Manager Picks (Team for a GW)

```
GET /entry/{manager_id}/event/{gameweek}/picks/
```

#### Response

```json
{
  "active_chip": null,  // or "bboost", "3xc", "freehit", "wildcard"
  "automatic_subs": [],
  "entry_history": {
    "event": 18,
    "points": 41,
    "total_points": 1043,
    "rank": 7766178,
    "overall_rank": 1226651,
    "bank": 14,
    "value": 1010,
    "event_transfers": 1,
    "event_transfers_cost": 0,
    "points_on_bench": 11
  },
  "picks": [
    {
      "element": 583,       // Player ID
      "position": 1,        // 1-11 = starting, 12-15 = bench
      "multiplier": 1,      // 0=bench, 1=normal, 2=captain, 3=triple
      "is_captain": false,
      "is_vice_captain": false
    },
    // ... 15 total picks
  ]
}
```

**Position Mapping:**
- 1-11: Starting XI (ordered by position)
- 12: Bench GK
- 13-15: Bench outfield (priority order for auto-subs)

**Multiplier Values:**
- `0`: Bench (no points unless auto-subbed)
- `1`: Normal starter
- `2`: Captain (2x points)
- `3`: Triple Captain chip active

---

### 5. Manager Transfers

```
GET /entry/{manager_id}/transfers/
```

#### Response

```json
[
  {
    "element_in": 469,
    "element_in_cost": 67,
    "element_out": 599,
    "element_out_cost": 60,
    "entry": 6578679,
    "event": 4,
    "time": "2025-09-13T12:30:00Z"
  }
]
```

---

### 6. League Standings

```
GET /leagues-classic/{league_id}/standings/
GET /leagues-classic/{league_id}/standings/?page_standings={page}
```

#### Response

```json
{
  "league": {
    "id": 1486488,
    "name": "Abe Yaar",
    "created": "2025-08-13T15:38:54.379815Z",
    "closed": false,
    "league_type": "x",   // x=private, s=public
    "admin_entry": 6578679,
    "rank_count": 22
  },
  "standings": {
    "has_next": false,
    "page": 1,
    "results": [
      {
        "id": 52533005,
        "entry": 2901215,          // Manager ID
        "entry_name": "RishX1",    // Team name
        "player_name": "Rishwanth R",
        "rank": 1,
        "last_rank": 1,
        "total": 1086,
        "event_total": 53,
        "has_played": true
      }
    ]
  },
  "new_entries": {...},
  "last_updated_data": "2025-12-28T10:00:00Z"
}
```

**Pagination:** 50 entries per page. Use `?page_standings=2` for more.

---

### 7. Live Gameweek Stats

```
GET /event/{gameweek}/live/
```

Returns stats for **all players** in a single call. Very efficient.

#### Response

```json
{
  "elements": [
    {
      "id": 1,  // Player ID
      "stats": {
        "minutes": 90,
        "goals_scored": 0,
        "assists": 0,
        "clean_sheets": 0,
        "goals_conceded": 1,
        "own_goals": 0,
        "penalties_saved": 0,
        "penalties_missed": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "saves": 2,
        "bonus": 0,
        "bps": 11,
        "influence": "21.8",
        "creativity": "10.0",
        "threat": "0.0",
        "ict_index": "3.2",
        "starts": 1,
        "expected_goals": "0.00",
        "expected_assists": "0.00",
        "expected_goal_involvements": "0.00",
        "expected_goals_conceded": "0.85",
        "total_points": 2,
        "in_dreamteam": false
      }
    }
  ]
}
```

---

### 8. Fixtures

```
GET /fixtures/
GET /fixtures/?event={gameweek}
```

#### Response

```json
[
  {
    "id": 178,
    "code": 2562072,
    "event": 18,
    "kickoff_time": "2025-12-27T12:30:00Z",
    "finished": true,
    "team_h": 13,
    "team_a": 16,
    "team_h_score": 1,
    "team_a_score": 2,
    "team_h_difficulty": 4,
    "team_a_difficulty": 3,
    "stats": [
      // Goal scorers, assists, bonus, etc.
    ]
  }
]
```

**Difficulty Rating:** 1 (easiest) to 5 (hardest)

---

### 9. Player Detail

```
GET /element-summary/{player_id}/
```

#### Response

```json
{
  "fixtures": [
    {
      "id": 189,
      "event": 19,
      "event_name": "Gameweek 19",
      "team_h": 17,
      "team_a": 13,
      "is_home": false,
      "difficulty": 3,
      "kickoff_time": "2026-01-01T20:00:00Z",
      "finished": false
    }
  ],
  "history": [
    {
      "element": 430,
      "fixture": 178,
      "round": 18,
      "opponent_team": 16,
      "was_home": false,
      "kickoff_time": "2025-12-27T12:30:00Z",
      "total_points": 2,
      "minutes": 90,
      "goals_scored": 0,
      "assists": 0,
      "clean_sheets": 0,
      "bonus": 0,
      "bps": 5,
      "expected_goals": "0.17",
      "expected_assists": "0.11",
      "value": 151,
      "selected": 9439331,
      "transfers_in": 70149,
      "transfers_out": 10261,
      "transfers_balance": 59888
    }
  ],
  "history_past": [
    {"season_name": "2024/25", "total_points": 281, ...},
    {"season_name": "2023/24", "total_points": 217, ...}
  ]
}
```

---

### 10. Overall League (Top X Managers)

```
GET /leagues-classic/314/standings/?page_standings={page}
```

League ID `314` is the global "Overall" league.

- 50 managers per page
- Top 100 = 2 pages
- Top 10,000 = 200 pages

---

## Common Patterns

### Mini-League Ownership Calculation

There's no direct endpoint. Pattern:

1. Get league standings → extract manager IDs
2. For each manager → get picks for GW
3. Aggregate player picks → calculate ownership %

### Price Conversion

FPL stores prices in £0.1m units:
```python
price_millions = now_cost / 10.0  # 60 → £6.0m
```

### Value Conversion

Team value is also in £0.1m:
```python
team_value = value / 10.0  # 1010 → £101.0m
```

---

## ID Reference

| Entity | ID Source | Example |
|--------|-----------|---------|
| Player | `bootstrap-static` → `elements[].id` | Haaland = 430 |
| Team | `bootstrap-static` → `teams[].id` | Arsenal = 1 |
| Position | `bootstrap-static` → `element_types[].id` | GK=1, DEF=2, MID=3, FWD=4 |
| Gameweek | `bootstrap-static` → `events[].id` | GW18 = 18 |
| Manager | URL or league standings | 6578679 |
| League | URL | 1486488 |

---

## Authenticated Endpoints (Not Used)

These require FPL session cookies:

```
GET /my-team/{manager_id}/   # Current squad state
GET /me/                     # Logged-in user info
```

We avoid these to maintain "no auth ownership" posture.

