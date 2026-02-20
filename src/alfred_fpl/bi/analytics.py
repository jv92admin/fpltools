"""FPL analytics — pure pandas computation functions.

These are the building blocks the LLM calls in ANALYZE steps. Every function
takes DataFrames in and returns DataFrames out. No database access.

Convention: functions that ADD columns return the original df with new columns.
Functions that COMPUTE new data return a new DataFrame.
"""

from __future__ import annotations

import pandas as pd


def add_rolling_mean(
    df: pd.DataFrame,
    column: str,
    window: int = 3,
    group_by: str | None = None,
    new_column: str | None = None,
) -> pd.DataFrame:
    """Add a rolling mean column to the DataFrame.

    Args:
        df: Input DataFrame, must have the target column. Should be sorted
            by the time dimension (e.g., gameweek) before calling.
        column: Column to compute rolling mean over.
        window: Window size (number of rows).
        group_by: Optional grouping column (e.g., 'player_id' for per-player rolling).
        new_column: Name for the new column. Default: '{column}_rolling_{window}'.

    Returns:
        DataFrame with the rolling mean column added.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not in DataFrame. Available: {list(df.columns)}")

    out_col = new_column or f"{column}_rolling_{window}"

    if group_by and group_by in df.columns:
        df[out_col] = df.groupby(group_by)[column].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )
    else:
        df[out_col] = df[column].rolling(window, min_periods=1).mean()

    return df


def compute_form_trend(
    df: pd.DataFrame,
    player_col: str = "player_id",
    gw_col: str = "gameweek",
    points_col: str = "total_points",
    n_gws: int = 5,
) -> pd.DataFrame:
    """Compute per-player form trend over the last N gameweeks.

    Returns a summary DataFrame with one row per player:
    - total_points: sum over window
    - avg_points: mean per GW
    - trend: 'up', 'down', or 'flat' (comparing first half vs second half)
    - min_points, max_points

    Args:
        df: player_gameweeks DataFrame.
        player_col: Column identifying the player.
        gw_col: Gameweek column for sorting/filtering.
        points_col: Points column to analyze.
        n_gws: Number of recent GWs to include.

    Returns:
        Summary DataFrame indexed by player.
    """
    # Take last N GWs per player
    max_gw = df[gw_col].max()
    min_gw = max_gw - n_gws + 1
    window = df[df[gw_col] >= min_gw].copy()

    if window.empty:
        return pd.DataFrame()

    window = window.sort_values([player_col, gw_col])

    def _player_trend(group):
        pts = group[points_col].values
        total = pts.sum()
        avg = pts.mean()
        mid = len(pts) // 2
        first_half = pts[:mid].mean() if mid > 0 else avg
        second_half = pts[mid:].mean() if mid > 0 else avg
        diff = second_half - first_half
        trend = "up" if diff > 0.5 else ("down" if diff < -0.5 else "flat")
        return pd.Series({
            "total_points": total,
            "avg_points": round(avg, 1),
            "trend": trend,
            "min_points": pts.min(),
            "max_points": pts.max(),
            "gws_played": len(pts),
        })

    result = window.groupby(player_col).apply(_player_trend, include_groups=False)
    return result.reset_index()


def compute_fixture_difficulty(
    fixtures_df: pd.DataFrame,
    team_id: str,
    n_gws: int = 5,
    gw_col: str = "gameweek",
) -> pd.DataFrame:
    """Compute fixture difficulty run for a specific team.

    For each upcoming fixture, determines the correct FDR:
    - home_difficulty when the team is the home side
    - away_difficulty when the team is the away side

    Args:
        fixtures_df: Fixtures DataFrame with home_team_id, away_team_id,
            home_difficulty, away_difficulty, gameweek.
        team_id: UUID of the team.
        n_gws: Number of gameweeks to look ahead.
        gw_col: Gameweek column name.

    Returns:
        DataFrame with columns: gameweek, opponent_id, is_home, fdr, opponent.
        Sorted by gameweek.
    """
    # Filter to team's fixtures
    home_mask = fixtures_df["home_team_id"] == team_id
    away_mask = fixtures_df["away_team_id"] == team_id
    team_fixtures = fixtures_df[home_mask | away_mask].copy()

    if team_fixtures.empty:
        return pd.DataFrame()

    # Sort and take next N
    team_fixtures = team_fixtures.sort_values(gw_col)
    # Only future / unfinished fixtures
    unfinished = team_fixtures[team_fixtures.get("finished", pd.Series(False)) != True]  # noqa: E712
    if not unfinished.empty:
        team_fixtures = unfinished.head(n_gws)
    else:
        team_fixtures = team_fixtures.tail(n_gws)

    rows = []
    for _, fix in team_fixtures.iterrows():
        is_home = fix["home_team_id"] == team_id
        rows.append({
            "gameweek": fix[gw_col],
            "opponent_id": fix["away_team_id"] if is_home else fix["home_team_id"],
            "is_home": is_home,
            "fdr": fix["home_difficulty"] if is_home else fix["away_difficulty"],
        })

    result = pd.DataFrame(rows)

    # Add opponent name if available
    if "home_team" in fixtures_df.columns:
        # Enriched fixtures have team names
        name_map = {}
        for _, fix in team_fixtures.iterrows():
            name_map[fix["home_team_id"]] = fix.get("home_team", "")
            name_map[fix["away_team_id"]] = fix.get("away_team", "")
        result["opponent"] = result["opponent_id"].map(name_map)

    return result


def compute_differentials(
    squad_a: pd.DataFrame,
    squad_b: pd.DataFrame,
    player_col: str = "player_id",
) -> pd.DataFrame:
    """Find differential players between two squads.

    A differential is a player in one squad but not the other.

    Args:
        squad_a: First squad DataFrame (e.g., your team).
        squad_b: Second squad DataFrame (e.g., rival's team).
        player_col: Column identifying players.

    Returns:
        DataFrame with columns: player_id, owner ('a', 'b', 'both'),
        plus any other columns from the source DataFrames.
    """
    a_ids = set(squad_a[player_col].dropna())
    b_ids = set(squad_b[player_col].dropna())

    shared = a_ids & b_ids
    only_a = a_ids - b_ids
    only_b = b_ids - a_ids

    rows = []

    for pid in shared:
        row = squad_a[squad_a[player_col] == pid].iloc[0].to_dict()
        row["owner"] = "both"
        rows.append(row)

    for pid in only_a:
        row = squad_a[squad_a[player_col] == pid].iloc[0].to_dict()
        row["owner"] = "a"
        rows.append(row)

    for pid in only_b:
        row = squad_b[squad_b[player_col] == pid].iloc[0].to_dict()
        row["owner"] = "b"
        rows.append(row)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def compute_price_velocity(
    snapshots_df: pd.DataFrame,
    player_col: str = "player_id",
    price_col: str = "price",
    gw_col: str = "gameweek",
) -> pd.DataFrame:
    """Compute price change velocity from snapshot time series.

    Returns per-player: price_change (total), gw_span, velocity (change per GW),
    latest_price, direction ('rising', 'falling', 'stable').

    Args:
        snapshots_df: Player snapshots with price, gameweek, player_id.
        player_col: Player identifier column.
        price_col: Price column.
        gw_col: Gameweek column.

    Returns:
        Summary DataFrame with one row per player.
    """
    if snapshots_df.empty:
        return pd.DataFrame()

    df = snapshots_df.sort_values([player_col, gw_col])

    def _velocity(group):
        prices = group[price_col].values
        gws = group[gw_col].values
        if len(prices) < 2:
            return pd.Series({
                "price_change": 0.0,
                "gw_span": 0,
                "velocity": 0.0,
                "latest_price": prices[-1] if len(prices) > 0 else None,
                "direction": "stable",
            })
        change = prices[-1] - prices[0]
        span = gws[-1] - gws[0]
        vel = change / span if span > 0 else 0.0
        direction = "rising" if vel > 0.05 else ("falling" if vel < -0.05 else "stable")
        return pd.Series({
            "price_change": round(change, 1),
            "gw_span": int(span),
            "velocity": round(vel, 2),
            "latest_price": prices[-1],
            "direction": direction,
        })

    result = df.groupby(player_col).apply(_velocity, include_groups=False)
    return result.reset_index()


def rank_by(
    df: pd.DataFrame,
    metric: str,
    n: int = 10,
    ascending: bool = False,
    group_by: str | None = None,
) -> pd.DataFrame:
    """Rank rows by a metric column and return top/bottom N.

    Args:
        df: Input DataFrame.
        metric: Column to rank by.
        n: Number of rows to return.
        ascending: If True, return bottom N (lowest values).
        group_by: If set, rank within each group and return top N per group.

    Returns:
        DataFrame sorted by metric with a 'rank' column added.
    """
    if metric not in df.columns:
        raise ValueError(f"Column '{metric}' not in DataFrame. Available: {list(df.columns)}")

    if group_by and group_by in df.columns:
        if ascending:
            result = df.groupby(group_by).apply(
                lambda g: g.nsmallest(n, metric), include_groups=False
            )
        else:
            result = df.groupby(group_by).apply(
                lambda g: g.nlargest(n, metric), include_groups=False
            )
        result = result.reset_index(drop=True)
    else:
        result = df.nlargest(n, metric) if not ascending else df.nsmallest(n, metric)
        result = result.reset_index(drop=True)

    result["rank"] = range(1, len(result) + 1)
    return result
