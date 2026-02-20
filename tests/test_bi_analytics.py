"""Tests for BI analytics functions — pure pandas, no Supabase."""

import pandas as pd
import pytest

from alfred_fpl.bi.analytics import (
    add_rolling_mean,
    compute_differentials,
    compute_fixture_difficulty,
    compute_form_trend,
    compute_price_velocity,
    rank_by,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def player_gw_df():
    """Player gameweek data for two players over 6 GWs."""
    return pd.DataFrame({
        "player_id": ["p1"] * 6 + ["p2"] * 6,
        "gameweek": list(range(1, 7)) * 2,
        "total_points": [2, 8, 5, 10, 3, 7, 6, 4, 9, 2, 8, 5],
        "minutes": [90, 90, 60, 90, 45, 90, 90, 70, 90, 90, 80, 90],
    })


@pytest.fixture
def fixtures_df():
    """Fixture data for team_a over 5 GWs."""
    return pd.DataFrame({
        "home_team_id": ["team_a", "team_b", "team_a", "team_c", "team_a"],
        "away_team_id": ["team_b", "team_a", "team_c", "team_a", "team_d"],
        "gameweek": [1, 2, 3, 4, 5],
        "home_difficulty": [3, 4, 2, 5, 3],
        "away_difficulty": [3, 2, 4, 3, 4],
        "finished": [True, True, False, False, False],
    })


@pytest.fixture
def squad_a():
    return pd.DataFrame({
        "player_id": ["p1", "p2", "p3", "p4", "p5"],
        "web_name": ["Salah", "Saka", "Haaland", "Palmer", "Watkins"],
    })


@pytest.fixture
def squad_b():
    return pd.DataFrame({
        "player_id": ["p1", "p3", "p6", "p7", "p8"],
        "web_name": ["Salah", "Haaland", "Son", "Bruno", "Isak"],
    })


@pytest.fixture
def snapshots_df():
    return pd.DataFrame({
        "player_id": ["p1"] * 4 + ["p2"] * 4,
        "gameweek": [1, 2, 3, 4, 1, 2, 3, 4],
        "price": [13.0, 13.1, 13.3, 13.5, 8.0, 8.0, 7.9, 7.8],
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRollingMean:
    def test_basic(self, player_gw_df):
        result = add_rolling_mean(player_gw_df, "total_points", window=3)
        assert "total_points_rolling_3" in result.columns
        assert len(result) == 12

    def test_grouped(self, player_gw_df):
        result = add_rolling_mean(
            player_gw_df, "total_points", window=2, group_by="player_id"
        )
        assert "total_points_rolling_2" in result.columns

    def test_custom_column_name(self, player_gw_df):
        result = add_rolling_mean(
            player_gw_df, "total_points", window=3, new_column="form_3gw"
        )
        assert "form_3gw" in result.columns

    def test_invalid_column(self, player_gw_df):
        with pytest.raises(ValueError, match="not in DataFrame"):
            add_rolling_mean(player_gw_df, "nonexistent")


class TestFormTrend:
    def test_returns_one_row_per_player(self, player_gw_df):
        result = compute_form_trend(player_gw_df, n_gws=5)
        assert len(result) == 2
        assert "trend" in result.columns
        assert "avg_points" in result.columns
        assert "total_points" in result.columns

    def test_trend_values(self, player_gw_df):
        result = compute_form_trend(player_gw_df, n_gws=6)
        trends = set(result["trend"].values)
        assert trends <= {"up", "down", "flat"}


class TestFixtureDifficulty:
    def test_returns_correct_fdr(self, fixtures_df):
        result = compute_fixture_difficulty(fixtures_df, "team_a", n_gws=5)
        assert len(result) > 0
        assert "fdr" in result.columns
        assert "is_home" in result.columns

    def test_home_away_correct(self, fixtures_df):
        result = compute_fixture_difficulty(fixtures_df, "team_a", n_gws=5)
        # GW1: team_a is home, home_difficulty=3
        gw1 = result[result["gameweek"] == 1]
        if not gw1.empty:
            assert gw1.iloc[0]["is_home"] is True
            assert gw1.iloc[0]["fdr"] == 3

    def test_empty_team(self, fixtures_df):
        result = compute_fixture_difficulty(fixtures_df, "nonexistent", n_gws=5)
        assert result.empty


class TestDifferentials:
    def test_identifies_shared_and_unique(self, squad_a, squad_b):
        result = compute_differentials(squad_a, squad_b)
        owners = set(result["owner"].values)
        assert "both" in owners  # Salah, Haaland
        assert "a" in owners     # Saka, Palmer, Watkins
        assert "b" in owners     # Son, Bruno, Isak

    def test_correct_counts(self, squad_a, squad_b):
        result = compute_differentials(squad_a, squad_b)
        assert len(result[result["owner"] == "both"]) == 2   # p1, p3
        assert len(result[result["owner"] == "a"]) == 3      # p2, p4, p5
        assert len(result[result["owner"] == "b"]) == 3      # p6, p7, p8


class TestPriceVelocity:
    def test_rising_and_falling(self, snapshots_df):
        result = compute_price_velocity(snapshots_df)
        assert len(result) == 2

        p1 = result[result["player_id"] == "p1"].iloc[0]
        assert p1["direction"] == "rising"
        assert p1["price_change"] > 0

        p2 = result[result["player_id"] == "p2"].iloc[0]
        assert p2["direction"] == "falling"
        assert p2["price_change"] < 0

    def test_empty_input(self):
        result = compute_price_velocity(pd.DataFrame())
        assert result.empty


class TestRankBy:
    def test_top_n(self):
        df = pd.DataFrame({
            "name": ["a", "b", "c", "d", "e"],
            "score": [10, 30, 20, 50, 40],
        })
        result = rank_by(df, "score", n=3)
        assert len(result) == 3
        assert result.iloc[0]["score"] == 50
        assert "rank" in result.columns

    def test_ascending(self):
        df = pd.DataFrame({
            "name": ["a", "b", "c"],
            "price": [5.0, 3.0, 8.0],
        })
        result = rank_by(df, "price", n=2, ascending=True)
        assert result.iloc[0]["price"] == 3.0

    def test_grouped(self):
        df = pd.DataFrame({
            "pos": ["MID", "MID", "FWD", "FWD"],
            "name": ["a", "b", "c", "d"],
            "points": [100, 80, 150, 120],
        })
        result = rank_by(df, "points", n=1, group_by="pos")
        assert len(result) == 2  # Top 1 per position

    def test_invalid_metric(self):
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match="not in DataFrame"):
            rank_by(df, "nonexistent")
