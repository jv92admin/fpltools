"""
Configuration management for FPL Tools.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional, List
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class SupabaseConfig:
    """Supabase connection configuration."""
    url: str
    key: str
    
    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError(
                "Missing Supabase credentials. "
                "Set SUPABASE_URL and SUPABASE_KEY in your .env file."
            )
        
        return cls(url=url, key=key)


@dataclass
class FPLConfig:
    """
    FPL-specific configuration.
    
    Note: These are development defaults. In production, user-specific
    values (league_id, manager_id, rival_ids) would come from the database.
    """
    default_league_id: Optional[int] = None
    default_manager_id: Optional[int] = None
    default_rival_ids: List[int] = None
    
    def __post_init__(self):
        if self.default_rival_ids is None:
            self.default_rival_ids = []
    
    @classmethod
    def from_env(cls) -> "FPLConfig":
        league_id = os.getenv("FPL_DEFAULT_LEAGUE_ID")
        manager_id = os.getenv("FPL_DEFAULT_MANAGER_ID")
        rival_ids_str = os.getenv("FPL_DEFAULT_RIVAL_IDS", "")
        
        rival_ids = []
        if rival_ids_str:
            rival_ids = [int(x.strip()) for x in rival_ids_str.split(",") if x.strip()]
        
        return cls(
            default_league_id=int(league_id) if league_id else None,
            default_manager_id=int(manager_id) if manager_id else None,
            default_rival_ids=rival_ids
        )
    
    # Convenience properties for backward compatibility
    @property
    def league_id(self) -> Optional[int]:
        return self.default_league_id
    
    @property
    def manager_id(self) -> Optional[int]:
        return self.default_manager_id
    
    @property
    def rival_ids(self) -> List[int]:
        return self.default_rival_ids


@dataclass
class Config:
    """Main application configuration."""
    supabase: SupabaseConfig
    fpl: FPLConfig
    
    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment."""
        return cls(
            supabase=SupabaseConfig.from_env(),
            fpl=FPLConfig.from_env()
        )

