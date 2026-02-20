"""Tests for Pandera schema validation."""

import pandas as pd
import pandera as pa
import pytest

from alfred_fpl.bi.schemas import get_schema, list_validated_tables, validate_df


class TestValidateDf:
    def test_valid_players(self):
        df = pd.DataFrame({
            "id": ["abc-123"],
            "web_name": ["Salah"],
            "price": [13.2],
            "total_points": [180],
            "form": [8.1],
            "selected_by_percent": [45.2],
            "minutes": [2500],
            "goals_scored": [15],
            "assists": [10],
            "clean_sheets": [0],
            "bonus": [25],
        })
        result = validate_df(df, "players")
        assert len(result) == 1

    def test_extra_columns_allowed(self):
        """strict=False means extra columns don't cause errors."""
        df = pd.DataFrame({
            "id": ["abc-123"],
            "web_name": ["Salah"],
            "price": [13.2],
            "extra_column": ["whatever"],
        })
        result = validate_df(df, "players")
        assert "extra_column" in result.columns

    def test_invalid_price_range(self):
        df = pd.DataFrame({
            "id": ["abc-123"],
            "web_name": ["Salah"],
            "price": [99.9],  # Out of range (0-20)
        })
        with pytest.raises(pa.errors.SchemaError):
            validate_df(df, "players")

    def test_invalid_fdr_range(self):
        df = pd.DataFrame({
            "id": ["abc-123"],
            "gameweek": [25],
            "home_team_id": ["t1"],
            "away_team_id": ["t2"],
            "home_difficulty": [6],  # FDR is 1-5
            "away_difficulty": [3],
        })
        with pytest.raises(pa.errors.SchemaError):
            validate_df(df, "fixtures")

    def test_unknown_table_passes_through(self):
        """Tables without schemas are returned as-is."""
        df = pd.DataFrame({"anything": [1, 2, 3]})
        result = validate_df(df, "unknown_table")
        assert len(result) == 3

    def test_coercion(self):
        """Numeric strings should be coerced to float."""
        df = pd.DataFrame({
            "id": ["abc"],
            "web_name": ["Test"],
            "price": ["13.2"],  # String, should be coerced
        })
        result = validate_df(df, "players")
        assert result["price"].dtype == float


class TestSchemaRegistry:
    def test_list_tables(self):
        tables = list_validated_tables()
        assert "players" in tables
        assert "fixtures" in tables
        assert "player_gameweeks" in tables

    def test_get_schema(self):
        schema = get_schema("players")
        assert schema is not None
        assert "web_name" in schema.columns

    def test_get_unknown_schema(self):
        assert get_schema("nonexistent") is None
