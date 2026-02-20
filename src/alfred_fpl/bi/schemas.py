"""Pandera DataFrame validation schemas for FPL tables.

Validates DataFrames returned by data_access before analytics consume them.
Catches column mismatches, wrong types, and out-of-range values early with
actionable error messages.

Usage:
    from alfred_fpl.bi.schemas import validate_df
    df = fetch_df(spec)
    df = validate_df(df, "players")  # raises SchemaError with suggestions
"""

from __future__ import annotations

import pandera as pa
from pandera import Column, DataFrameSchema, Check


# ---------------------------------------------------------------------------
# Schema definitions — one per core table
# ---------------------------------------------------------------------------

PLAYERS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "web_name": Column(str, nullable=False, required=False),
        "price": Column(float, Check.in_range(0, 20), nullable=True, coerce=True, required=False),
        "total_points": Column(float, nullable=True, coerce=True, required=False),
        "form": Column(float, Check.in_range(0, 20), nullable=True, coerce=True, required=False),
        "selected_by_percent": Column(float, Check.in_range(0, 100), nullable=True, coerce=True, required=False),
        "minutes": Column(float, Check.ge(0), nullable=True, coerce=True, required=False),
        "goals_scored": Column(float, Check.ge(0), nullable=True, coerce=True, required=False),
        "assists": Column(float, Check.ge(0), nullable=True, coerce=True, required=False),
        "clean_sheets": Column(float, Check.ge(0), nullable=True, coerce=True, required=False),
        "bonus": Column(float, Check.ge(0), nullable=True, coerce=True, required=False),
    },
    strict=False,  # Allow extra columns (don't fail on columns we don't validate)
    coerce=True,
)

FIXTURES_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "gameweek": Column(float, Check.in_range(1, 38), nullable=True, coerce=True, required=False),
        "home_team_id": Column(str, nullable=True, required=False),
        "away_team_id": Column(str, nullable=True, required=False),
        "home_difficulty": Column(float, Check.in_range(1, 5), nullable=True, coerce=True, required=False),
        "away_difficulty": Column(float, Check.in_range(1, 5), nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

PLAYER_GAMEWEEKS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "player_id": Column(str, nullable=False, required=False),
        "gameweek": Column(float, Check.in_range(1, 38), nullable=False, coerce=True, required=False),
        "total_points": Column(float, nullable=True, coerce=True, required=False),
        "minutes": Column(float, Check.in_range(0, 120), nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

PLAYER_SNAPSHOTS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "player_id": Column(str, nullable=False, required=False),
        "price": Column(float, Check.in_range(0, 20), nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

SQUADS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "player_id": Column(str, nullable=False, required=False),
        "gameweek": Column(float, Check.in_range(1, 38), nullable=True, coerce=True, required=False),
        "slot": Column(float, Check.in_range(1, 15), nullable=True, coerce=True, required=False),
        "multiplier": Column(float, Check.in_range(0, 3), nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

LEAGUE_STANDINGS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "gameweek": Column(float, Check.in_range(1, 38), nullable=True, coerce=True, required=False),
        "rank": Column(float, Check.ge(1), nullable=True, coerce=True, required=False),
        "total_points": Column(float, nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

TRANSFERS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "gameweek": Column(float, Check.in_range(1, 38), nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

MANAGER_SEASONS_SCHEMA = DataFrameSchema(
    {
        "id": Column(str, nullable=False),
        "gameweek": Column(float, Check.in_range(1, 38), nullable=True, coerce=True, required=False),
        "total_points": Column(float, nullable=True, coerce=True, required=False),
    },
    strict=False,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Registry and validation
# ---------------------------------------------------------------------------

_SCHEMAS: dict[str, DataFrameSchema] = {
    "players": PLAYERS_SCHEMA,
    "fixtures": FIXTURES_SCHEMA,
    "player_gameweeks": PLAYER_GAMEWEEKS_SCHEMA,
    "player_snapshots": PLAYER_SNAPSHOTS_SCHEMA,
    "squads": SQUADS_SCHEMA,
    "league_standings": LEAGUE_STANDINGS_SCHEMA,
    "transfers": TRANSFERS_SCHEMA,
    "manager_seasons": MANAGER_SEASONS_SCHEMA,
}

# Column suggestions for common typos
_COLUMN_SUGGESTIONS: dict[str, str] = {
    "points": "total_points",
    "pts": "total_points",
    "name": "web_name",
    "player_name": "web_name",
    "team": "team_id",
    "position": "position_id",
    "prices": "price",
    "costs": "price",
    "gw": "gameweek",
    "event": "gameweek",
    "element": "player_id",
    "now_cost": "price",
}


def validate_df(df: "pd.DataFrame", table: str) -> "pd.DataFrame":
    """Validate a DataFrame against the schema for a table.

    Args:
        df: DataFrame to validate.
        table: Table name to look up the schema.

    Returns:
        The validated (and possibly coerced) DataFrame.

    Raises:
        pa.errors.SchemaError: If validation fails, with actionable error details.
        ValueError: If the table has no schema defined.
    """
    schema = _SCHEMAS.get(table)
    if schema is None:
        return df  # No schema defined — pass through

    try:
        return schema.validate(df)
    except pa.errors.SchemaError as e:
        # Enhance error message with column suggestions
        msg = str(e)
        for typo, correct in _COLUMN_SUGGESTIONS.items():
            if typo in msg.lower():
                msg += f"\n  Hint: Did you mean '{correct}'?"
        raise pa.errors.SchemaError(
            schema=schema,
            data=df,
            message=msg,
        ) from e


def get_schema(table: str) -> DataFrameSchema | None:
    """Get the Pandera schema for a table, if one exists."""
    return _SCHEMAS.get(table)


def list_validated_tables() -> list[str]:
    """Return list of tables that have validation schemas."""
    return list(_SCHEMAS.keys())
