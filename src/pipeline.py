"""
FPL Data Pipeline.

Orchestrates data ingestion from FPL API to Supabase.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from .config import Config
from .fpl_client import FPLClient, FPLPlayer, FPLTeam, FPLGameweek, FPLFixture
from .database import Database

logger = logging.getLogger(__name__)


class Pipeline:
    """
    FPL data ingestion pipeline.
    
    Usage:
        config = Config.load()
        pipeline = Pipeline(config)
        pipeline.run_full_sync()
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.fpl = FPLClient()
        self.db = Database.from_config(config.supabase)
    
    # -------------------------------------------------------------------------
    # Dimension Sync
    # -------------------------------------------------------------------------
    
    def sync_teams(self) -> Dict[str, Any]:
        """Sync team dimension data."""
        logger.info("Syncing teams...")
        
        teams = self.fpl.get_teams()
        data = [
            {
                "fpl_id": t.id,
                "name": t.name,
                "short_name": t.short_name,
                "code": t.code
            }
            for t in teams
        ]
        
        result = self.db.upsert_teams(data)
        logger.info(f"Synced {len(teams)} teams")
        return result
    
    def sync_gameweeks(self) -> Dict[str, Any]:
        """Sync gameweek dimension data."""
        logger.info("Syncing gameweeks...")
        
        gameweeks = self.fpl.get_gameweeks()
        data = [
            {
                "fpl_id": gw.id,
                "name": gw.name,
                "deadline_time": gw.deadline_time,
                "is_current": gw.is_current,
                "is_next": gw.is_next,
                "finished": gw.finished,
                "average_score": gw.average_score,
                "highest_score": gw.highest_score
            }
            for gw in gameweeks
        ]
        
        result = self.db.upsert_gameweeks(data)
        logger.info(f"Synced {len(gameweeks)} gameweeks")
        return result
    
    def sync_players(self) -> Dict[str, Any]:
        """Sync player dimension data."""
        logger.info("Syncing players...")
        
        players = self.fpl.get_players()
        data = [
            {
                "fpl_id": p.id,
                "web_name": p.web_name,
                "first_name": p.first_name,
                "second_name": p.second_name,
                "team_id": p.team_id,
                "position_id": p.position_id,
                "price": p.price,
                "total_points": p.total_points,
                "selected_by_percent": p.selected_by_percent,
                "status": p.status,
                "news": p.news
            }
            for p in players
        ]
        
        result = self.db.upsert_players(data)
        logger.info(f"Synced {len(players)} players")
        return result
    
    def sync_fixtures(self) -> Dict[str, Any]:
        """Sync fixture data."""
        logger.info("Syncing fixtures...")
        
        fixtures = self.fpl.get_fixtures()
        data = [
            {
                "fpl_id": f.id,
                "gameweek": f.gameweek,
                "home_team_id": f.home_team_id,
                "away_team_id": f.away_team_id,
                "home_score": f.home_team_score,
                "away_score": f.away_team_score,
                "kickoff_time": f.kickoff_time,
                "finished": f.finished,
                "home_difficulty": f.home_difficulty,
                "away_difficulty": f.away_difficulty
            }
            for f in fixtures
        ]
        
        result = self.db.upsert_fixtures(data)
        logger.info(f"Synced {len(fixtures)} fixtures")
        return result
    
    # -------------------------------------------------------------------------
    # Fact Sync
    # -------------------------------------------------------------------------
    
    def sync_player_gw_stats(self, gameweek: int) -> Dict[str, Any]:
        """Sync player stats for a specific gameweek."""
        logger.info(f"Syncing player stats for GW{gameweek}...")
        
        stats = self.fpl.get_live_player_stats(gameweek)
        
        data = [
            {
                "fpl_player_id": player_id,
                "minutes": s.get("minutes", 0),
                "goals_scored": s.get("goals_scored", 0),
                "assists": s.get("assists", 0),
                "clean_sheets": s.get("clean_sheets", 0),
                "goals_conceded": s.get("goals_conceded", 0),
                "own_goals": s.get("own_goals", 0),
                "penalties_saved": s.get("penalties_saved", 0),
                "penalties_missed": s.get("penalties_missed", 0),
                "yellow_cards": s.get("yellow_cards", 0),
                "red_cards": s.get("red_cards", 0),
                "saves": s.get("saves", 0),
                "bonus": s.get("bonus", 0),
                "bps": s.get("bps", 0),
                "total_points": s.get("total_points", 0),
                "value": s.get("value", 0) / 10.0 if s.get("value") else None
            }
            for player_id, s in stats.items()
        ]
        
        result = self.db.insert_player_gw_stats(gameweek, data)
        logger.info(f"Synced stats for {len(data)} players in GW{gameweek}")
        return result
    
    def sync_league_standings(
        self, 
        league_id: int = None, 
        gameweek: int = None
    ) -> Dict[str, Any]:
        """Sync league standings for a gameweek."""
        if league_id is None:
            league_id = self.config.fpl.league_id
        
        if league_id is None:
            logger.warning("No league ID configured, skipping standings sync")
            return {"count": 0}
        
        if gameweek is None:
            gw = self.fpl.get_current_gameweek()
            gameweek = gw.id if gw else 1
        
        logger.info(f"Syncing standings for league {league_id}, GW{gameweek}...")
        
        managers = self.fpl.get_league_managers(league_id)
        result = self.db.insert_league_standings(league_id, gameweek, managers)
        
        logger.info(f"Synced standings for {len(managers)} managers")
        return result
    
    def sync_manager_picks(
        self, 
        manager_ids: List[int] = None,
        gameweek: int = None
    ) -> Dict[str, Any]:
        """Sync manager picks for a gameweek."""
        if manager_ids is None:
            # Use configured rival IDs if available
            manager_ids = self.config.fpl.rival_ids or []
            if self.config.fpl.manager_id:
                manager_ids = [self.config.fpl.manager_id] + manager_ids
        
        if not manager_ids:
            logger.warning("No manager IDs configured, skipping picks sync")
            return {"count": 0}
        
        if gameweek is None:
            gw = self.fpl.get_current_gameweek()
            gameweek = gw.id if gw else 1
        
        logger.info(f"Syncing picks for {len(manager_ids)} managers, GW{gameweek}...")
        
        total_picks = 0
        for manager_id in manager_ids:
            try:
                picks_data = self.fpl.get_manager_picks(manager_id, gameweek)
                picks = picks_data.get("picks", [])
                
                if picks:
                    self.db.insert_manager_picks(gameweek, manager_id, picks)
                    total_picks += len(picks)
                
                self.fpl._rate_limit()
            except Exception as e:
                logger.warning(f"Failed to sync picks for manager {manager_id}: {e}")
                continue
        
        logger.info(f"Synced {total_picks} picks across {len(manager_ids)} managers")
        return {"count": total_picks}
    
    # -------------------------------------------------------------------------
    # Full Sync
    # -------------------------------------------------------------------------
    
    def run_bootstrap_sync(self) -> Dict[str, Any]:
        """
        Sync all bootstrap data (dimensions).
        
        Run this periodically (hourly) to keep reference data fresh.
        """
        logger.info("=" * 60)
        logger.info("Starting bootstrap sync...")
        logger.info("=" * 60)
        
        results = {
            "teams": self.sync_teams(),
            "gameweeks": self.sync_gameweeks(),
            "players": self.sync_players(),
            "fixtures": self.sync_fixtures()
        }
        
        logger.info("Bootstrap sync complete")
        return results
    
    def run_gameweek_sync(self, gameweek: int = None) -> Dict[str, Any]:
        """
        Sync all data for a specific gameweek.
        
        Run this during/after each gameweek.
        """
        if gameweek is None:
            gw = self.fpl.get_current_gameweek()
            gameweek = gw.id if gw else 1
        
        logger.info("=" * 60)
        logger.info(f"Starting gameweek sync for GW{gameweek}...")
        logger.info("=" * 60)
        
        results = {
            "player_stats": self.sync_player_gw_stats(gameweek),
            "league_standings": self.sync_league_standings(gameweek=gameweek),
            "manager_picks": self.sync_manager_picks(gameweek=gameweek)
        }
        
        logger.info(f"Gameweek {gameweek} sync complete")
        return results
    
    def run_full_sync(self, gameweek: int = None) -> Dict[str, Any]:
        """
        Run a complete sync (bootstrap + current gameweek).
        
        This is the main entry point for scheduled runs.
        """
        logger.info("=" * 60)
        logger.info("Starting full sync...")
        logger.info("=" * 60)
        
        results = {
            "bootstrap": self.run_bootstrap_sync(),
            "gameweek": self.run_gameweek_sync(gameweek)
        }
        
        logger.info("Full sync complete")
        return results

