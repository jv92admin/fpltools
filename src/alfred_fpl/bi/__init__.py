"""Alfred FPL BI Library — data access, analytics, visualization.

Public API for LLM-generated Python code and local experimentation.

Usage:
    from alfred_fpl.bi import fetch_df, fetch_enriched, QuerySpec
    from alfred_fpl.bi import add_rolling_mean, rank_by, compute_differentials
    from alfred_fpl.bi import render_line, render_bar, render_heatmap
"""

from alfred_fpl.bi.data_access import QuerySpec, Filter, fetch_df, fetch_enriched
from alfred_fpl.bi.analytics import (
    add_rolling_mean,
    compute_form_trend,
    compute_fixture_difficulty,
    compute_differentials,
    compute_price_velocity,
    rank_by,
)
from alfred_fpl.bi.viz import render_line, render_bar, render_heatmap, render_comparison

__all__ = [
    # Data access
    "QuerySpec",
    "Filter",
    "fetch_df",
    "fetch_enriched",
    # Analytics
    "add_rolling_mean",
    "compute_form_trend",
    "compute_fixture_difficulty",
    "compute_differentials",
    "compute_price_velocity",
    "rank_by",
    # Visualization
    "render_line",
    "render_bar",
    "render_heatmap",
    "render_comparison",
]
