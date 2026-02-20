"""FPL CRUD middleware — query intelligence layer.

Handles the hard parts that the LLM shouldn't need to think about:
- Integer FK translation (manager_id, league_id are ints, not UUIDs)
- Primary manager auto-injection (default scoping on manager-owned tables)
- Per-table default limits (prevent context explosion)
- Headline column selection (strip noise from large tables)
- Null filter stripping (LLM sometimes emits null filters)
- Required filter enforcement (refuse unfiltered reads on huge tables)

Bridge dicts:
  The FPL schema has integer FKs (manager_id, league_id) that core's UUID
  enrichment cannot handle. Middleware maintains bridge dicts that map
  UUID refs to integer IDs, populated at session start from manager_links.
"""

import logging
from typing import Any

import pandas as pd

from alfred.domain.base import CRUDMiddleware, ReadPreprocessResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tables scoped by integer manager_id (pipeline-managed, public data)
MANAGER_SCOPED_TABLES: set[str] = {
    "squads", "transfers", "manager_seasons",
}

# Tables where current gameweek should be auto-injected if no GW filter present.
# Without this, queries return rows from ALL synced gameweeks — e.g., squads
# with limit=15 returns 15 copies of slot=1 across different GWs.
GW_SCOPED_TABLES: set[str] = {
    "squads",
}

# Tables scoped by integer league_id
LEAGUE_SCOPED_TABLES: set[str] = {
    "league_standings",
}

# Tables scoped by user_id via RLS (private, user-owned)
USER_OWNED_TABLES: set[str] = {
    "manager_links", "watchlist", "transfer_plans",
}

# All FK fields that hold UUIDs (for core's ref↔UUID translation)
UUID_FIELDS: set[str] = {
    "team_id", "position_id",
    "home_team_id", "away_team_id",
    "player_id", "player_in_id", "player_out_id",
}

# --- Per-table guardrails ---

# Default row limits — prevent context flooding
DEFAULT_LIMITS: dict[str, int] = {
    "players": 20,
    "fixtures": 30,
    "player_gameweeks": 50,
    "player_snapshots": 30,
    "manager_seasons": 38,
    "league_standings": 30,
    "squads": 15,
    "transfers": 20,
}

# Tables that MUST have at least one filter (unfiltered reads are refused)
REQUIRE_FILTER: set[str] = {
    "player_gameweeks",
    "player_snapshots",
}

# Headline columns — lighter column sets for browsing large tables.
# Full column sets are used when the LLM explicitly requests specific columns.
HEADLINE_COLUMNS: dict[str, list[str]] = {
    "players": [
        "id", "web_name", "team_id", "position_id",
        "price", "total_points", "form", "points_per_game",
        "selected_by_percent", "status", "news", "minutes",
        "goals_scored", "assists", "clean_sheets", "bonus",
    ],
    "player_gameweeks": [
        "id", "player_id", "gameweek",
        "total_points", "minutes", "goals_scored", "assists",
        "clean_sheets", "bonus", "bps",
        "expected_goals", "expected_assists", "ict_index",
        "value",
    ],
    "player_snapshots": [
        "id", "player_id", "gameweek", "snapshot_time",
        "price", "selected_by_percent", "form",
        "transfers_in_event", "transfers_out_event",
    ],
    "fixtures": [
        "id", "gameweek", "home_team_id", "away_team_id",
        "home_score", "away_score", "kickoff_time", "finished",
        "home_difficulty", "away_difficulty",
    ],
}


class FPLMiddleware(CRUDMiddleware):
    """FPL-specific CRUD middleware with bridge dict state.

    Must be cached as a singleton (get_crud_middleware returns same instance)
    because bridge dicts are populated once at session start and reused.
    """

    def __init__(self):
        self._manager_bridge: dict[str, int] = {}   # UUID → FPL integer manager_id
        self._league_bridge: dict[str, int] = {}     # UUID → FPL integer league_id
        self._primary_manager_id: int | None = None
        self.current_gw: int | None = None            # Set by get_domain_snapshot()
        self._dataframe_cache: dict[str, pd.DataFrame] = {}  # table → DataFrame from last read
        self._team_map: dict[str, str] = {}  # UUID → short_name (for DataFrame enrichment)

    def set_team_map(self, team_map: dict[str, str]):
        """Cache team UUID→short_name map for DataFrame enrichment."""
        self._team_map = team_map
        logger.debug("Team map set: %d teams", len(team_map))

    def set_bridges(
        self,
        manager_bridge: dict[str, int],
        league_bridge: dict[str, int],
        primary_manager_id: int | None,
    ):
        """Called by get_domain_snapshot() at session start."""
        self._manager_bridge = manager_bridge
        self._league_bridge = league_bridge
        self._primary_manager_id = primary_manager_id
        logger.info(
            "Bridges set: %d managers, %d leagues, primary=%s",
            len(manager_bridge), len(league_bridge), primary_manager_id,
        )

    # ----- pre_read: query intelligence before DB call -----

    async def pre_read(self, params: Any, user_id: str) -> ReadPreprocessResult:
        """Preprocess read params: translate IDs, inject defaults, enforce limits."""
        table = params.table
        filters = list(params.filters or [])

        # 1. Strip null filter values (LLM sometimes emits these)
        filters = [f for f in filters if f.value is not None]

        # 2. Translate UUID refs to integer IDs for manager/league scoped tables
        filters = self._translate_integer_fks(table, filters)

        # 3. Auto-inject primary manager_id if missing on manager-scoped tables
        if table in MANAGER_SCOPED_TABLES:
            has_manager_filter = any(f.field == "manager_id" for f in filters)
            if not has_manager_filter and self._primary_manager_id is not None:
                from alfred.tools.crud import FilterClause
                filters.append(
                    FilterClause(field="manager_id", op="=", value=self._primary_manager_id)
                )
                logger.debug("Auto-injected primary manager_id=%s on %s", self._primary_manager_id, table)

        # 3b. Auto-inject current gameweek if missing on GW-scoped tables
        if table in GW_SCOPED_TABLES:
            has_gw_filter = any(f.field == "gameweek" for f in filters)
            if not has_gw_filter and self.current_gw is not None:
                from alfred.tools.crud import FilterClause
                filters.append(
                    FilterClause(field="gameweek", op="=", value=self.current_gw)
                )
                logger.debug("Auto-injected gameweek=%s on %s", self.current_gw, table)

        # 4. Auto-inject league_id if missing on league-scoped tables
        if table in LEAGUE_SCOPED_TABLES:
            has_league_filter = any(f.field == "league_id" for f in filters)
            if not has_league_filter and self._league_bridge:
                # Use the first league (single-league MVP)
                league_id = next(iter(self._league_bridge.values()), None)
                if league_id is not None:
                    from alfred.tools.crud import FilterClause
                    filters.append(
                        FilterClause(field="league_id", op="=", value=league_id)
                    )

        # 5. Enforce required filters on high-volume tables
        if table in REQUIRE_FILTER and not filters:
            logger.warning("Refusing unfiltered read on %s — requires at least one filter", table)
            # Return empty result rather than scanning the whole table
            params.filters = filters
            params.limit = 0
            return ReadPreprocessResult(params=params)

        # 6. Apply default limits
        if params.limit is None or params.limit == 0:
            default_limit = DEFAULT_LIMITS.get(table)
            if default_limit is not None:
                params.limit = default_limit

        # 7. Apply headline columns if no specific columns requested
        if (params.columns is None or len(params.columns) == 0) and table in HEADLINE_COLUMNS:
            params.columns = HEADLINE_COLUMNS[table]

        params.filters = filters
        return ReadPreprocessResult(params=params)

    # ----- post_read: enrich results after DB call -----

    async def post_read(
        self, records: list[dict], table: str, user_id: str
    ) -> list[dict]:
        """Post-process read results: enrich integer FK labels + cache DataFrames."""
        if not records:
            return records

        # Stash DataFrame for ANALYZE/GENERATE steps (domain-side session cache)
        self._dataframe_cache[table] = pd.DataFrame(records)
        logger.debug("Cached DataFrame for %s: %d rows", table, len(records))

        return records

    def get_dataframe_cache(self) -> dict[str, pd.DataFrame]:
        """Return cached DataFrames from recent READ steps."""
        return dict(self._dataframe_cache)

    def clear_dataframe_cache(self) -> None:
        """Clear the DataFrame cache (e.g., between sessions)."""
        self._dataframe_cache.clear()

    # ----- Internal helpers -----

    def _translate_integer_fks(self, table: str, filters: list) -> list:
        """Translate UUID refs in filters to integer IDs for manager/league scoped tables.

        Core's _translate_input_params() converts refs to UUIDs before middleware
        sees them. For manager-scoped tables, the "manager_id" filter value is a UUID
        from the manager_links table. We need to translate it to the FPL integer ID.
        """
        translated = []
        for f in filters:
            if f.field == "manager_id" and table in (MANAGER_SCOPED_TABLES | LEAGUE_SCOPED_TABLES):
                int_id = self._manager_bridge.get(str(f.value))
                if int_id is not None:
                    f.value = int_id
                    logger.debug("Translated manager_id UUID→int: %s→%s", f.value, int_id)
                # If it's already an int (LLM passed raw), keep it
            elif f.field == "league_id" and table in LEAGUE_SCOPED_TABLES:
                int_id = self._league_bridge.get(str(f.value))
                if int_id is not None:
                    f.value = int_id
            translated.append(f)
        return translated
