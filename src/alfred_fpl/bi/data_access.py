"""DataFrame gateway to Supabase.

Fetches data as pandas DataFrames with filter DSL matching PostgREST semantics.
Enriched views provide pre-built JOINs for common analysis patterns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filter DSL
# ---------------------------------------------------------------------------

VALID_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "ilike", "is"}


@dataclass
class Filter:
    """A single filter clause matching PostgREST operators."""

    field: str
    op: str  # eq, neq, gt, gte, lt, lte, in, ilike, is
    value: Any

    def __post_init__(self):
        if self.op not in VALID_OPS:
            raise ValueError(f"Invalid filter op '{self.op}'. Valid: {VALID_OPS}")


@dataclass
class QuerySpec:
    """Specification for a database query returning a DataFrame."""

    table: str
    filters: list[Filter] = field(default_factory=list)
    columns: list[str] | None = None
    order_by: str | None = None
    ascending: bool = True
    limit: int | None = None


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def _apply_filters(query, filters: list[Filter]):
    """Apply Filter list to a Supabase query builder."""
    for f in filters:
        if f.op == "eq":
            query = query.eq(f.field, f.value)
        elif f.op == "neq":
            query = query.neq(f.field, f.value)
        elif f.op == "gt":
            query = query.gt(f.field, f.value)
        elif f.op == "gte":
            query = query.gte(f.field, f.value)
        elif f.op == "lt":
            query = query.lt(f.field, f.value)
        elif f.op == "lte":
            query = query.lte(f.field, f.value)
        elif f.op == "in":
            query = query.in_(f.field, f.value)
        elif f.op == "ilike":
            query = query.ilike(f.field, f.value)
        elif f.op == "is":
            query = query.is_(f.field, f.value)
    return query


def fetch_df(spec: QuerySpec, client=None) -> pd.DataFrame:
    """Fetch data from Supabase as a pandas DataFrame.

    Args:
        spec: Query specification (table, filters, columns, order, limit).
        client: Supabase client. If None, uses the default service client.

    Returns:
        DataFrame with query results. Empty DataFrame if no results.
    """
    if client is None:
        from alfred_fpl.db.client import get_service_client
        client = get_service_client()

    select_str = ", ".join(spec.columns) if spec.columns else "*"
    query = client.table(spec.table).select(select_str)

    query = _apply_filters(query, spec.filters)

    if spec.order_by:
        query = query.order(spec.order_by, desc=not spec.ascending)

    if spec.limit:
        query = query.limit(spec.limit)

    response = query.execute()
    data = response.data or []

    if not data:
        return pd.DataFrame()

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Enriched views — pre-built JOINs for common patterns
# ---------------------------------------------------------------------------

# Maps view name → (base_table, joins)
# Each join: (fk_column, target_table, target_select, rename_map)
_ENRICHED_VIEWS: dict[str, dict] = {
    "players": {
        "base": "players",
        "joins": [
            ("team_id", "teams", "id, short_name", {"short_name": "team"}),
            ("position_id", "positions", "id, short_name", {"short_name": "position"}),
        ],
    },
    "squad": {
        "base": "squads",
        "joins": [
            ("player_id", "players", "id, web_name, price, form, total_points", {
                "web_name": "player_name",
                "price": "player_price",
                "form": "player_form",
                "total_points": "player_total_points",
            }),
        ],
    },
    "player_form": {
        "base": "player_gameweeks",
        "joins": [
            ("player_id", "players", "id, web_name, team_id", {
                "web_name": "player_name",
            }),
        ],
    },
    "standings": {
        "base": "league_standings",
        "joins": [],  # Already denormalized (manager_name, team_name, league_name)
    },
    "fixtures": {
        "base": "fixtures",
        "joins": [
            ("home_team_id", "teams", "id, short_name", {"short_name": "home_team"}),
            ("away_team_id", "teams", "id, short_name", {"short_name": "away_team"}),
        ],
    },
}


def fetch_enriched(
    view: str,
    filters: list[Filter] | None = None,
    columns: list[str] | None = None,
    order_by: str | None = None,
    ascending: bool = True,
    limit: int | None = None,
    client=None,
) -> pd.DataFrame:
    """Fetch an enriched view with pre-built JOINs.

    Available views: players, squad, player_form, standings, fixtures.

    Since Supabase REST doesn't support JOINs, this fetches the base table
    and then merges dimension tables client-side.

    Args:
        view: Name of the enriched view.
        filters: Filters applied to the base table.
        columns: Columns to select from the base table (None = all).
        order_by: Column to sort by.
        ascending: Sort direction.
        limit: Max rows.
        client: Supabase client.

    Returns:
        Enriched DataFrame with joined dimension columns.
    """
    if view not in _ENRICHED_VIEWS:
        raise ValueError(f"Unknown view '{view}'. Available: {list(_ENRICHED_VIEWS.keys())}")

    if client is None:
        from alfred_fpl.db.client import get_service_client
        client = get_service_client()

    view_def = _ENRICHED_VIEWS[view]

    # Fetch base table
    base_spec = QuerySpec(
        table=view_def["base"],
        filters=filters or [],
        columns=columns,
        order_by=order_by,
        ascending=ascending,
        limit=limit,
    )
    df = fetch_df(base_spec, client=client)

    if df.empty:
        return df

    # Apply joins
    for fk_col, target_table, target_select, rename_map in view_def["joins"]:
        if fk_col not in df.columns:
            continue

        # Fetch unique FK values
        fk_values = df[fk_col].dropna().unique().tolist()
        if not fk_values:
            continue

        dim_spec = QuerySpec(
            table=target_table,
            filters=[Filter(field="id", op="in", value=fk_values)],
            columns=target_select.replace(" ", "").split(","),
        )
        dim_df = fetch_df(dim_spec, client=client)

        if dim_df.empty:
            continue

        # Rename dimension columns to avoid collisions
        dim_df = dim_df.rename(columns=rename_map)

        # Merge on FK
        df = df.merge(
            dim_df,
            left_on=fk_col,
            right_on="id",
            how="left",
            suffixes=("", f"_{target_table}"),
        )

        # Drop the duplicate 'id' column from dimension table
        id_col = f"id_{target_table}"
        if id_col in df.columns:
            df = df.drop(columns=[id_col])

    return df
