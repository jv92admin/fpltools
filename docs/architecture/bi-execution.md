# BI Execution Layer

The computation engine that LLM-generated Python runs against. Covers the sandboxed executor, analytics functions, visualization pipeline, and data validation.

## Package Structure

```
src/alfred_fpl/bi/
├── __init__.py        # Public API exports
├── data_access.py     # QuerySpec → DataFrame from Supabase
├── analytics.py       # Pure pandas computation functions
├── viz.py             # matplotlib headless rendering → PNG
├── schemas.py         # Pandera DataFrame validation
└── executor.py        # Sandboxed Python execution
```

## Executor

**File:** `src/alfred_fpl/bi/executor.py`

Runs LLM-generated Python in a restricted sandbox. The LLM writes code; the executor runs it safely.

### Sandbox Rules

| Category | Allowed | Blocked |
|----------|---------|---------|
| **Libraries** | `pd` (pandas), `np` (numpy) | os, sys, subprocess, socket, http, requests, pickle, threading |
| **BI Functions** | All analytics + viz functions (pre-loaded) | No raw imports allowed |
| **Builtins** | print, len, sorted, range, zip, min, max, sum, round, list, dict, set, tuple | open, eval, exec, compile, __import__, input, exit |
| **Limits** | 30s timeout, 100K row cap, 5 chart max | No file I/O, no network, no process spawning |

### Execution Flow

```
code string
  → compile(code, "<llm_code>", "exec")
  → exec(compiled, safe_globals, safe_locals)
  → capture stdout (io.StringIO)
  → collect DataFrames from locals (name → pd.DataFrame)
  → collect chart PNGs from temp dir
  → return ExecutionResult
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    stdout: str = ""                          # Captured print() output
    result: Any = None                        # Last expression value (best-effort)
    dataframes: dict[str, pd.DataFrame] = {}  # Named DataFrames created by code
    charts: list[Path] = []                   # PNG file paths from render_* calls
    error: str | None = None                  # Error message if execution failed
    duration_ms: int = 0                      # Wall-clock execution time
```

## Analytics Functions

**File:** `src/alfred_fpl/bi/analytics.py`

Pure pandas — no side effects, no I/O. Available as globals in the executor.

| Function | Purpose | Key Params |
|----------|---------|-----------|
| `add_rolling_mean` | Rolling average of a column | `column`, `window=3`, `group_by` |
| `compute_form_trend` | Per-player form over recent GWs | `n_gws=5` |
| `compute_fixture_difficulty` | FDR schedule for a team | `team_id`, `n_gws=5` |
| `compute_differentials` | Players unique to squad A vs B | `squad_a`, `squad_b` |
| `compute_price_velocity` | Price change direction/speed | `player_col`, `price_col`, `gw_col` |
| `rank_by` | Top/bottom N by metric | `metric`, `n=10`, `ascending=False` |

## Visualization

**File:** `src/alfred_fpl/bi/viz.py`

All functions return `Path` to a saved PNG. Never display inline.

### Standards

- **Backend:** `matplotlib.use("Agg")` — headless, no display
- **DPI:** 150 (fixed)
- **Figure size:** (10, 6) default
- **Colors:** 10-color palette, cycle with `COLORS[i % len(COLORS)]`
- **Heatmap colormap:** `RdYlGn_r` (red=hard, green=easy for FDR)
- **Cleanup:** `plt.close(fig)` after every save (memory leak prevention)

### Functions

| Function | Chart Type | Best For |
|----------|-----------|----------|
| `render_line` | Line chart | Time series (GW-by-GW trends) |
| `render_bar` | Bar chart (horizontal optional) | Rankings, comparisons |
| `render_heatmap` | Annotated heatmap | Team × GW grids (FDR) |
| `render_comparison` | Grouped bar | Multi-player multi-metric |

### Executor Integration

In the executor, viz functions are wrapped with `output_dir` baked in:

```python
# User writes:
render_bar(df=df_players, x="web_name", y="form", title="Top Form")

# Executor wraps to:
viz.render_bar(df=df_players, x="web_name", y="form", title="Top Form", output_dir=chart_dir)
```

Chart PNGs land in a temp directory and are collected into `ExecutionResult.charts`.

## Data Access

**File:** `src/alfred_fpl/bi/data_access.py`

Gateway from Supabase to pandas DataFrames. Used by the BI CLI and Jupyter notebooks (not by the executor directly — the executor receives DataFrames from the middleware cache).

### QuerySpec

```python
@dataclass
class QuerySpec:
    table: str
    filters: list[Filter] = []      # Filter(field, op, value)
    columns: list[str] | None = None
    order_by: str | None = None
    ascending: bool = True
    limit: int | None = None
```

### Enriched Views

`fetch_enriched(view)` provides pre-built JOINs:

| View | Base Table | JOINs |
|------|-----------|-------|
| `"players"` | players | + team name, position name |
| `"squad"` | squads | + player name, team, position |
| `"player_form"` | player_gameweeks | + player name |
| `"standings"` | league_standings | (already denormalized) |
| `"fixtures"` | fixtures | + home/away team names |

## Validation

**File:** `src/alfred_fpl/bi/schemas.py`

Pandera schemas for data quality. All columns are `required=False` (except `id`) because headline column selection means queries may return subsets.

Validated tables: `players`, `fixtures`, `player_gameweeks`, `player_snapshots`.

## Tests

| File | Count | What |
|------|-------|------|
| `test_bi_analytics.py` | 17 | All 6 analytics functions, edge cases |
| `test_bi_viz.py` | 8 | All 4 chart types → verify PNG created |
| `test_bi_schemas.py` | 9 | Validation, coercion, range checks |
| `test_executor.py` | 26 | Execution, safety blocks, edge cases |
