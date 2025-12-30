"""
FPL API Client with Master ID Integration

SCOPE & PURPOSE:
================
This module provides a standardized API client wrapper for FPL data with Master ID resolution.
It is designed to complement (not replace) the existing FPL integration.

DIFFERENCES FROM EXISTING INTEGRATION:
=====================================
- src/fantrax_pipeline/integrations/fpl.py:
  * Direct database integration and storage
  * Async operations for full pipeline processing  
  * Saves data directly to SQLite database
  * Used by main pipeline orchestrator
  * Focus: Data ingestion and persistence

- src/fantrax_pipeline/api/fpl_client.py (THIS MODULE):
  * Standardized API wrapper with Master ID resolution
  * Synchronous operations for analysis and discovery
  * Returns structured data objects (FPLPlayerData, etc.)
  * Used by analysis modules and data exploration
  * Focus: Entity resolution and data standardization

WHEN TO USE WHICH:
==================
Use FPLIntegration (integrations/fpl.py) when:
- Running the main data pipeline
- Saving data to database
- Bulk data processing
- Scheduled data pulls

Use FPLAPIClient (api/fpl_client.py) when:
- Discovering unmapped players/teams
- Analysis modules need FPL data
- Interactive data exploration
- Need Master ID resolution
- Building reports or dashboards

MASTER ID INTEGRATION:
=====================
This client automatically resolves FPL entities to Master IDs and tracks
unmapped entities for later addition to the Master ID system.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import asyncio
import requests
import time
from datetime import datetime

from .base_client import BaseAPIClient, RequestConfig, APIError
from .response_models import APIResponse
from ..unified_player_matcher import UnifiedPlayerMatcher
from ..integrations.fpl import FPLIntegration, FPLConfig, load_fpl_config


logger = logging.getLogger(__name__)


@dataclass
class FPLPlayerData:
    """Standardized FPL player data with Master ID resolution."""
    fpl_id: int
    web_name: str
    first_name: str
    second_name: str
    full_name: str
    team_id: int
    team_name: str
    position: str
    price: float
    total_points: int
    selected_by_percent: float
    master_player_id: Optional[str] = None
    resolution_confidence: Optional[float] = None
    raw_fpl_data: Optional[Dict[str, Any]] = None


@dataclass
class FPLTeamData:
    """Standardized FPL team data with Master ID resolution."""
    fpl_id: int
    name: str
    short_name: str
    code: int
    master_team_id: Optional[str] = None
    resolution_confidence: Optional[float] = None


@dataclass
class FPLManagerData:
    """Standardized FPL manager data with Master ID resolution."""
    fpl_id: int
    player_first_name: str
    player_last_name: str
    player_region_name: str
    summary_overall_points: int
    summary_overall_rank: int
    master_manager_id: Optional[str] = None
    resolution_confidence: Optional[float] = None


class FPLAPIClient(BaseAPIClient):
    """
    FPL API client with Master ID integration.
    
    Wraps the existing FPLIntegration and adds Master ID resolution capabilities.
    """
    
    FPL_BASE_URL = "https://fantasy.premierleague.com/api"
    
    def __init__(self, unified_player_matcher: Optional[UnifiedPlayerMatcher] = None,
                 fpl_config: Optional[FPLConfig] = None):
        """
        Initialize FPL API client with unified player matching.
        
        Args:
            unified_player_matcher: Unified player matcher for cross-source matching
            fpl_config: FPL configuration, will load from env if not provided
        """
        config = RequestConfig(
            timeout=30,
            max_retries=3,
            backoff_factor=1.5,
            headers={
                'User-Agent': 'fantrax-pipeline/FPLClient'
            }
        )
        
        super().__init__(self.FPL_BASE_URL, config)
        
        self.unified_player_matcher = unified_player_matcher
        
        # Initialize the existing FPL integration
        if fpl_config is None:
            fpl_config = load_fpl_config()
        
        if fpl_config is None:
            raise ValueError("FPL configuration not found. Set FPL_LEAGUE_ID environment variable.")
        
        self.fpl_integration = FPLIntegration(fpl_config)
        self.bootstrap_data = None
        self.teams_cache = {}
        self.positions_cache = {}
        
        # Tracking for unmapped entities
        self.unmapped_players: List[Dict[str, Any]] = []
        self.unmapped_teams: List[Dict[str, Any]] = []
        self.unmapped_managers: List[Dict[str, Any]] = []
        
        # Seed unified player matcher with FPL players if provided
        if self.unified_player_matcher:
            self._seed_fpl_players()
    
    def _seed_fpl_players(self) -> None:
        """Seed the unified player matcher with FPL players."""
        try:
            logger.info("🌱 Seeding unified player matcher with FPL players...")
            
            # Get FPL bootstrap data
            bootstrap_response = self.get(endpoint="bootstrap-static")
            if not bootstrap_response.is_success():
                logger.warning("Failed to fetch FPL data for seeding")
                return
            
            players = bootstrap_response.data.get('elements', [])
            teams = bootstrap_response.data.get('teams', [])
            
            logger.info(f"FPL bootstrap data: {len(players)} total players, {len(teams)} teams")
            
            # Create team lookup
            team_lookup = {team['id']: team['name'] for team in teams}
            
            # Add each FPL player to unified matcher
            processed_count = 0
            for player_data in players:
                fpl_first = player_data.get('first_name', '')
                fpl_second = player_data.get('second_name', '')
                fpl_web = player_data.get('web_name', '')
                team_id = player_data.get('team', 0)
                team_name = team_lookup.get(team_id, '')
                
                # Construct full name (optimal source)
                full_name = f"{fpl_first} {fpl_second}".strip()
                canonical_name = full_name if full_name else fpl_web
                
                # Debug logging for first few players only
                if processed_count < 3:
                    logger.info(f"Sample FPL player {processed_count}: first='{fpl_first}', second='{fpl_second}', web='{fpl_web}', chosen='{canonical_name}'")
                
                # Add to unified matcher
                master_id = self.unified_player_matcher.add_or_update_player(
                    name=canonical_name,
                    fpl_id=str(player_data['id']),
                    fpl_first_name=fpl_first,
                    fpl_second_name=fpl_second,
                    fpl_web_name=fpl_web,
                    team=team_name,
                    source='fpl'
                )
                processed_count += 1
            
            stats = self.unified_player_matcher.get_stats()
            logger.info(f"✅ Seeded {processed_count} FPL players, unified matcher now has {stats['fpl_players']} FPL players total")
            
        except Exception as e:
            logger.error(f"Error seeding FPL players: {e}")
    
    def authenticate(self) -> bool:
        """
        FPL API doesn't require authentication for basic data.
        
        Returns:
            bool: Always True for FPL API
        """
        return True
    
    def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Get FPL API rate limit information.
        
        FPL doesn't provide explicit rate limit headers, so we estimate.
        
        Returns:
            Dict with estimated rate limit info
        """
        return {
            'estimated_limit': 100,  # Conservative estimate
            'estimated_remaining': 95,  # Assume we have most requests left
            'reset_time': int(time.time()) + 3600  # Reset every hour
        }
    
    async def get_bootstrap_data(self, force_refresh: bool = False) -> APIResponse:
        """
        Get FPL bootstrap data using existing integration.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            APIResponse with bootstrap data
        """
        if self.bootstrap_data and not force_refresh:
            logger.debug("Using cached bootstrap data")
            return APIResponse(
                data=self.bootstrap_data,
                metadata={'cached': True},
                success=True
            )
        
        logger.info("Fetching FPL bootstrap data via existing integration")
        
        try:
            # Use existing FPL integration
            bootstrap_dataframes = await self.fpl_integration.pull_bootstrap_static()
            
            # Convert DataFrames back to dict format for compatibility
            bootstrap_data = {}
            for key, df in bootstrap_dataframes.items():
                bootstrap_data[key] = df.to_dict('records')
            
            self.bootstrap_data = bootstrap_data
            self._cache_reference_data()
            
            logger.info("Successfully fetched and cached FPL bootstrap data")
            
            return APIResponse(
                data=bootstrap_data,
                metadata={'source': 'existing_integration', 'cached': False},
                success=True
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch FPL bootstrap data: {e}")
            return APIResponse(
                data={},
                metadata={'error': str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _cache_reference_data(self):
        """Cache teams and positions data for quick lookup."""
        if not self.bootstrap_data:
            return
        
        # Cache teams
        for team in self.bootstrap_data.get('teams', []):
            self.teams_cache[team['id']] = team
        
        # Cache positions
        for position in self.bootstrap_data.get('element_types', []):
            self.positions_cache[position['id']] = position
        
        logger.debug(f"Cached {len(self.teams_cache)} teams and {len(self.positions_cache)} positions")
    
    async def get_players_with_master_ids(self) -> List[FPLPlayerData]:
        """
        Get all FPL players with Master ID resolution.
        
        Returns:
            List of FPLPlayerData with resolved Master IDs
        """
        bootstrap_response = await self.get_bootstrap_data()
        if not bootstrap_response.is_success():
            raise APIError("Failed to fetch bootstrap data")
        
        players = bootstrap_response.data.get('elements', [])
        logger.info(f"Processing {len(players)} FPL players for Master ID resolution")
        
        resolved_players = []
        unmapped_count = 0
        
        for player_data in players:
            fpl_player = self._create_fpl_player_data(player_data)
            
            # Resolve Master ID using unified player matcher
            if self.unified_player_matcher:
                master_id = self.unified_player_matcher.find_player(
                    name=fpl_player.full_name,
                    fpl_id=str(fpl_player.fpl_id),
                    team=fpl_player.team_name
                )
                fpl_player.master_player_id = master_id
                fpl_player.resolution_confidence = 1.0 if master_id else 0.0
                
                if not master_id:
                    unmapped_count += 1
                    self.unmapped_players.append({
                        'fpl_id': fpl_player.fpl_id,
                        'web_name': fpl_player.web_name,
                        'full_name': fpl_player.full_name,
                        'team_name': fpl_player.team_name,
                        'position': fpl_player.position
                    })
            else:
                fpl_player.master_player_id = None
                fpl_player.resolution_confidence = 0.0
            
            resolved_players.append(fpl_player)
        
        logger.info(f"Resolved {len(players) - unmapped_count}/{len(players)} players to Master IDs")
        if unmapped_count > 0:
            logger.warning(f"Found {unmapped_count} unmapped players")
        
        return resolved_players
    

    
    async def get_teams_with_master_ids(self) -> List[FPLTeamData]:
        """
        Get all FPL teams with Master ID resolution.
        
        Returns:
            List of FPLTeamData with resolved Master IDs
        """
        bootstrap_response = await self.get_bootstrap_data()
        if not bootstrap_response.is_success():
            raise APIError("Failed to fetch bootstrap data")
        
        teams = bootstrap_response.data.get('teams', [])
        logger.info(f"Processing {len(teams)} FPL teams for Master ID resolution")
        
        resolved_teams = []
        unmapped_count = 0
        
        for team_data in teams:
            fpl_team = FPLTeamData(
                fpl_id=team_data['id'],
                name=team_data['name'],
                short_name=team_data['short_name'],
                code=team_data['code']
            )
            
            # Team resolution not needed for unified player matching
            fpl_team.master_team_id = None
            fpl_team.resolution_confidence = 1.0
            
            resolved_teams.append(fpl_team)
        
        logger.info(f"Resolved {len(teams) - unmapped_count}/{len(teams)} teams to Master IDs")
        if unmapped_count > 0:
            logger.warning(f"Found {unmapped_count} unmapped teams")
        
        return resolved_teams
    
    def get_league_data(self, league_id: int) -> APIResponse:
        """
        Get FPL league data.
        
        Args:
            league_id: FPL league ID
            
        Returns:
            APIResponse with league data
        """
        logger.info(f"Fetching FPL league data for league {league_id}")
        return self.get(f'/leagues-classic/{league_id}/standings/')
    
    def get_manager_data(self, manager_id: int) -> APIResponse:
        """
        Get FPL manager data.
        
        Args:
            manager_id: FPL manager ID
            
        Returns:
            APIResponse with manager data
        """
        logger.info(f"Fetching FPL manager data for manager {manager_id}")
        return self.get(f'/entry/{manager_id}/')
    
    def get_gameweek_data(self, gameweek: int) -> APIResponse:
        """
        Get FPL gameweek data.
        
        Args:
            gameweek: Gameweek number
            
        Returns:
            APIResponse with gameweek data
        """
        logger.info(f"Fetching FPL gameweek {gameweek} data")
        return self.get(f'/event/{gameweek}/live/')
    
    def _create_fpl_player_data(self, player_data: Dict[str, Any]) -> FPLPlayerData:
        """Create FPLPlayerData from raw API data."""
        team_id = player_data['team']
        team_data = self.teams_cache.get(team_id, {})
        
        position_id = player_data['element_type']
        position_data = self.positions_cache.get(position_id, {})
        
        return FPLPlayerData(
            fpl_id=player_data['id'],
            web_name=player_data['web_name'],
            first_name=player_data['first_name'],
            second_name=player_data['second_name'],
            full_name=f"{player_data['first_name']} {player_data['second_name']}".strip(),
            team_id=team_id,
            team_name=team_data.get('name', 'Unknown'),
            position=position_data.get('singular_name_short', 'UNK'),
            price=player_data['now_cost'] / 10.0,  # FPL prices are in tenths
            total_points=player_data['total_points'],
            selected_by_percent=float(player_data['selected_by_percent']),
            raw_fpl_data=player_data  # 🔥 STORE ALL 101 FIELDS!
        )
    
    def _resolve_player_master_id(self, fpl_player: FPLPlayerData) -> Tuple[Optional[str], Optional[float]]:
        """
        Resolve FPL player to Master ID using unified matcher.
        
        Args:
            fpl_player: FPL player data
            
        Returns:
            Tuple of (master_id, confidence_score)
        """
        # Use unified matcher if available
        if self.unified_player_matcher:
            master_id = self.unified_player_matcher.find_player(
                name=fpl_player.full_name,
                fpl_id=str(fpl_player.fpl_id),
                team=fpl_player.team_name
            )
            if master_id:
                return master_id, 1.0
            else:
                # Add new player if not found (shouldn't happen after seeding)
                master_id = self.unified_player_matcher.add_or_update_player(
                    name=fpl_player.full_name,
                    fpl_id=str(fpl_player.fpl_id),
                    fpl_first_name=fpl_player.first_name,
                    fpl_second_name=fpl_player.second_name,
                    fpl_web_name=fpl_player.web_name,
                    team=fpl_player.team_name,
                    source='fpl'
                )
                return master_id, 1.0
        
        # No unified matcher available - return None
        return None, None
    
    def _resolve_team_master_id(self, fpl_team: FPLTeamData) -> Tuple[Optional[str], Optional[float]]:
        """
        Resolve FPL team to Master ID.
        
        Args:
            fpl_team: FPL team data
            
        Returns:
            Tuple of (master_id, confidence_score)
        """
        # No longer using legacy master_id_resolver
        return None, None
        
        # Try different name variations
        name_variations = [
            fpl_team.name,
            fpl_team.short_name
        ]
        
        for name in name_variations:
            if not name:
                continue
                
            # Handle different resolver types
            if hasattr(self.master_id_resolver, 'resolve_team_id'):
                # Standard MasterIDResolver
                master_id = self.master_id_resolver.resolve_team_id(name)
            elif hasattr(self.master_id_resolver, 'resolve_team'):
                # FantraxMasterIDResolver
                team_data = self.master_id_resolver.resolve_team(name)
                master_id = team_data.get('master_team_id')
            else:
                master_id = None
            
            if master_id:
                confidence = self._calculate_name_confidence(name, master_id)
                return master_id, confidence
        
        return None, None
    
    def _map_fpl_position(self, fpl_position: str) -> str:
        """Map FPL position to Master ID position format."""
        position_map = {
            'GKP': 'G',
            'DEF': 'D', 
            'MID': 'M',
            'FWD': 'F'
        }
        return position_map.get(fpl_position, 'M')  # Default to midfielder
    
    def _calculate_name_confidence(self, query_name: str, master_id: str) -> float:
        """
        Calculate confidence score for name resolution.
        
        Args:
            query_name: Original query name
            master_id: Resolved master ID
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # No longer using legacy master_id_resolver
        return 1.0  # Full confidence in unified matching
        
        # Get the canonical name for the master ID
        if hasattr(self.master_id_resolver, 'get_player_record'):
            # Standard MasterIDResolver
            record = self.master_id_resolver.get_player_record(master_id)
            if not record:
                return 0.5
            canonical_name = record.canonical_name.lower()
        elif hasattr(self.master_id_resolver, 'player_mapping'):
            # FantraxMasterIDResolver - find by master_id
            canonical_name = None
            for player_data in self.master_id_resolver.player_mapping.values():
                if player_data.get('master_player_id') == master_id:
                    canonical_name = player_data.get('canonical_name', '').lower()
                    break
            if not canonical_name:
                return 0.5
        else:
            return 0.5
        query_lower = query_name.lower()
        
        # Handle different resolver types for similarity calculation
        if hasattr(self.master_id_resolver, '_calculate_similarity'):
            return self.master_id_resolver._calculate_similarity(query_lower, canonical_name)
        else:
            # Simple similarity calculation for FantraxMasterIDResolver
            if query_lower == canonical_name:
                return 1.0
            elif query_lower in canonical_name or canonical_name in query_lower:
                return 0.8
            else:
                return 0.3
    
    def _create_fpl_player_data(self, player_data: Dict[str, Any]) -> FPLPlayerData:
        """
        Create FPLPlayerData object from raw API data.
        
        Args:
            player_data: Raw player data from FPL API
            
        Returns:
            FPLPlayerData object with raw data preserved
        """
        # Get team name from cache
        team_name = "Unknown"
        if player_data.get('team') and player_data['team'] in self.teams_cache:
            team_name = self.teams_cache[player_data['team']]['name']
        
        # Get position name from cache
        position = "Unknown"
        if player_data.get('element_type') and player_data['element_type'] in self.positions_cache:
            position = self.positions_cache[player_data['element_type']]['singular_name_short']
        
        return FPLPlayerData(
            fpl_id=player_data.get('id', 0),
            web_name=player_data.get('web_name', ''),
            first_name=player_data.get('first_name', ''),
            second_name=player_data.get('second_name', ''),
            full_name=f"{player_data.get('first_name', '')} {player_data.get('second_name', '')}".strip(),
            team_id=player_data.get('team', 0),
            team_name=team_name,
            position=position,
            price=player_data.get('now_cost', 0) / 10.0,  # Convert from tenths
            total_points=player_data.get('total_points', 0),
            selected_by_percent=float(player_data.get('selected_by_percent', 0.0)),
            raw_fpl_data=player_data  # Store complete raw data
        )
    
    def get_unmapped_entities(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all unmapped entities discovered during resolution.
        
        Returns:
            Dict with lists of unmapped players, teams, and managers
        """
        return {
            'players': self.unmapped_players.copy(),
            'teams': self.unmapped_teams.copy(),
            'managers': self.unmapped_managers.copy()
        }
    
    def clear_unmapped_entities(self):
        """Clear the unmapped entities lists."""
        self.unmapped_players.clear()
        self.unmapped_teams.clear()
        self.unmapped_managers.clear()
    
    def get_mapping_report(self) -> Dict[str, Any]:
        """
        Generate a mapping report showing resolution statistics.
        
        Returns:
            Dict with mapping statistics and unmapped entities
        """
        unmapped = self.get_unmapped_entities()
        
        return {
            'unmapped_counts': {
                'players': len(unmapped['players']),
                'teams': len(unmapped['teams']),
                'managers': len(unmapped['managers'])
            },
            'unmapped_entities': unmapped,
            'resolver_available': self.master_id_resolver is not None,
            'bootstrap_cached': self.bootstrap_data is not None
        }
    
    def get_manager_team_picks(self, entry_id: int, gameweek: int = None) -> Dict[str, Any]:
        """Get a manager's team picks for a specific gameweek."""
        try:
            if gameweek is None:
                # Get current gameweek
                bootstrap = self._get_bootstrap_data()
                current_events = [e for e in bootstrap.get('events', []) if e.get('is_current')]
                gameweek = current_events[0]['id'] if current_events else 1
            
            # FPL API endpoint for manager team
            url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gameweek}/picks/"
            
            # Add timeout and retry logic
            import time
            for attempt in range(2):  # Try twice
                try:
                    response = requests.get(url, timeout=10)  # 10 second timeout
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout getting team for entry {entry_id}, attempt {attempt + 1}")
                    if attempt == 0:
                        time.sleep(2)  # Wait before retry
                        continue
                    raise
                except requests.exceptions.RequestException as e:
                    if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
                        # Gameweek doesn't exist yet, try gameweek 1
                        if gameweek != 1:
                            logger.info(f"GW {gameweek} not available for entry {entry_id}, trying GW 1")
                            try:
                                url_gw1 = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/1/picks/"
                                response_gw1 = requests.get(url_gw1, timeout=10)
                                if response_gw1.status_code == 200:
                                    return response_gw1.json()
                            except:
                                pass
                    raise e
            
        except Exception as e:
            logger.error(f"Error getting manager team for entry {entry_id}, GW {gameweek}: {e}")
            return {'picks': []}

    def get_player_gameweek_history(self, element_id: int, gameweek: int = None) -> Dict[str, Any]:
        """
        Get detailed gameweek history for a specific player.
        
        Args:
            element_id: FPL player element ID
            gameweek: Specific gameweek (None for all history)
            
        Returns:
            Dict with player GW history data
        """
        try:
            url = f"https://fantasy.premierleague.com/api/element-summary/{element_id}/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if gameweek is None:
                # Return all history
                return data.get('history', [])
            else:
                # Return specific gameweek
                history = data.get('history', [])
                for gw_data in history:
                    if gw_data.get('round') == gameweek:
                        return gw_data
                return {}
                
        except Exception as e:
            logger.error(f"Error getting player {element_id} GW history: {e}")
            return {}

    def get_live_gw_player_stats(self, gameweek: int) -> Dict[int, Dict[str, Any]]:
        """
        Get gameweek stats for ALL players in a single call.

        Uses /event/{gw}/live which returns stats for every element.

        Returns:
            Dict[element_id, stats_dict]
        """
        try:
            url = f"https://fantasy.premierleague.com/api/event/{gameweek}/live/"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            elements = data.get('elements', [])
            result: Dict[int, Dict[str, Any]] = {}
            for el in elements:
                el_id = el.get('id')
                stats = el.get('stats', {})
                if el_id is not None and isinstance(stats, dict):
                    # Flatten to match map_fpl_player_gw_data expected fields
                    result[el_id] = stats
            logger.info(f"Fetched live GW stats for {len(result)} players from /event/{gameweek}/live")
            return result
        except Exception as e:
            logger.error(f"Error getting live GW stats for GW {gameweek}: {e}")
            return {}

    def get_next_fixtures_by_team(self) -> Dict[int, Dict[str, Any]]:
        """
        Compute the next real-life fixture for each FPL team using /fixtures/.

        Returns:
            Dict[team_id, {event, kickoff_time, opponent_team_id, opponent_team_name, is_home, difficulty}]
        """
        try:
            url = f"{self.FPL_BASE_URL}/fixtures/"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            fixtures = response.json() if isinstance(response.json(), list) else []

            # Ensure bootstrap (teams cache) is available
            if not self.teams_cache:
                # Populate by fetching bootstrap quickly (sync)
                bootstrap = self._get_bootstrap_data()
                self.bootstrap_data = bootstrap
                self._cache_reference_data()

            team_name_lookup = {tid: t['name'] for tid, t in self.teams_cache.items()}

            # Build next fixture per team
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            next_by_team: Dict[int, Dict[str, Any]] = {}

            # Consider only fixtures with kickoff_time in future
            for fx in fixtures:
                kickoff = fx.get('kickoff_time')
                if not kickoff:
                    continue
                try:
                    kickoff_dt = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
                except Exception:
                    continue
                if kickoff_dt < now:
                    continue
                event = fx.get('event')
                team_h = fx.get('team_h')
                team_a = fx.get('team_a')
                if team_h is None or team_a is None:
                    continue

                # Home team perspective
                cand_h = {
                    'event': event,
                    'kickoff_time': kickoff,
                    'opponent_team_id': team_a,
                    'opponent_team_name': team_name_lookup.get(team_a, 'Unknown'),
                    'is_home': True,
                    'difficulty': fx.get('team_h_difficulty')
                }
                prev_h = next_by_team.get(team_h)
                if prev_h is None or kickoff_dt < datetime.fromisoformat(prev_h['kickoff_time'].replace('Z', '+00:00')):
                    next_by_team[team_h] = cand_h

                # Away team perspective
                cand_a = {
                    'event': event,
                    'kickoff_time': kickoff,
                    'opponent_team_id': team_h,
                    'opponent_team_name': team_name_lookup.get(team_h, 'Unknown'),
                    'is_home': False,
                    'difficulty': fx.get('team_a_difficulty')
                }
                prev_a = next_by_team.get(team_a)
                if prev_a is None or kickoff_dt < datetime.fromisoformat(prev_a['kickoff_time'].replace('Z', '+00:00')):
                    next_by_team[team_a] = cand_a

            logger.info(f"Computed next fixtures for {len(next_by_team)} teams")
            return next_by_team
        except Exception as e:
            logger.error(f"Error computing next fixtures: {e}")
            return {}

    def get_all_players_gameweek_data(self, gameweek: int, limit: int = None) -> Dict[int, Dict[str, Any]]:
        """
        Get gameweek data for all players (expensive call - use sparingly).
        
        Args:
            gameweek: Gameweek number
            limit: Limit number of players to process (for testing)
            
        Returns:
            Dict mapping element_id to GW data
        """
        bootstrap_response = self.get_bootstrap_data()
        if not bootstrap_response.is_success():
            return {}
        
        players = bootstrap_response.data.get('elements', [])
        if limit:
            players = players[:limit]  # Limit for testing
        
        player_gw_data = {}
        
        logger.info(f"Fetching GW {gameweek} data for {len(players)} players...")
        
        # Note: This makes many API calls - consider caching/rate limiting
        for i, player in enumerate(players):
            element_id = player['id']
            
            # Add rate limiting
            if i > 0 and i % 10 == 0:
                import time
                time.sleep(1)  # 1 second delay every 10 requests
            
            gw_data = self.get_player_gameweek_history(element_id, gameweek)
            if gw_data:
                player_gw_data[element_id] = gw_data
            
            if i % 50 == 0:
                logger.info(f"Processed {i}/{len(players)} players...")
        
        logger.info(f"Completed GW {gameweek} data collection for {len(player_gw_data)} players")
        return player_gw_data

    def get_manager_gameweek_history(self, entry_id: int) -> List[Dict[str, Any]]:
        """
        Get complete gameweek history for a manager.
        
        Args:
            entry_id: FPL manager entry ID
            
        Returns:
            List of GW history entries
        """
        try:
            url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return data.get('current', [])
            
        except Exception as e:
            logger.error(f"Error getting manager {entry_id} history: {e}")
            return []

    def get_manager_gameweek_data(self, entry_id: int, gameweek: int = None) -> Dict[str, Any]:
        """
        Get comprehensive manager data for a specific gameweek.
        
        Args:
            entry_id: FPL manager entry ID
            gameweek: Specific gameweek (None for current)
            
        Returns:
            Dict with manager GW data including team picks and history
        """
        try:
            # Get team picks for the gameweek
            team_data = self.get_manager_team_picks(entry_id, gameweek)
            
            # Get manager history
            history_data = self.get_manager_gameweek_history(entry_id)
            
            # Find specific gameweek in history
            gw_history = None
            if gameweek and history_data:
                for entry in history_data:
                    if entry.get('event') == gameweek:
                        gw_history = entry
                        break
            
            return {
                'entry_id': entry_id,
                'gameweek': gameweek,
                'team_picks': team_data,
                'gw_history': gw_history,
                'all_history': history_data
            }
            
        except Exception as e:
            logger.error(f"Error getting manager {entry_id} GW {gameweek} data: {e}")
            return {}

    def get_league_managers_gameweek_data(self, league_id: int, gameweek: int = None) -> Dict[int, Dict[str, Any]]:
        """
        Get gameweek data for all managers in a league.
        
        Args:
            league_id: FPL league ID
            gameweek: Specific gameweek (None for current)
            
        Returns:
            Dict mapping entry_id to manager GW data
        """
        try:
            # Get league standings to find all managers
            league_data = self.get_league_standings(league_id)
            if not league_data or 'standings' not in league_data:
                return {}
            
            managers = league_data['standings'].get('results', [])
            manager_data = {}
            
            logger.info(f"Fetching GW {gameweek} data for {len(managers)} managers...")
            
            for i, manager in enumerate(managers):
                entry_id = manager['entry']
                
                # Add rate limiting
                if i > 0 and i % 5 == 0:
                    import time
                    time.sleep(2)  # 2 second delay every 5 requests
                
                gw_data = self.get_manager_gameweek_data(entry_id, gameweek)
                if gw_data:
                    manager_data[entry_id] = gw_data
                
                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(managers)} managers...")
            
            logger.info(f"Completed GW {gameweek} data collection for {len(manager_data)} managers")
            return manager_data
            
        except Exception as e:
            logger.error(f"Error getting league {league_id} managers GW {gameweek} data: {e}")
            return {}

    # === PHASE 3: COMPREHENSIVE FPL DATA COLLECTION METHODS ===
    
    def get_comprehensive_fpl_gameweek_data(self, gameweek: int, league_id: int = None) -> Dict[str, Any]:
        """
        Get comprehensive FPL data for a specific gameweek.
        
        This method collects all FPL data sources for a gameweek:
        - Bootstrap data (players, teams, positions)
        - League standings
        - Manager team picks
        - Player gameweek history
        - Manager gameweek history
        
        Args:
            gameweek: Gameweek number
            league_id: FPL league ID (uses config if not provided)
            
        Returns:
            Dict with all FPL data for the gameweek
        """
        if league_id is None:
            league_id = int(self.fpl_integration.config.league_id)
        
        logger.info(f"Collecting comprehensive FPL data for GW {gameweek}")
        
        comprehensive_data = {
            'gameweek': gameweek,
            'timestamp': datetime.now().isoformat(),
            'bootstrap_data': None,
            'league_standings': None,
            'manager_teams': {},
            'player_gw_history': {},
            'manager_gw_history': {},
            'league_id': league_id
        }
        
        try:
            # 1. Get bootstrap data (players, teams, positions)
            import asyncio
            bootstrap_response = asyncio.run(self.get_bootstrap_data(force_refresh=True))
            if bootstrap_response.is_success():
                comprehensive_data['bootstrap_data'] = bootstrap_response.data
                logger.info(f"✅ Bootstrap data collected: {len(bootstrap_response.data.get('elements', []))} players")
            else:
                logger.error(f"❌ Failed to get bootstrap data: {bootstrap_response.error_message}")
            
            # 2. Get league standings
            league_response = self.get_league_data(league_id)
            if league_response.is_success():
                comprehensive_data['league_standings'] = league_response.data
                logger.info(f"✅ League standings collected")
            else:
                logger.error(f"❌ Failed to get league standings")
            
            # 3. Get manager team picks for this gameweek
            if comprehensive_data['league_standings']:
                standings_data = comprehensive_data['league_standings']
                if 'standings' in standings_data and 'results' in standings_data['standings']:
                    managers = standings_data['standings']['results']
                    
                    for i, manager in enumerate(managers):
                        entry_id = manager['entry']
                        
                        # Rate limiting
                        if i > 0 and i % 3 == 0:
                            import time
                            time.sleep(1)  # 1 second delay every 3 requests
                        
                        try:
                            team_data = self.get_manager_team_picks(entry_id, gameweek)
                            if team_data and 'picks' in team_data:
                                comprehensive_data['manager_teams'][entry_id] = {
                                    'team_data': team_data,
                                    'manager_info': manager
                                }
                        except Exception as e:
                            logger.warning(f"Failed to get team for entry {entry_id}: {e}")
                            continue
                    
                    logger.info(f"✅ Manager teams collected: {len(comprehensive_data['manager_teams'])} teams")
            
            # 4. Get player gameweek history (sample of top players for efficiency)
            if comprehensive_data['bootstrap_data']:
                players = comprehensive_data['bootstrap_data'].get('elements', [])
                # Sample top 50 players by total points for efficiency
                top_players = sorted(players, key=lambda x: x.get('total_points', 0), reverse=True)[:50]
                
                for i, player in enumerate(top_players):
                    element_id = player['id']
                    
                    # Rate limiting
                    if i > 0 and i % 10 == 0:
                        import time
                        time.sleep(1)  # 1 second delay every 10 requests
                    
                    try:
                        gw_history = self.get_player_gameweek_history(element_id, gameweek)
                        if gw_history:
                            comprehensive_data['player_gw_history'][element_id] = gw_history
                    except Exception as e:
                        logger.warning(f"Failed to get GW history for player {element_id}: {e}")
                        continue
                
                logger.info(f"✅ Player GW history collected: {len(comprehensive_data['player_gw_history'])} players")
            
            # 5. Get manager gameweek history
            if comprehensive_data['league_standings']:
                standings_data = comprehensive_data['league_standings']
                if 'standings' in standings_data and 'results' in standings_data['standings']:
                    managers = standings_data['standings']['results']
                    
                    for i, manager in enumerate(managers):
                        entry_id = manager['entry']
                        
                        # Rate limiting
                        if i > 0 and i % 3 == 0:
                            import time
                            time.sleep(1)  # 1 second delay every 3 requests
                        
                        try:
                            history_data = self.get_manager_gameweek_history(entry_id)
                            if history_data:
                                # Find specific gameweek in history
                                gw_history = None
                                for entry in history_data:
                                    if entry.get('event') == gameweek:
                                        gw_history = entry
                                        break
                                
                                comprehensive_data['manager_gw_history'][entry_id] = {
                                    'gw_history': gw_history,
                                    'all_history': history_data,
                                    'manager_info': manager
                                }
                        except Exception as e:
                            logger.warning(f"Failed to get history for entry {entry_id}: {e}")
                            continue
                    
                    logger.info(f"✅ Manager GW history collected: {len(comprehensive_data['manager_gw_history'])} managers")
            
            logger.info(f"🎉 Comprehensive FPL data collection completed for GW {gameweek}")
            
        except Exception as e:
            logger.error(f"❌ Comprehensive FPL data collection failed for GW {gameweek}: {e}")
        
        return comprehensive_data

    def get_fpl_data_for_comprehensive_pipeline(self, gameweek: int, league_id: int = None) -> Dict[str, Any]:
        """
        Get FPL data formatted for integration with the comprehensive pipeline.
        
        This method returns data in a format compatible with the existing
        generate_full_comprehensive_files.py pipeline.
        
        Args:
            gameweek: Gameweek number
            league_id: FPL league ID (uses config if not provided)
            
        Returns:
            Dict with FPL data formatted for pipeline integration
        """
        if league_id is None:
            league_id = int(self.fpl_integration.config.league_id)
        
        logger.info(f"Getting FPL data for comprehensive pipeline - GW {gameweek}")
        
        pipeline_data = {
            'gameweek': gameweek,
            'fpl_players': [],
            'fpl_teams': [],
            'fpl_managers': [],
            'fpl_league_standings': None,
            'fpl_manager_teams': {},
            'fpl_player_gw_data': {},
            'fpl_manager_gw_data': {},
            'success': False,
            'error': None
        }
        
        try:
            # 1. Get players with Master ID resolution
            import asyncio
            fpl_players = asyncio.run(self.get_players_with_master_ids())
            pipeline_data['fpl_players'] = fpl_players
            logger.info(f"✅ FPL players with Master IDs: {len(fpl_players)}")
            
            # 2. Get teams with Master ID resolution
            fpl_teams = asyncio.run(self.get_teams_with_master_ids())
            pipeline_data['fpl_teams'] = fpl_teams
            logger.info(f"✅ FPL teams with Master IDs: {len(fpl_teams)}")
            
            # 3. Get league standings
            league_response = self.get_league_data(league_id)
            if league_response.is_success():
                pipeline_data['fpl_league_standings'] = league_response.data
                
                # 4. Get manager team picks for this gameweek
                standings_data = league_response.data
                if 'standings' in standings_data and 'results' in standings_data['standings']:
                    managers = standings_data['standings']['results']
                    
                    for i, manager in enumerate(managers):
                        entry_id = manager['entry']
                        
                        # Rate limiting
                        if i > 0 and i % 3 == 0:
                            import time
                            time.sleep(1)
                        
                        try:
                            team_data = self.get_manager_team_picks(entry_id, gameweek)
                            if team_data and 'picks' in team_data:
                                pipeline_data['fpl_manager_teams'][entry_id] = team_data
                        except Exception as e:
                            logger.warning(f"Failed to get team for entry {entry_id}: {e}")
                            continue
                    
                    logger.info(f"✅ FPL manager teams: {len(pipeline_data['fpl_manager_teams'])} teams")
            
            # 5. Get player gameweek data in ONE bulk call
            pipeline_data['fpl_player_gw_data'] = self.get_live_gw_player_stats(gameweek)
            logger.info(f"✅ FPL player GW data: {len(pipeline_data['fpl_player_gw_data'])} players (bulk)")

            # 5b. Compute next fixtures per team (for player mapping)
            pipeline_data['fpl_next_fixtures'] = self.get_next_fixtures_by_team()
            
            # 6. Get manager gameweek data
            if pipeline_data['fpl_league_standings']:
                standings_data = pipeline_data['fpl_league_standings']
                if 'standings' in standings_data and 'results' in standings_data['standings']:
                    managers = standings_data['standings']['results']
                    
                    for i, manager in enumerate(managers):
                        entry_id = manager['entry']
                        
                        # Rate limiting
                        if i > 0 and i % 3 == 0:
                            import time
                            time.sleep(1)
                        
                        try:
                            gw_data = self.get_manager_gameweek_data(entry_id, gameweek)
                            if gw_data:
                                pipeline_data['fpl_manager_gw_data'][entry_id] = gw_data
                        except Exception as e:
                            logger.warning(f"Failed to get GW data for manager {entry_id}: {e}")
                            continue
                    
                    logger.info(f"✅ FPL manager GW data: {len(pipeline_data['fpl_manager_gw_data'])} managers")
            
            pipeline_data['success'] = True
            logger.info(f"🎉 FPL data collection for pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"❌ FPL data collection for pipeline failed: {e}")
            pipeline_data['error'] = str(e)
        
        return pipeline_data

    def get_manager_info(self, entry_id: int) -> Dict[str, Any]:
        """Get basic manager information."""
        try:
            url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
            response = requests.get(url)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Error getting manager info for entry {entry_id}: {e}")
            return {}

    def get_league_standings(self, league_id: int) -> Dict[str, Any]:
        """Get league standings with all manager entries."""
        try:
            url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
            response = requests.get(url, timeout=15)  # 15 second timeout
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Error getting league standings for {league_id}: {e}")
            return {'standings': {'results': []}}

    def _get_bootstrap_data(self) -> Dict[str, Any]:
        """Get FPL bootstrap data (players, teams, gameweeks)."""
        if self.bootstrap_data:
            return self.bootstrap_data
            
        try:
            url = "https://fantasy.premierleague.com/api/bootstrap-static/"
            response = requests.get(url)
            response.raise_for_status()
            
            self.bootstrap_data = response.json()
            return self.bootstrap_data
        except Exception as e:
            logger.error(f"Error getting bootstrap data: {e}")
            return {'events': [], 'elements': [], 'teams': []}