"""
Supabase Database Client.

Thin persistence layer — all data formatting and UUID resolution
happens in the pipeline. This module just handles upsert/insert/select.
"""

import logging
from typing import Dict, Any, List, Optional

from supabase import create_client, Client

from .config import SupabaseConfig

logger = logging.getLogger(__name__)


class Database:
    """
    Supabase database client for FPL data storage.

    Usage:
        db = Database.from_config(config.supabase)
        db.upsert_teams(data)
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

        Returns the upserted rows (including generated UUIDs) so the
        pipeline can build FK lookup caches.
        """
        if not data:
            logger.warning(f"No data to upsert into {table}")
            return {"count": 0, "data": []}

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

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Select records from a table."""
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
    # Dimension Tables
    # -------------------------------------------------------------------------

    def upsert_positions(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert position dimension data."""
        return self.upsert("positions", data, on_conflict="fpl_id")

    def upsert_teams(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert team dimension data."""
        return self.upsert("teams", data, on_conflict="fpl_id")

    def upsert_gameweeks(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert gameweek dimension data."""
        return self.upsert("gameweeks", data, on_conflict="fpl_id")

    def upsert_leagues(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert league dimension data."""
        return self.upsert("leagues", data, on_conflict="fpl_id")

    def upsert_players(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert player dimension data."""
        return self.upsert("players", data, on_conflict="fpl_id")

    # -------------------------------------------------------------------------
    # Reference / Fact Tables
    # -------------------------------------------------------------------------

    def upsert_fixtures(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert fixture data."""
        return self.upsert("fixtures", data, on_conflict="fpl_id")

    def upsert_player_gw_stats(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert player gameweek stats."""
        return self.upsert("player_gameweeks", data, on_conflict="player_id,gameweek")

    def upsert_player_snapshots(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert player ownership/transfer snapshots."""
        return self.upsert("player_snapshots", data, on_conflict="player_id,snapshot_time")

    # -------------------------------------------------------------------------
    # Manager Subview Tables
    # -------------------------------------------------------------------------

    def upsert_squads(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert manager squad picks."""
        return self.upsert("squads", data, on_conflict="manager_id,gameweek,player_id")

    def upsert_transfers(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert manager transfer history."""
        return self.upsert("transfers", data, on_conflict="manager_id,gameweek,player_in_id,player_out_id")

    def upsert_manager_seasons(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert manager season history."""
        return self.upsert("manager_seasons", data, on_conflict="manager_id,gameweek")

    def upsert_league_standings(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert league standings snapshot."""
        return self.upsert("league_standings", data, on_conflict="league_id,gameweek,manager_id")

    # -------------------------------------------------------------------------
    # Reads
    # -------------------------------------------------------------------------

    def get_players(self, team_id: str = None) -> List[Dict[str, Any]]:
        """Get players, optionally filtered by team UUID."""
        filters = {"team_id": team_id} if team_id else None
        return self.select("players", filters=filters)

    def get_teams(self) -> List[Dict[str, Any]]:
        """Get all teams."""
        return self.select("teams")

    def get_current_gameweek(self) -> Optional[Dict[str, Any]]:
        """Get the current gameweek."""
        results = self.select(
            "gameweeks",
            filters={"is_current": True},
            limit=1
        )
        return results[0] if results else None

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check if database connection is working."""
        try:
            self.client.table("teams").select("fpl_id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
