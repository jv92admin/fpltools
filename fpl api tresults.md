 PS C:\Projects\fpltools> python scripts/test_fpl_api.py
============================================================
FPL API Test
============================================================

📦 Fetching bootstrap data...
   Players: 775
   Teams: 20
   Gameweeks: 38

📅 Current gameweek...
   Gameweek 18 (ID: 18)
   Finished: True
   Average score: 44

⭐ Top 5 players by points...
   1. Haaland (Man City) - 153 pts
   2. Semenyo (Bournemouth) - 108 pts
   3. Rice (Arsenal) - 102 pts
   4. B.Fernandes (Man Utd) - 99 pts
   5. Guéhi (Crystal Palace) - 95 pts

👥 Top 5 most selected...
   1. Haaland (Man City) - 74.2%
   2. Semenyo (Bournemouth) - 46.5%
   3. Guéhi (Crystal Palace) - 41.5%
   4. Foden (Man City) - 40.4%
   5. Ekitiké (Liverpool) - 35.7%

🏟️ Teams...
   Arsenal (ARS)
   Aston Villa (AVL)
   Burnley (BUR)
   Bournemouth (BOU)
   Brentford (BRE)
   ... and 15 more

🏆 Top 10 overall managers...
   #1: Matt Chamberlain - 1283 pts
   #2: Ian Foster - 1279 pts
   #3: Gustav Walkin - 1273 pts
   #4: Chris Mounsey-Thear - 1268 pts
   #5: A Khaled - 1268 pts
   #6: Captain Ahmed - 1267 pts
   #6: Captain Ahmed - 1267 pts
   #6: Ryan Monaghan - 1267 pts
   #8: Janne Ojanpera - 1265 pts
   #6: Captain Ahmed - 1267 pts
   #6: Ryan Monaghan - 1267 pts
   #8: Janne Ojanpera - 1265 pts
   #6: Captain Ahmed - 1267 pts
   #6: Ryan Monaghan - 1267 pts
   #6: Captain Ahmed - 1267 pts
(venv) PS C:\Projects\fpltools> python scripts/explore_fpl_api.py

============================================================
  Configuration
============================================================
  Manager ID: 6578679
  League ID: 1486488
  Rival IDs: [6655564]
  Current GW: 18

============================================================
  1. BOOTSTRAP DATA STRUCTURE
============================================================

📦 Top-level keys in bootstrap-static:
   - chips: list[8 items]
   - events: list[38 items]
   - game_settings: dict with keys ['league_join_private_max', 'league_join_public_max', 'league_max_size_public_classic', 'league_max_size_public_h2h', 'league_max_size_private_h2h']...
   - game_config: dict with keys ['settings', 'rules', 'scoring']...
   - phases: list[11 items]
   - teams: list[20 items]
   - total_players: int
   - element_stats: list[26 items]
   - element_types: list[4 items]
   - elements: list[775 items]

📋 Sample PLAYER fields (elements[0]):
   Total fields: 102
   Key fields:
     id: 1
     web_name: Raya
     first_name: David
     second_name: Raya Martín
     team: 1
     element_type: 1
     now_cost: 60
     total_points: 77
     selected_by_percent: 35.5
     status: a
     news:
     minutes: 1620
     goals_scored: 0
     assists: 0
     clean_sheets: 9
     bonus: 4
     bps: 314
     form: 3.7
     points_per_game: 4.3

🏟️ Sample TEAM fields (teams[0]):
{
  "code": 3,
  "draw": 0,
  "form": null,
  "id": 1,
  "loss": 0,
  "name": "Arsenal",
  "played": 0,
  "points": 0,
  "position": 1,
  "short_name": "ARS",
  "strength": 5,
  "team_division": null,
  "unavailable": false,
  "win": 0,
  "strength_overall_home": 1300,
  "strength_overall_away": 1375,
  "strength_attack_home": 1340,
  "strength_attack_away": 1400,
  "strength_defence_home": 1260,
  "strength_defence_away": 1350,
  "pulse_id": 1
}

📅 Sample GAMEWEEK fields (events[0]):
{
  "id": 1,
  "name": "Gameweek 1",
  "deadline_time": "2025-08-15T17:30:00Z",
  "release_time": null,
  "average_entry_score": 54,
  "finished": true,
  "data_checked": true,
  "highest_scoring_entry": 3772644,
  "deadline_time_epoch": 1755279000,
  "deadline_time_game_offset": 0,
  "highest_score": 127,
  "is_previous": false,
  "is_current": false,
  "is_next": false,
  "cup_leagues_created": false,
  "h2h_ko_matches_created": false,
  "can_enter": false,
  "can_manage": false,
  "released": true,
  "ranked_count": 9469118,
  "overrides": {
    "rules": {},
    "scoring": {},
    "element_types": [],
    "pick_multiplier": null
  },
  "chip_plays": [
    {
      "chip_name": "bboost",
      "num_played": 342779
    },
    {
      "chip_name": "3xc",
      "num_played": 272642
    }
  ],
  "most_selected": 235,
  "most_transferred_in": 1,
  "top_element": 531,
  "top_element_info": {
    "id": 531,
    "points": 17
  },
  "transfers_made": 0,
  "most_captained": 381,
  "most_vice_captained": 235
}

============================================================
  2. MANAGER DATA (ID: 6578679)
============================================================

👤 Manager Profile (entry/{id}):
{
  "id": 6578679,
  "joined_time": "2025-08-13T15:38:32.968798Z",
  "started_event": 1,
  "favourite_team": null,
  "player_first_name": "Vignesh",
  "player_last_name": "Jeyaraman",
  "player_region_id": 229,
  "player_region_name": "USA",
  "player_region_iso_code_short": "US",
  "player_region_iso_code_long": "USA",
  "years_active": 13,
  "summary_overall_points": 1043,
  "summary_overall_rank": 1226651,
  "summary_event_points": 41,
  "summary_event_rank": 7766178,
  "current_event": 18,
  "leagues": {
    "classic": [
      {
        "id": 249,
        "name": "USA",
        "short_name": "region-229",
        "created": "2025-07-20T23:14:32.785979Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "s",
        "scoring": "c",
        "admin_entry": null,
        "start_event": 1,
        "entry_can_leave": false,
        "entry_can_admin": false,
        "entry_can_invite": false,
        "has_cup": true,
        "cup_league": null,
        "cup_qualified": null,
        "rank_count": 430364,
        "entry_percentile_rank": 10,
        "active_phases": [
          {
            "phase": 1,
            "rank": 40328,
            "last_rank": 35666,
            "rank_sort": 40358,
            "total": 1043,
            "league_id": 249,
            "rank_count": 430364,
            "entry_percentile_rank": 10
          },
          {
            "phase": 6,
            "rank": 171059,
            "last_rank": 156101,
            "rank_sort": 171134,
            "total": 292,
            "league_id": 249,
            "rank_count": 430363,
            "entry_percentile_rank": 40
          }
        ],
        "entry_rank": 40328,
        "entry_last_rank": 35666
      },
      {
        "id": 276,
        "name": "Gameweek 1",
        "short_name": "event-1",
        "created": "2025-07-20T23:14:33.264422Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "s",
        "scoring": "c",
        "admin_entry": null,
        "start_event": 1,
        "entry_can_leave": false,
        "entry_can_admin": false,
        "entry_can_invite": false,
        "has_cup": false,
        "cup_league": null,
        "cup_qualified": null,
        "rank_count": 9447133,
        "entry_percentile_rank": 15,
        "active_phases": [
          {
            "phase": 1,
            "rank": 1220873,
            "last_rank": 1084469,
            "rank_sort": 1222277,
            "total": 1043,
            "league_id": 276,
            "rank_count": 9447133,
            "entry_percentile_rank": 15
          },
          {
            "phase": 6,
            "rank": 4681264,
            "last_rank": 4336566,
            "rank_sort": 4684604,
            "total": 292,
            "league_id": 276,
            "rank_count": 9435216,
            "entry_percentile_rank": 50
          }
        ],
        "entry_rank": 1220873,
        "entry_last_rank": 1084469
      },
      {
        "id": 314,
        "name": "Overall",
        "short_name": "overall",
        "created": "2025-07-20T23:14:33.933835Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "s",
        "scoring": "c",
        "admin_entry": null,
        "start_event": 1,
        "entry_can_leave": false,
        "entry_can_admin": false,
        "entry_can_invite": false,
        "has_cup": true,
        "cup_league": 2815434,
        "cup_qualified": true,
        "rank_count": 12620800,
        "entry_percentile_rank": 10,
        "active_phases": [
          {
            "phase": 1,
            "rank": 1226651,
            "last_rank": 1089054,
            "rank_sort": 1228055,
            "total": 1043,
            "league_id": 314,
            "rank_count": 12620800,
            "entry_percentile_rank": 10
          },
          {
            "phase": 6,
            "rank": 5465736,
            "last_rank": 5067907,
            "rank_sort": 5469076,
            "total": 292,
            "league_id": 314,
            "rank_count": 12620794,
            "entry_percentile_rank": 45
          }
        ],
        "entry_rank": 1226651,
        "entry_last_rank": 1089054
      },
      {
        "id": 315,
        "name": "NBC Sports League",
        "short_name": "brd-nbcsports",
        "created": "2025-07-20T23:14:33.951644Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "s",
        "scoring": "c",
        "admin_entry": null,
        "start_event": 1,
        "entry_can_leave": false,
        "entry_can_admin": false,
        "entry_can_invite": false,
        "has_cup": true,
        "cup_league": null,
        "cup_qualified": null,
        "rank_count": 431902,
        "entry_percentile_rank": 10,
        "active_phases": [
          {
            "phase": 1,
            "rank": 40452,
            "last_rank": 35782,
            "rank_sort": 40482,
            "total": 1043,
            "league_id": 315,
            "rank_count": 431902,
            "entry_percentile_rank": 10
          },
          {
            "phase": 6,
            "rank": 171647,
            "last_rank": 156630,
            "rank_sort": 171722,
            "total": 292,
            "league_id": 315,
            "rank_count": 431902,
            "entry_percentile_rank": 40
          }
        ],
        "entry_rank": 40452,
        "entry_last_rank": 35782
      },
      {
        "id": 333,
        "name": "Second Chance",
        "short_name": "sc",
        "created": "2025-07-20T23:14:34.276586Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "s",
        "scoring": "c",
        "admin_entry": null,
        "start_event": 21,
        "entry_can_leave": false,
        "entry_can_admin": false,
        "entry_can_invite": false,
        "has_cup": false,
        "cup_league": null,
        "cup_qualified": null,
        "rank_count": null,
        "entry_percentile_rank": null,
        "active_phases": [
          {
            "phase": 1,
            "rank": 0,
            "last_rank": 0,
            "rank_sort": 0,
            "total": 0,
            "league_id": 333,
            "rank_count": null,
            "entry_percentile_rank": null
          },
          {
            "phase": 6,
            "rank": 0,
            "last_rank": 0,
            "rank_sort": 0,
            "total": 0,
            "league_id": 333,
            "rank_count": null,
            "entry_percentile_rank": null
          }
        ],
        "entry_rank": 0,
        "entry_last_rank": 0
      },
      {
        "id": 1521,
        "name": "EPL",
        "short_name": null,
        "created": "2025-07-21T11:35:46.853979Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "x",
        "scoring": "c",
        "admin_entry": 6007,
        "start_event": 1,
        "entry_can_leave": true,
        "entry_can_admin": false,
        "entry_can_invite": false,
        "has_cup": true,
        "cup_league": null,
        "cup_qualified": null,
        "rank_count": 14,
        "entry_percentile_rank": 30,
        "active_phases": [
          {
            "phase": 1,
            "rank": 4,
            "last_rank": 2,
            "rank_sort": 4,
            "total": 1043,
            "league_id": 1521,
            "rank_count": 14,
            "entry_percentile_rank": 30
          },
          {
            "phase": 6,
            "rank": 13,
            "last_rank": 11,
            "rank_sort": 13,
            "total": 292,
            "league_id": 1521,
            "rank_count": 14,
            "entry_percentile_rank": 95
          }
        ],
        "entry_rank": 4,
        "entry_last_rank": 2
      },
      {
        "id": 1486488,
        "name": "Abe Yaar",
        "short_name": null,
        "created": "2025-08-13T15:38:54.379815Z",
        "closed": false,
        "rank": null,
        "max_entries": null,
        "league_type": "x",
        "scoring": "c",
        "admin_entry": 6578679,
        "start_event": 1,
        "entry_can_leave": false,
        "entry_can_admin": true,
        "entry_can_invite": true,
        "has_cup": true,
        "cup_league": null,
        "cup_qualified": null,
        "rank_count": 22,
        "entry_percentile_rank": 25,
        "active_phases": [
          {
            "phase": 1,
            "rank": 5,
            "last_rank": 4,
            "rank_sort": 5,
            "total": 1043,
            "league_id": 1486488,
            "rank_count": 22,
            "entry_percentile_rank": 25
          },
          {
            "phase": 6,
            "rank": 17,
            "last_rank": 16,
            "rank_sort": 17,
            "total": 292,
            "league_id": 1486488,
            "rank_count": 22,
            "entry_percentile_rank": 80
          }
        ],
        "entry_rank": 5,
        "entry_last_rank": 4
      }
    ],
    "h2h": [],
    "cup": {
      "matches": [],
      "status": {
        "qualification_event": null,
        "qualification_numbers": null,
        "qualification_rank": null,
        "qualification_state": null
      },
      "cup_league": null
    },
    "cup_matches": [
      {
        "id": 54499457,
        "entry_1_entry": 6578679,
        "entry_1_name": "Kiseki no sedai",
        "entry_1_player_name": "Vignesh Jeyaraman",
        "entry_1_points": 74,
        "entry_1_win": 0,
        "entry_1_draw": 0,
        "entry_1_loss": 0,
        "entry_1_total": 0,
        "entry_2_entry": 26730,
        "entry_2_name": "Stay Humble",
        "entry_2_player_name": "Richard Swain",
        "entry_2_points": 83,
        "entry_2_win": 0,
        "entry_2_draw": 0,
        "entry_2_loss": 0,
        "entry_2_total": 0,
        "is_knockout": true,
        "league": 2815434,
        "winner": 26730,
        "seed_value": null,
        "event": 16,
        "tiebreak": null,
        "is_bye": false,
        "knockout_name": "Round of 8388608"
      }
    ]
  },
  "name": "Kiseki no sedai",
  "name_change_blocked": false,
  "entered_events": [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18
  ],
  "kit": null,
  "last_deadline_bank": 14,
  "last_deadline_value": 1010,
  "last_deadline_total_transfers": 22,
  "club_badge_src": null
}

📊 Manager History (entry/{id}/history):
   Keys: ['current', 'past', 'chips']
   Current season GWs: 18
   Latest GW:
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
   Past seasons: 13
   Chips used: [{'name': 'wildcard', 'time': '2025-09-27T02:20:46.247838Z', 'event': 6}, {'name': 'bboost', 'time': '2025-10-02T21:28:17.606870Z', 'event': 7}, {'name': '3xc', 'time': '2025-11-26T06:00:44.851849Z', 'event': 13}]    

🎯 Manager Picks for GW18 (entry/<built-in function id>/event/18/picks):
   Keys: ['active_chip', 'automatic_subs', 'entry_history', 'picks']
   Squad size: 15
   Starting XI + Bench:
     Pos 1: Roefs (multiplier: 1)
     Pos 2: Virgil (multiplier: 1)
     Pos 3: Andersen (multiplier: 1)
     Pos 4: Thiaw (multiplier: 1)
     Pos 5: Wilson (VC) (multiplier: 1)
     Pos 6: Rice (multiplier: 1)
     Pos 7: Foden (multiplier: 1)
     Pos 8: Saka (multiplier: 1)
     Pos 9: Minteh (multiplier: 1)
     Pos 10: Thiago (multiplier: 1)
     Pos 11: Haaland (C) (multiplier: 2)
     BENCH: Dúbravka (multiplier: 0)
     BENCH: J.Timber (multiplier: 0)
     BENCH: Estève (multiplier: 0)
     BENCH: Marc Guiu (multiplier: 0)
   Entry history for this GW:
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

🔄 Manager Transfers (entry/<built-in function id>/transfers):
   Total transfers this season: 32
   Recent transfers:
     GW4: Minteh → Semenyo
     GW3: Palmer → M.Salah
     GW3: Haaland → Watkins

============================================================
  3. LEAGUE DATA (ID: 1486488)
============================================================

🏆 League Standings:
   Keys: ['new_entries', 'last_updated_data', 'league', 'standings']
   League name: Abe Yaar
   Created: 2025-08-13T15:38:54.379815Z
   Total managers: 22
   Top 5:
     #1: Rishwanth R (RishX1) - 1086 pts
     #2: Afdal Basheer (Hopeless FC) - 1064 pts
     #3: Krishanth Kanakarajah (PaTTa PaTTi XI) - 1061 pts
     #4: Harish Raghu (Scranton Strangler) - 1048 pts
     #5: Vignesh Jeyaraman (Kiseki no sedai) - 1043 pts

   Sample manager entry structure:
{
  "id": 52533005,
  "event_total": 53,
  "player_name": "Rishwanth R",
  "rank": 1,
  "last_rank": 1,
  "rank_sort": 1,
  "total": 1086,
  "entry": 2901215,
  "entry_name": "RishX1",
  "has_played": true
}

============================================================
  4. LIVE GAMEWEEK DATA (GW18)
============================================================

⚡ Live Player Stats (event/18/live):
   Players with stats: 775

   Sample stats for Raya:
{
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
  "clearances_blocks_interceptions": 0,
  "recoveries": 6,
  "tackles": 0,
  "defensive_contribution": 0,
  "starts": 1,
  "expected_goals": "0.00",
  "expected_assists": "0.00",
  "expected_goal_involvements": "0.00",
  "expected_goals_conceded": "0.85",
  "total_points": 2,
  "in_dreamteam": false
}

============================================================
  5. FIXTURES
============================================================

📅 Fixtures for GW18:
   Total fixtures: 10
     MUN 1-0 NEW (Difficulty: H3/A3)
     NFO 1-2 MCI (Difficulty: H4/A3)
     ARS 2-1 BHA (Difficulty: H3/A5)
     BRE 4-1 BOU (Difficulty: H3/A3)
     BUR 0-0 EVE (Difficulty: H2/A2)

============================================================
  6. PLAYER DETAIL ENDPOINT
============================================================

🌟 Detailed data for Haaland (element-summary/430):
   Keys: ['fixtures', 'history', 'history_past']
   Upcoming fixtures: 20
   Next fixture:
{
  "id": 189,
  "code": 2562083,
  "team_h": 17,
  "team_h_score": null,
  "team_a": 13,
  "team_a_score": null,
  "event": 19,
  "finished": false,
  "minutes": 0,
  "provisional_start_time": false,
  "kickoff_time": "2026-01-01T20:00:00Z",
  "event_name": "Gameweek 19",
  "is_home": false,
  "difficulty": 3
}
   GW history entries: 18
   Latest GW performance:
{
  "element": 430,
  "fixture": 178,
  "opponent_team": 16,
  "total_points": 2,
  "was_home": false,
  "kickoff_time": "2025-12-27T12:30:00Z",
  "team_h_score": 1,
  "team_a_score": 2,
  "round": 18,
  "modified": false,
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
  "saves": 0,
  "bonus": 0,
  "bps": 5,
  "influence": "2.4",
  "creativity": "10.6",
  "threat": "15.0",
  "ict_index": "2.8",
  "clearances_blocks_interceptions": 1,
  "recoveries": 2,
  "tackles": 0,
  "defensive_contribution": 3,
  "starts": 1,
  "expected_goals": "0.17",
  "expected_assists": "0.11",
  "expected_goal_involvements": "0.28",
  "expected_goals_conceded": "0.55",
  "value": 151,
  "transfers_balance": 59888,
  "selected": 9439331,
  "transfers_in": 70149,
  "transfers_out": 10261
}
   Past seasons: 3

============================================================
  SUMMARY
============================================================

    ✅ Endpoints tested:
       - bootstrap-static/ (players, teams, gameweeks, positions)
       - entry/{id}/ (manager profile)
       - entry/{id}/history/ (season history)
       - entry/{id}/event/{gw}/picks/ (team picks)
       - entry/{id}/transfers/ (transfer history)
       - leagues-classic/{id}/standings/ (league standings)
       - event/{gw}/live/ (live player stats)
       - fixtures/ (match data)
       - element-summary/{id}/ (player detail)

    📝 See /docs/fpl_api.md for full documentation.
