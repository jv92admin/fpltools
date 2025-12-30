#!/usr/bin/env python3
"""
Quick test script for FPL API - no database required.

Useful for exploring the API and verifying data structures.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fpl_client import FPLClient


def main():
    print("=" * 60)
    print("FPL API Test")
    print("=" * 60)
    
    client = FPLClient()
    
    # Test 1: Bootstrap
    print("\n📦 Fetching bootstrap data...")
    bootstrap = client.get_bootstrap()
    print(f"   Players: {len(bootstrap.get('elements', []))}")
    print(f"   Teams: {len(bootstrap.get('teams', []))}")
    print(f"   Gameweeks: {len(bootstrap.get('events', []))}")
    
    # Test 2: Current gameweek
    print("\n📅 Current gameweek...")
    gw = client.get_current_gameweek()
    if gw:
        print(f"   {gw.name} (ID: {gw.id})")
        print(f"   Finished: {gw.finished}")
        print(f"   Average score: {gw.average_score}")
    else:
        print("   No current gameweek (season not started?)")
    
    # Test 3: Top players
    print("\n⭐ Top 5 players by points...")
    players = client.get_players()
    top_players = sorted(players, key=lambda p: p.total_points, reverse=True)[:5]
    for i, p in enumerate(top_players, 1):
        print(f"   {i}. {p.web_name} ({p.team_name}) - {p.total_points} pts")
    
    # Test 4: Most selected
    print("\n👥 Top 5 most selected...")
    most_selected = sorted(players, key=lambda p: p.selected_by_percent, reverse=True)[:5]
    for i, p in enumerate(most_selected, 1):
        print(f"   {i}. {p.web_name} ({p.team_name}) - {p.selected_by_percent}%")
    
    # Test 5: Teams
    print("\n🏟️ Teams...")
    teams = client.get_teams()
    for t in teams[:5]:
        print(f"   {t.name} ({t.short_name})")
    print(f"   ... and {len(teams) - 5} more")
    
    # Test 6: Top managers (overall)
    print("\n🏆 Top 10 overall managers...")
    top_managers = client.get_top_managers(10)
    for m in top_managers:
        print(f"   #{m['rank']}: {m['player_name']} - {m['total']} pts")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

