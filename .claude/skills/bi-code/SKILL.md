---
name: bi-code
description: Generate Python analytics code using the FPL BI library. Use when writing pandas code, data analysis, or executor-compatible scripts for FPL data.
---

# FPL BI Code Generator

Generate Python code that uses our BI library (`src/alfred_fpl/bi/`). All code should be executor-compatible (sandboxed, no imports beyond what's whitelisted).

## Available Functions

### Data Access (`bi/data_access.py`)
```python
fetch_df(QuerySpec(table, filters, columns, order_by, ascending, limit), client=None) -> DataFrame
fetch_enriched(view, filters=None, columns=None, order_by=None, ascending=True, limit=None) -> DataFrame

# Enriched views: "players", "squad", "player_form", "standings", "fixtures"
# Filter: Filter(field, op, value)  — ops: eq, neq, gt, gte, lt, lte, in, ilike, is
```

### Analytics (`bi/analytics.py`)
```python
add_rolling_mean(df, column, window=3, group_by=None, new_column=None) -> DataFrame
compute_form_trend(df, player_col="player_id", gw_col="gameweek", points_col="total_points", n_gws=5) -> DataFrame
compute_fixture_difficulty(fixtures_df, team_id, n_gws=5, gw_col="gameweek") -> DataFrame
compute_differentials(squad_a, squad_b, player_col="player_id") -> DataFrame
compute_price_velocity(snapshots_df, player_col="player_id", price_col="price", gw_col="gameweek") -> DataFrame
rank_by(df, metric, n=10, ascending=False, group_by=None) -> DataFrame
```

### Visualization (`bi/viz.py`)
```python
render_line(df, x, y, hue=None, title=None, xlabel=None, ylabel=None, output_dir=None) -> Path
render_bar(df, x, y, title=None, xlabel=None, ylabel=None, horizontal=False, output_dir=None) -> Path
render_heatmap(df, title=None, cmap="RdYlGn_r", vmin=1, vmax=5, annot=True, output_dir=None) -> Path
render_comparison(dfs, metrics, title=None, output_dir=None) -> Path
```

### Executor (`bi/executor.py`)
```python
execute(code, context={"df_name": dataframe}, timeout_seconds=30) -> ExecutionResult
# ExecutionResult: stdout, result, dataframes, charts, error, duration_ms
```

## Executor Safe Globals
- `pd` (pandas), `np` (numpy)
- All analytics functions above (no import needed)
- All viz functions (called with keyword args, output_dir auto-set)
- `print`, `len`, `sorted`, `range`, `zip`, `min`, `max`, `sum`, `round`
- NO: `os`, `sys`, `open`, `import`, `eval`, `exec`

## Code Patterns

### Pattern: Player comparison
```python
# Context: df_players (from fetch_enriched("players"))
top = rank_by(df_players, "form", n=5)
print(top[["web_name", "team", "price", "form", "total_points"]].to_string(index=False))
```

### Pattern: Rolling form with chart
```python
# Context: df_player_gameweeks (enriched with player_name)
df = add_rolling_mean(df_player_gameweeks, "total_points", window=3, group_by="player_id")
render_line(df=df, x="gameweek", y="total_points_rolling_3", hue="player_name",
    title="3-GW Rolling Points")
```

### Pattern: Fixture difficulty heatmap
```python
# Context: df_fixtures (enriched with home_team_name, away_team_name)
# Unstack home/away into rows, then pivot to team × GW grid
home = df_fixtures[['home_team_name', 'gameweek', 'home_difficulty']].rename(
    columns={'home_team_name': 'team', 'home_difficulty': 'difficulty'})
away = df_fixtures[['away_team_name', 'gameweek', 'away_difficulty']].rename(
    columns={'away_team_name': 'team', 'away_difficulty': 'difficulty'})
all_rows = pd.concat([home, away])
pivot = all_rows.pivot_table(index='team', columns='gameweek', values='difficulty', aggfunc='mean')
render_heatmap(pivot, title='Fixture Difficulty', cmap='RdYlGn_r', vmin=1, vmax=5)
```

### Pattern: Squad differentials
```python
# Context: df_squad_a, df_squad_b
diff = compute_differentials(df_squad_a, df_squad_b)
only_mine = diff[diff["owner"] == "a"]
only_rival = diff[diff["owner"] == "b"]
print(f"My differentials: {len(only_mine)}, Rival's: {len(only_rival)}")
```

### Pattern: Points per million value
```python
df = df_players.copy()
df["pts_per_m"] = df["total_points"] / df["price"]
top_value = rank_by(df, "pts_per_m", n=10)
render_bar(df=top_value, x="web_name", y="pts_per_m", title="Best Value Players", horizontal=True)
```

## Key Tables (column reference)
- **players**: id, web_name, team_id, position_id, price, total_points, form, selected_by_percent, minutes, goals_scored, assists, clean_sheets, bonus, status, news
- **player_gameweeks**: id, player_id, gameweek, total_points, minutes, goals_scored, assists, clean_sheets, bonus, bps, expected_goals, expected_assists, ict_index, value
- **fixtures**: id, gameweek, home_team_id, away_team_id, home_score, away_score, kickoff_time, finished, home_difficulty (FDR 1-5), away_difficulty
- **squads**: id, manager_id (INT), gameweek, player_id, slot (1-15), multiplier (0-3), is_captain, is_vice_captain
- **player_snapshots**: id, player_id, gameweek, price, selected_by_percent, form, transfers_in_event, transfers_out_event

## Enriched DataFrame Columns (runtime)

When DataFrames are loaded for executor code (via `fpl_analyze`/`fpl_plot`), they are **enriched** with human-readable names by `_enrich_dataframes()`. Use these columns in executor code, NOT the raw FK columns.

| DataFrame | Enriched columns | Source |
|-----------|-----------------|--------|
| `df_fixtures` | `home_team_name`, `away_team_name` | UUID team_id → team short_name via team map |
| `df_player_gameweeks` | `player_name` | UUID player_id → web_name via players cache |
| `df_player_snapshots` | `player_name` | UUID player_id → web_name via players cache |

**CRITICAL:** Use `home_team_name` / `away_team_name` (NOT `_home_team_id_label` or `home_team_id`). Use `player_name` (NOT `player_id`) for display. The enrichment happens automatically — you don't need to join manually.

When generating code for $ARGUMENTS:
1. Identify which tables/views are needed
2. Use `fetch_enriched` where possible (pre-built JOINs)
3. Use analytics functions instead of raw pandas where available
4. Always include a `print()` summary
5. Add a chart if the analysis is visual (trends, rankings, comparisons)
