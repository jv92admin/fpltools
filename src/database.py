"""
Supabase Database Client.

Handles all database operations for FPL Tools.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from supabase import create_client, Client

from .config import SupabaseConfig

logger = logging.getLogger(__name__)


class Database:
    """
    Supabase database client for FPL data storage.
    
    Usage:
        db = Database.from_config(config.supabase)
        db.upsert_players(players)
    """
    
    def __init__(self, client: Client):
        self.client = client
    
    @classmethod
    def from_config(cls, config: SupabaseConfig) -> "Database":
        """Create database client from config."""
        client = create_client(config.url, config.key)
        return cls(client)
    
    # -------------------------------------------------------------------------
    # Generic Operations
    # -------------------------------------------------------------------------
    
    def upsert(
        self, 
        table: str, 
        data: List[Dict[str, Any]], 
        on_conflict: str = "id"
    ) -> Dict[str, Any]:
        """
        Upsert records into a table.
        
        Args:
            table: Table name
            data: List of records to upsert
            on_conflict: Column(s) to use for conflict resolution
        """
        if not data:
            logger.warning(f"No data to upsert into {table}")
            return {"count": 0}
        
        try:
            result = (
                self.client.table(table)
                .upsert(data, on_conflict=on_conflict)
                .execute()
            )
            logger.info(f"Upserted {len(data)} records into {table}")
            return {"count": len(data), "data": result.data}
        except Exception as e:
            logger.error(f"Error upserting into {table}: {e}")
            raise
    
    def insert(self, table: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert records into a table."""
        if not data:
            return {"count": 0}
        
        try:
            result = self.client.table(table).insert(data).execute()
            logger.info(f"Inserted {len(data)} records into {table}")
            return {"count": len(data), "data": result.data}
        except Exception as e:
            logger.error(f"Error inserting into {table}: {e}")
            raise
    
    def select(
        self, 
        table: str, 
        columns: str = "*",
        filters: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        Select records from a table.
        
        Args:
            table: Table name
            columns: Columns to select (default: all)
            filters: Dict of {column: value} filters
            order_by: Column to order by (prefix with - for desc)
            limit: Maximum records to return
        """
        try:
            query = self.client.table(table).select(columns)
            
            if filters:
                for col, val in filters.items():
                    query = query.eq(col, val)
            
            if order_by:
                if order_by.startswith("-"):
                    query = query.order(order_by[1:], desc=True)
                else:
                    query = query.order(order_by)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Error selecting from {table}: {e}")
            raise
    
    # -------------------------------------------------------------------------
    # Players
    # -------------------------------------------------------------------------
    
    def upsert_players(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert player dimension data."""
        return self.upsert("dim_players", players, on_conflict="fpl_id")
    
    def get_players(self, team_id: int = None) -> List[Dict[str, Any]]:
        """Get players, optionally filtered by team."""
        filters = {"team_id": team_id} if team_id else None
        return self.select("dim_players", filters=filters)
    
    # -------------------------------------------------------------------------
    # Teams
    # -------------------------------------------------------------------------
    
    def upsert_teams(self, teams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert team dimension data."""
        return self.upsert("dim_teams", teams, on_conflict="fpl_id")
    
    def get_teams(self) -> List[Dict[str, Any]]:
        """Get all teams."""
        return self.select("dim_teams")
    
    # -------------------------------------------------------------------------
    # Gameweeks
    # -------------------------------------------------------------------------
    
    def upsert_gameweeks(self, gameweeks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert gameweek dimension data."""
        return self.upsert("dim_gameweeks", gameweeks, on_conflict="fpl_id")
    
    def get_current_gameweek(self) -> Optional[Dict[str, Any]]:
        """Get the current gameweek."""
        results = self.select(
            "dim_gameweeks", 
            filters={"is_current": True},
            limit=1
        )
        return results[0] if results else None
    
    # -------------------------------------------------------------------------
    # Player Gameweek Stats (Fact Table)
    # -------------------------------------------------------------------------
    
    def insert_player_gw_stats(
        self, 
        gameweek: int, 
        stats: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Insert player gameweek stats."""
        # Add gameweek and timestamp to each record
        now = datetime.utcnow().isoformat()
        for stat in stats:
            stat["gameweek"] = gameweek
            stat["ingested_at"] = now
        
        return self.upsert(
            "fact_player_gw", 
            stats, 
            on_conflict="fpl_player_id,gameweek"
        )
    
    def get_player_gw_stats(
        self, 
        gameweek: int = None,
        player_id: int = None
    ) -> List[Dict[str, Any]]:
        """Get player gameweek stats."""
        filters = {}
        if gameweek:
            filters["gameweek"] = gameweek
        if player_id:
            filters["fpl_player_id"] = player_id
        
        return self.select("fact_player_gw", filters=filters or None)
    
    # -------------------------------------------------------------------------
    # Manager Picks (Fact Table)
    # -------------------------------------------------------------------------
    
    def insert_manager_picks(
        self, 
        gameweek: int,
        manager_id: int,
        picks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Insert manager picks for a gameweek."""
        now = datetime.utcnow().isoformat()
        
        # Format picks with context
        formatted = []
        for pick in picks:
            formatted.append({
                "gameweek": gameweek,
                "manager_id": manager_id,
                "fpl_player_id": pick.get("element"),
                "position": pick.get("position"),
                "multiplier": pick.get("multiplier"),  # 0=bench, 1=starter, 2=captain, 3=TC
                "is_captain": pick.get("is_captain", False),
                "is_vice_captain": pick.get("is_vice_captain", False),
                "ingested_at": now
            })
        
        return self.upsert(
            "fact_manager_picks",
            formatted,
            on_conflict="gameweek,manager_id,fpl_player_id"
        )
    
    # -------------------------------------------------------------------------
    # League Standings (Fact Table)
    # -------------------------------------------------------------------------
    
    def insert_league_standings(
        self,
        league_id: int,
        gameweek: int,
        standings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Insert league standings snapshot."""
        now = datetime.utcnow().isoformat()
        
        formatted = []
        for entry in standings:
            formatted.append({
                "league_id": league_id,
                "gameweek": gameweek,
                "manager_id": entry.get("entry"),
                "manager_name": entry.get("player_name"),
                "team_name": entry.get("entry_name"),
                "rank": entry.get("rank"),
                "last_rank": entry.get("last_rank"),
                "total_points": entry.get("total"),
                "event_points": entry.get("event_total"),
                "ingested_at": now
            })
        
        return self.upsert(
            "fact_league_standings",
            formatted,
            on_conflict="league_id,gameweek,manager_id"
        )
    
    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------
    
    def upsert_fixtures(self, fixtures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert fixture data."""
        return self.upsert("fact_fixtures", fixtures, on_conflict="fpl_id")
    
    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------
    
    def health_check(self) -> bool:
        """Check if database connection is working."""
        try:
            # Try to query a system table or simple select
            self.client.table("dim_teams").select("fpl_id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

