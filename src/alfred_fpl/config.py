"""FPL domain settings.

Extends Pydantic BaseSettings for FPL-specific environment variables.
Uses dual .env pattern: fpl-specific vars first, shared vars as fallback.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class FPLSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("fpl/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase (FPL project)
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""

    # Dev defaults for testing
    fpl_default_manager_id: int = 0
    fpl_default_league_id: int = 0
    fpl_dev_user_id: str = ""


_settings = None


def get_settings() -> FPLSettings:
    global _settings
    if _settings is None:
        _settings = FPLSettings()
    return _settings


settings = get_settings()
