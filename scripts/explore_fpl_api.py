#!/usr/bin/env python3
"""
FPL API Exploration Script.

Explores various FPL API endpoints using your configured IDs.
Outputs detailed data for documentation purposes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.fpl_client import FPLClient


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_json(data, indent=2, max_items=5):
    """Print JSON with truncation for large lists."""
    if isinstance(data, list) and len(data) > max_items:
        print(f"  (Showing first {max_items} of {len(data)} items)")
        print(json.dumps(data[:max_items], indent=indent, default=str))
        print(f"  ... and {len(data) - max_items} more")
    else:
        print(json.dumps(data, indent=indent, default=str))


def main():
    # Load config
    config = Config.load()
    client = FPLClient()
    
    manager_id = config.fpl.manager_id
    league_id = config.fpl.league_id
    
    print_section("Configuration")
    print(f"  Manager ID: {manager_id or 'Not set'}")
    print(f"  League ID: {league_id or 'Not set'}")
    print(f"  Rival IDs: {config.fpl.rival_ids or 'None'}")
    
    # Get current gameweek
    current_gw = client.get_current_gameweek()
    gw_num = current_gw.id if current_gw else 1
    print(f"  Current GW: {gw_num}")
    
    # =========================================================================
    # 1. BOOTSTRAP DATA STRUCTURE
    # =========================================================================
    print_section("1. BOOTSTRAP DATA STRUCTURE")
    bootstrap = client.get_bootstrap()
    
    print("\n📦 Top-level keys in bootstrap-static:")
    for key in bootstrap.keys():
        val = bootstrap[key]
        if isinstance(val, list):
            print(f"   - {key}: list[{len(val)} items]")
        elif isinstance(val, dict):
            print(f"   - {key}: dict with keys {list(val.keys())[:5]}...")
        else:
            print(f"   - {key}: {type(val).__name__}")
    
    print("\n📋 Sample PLAYER fields (elements[0]):")
    if bootstrap.get('elements'):
        sample_player = bootstrap['elements'][0]
        print(f"   Total fields: {len(sample_player)}")
        print("   Key fields:")
        key_fields = ['id', 'web_name', 'first_name', 'second_name', 'team', 
                      'element_type', 'now_cost', 'total_points', 'selected_by_percent',
                      'status', 'news', 'minutes', 'goals_scored', 'assists',
                      'clean_sheets', 'bonus', 'bps', 'form', 'points_per_game']
        for field in key_fields:
            if field in sample_player:
                print(f"     {field}: {sample_player[field]}")
    
    print("\n🏟️ Sample TEAM fields (teams[0]):")
    if bootstrap.get('teams'):
        sample_team = bootstrap['teams'][0]
        print_json(sample_team)
    
    print("\n📅 Sample GAMEWEEK fields (events[0]):")
    if bootstrap.get('events'):
        sample_event = bootstrap['events'][0]
        print_json(sample_event)
    
    # =========================================================================
    # 2. MANAGER DATA (if configured)
    # =========================================================================
    if manager_id:
        print_section(f"2. MANAGER DATA (ID: {manager_id})")
        
        # Manager profile
        print("\n👤 Manager Profile (entry/{id}):")
        try:
            manager = client.get_manager(manager_id)
            print_json(manager)
        except Exception as e:
            print(f"   Error: {e}")
        
        # Manager history
        print("\n📊 Manager History (entry/{id}/history):")
        try:
            history = client.get_manager_history(manager_id)
            print(f"   Keys: {list(history.keys())}")
            if 'current' in history:
                print(f"   Current season GWs: {len(history['current'])}")
                if history['current']:
                    print("   Latest GW:")
                    print_json(history['current'][-1])
            if 'past' in history:
                print(f"   Past seasons: {len(history['past'])}")
            if 'chips' in history:
                print(f"   Chips used: {history['chips']}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Manager picks for current GW
        print(f"\n🎯 Manager Picks for GW{gw_num} (entry/{id}/event/{gw_num}/picks):")
        try:
            picks = client.get_manager_picks(manager_id, gw_num)
            print(f"   Keys: {list(picks.keys())}")
            if 'picks' in picks:
                print(f"   Squad size: {len(picks['picks'])}")
                print("   Starting XI + Bench:")
                for pick in picks['picks']:
                    player = next((p for p in bootstrap['elements'] if p['id'] == pick['element']), None)
                    name = player['web_name'] if player else f"ID:{pick['element']}"
                    role = ""
                    if pick.get('is_captain'):
                        role = " (C)"
                    elif pick.get('is_vice_captain'):
                        role = " (VC)"
                    pos = "BENCH" if pick['position'] > 11 else f"Pos {pick['position']}"
                    print(f"     {pos}: {name}{role} (multiplier: {pick['multiplier']})")
            if 'entry_history' in picks:
                print("   Entry history for this GW:")
                print_json(picks['entry_history'])
        except Exception as e:
            print(f"   Error: {e}")
        
        # Manager transfers
        print(f"\n🔄 Manager Transfers (entry/{id}/transfers):")
        try:
            transfers = client.get_manager_transfers(manager_id)
            print(f"   Total transfers this season: {len(transfers)}")
            if transfers:
                print("   Recent transfers:")
                for t in transfers[-3:]:
                    player_in = next((p for p in bootstrap['elements'] if p['id'] == t['element_in']), None)
                    player_out = next((p for p in bootstrap['elements'] if p['id'] == t['element_out']), None)
                    in_name = player_in['web_name'] if player_in else f"ID:{t['element_in']}"
                    out_name = player_out['web_name'] if player_out else f"ID:{t['element_out']}"
                    print(f"     GW{t['event']}: {out_name} → {in_name}")
        except Exception as e:
            print(f"   Error: {e}")
    
    # =========================================================================
    # 3. LEAGUE DATA (if configured)
    # =========================================================================
    if league_id:
        print_section(f"3. LEAGUE DATA (ID: {league_id})")
        
        print("\n🏆 League Standings:")
        try:
            standings = client.get_league_standings(league_id)
            print(f"   Keys: {list(standings.keys())}")
            
            if 'league' in standings:
                print(f"   League name: {standings['league'].get('name')}")
                print(f"   Created: {standings['league'].get('created')}")
            
            if 'standings' in standings:
                results = standings['standings'].get('results', [])
                print(f"   Total managers: {len(results)}")
                print("   Top 5:")
                for m in results[:5]:
                    print(f"     #{m['rank']}: {m['player_name']} ({m['entry_name']}) - {m['total']} pts")
                
                if results:
                    print("\n   Sample manager entry structure:")
                    print_json(results[0])
        except Exception as e:
            print(f"   Error: {e}")
    
    # =========================================================================
    # 4. LIVE GAMEWEEK DATA
    # =========================================================================
    print_section(f"4. LIVE GAMEWEEK DATA (GW{gw_num})")
    
    print(f"\n⚡ Live Player Stats (event/{gw_num}/live):")
    try:
        live_stats = client.get_live_player_stats(gw_num)
        print(f"   Players with stats: {len(live_stats)}")
        
        # Show a sample
        if live_stats:
            sample_id = list(live_stats.keys())[0]
            sample_stats = live_stats[sample_id]
            player = next((p for p in bootstrap['elements'] if p['id'] == sample_id), None)
            name = player['web_name'] if player else f"ID:{sample_id}"
            print(f"\n   Sample stats for {name}:")
            print_json(sample_stats)
    except Exception as e:
        print(f"   Error: {e}")
    
    # =========================================================================
    # 5. FIXTURES
    # =========================================================================
    print_section("5. FIXTURES")
    
    print(f"\n📅 Fixtures for GW{gw_num}:")
    try:
        fixtures = client.get_fixtures(gw_num)
        teams_lookup = {t.id: t.short_name for t in client.get_teams()}
        
        print(f"   Total fixtures: {len(fixtures)}")
        for f in fixtures[:5]:
            home = teams_lookup.get(f.home_team_id, "???")
            away = teams_lookup.get(f.away_team_id, "???")
            score = f"{f.home_team_score}-{f.away_team_score}" if f.finished else "vs"
            print(f"     {home} {score} {away} (Difficulty: H{f.home_difficulty}/A{f.away_difficulty})")
    except Exception as e:
        print(f"   Error: {e}")
    
    # =========================================================================
    # 6. PLAYER DETAIL
    # =========================================================================
    print_section("6. PLAYER DETAIL ENDPOINT")
    
    # Get top player
    players = client.get_players()
    top_player = max(players, key=lambda p: p.total_points)
    
    print(f"\n🌟 Detailed data for {top_player.web_name} (element-summary/{top_player.id}):")
    try:
        detail = client.get_player_detail(top_player.id)
        print(f"   Keys: {list(detail.keys())}")
        
        if 'fixtures' in detail:
            print(f"   Upcoming fixtures: {len(detail['fixtures'])}")
            if detail['fixtures']:
                print("   Next fixture:")
                print_json(detail['fixtures'][0])
        
        if 'history' in detail:
            print(f"   GW history entries: {len(detail['history'])}")
            if detail['history']:
                print("   Latest GW performance:")
                print_json(detail['history'][-1])
        
        if 'history_past' in detail:
            print(f"   Past seasons: {len(detail['history_past'])}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_section("SUMMARY")
    print("""
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
    """)


if __name__ == "__main__":
    main()

