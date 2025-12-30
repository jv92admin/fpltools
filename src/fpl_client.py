"""
FPL API Client - Clean, minimal implementation.

This client wraps the Fantasy Premier League API with:
- Proper error handling and retries
- Rate limiting protection
- Type hints and structured responses
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

FPL_BASE_URL = "https://fantasy.premierleague.com/api"
OVERALL_LEAGUE_ID = 314  # The global "Overall" league

# Rate limiting
DEFAULT_TIMEOUT = 15
RATE_LIMIT_DELAY = 0.5  # seconds between requests


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FPLPlayer:
    """Player data from FPL API."""
    id: int
    web_name: str
    first_name: str
    second_name: str
    team_id: int
    team_name: str
    position_id: int
    position: str
    price: float  # In millions (e.g., 10.5)
    total_points: int
    selected_by_percent: float
    status: str  # 'a' = available, 'i' = injured, etc.
    news: str
    raw_data: Dict[str, Any]  # All original fields


@dataclass 
class FPLTeam:
    """Team data from FPL API."""
    id: int
    name: str
    short_name: str
    code: int


@dataclass
class FPLGameweek:
    """Gameweek data from FPL API."""
    id: int
    name: str
    deadline_time: str
    is_current: bool
    is_next: bool
    finished: bool
    average_score: Optional[int]
    highest_score: Optional[int]


@dataclass
class FPLFixture:
    """Fixture data from FPL API."""
    id: int
    gameweek: Optional[int]
    home_team_id: int
    away_team_id: int
    home_team_score: Optional[int]
    away_team_score: Optional[int]
    kickoff_time: Optional[str]
    finished: bool
    home_difficulty: int
    away_difficulty: int


# =============================================================================
# API Client
# =============================================================================

class FPLClient:
    """
    Client for the Fantasy Premier League API.
    
    Usage:
        client = FPLClient()
        bootstrap = client.get_bootstrap()
        players = client.get_players()
    """
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FPLTools/1.0"
        })
        
        # Caches
        self._bootstrap_cache: Optional[Dict[str, Any]] = None
        self._teams_lookup: Dict[int, FPLTeam] = {}
        self._positions_lookup: Dict[int, str] = {}
    
    # -------------------------------------------------------------------------
    # Core HTTP
    # -------------------------------------------------------------------------
    
    def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a GET request to the FPL API."""
        url = f"{FPL_BASE_URL}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {endpoint}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching {endpoint}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            raise
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        time.sleep(RATE_LIMIT_DELAY)
    
    # -------------------------------------------------------------------------
    # Bootstrap (Core Data)
    # -------------------------------------------------------------------------
    
    def get_bootstrap(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get bootstrap-static data (players, teams, gameweeks, etc.)
        
        This is the core endpoint - cache aggressively.
        """
        if self._bootstrap_cache and not force_refresh:
            return self._bootstrap_cache
        
        logger.info("Fetching bootstrap-static data...")
        data = self._get("bootstrap-static/")
        
        self._bootstrap_cache = data
        self._build_lookups(data)
        
        logger.info(
            f"Bootstrap loaded: {len(data.get('elements', []))} players, "
            f"{len(data.get('teams', []))} teams, "
            f"{len(data.get('events', []))} gameweeks"
        )
        
        return data
    
    def _build_lookups(self, bootstrap: Dict[str, Any]):
        """Build lookup dictionaries from bootstrap data."""
        # Teams lookup
        for team in bootstrap.get("teams", []):
            self._teams_lookup[team["id"]] = FPLTeam(
                id=team["id"],
                name=team["name"],
                short_name=team["short_name"],
                code=team["code"]
            )
        
        # Positions lookup
        for pos in bootstrap.get("element_types", []):
            self._positions_lookup[pos["id"]] = pos["singular_name_short"]
    
    # -------------------------------------------------------------------------
    # Players
    # -------------------------------------------------------------------------
    
    def get_players(self) -> List[FPLPlayer]:
        """Get all players with structured data."""
        bootstrap = self.get_bootstrap()
        players = []
        
        for p in bootstrap.get("elements", []):
            team = self._teams_lookup.get(p["team"])
            position = self._positions_lookup.get(p["element_type"], "UNK")
            
            players.append(FPLPlayer(
                id=p["id"],
                web_name=p["web_name"],
                first_name=p["first_name"],
                second_name=p["second_name"],
                team_id=p["team"],
                team_name=team.name if team else "Unknown",
                position_id=p["element_type"],
                position=position,
                price=p["now_cost"] / 10.0,
                total_points=p["total_points"],
                selected_by_percent=float(p["selected_by_percent"]),
                status=p.get("status", ""),
                news=p.get("news", ""),
                raw_data=p
            ))
        
        return players
    
    def get_player_detail(self, player_id: int) -> Dict[str, Any]:
        """Get detailed player data including history."""
        return self._get(f"element-summary/{player_id}/")
    
    # -------------------------------------------------------------------------
    # Teams
    # -------------------------------------------------------------------------
    
    def get_teams(self) -> List[FPLTeam]:
        """Get all Premier League teams."""
        self.get_bootstrap()  # Ensure lookups are built
        return list(self._teams_lookup.values())
    
    # -------------------------------------------------------------------------
    # Gameweeks
    # -------------------------------------------------------------------------
    
    def get_gameweeks(self) -> List[FPLGameweek]:
        """Get all gameweeks."""
        bootstrap = self.get_bootstrap()
        gameweeks = []
        
        for gw in bootstrap.get("events", []):
            gameweeks.append(FPLGameweek(
                id=gw["id"],
                name=gw["name"],
                deadline_time=gw["deadline_time"],
                is_current=gw["is_current"],
                is_next=gw["is_next"],
                finished=gw["finished"],
                average_score=gw.get("average_entry_score"),
                highest_score=gw.get("highest_score")
            ))
        
        return gameweeks
    
    def get_current_gameweek(self) -> Optional[FPLGameweek]:
        """Get the current gameweek."""
        gameweeks = self.get_gameweeks()
        for gw in gameweeks:
            if gw.is_current:
                return gw
        return None
    
    # -------------------------------------------------------------------------
    # Live Gameweek Data
    # -------------------------------------------------------------------------
    
    def get_live_gameweek(self, gameweek: int) -> Dict[str, Any]:
        """
        Get live stats for all players in a specific gameweek.
        
        Returns dict with 'elements' list containing player stats.
        """
        return self._get(f"event/{gameweek}/live/")
    
    def get_live_player_stats(self, gameweek: int) -> Dict[int, Dict[str, Any]]:
        """
        Get live stats indexed by player ID.
        
        Returns: {player_id: stats_dict}
        """
        data = self.get_live_gameweek(gameweek)
        return {
            el["id"]: el.get("stats", {})
            for el in data.get("elements", [])
        }
    
    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------
    
    def get_fixtures(self, gameweek: int = None) -> List[FPLFixture]:
        """Get fixtures, optionally filtered by gameweek."""
        params = {"event": gameweek} if gameweek else None
        data = self._get("fixtures/", params=params)
        
        fixtures = []
        for f in data:
            fixtures.append(FPLFixture(
                id=f["id"],
                gameweek=f.get("event"),
                home_team_id=f["team_h"],
                away_team_id=f["team_a"],
                home_team_score=f.get("team_h_score"),
                away_team_score=f.get("team_a_score"),
                kickoff_time=f.get("kickoff_time"),
                finished=f.get("finished", False),
                home_difficulty=f.get("team_h_difficulty", 0),
                away_difficulty=f.get("team_a_difficulty", 0)
            ))
        
        return fixtures
    
    # -------------------------------------------------------------------------
    # Managers
    # -------------------------------------------------------------------------
    
    def get_manager(self, manager_id: int) -> Dict[str, Any]:
        """Get manager profile."""
        return self._get(f"entry/{manager_id}/")
    
    def get_manager_history(self, manager_id: int) -> Dict[str, Any]:
        """Get manager's season history (all gameweeks + past seasons)."""
        return self._get(f"entry/{manager_id}/history/")
    
    def get_manager_picks(self, manager_id: int, gameweek: int) -> Dict[str, Any]:
        """Get manager's team picks for a specific gameweek."""
        return self._get(f"entry/{manager_id}/event/{gameweek}/picks/")
    
    def get_manager_transfers(self, manager_id: int) -> List[Dict[str, Any]]:
        """Get manager's transfer history this season."""
        return self._get(f"entry/{manager_id}/transfers/")
    
    # -------------------------------------------------------------------------
    # Leagues
    # -------------------------------------------------------------------------
    
    def get_league_standings(
        self, 
        league_id: int, 
        page: int = 1
    ) -> Dict[str, Any]:
        """Get classic league standings (paginated)."""
        return self._get(
            f"leagues-classic/{league_id}/standings/",
            params={"page_standings": page}
        )
    
    def get_league_managers(
        self, 
        league_id: int, 
        max_pages: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all managers in a league (handles pagination).
        
        Args:
            league_id: FPL league ID
            max_pages: Maximum pages to fetch (50 managers per page)
        """
        all_managers = []
        
        for page in range(1, max_pages + 1):
            data = self.get_league_standings(league_id, page)
            results = data.get("standings", {}).get("results", [])
            
            if not results:
                break
            
            all_managers.extend(results)
            
            # Check if there are more pages
            has_next = data.get("standings", {}).get("has_next", False)
            if not has_next:
                break
            
            self._rate_limit()
        
        return all_managers
    
    # -------------------------------------------------------------------------
    # Top Managers (Overall League)
    # -------------------------------------------------------------------------
    
    def get_top_managers(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Get top X managers from the overall league.
        
        Args:
            count: Number of top managers to fetch (max practical: ~10,000)
        """
        PAGE_SIZE = 50
        pages_needed = (count // PAGE_SIZE) + 1
        
        managers = []
        
        for page in range(1, pages_needed + 1):
            data = self.get_league_standings(OVERALL_LEAGUE_ID, page)
            results = data.get("standings", {}).get("results", [])
            
            managers.extend(results)
            
            if len(managers) >= count:
                break
            
            self._rate_limit()
        
        return managers[:count]

