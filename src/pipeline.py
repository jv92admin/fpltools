"""
FPL Data Pipeline.

Orchestrates data ingestion from FPL API to Supabase.

Key responsibility: maps FPL API integer IDs to Supabase UUIDs for all
FK columns. Dimension tables are synced first to build UUID lookup caches,
then used when syncing fact/subview tables.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .config import Config
from .fpl_client import FPLClient
from .database import Database

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float (handles string decimals from FPL API)."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


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

        # UUID lookup caches: {fpl_id: uuid_string}
        # Populated during bootstrap sync or loaded from DB on demand.
        self._team_uuids: Dict[int, str] = {}
        self._position_uuids: Dict[int, str] = {}
        self._player_uuids: Dict[int, str] = {}

        # Manager name cache: {fpl_manager_id: display_name}
        self._manager_names: Dict[int, Optional[str]] = {}

    # -------------------------------------------------------------------------
    # UUID Lookup Management
    # -------------------------------------------------------------------------

    def _build_uuid_lookup(
        self,
        result: Dict[str, Any],
        cache: Dict[int, str]
    ):
        """Populate a UUID cache from an upsert result."""
        for row in result.get("data", []):
            fpl_id = row.get("fpl_id")
            uuid = row.get("id")
            if fpl_id is not None and uuid is not None:
                cache[fpl_id] = uuid

    def _load_uuid_lookups(self):
        """Load UUID lookups from the DB if not already cached."""
        if not self._team_uuids:
            rows = self.db.select("teams", columns="id,fpl_id")
            self._team_uuids = {r["fpl_id"]: r["id"] for r in rows}

        if not self._position_uuids:
            rows = self.db.select("positions", columns="id,fpl_id")
            self._position_uuids = {r["fpl_id"]: r["id"] for r in rows}

        if not self._player_uuids:
            rows = self.db.select("players", columns="id,fpl_id")
            self._player_uuids = {r["fpl_id"]: r["id"] for r in rows}

    def _get_tracked_manager_ids(self) -> List[int]:
        """Get list of manager IDs to sync (from config)."""
        ids = list(self.config.fpl.rival_ids or [])
        if self.config.fpl.manager_id:
            ids = [self.config.fpl.manager_id] + ids
        return ids

    def _ensure_manager_names(self, manager_ids: List[int]):
        """Fetch and cache display names for the given manager IDs."""
        for mid in manager_ids:
            if mid not in self._manager_names:
                try:
                    profile = self.fpl.get_manager(mid)
                    first = profile.get("player_first_name", "")
                    last = profile.get("player_last_name", "")
                    self._manager_names[mid] = f"{first} {last}".strip() or None
                    self.fpl._rate_limit()
                except Exception:
                    self._manager_names[mid] = None

    # -------------------------------------------------------------------------
    # Dimension Sync
    # -------------------------------------------------------------------------

    def sync_positions(self) -> Dict[str, Any]:
        """Sync position dimension data from bootstrap."""
        logger.info("Syncing positions...")

        bootstrap = self.fpl.get_bootstrap()
        data = [
            {
                "fpl_id": p["id"],
                "name": p["singular_name"],
                "short_name": p["singular_name_short"],
            }
            for p in bootstrap.get("element_types", [])
        ]

        result = self.db.upsert_positions(data)
        self._build_uuid_lookup(result, self._position_uuids)
        logger.info(f"Synced {len(data)} positions")
        return result

    def sync_teams(self) -> Dict[str, Any]:
        """Sync team dimension data."""
        logger.info("Syncing teams...")

        teams = self.fpl.get_teams()
        data = [
            {
                "fpl_id": t.id,
                "name": t.name,
                "short_name": t.short_name,
                "code": t.code,
            }
            for t in teams
        ]

        result = self.db.upsert_teams(data)
        self._build_uuid_lookup(result, self._team_uuids)
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
                "highest_score": gw.highest_score,
            }
            for gw in gameweeks
        ]

        result = self.db.upsert_gameweeks(data)
        logger.info(f"Synced {len(gameweeks)} gameweeks")
        return result

    def sync_leagues(self) -> Dict[str, Any]:
        """Sync league dimension data from league standings API."""
        league_id = self.config.fpl.league_id
        if league_id is None:
            logger.warning("No league ID configured, skipping league sync")
            return {"count": 0, "data": []}

        logger.info(f"Syncing league metadata for league {league_id}...")

        # Extract league metadata from standings endpoint
        standings_data = self.fpl.get_league_standings(league_id, page=1)
        league_meta = standings_data.get("league", {})

        data = [
            {
                "fpl_id": league_meta.get("id", league_id),
                "name": league_meta.get("name", f"League {league_id}"),
            }
        ]

        result = self.db.upsert_leagues(data)
        logger.info(f"Synced league: {data[0]['name']}")
        return result

    def sync_players(self) -> Dict[str, Any]:
        """Sync player dimension data with UUID FK resolution."""
        logger.info("Syncing players...")

        players = self.fpl.get_players()
        data = []
        for p in players:
            team_uuid = self._team_uuids.get(p.team_id)
            position_uuid = self._position_uuids.get(p.position_id)

            if not team_uuid or not position_uuid:
                logger.warning(
                    f"Skipping player {p.web_name}: missing team/position UUID "
                    f"(team_id={p.team_id}, position_id={p.position_id})"
                )
                continue

            data.append({
                "fpl_id": p.id,
                "web_name": p.web_name,
                "first_name": p.first_name,
                "second_name": p.second_name,
                "team_id": team_uuid,
                "position_id": position_uuid,
                "price": p.price,
                "total_points": p.total_points,
                "selected_by_percent": p.selected_by_percent,
                "status": p.status,
                "news": p.news,
                "form": _safe_float(p.raw_data.get("form")),
                "points_per_game": _safe_float(p.raw_data.get("points_per_game")),
                "minutes": p.raw_data.get("minutes", 0),
                "goals_scored": p.raw_data.get("goals_scored", 0),
                "assists": p.raw_data.get("assists", 0),
                "clean_sheets": p.raw_data.get("clean_sheets", 0),
                "bonus": p.raw_data.get("bonus", 0),
            })

        result = self.db.upsert_players(data)
        self._build_uuid_lookup(result, self._player_uuids)
        logger.info(f"Synced {len(data)} players")
        return result

    def sync_fixtures(self) -> Dict[str, Any]:
        """Sync fixture data with UUID FK resolution for team IDs."""
        logger.info("Syncing fixtures...")

        fixtures = self.fpl.get_fixtures()
        data = []
        for f in fixtures:
            home_uuid = self._team_uuids.get(f.home_team_id)
            away_uuid = self._team_uuids.get(f.away_team_id)

            if not home_uuid or not away_uuid:
                logger.warning(
                    f"Skipping fixture {f.id}: missing team UUID "
                    f"(home={f.home_team_id}, away={f.away_team_id})"
                )
                continue

            data.append({
                "fpl_id": f.id,
                "gameweek": f.gameweek,
                "home_team_id": home_uuid,
                "away_team_id": away_uuid,
                "home_score": f.home_team_score,
                "away_score": f.away_team_score,
                "kickoff_time": f.kickoff_time,
                "finished": f.finished,
                "home_difficulty": f.home_difficulty,
                "away_difficulty": f.away_difficulty,
            })

        result = self.db.upsert_fixtures(data)
        logger.info(f"Synced {len(data)} fixtures")
        return result

    def sync_player_snapshots(self) -> Dict[str, Any]:
        """Capture current player ownership/price snapshots."""
        logger.info("Syncing player snapshots...")

        current_gw = self.fpl.get_current_gameweek()
        gw_num = current_gw.id if current_gw else 1
        now = datetime.now(timezone.utc).isoformat()

        players = self.fpl.get_players()
        data = []
        for p in players:
            player_uuid = self._player_uuids.get(p.id)
            if not player_uuid:
                continue

            data.append({
                "player_id": player_uuid,
                "snapshot_time": now,
                "gameweek": gw_num,
                "transfers_in_event": p.raw_data.get("transfers_in_event", 0),
                "transfers_out_event": p.raw_data.get("transfers_out_event", 0),
                "selected_by_percent": p.selected_by_percent,
                "price": p.price,
                "form": _safe_float(p.raw_data.get("form")),
                "points_per_game": _safe_float(p.raw_data.get("points_per_game")),
            })

        result = self.db.upsert_player_snapshots(data)
        logger.info(f"Synced snapshots for {len(data)} players")
        return result

    # -------------------------------------------------------------------------
    # Gameweek / Subview Sync
    # -------------------------------------------------------------------------

    def sync_player_gw_stats(self, gameweek: int) -> Dict[str, Any]:
        """Sync player stats for a specific gameweek."""
        logger.info(f"Syncing player stats for GW{gameweek}...")
        self._load_uuid_lookups()

        stats = self.fpl.get_live_player_stats(gameweek)

        data = []
        for player_fpl_id, s in stats.items():
            player_uuid = self._player_uuids.get(player_fpl_id)
            if not player_uuid:
                continue

            data.append({
                "player_id": player_uuid,
                "gameweek": gameweek,
                "minutes": s.get("minutes", 0),
                "goals_scored": s.get("goals_scored", 0),
                "assists": s.get("assists", 0),
                "clean_sheets": s.get("clean_sheets", 0),
                "goals_conceded": s.get("goals_conceded", 0),
                "saves": s.get("saves", 0),
                "bonus": s.get("bonus", 0),
                "bps": s.get("bps", 0),
                "influence": _safe_float(s.get("influence")),
                "creativity": _safe_float(s.get("creativity")),
                "threat": _safe_float(s.get("threat")),
                "ict_index": _safe_float(s.get("ict_index")),
                "expected_goals": _safe_float(s.get("expected_goals")),
                "expected_assists": _safe_float(s.get("expected_assists")),
                "expected_goal_involvements": _safe_float(s.get("expected_goal_involvements")),
                "expected_goals_conceded": _safe_float(s.get("expected_goals_conceded")),
                "total_points": s.get("total_points", 0),
                "in_dreamteam": s.get("in_dreamteam", False),
                "value": s.get("value", 0) / 10.0 if s.get("value") else None,
            })

        result = self.db.upsert_player_gw_stats(data)
        logger.info(f"Synced stats for {len(data)} players in GW{gameweek}")
        return result

    def sync_squads(
        self,
        manager_ids: List[int] = None,
        gameweek: int = None,
    ) -> Dict[str, Any]:
        """Sync manager squad picks for a gameweek."""
        if manager_ids is None:
            manager_ids = self._get_tracked_manager_ids()

        if not manager_ids:
            logger.warning("No manager IDs configured, skipping squad sync")
            return {"count": 0}

        if gameweek is None:
            gw = self.fpl.get_current_gameweek()
            gameweek = gw.id if gw else 1

        logger.info(f"Syncing squads for {len(manager_ids)} managers, GW{gameweek}...")
        self._load_uuid_lookups()
        self._ensure_manager_names(manager_ids)

        all_data = []
        for manager_id in manager_ids:
            try:
                picks_data = self.fpl.get_manager_picks(manager_id, gameweek)
                picks = picks_data.get("picks", [])

                for pick in picks:
                    player_uuid = self._player_uuids.get(pick.get("element"))
                    if not player_uuid:
                        continue

                    all_data.append({
                        "manager_id": manager_id,
                        "manager_name": self._manager_names.get(manager_id),
                        "gameweek": gameweek,
                        "player_id": player_uuid,
                        "slot": pick.get("position"),
                        "multiplier": pick.get("multiplier", 1),
                        "is_captain": pick.get("is_captain", False),
                        "is_vice_captain": pick.get("is_vice_captain", False),
                    })

                self.fpl._rate_limit()
            except Exception as e:
                logger.warning(f"Failed to sync squad for manager {manager_id}: {e}")
                continue

        if all_data:
            result = self.db.upsert_squads(all_data)
            logger.info(f"Synced {len(all_data)} squad picks across {len(manager_ids)} managers")
            return result
        return {"count": 0}

    def sync_league_standings(
        self,
        league_id: int = None,
        gameweek: int = None,
    ) -> Dict[str, Any]:
        """Sync league standings for a gameweek with denormalized names."""
        if league_id is None:
            league_id = self.config.fpl.league_id

        if league_id is None:
            logger.warning("No league ID configured, skipping standings sync")
            return {"count": 0}

        if gameweek is None:
            gw = self.fpl.get_current_gameweek()
            gameweek = gw.id if gw else 1

        logger.info(f"Syncing standings for league {league_id}, GW{gameweek}...")

        # Get league name from the first page of standings
        first_page = self.fpl.get_league_standings(league_id, page=1)
        league_name = first_page.get("league", {}).get("name", "")

        # Get all managers (handles pagination)
        managers = self.fpl.get_league_managers(league_id)

        data = [
            {
                "league_id": league_id,
                "league_name": league_name,
                "gameweek": gameweek,
                "manager_id": entry.get("entry"),
                "manager_name": entry.get("player_name"),
                "team_name": entry.get("entry_name"),
                "rank": entry.get("rank"),
                "last_rank": entry.get("last_rank"),
                "total_points": entry.get("total", 0),
                "event_points": entry.get("event_total", 0),
            }
            for entry in managers
        ]

        result = self.db.upsert_league_standings(data)
        logger.info(f"Synced standings for {len(managers)} managers")
        return result

    def sync_manager_history(
        self,
        manager_ids: List[int] = None,
    ) -> Dict[str, Any]:
        """Sync full season history for managers."""
        if manager_ids is None:
            manager_ids = self._get_tracked_manager_ids()

        if not manager_ids:
            logger.warning("No manager IDs configured, skipping history sync")
            return {"count": 0}

        logger.info(f"Syncing history for {len(manager_ids)} managers...")
        self._ensure_manager_names(manager_ids)

        all_data = []
        for manager_id in manager_ids:
            try:
                history = self.fpl.get_manager_history(manager_id)
                current_season = history.get("current", [])
                chips = history.get("chips", [])

                # Build chip lookup
                chip_by_gw = {}
                for chip in chips:
                    chip_by_gw[chip.get("event")] = chip.get("name")

                for entry in current_season:
                    gw = entry.get("event")
                    all_data.append({
                        "manager_id": manager_id,
                        "manager_name": self._manager_names.get(manager_id),
                        "gameweek": gw,
                        "points": entry.get("points", 0),
                        "total_points": entry.get("total_points", 0),
                        "rank": entry.get("rank"),
                        "overall_rank": entry.get("overall_rank"),
                        "percentile_rank": entry.get("percentile_rank"),
                        "bank": entry.get("bank", 0) / 10.0 if entry.get("bank") else 0,
                        "team_value": entry.get("value", 0) / 10.0 if entry.get("value") else 0,
                        "transfers_made": entry.get("event_transfers", 0),
                        "transfers_cost": entry.get("event_transfers_cost", 0),
                        "points_on_bench": entry.get("points_on_bench", 0),
                        "chip_used": chip_by_gw.get(gw),
                    })

                self.fpl._rate_limit()
            except Exception as e:
                logger.warning(f"Failed to sync history for manager {manager_id}: {e}")
                continue

        if all_data:
            result = self.db.upsert_manager_seasons(all_data)
            logger.info(f"Synced {len(all_data)} GW history entries")
            return result
        return {"count": 0}

    def sync_manager_transfers(
        self,
        manager_ids: List[int] = None,
    ) -> Dict[str, Any]:
        """Sync manager transfer history from FPL API."""
        if manager_ids is None:
            manager_ids = self._get_tracked_manager_ids()

        if not manager_ids:
            logger.warning("No manager IDs configured, skipping transfers sync")
            return {"count": 0}

        logger.info(f"Syncing transfers for {len(manager_ids)} managers...")
        self._load_uuid_lookups()
        self._ensure_manager_names(manager_ids)

        all_data = []
        for manager_id in manager_ids:
            try:
                transfers = self.fpl.get_manager_transfers(manager_id)

                for t in transfers:
                    pin_uuid = self._player_uuids.get(t.get("element_in"))
                    pout_uuid = self._player_uuids.get(t.get("element_out"))
                    if not pin_uuid or not pout_uuid:
                        continue

                    all_data.append({
                        "manager_id": manager_id,
                        "manager_name": self._manager_names.get(manager_id),
                        "gameweek": t.get("event"),
                        "player_in_id": pin_uuid,
                        "player_out_id": pout_uuid,
                        "price_in": t.get("element_in_cost", 0) / 10.0,
                        "price_out": t.get("element_out_cost", 0) / 10.0,
                        "transfer_time": t.get("time"),
                    })

                self.fpl._rate_limit()
            except Exception as e:
                logger.warning(f"Failed to sync transfers for manager {manager_id}: {e}")
                continue

        if all_data:
            result = self.db.upsert_transfers(all_data)
            logger.info(f"Synced {len(all_data)} transfers")
            return result
        return {"count": 0}

    # -------------------------------------------------------------------------
    # Orchestration
    # -------------------------------------------------------------------------

    def run_bootstrap_sync(self, include_snapshots: bool = True) -> Dict[str, Any]:
        """
        Sync all bootstrap data (dimensions + reference tables).

        Order matters: positions/teams first (no deps), then players
        (needs team/position UUIDs), then fixtures (needs team UUIDs).
        """
        logger.info("=" * 60)
        logger.info("Starting bootstrap sync...")
        logger.info("=" * 60)

        results = {}

        # 1. Dimension tables (no FK dependencies)
        results["positions"] = self.sync_positions()
        results["teams"] = self.sync_teams()
        results["gameweeks"] = self.sync_gameweeks()
        results["leagues"] = self.sync_leagues()

        # 2. Players (depends on teams + positions for UUID FKs)
        results["players"] = self.sync_players()

        # 3. Fixtures (depends on teams for UUID FKs)
        results["fixtures"] = self.sync_fixtures()

        # 4. Snapshots (depends on players for UUID FKs)
        if include_snapshots:
            results["snapshots"] = self.sync_player_snapshots()

        logger.info("Bootstrap sync complete")
        return results

    def run_gameweek_sync(self, gameweek: int = None) -> Dict[str, Any]:
        """
        Sync all data for a specific gameweek.

        Assumes bootstrap has been run (UUID lookups available).
        Falls back to loading lookups from DB if needed.
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
            "squads": self.sync_squads(gameweek=gameweek),
            "manager_history": self.sync_manager_history(),
            "transfers": self.sync_manager_transfers(),
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
            "gameweek": self.run_gameweek_sync(gameweek),
        }

        logger.info("Full sync complete")
        return results
