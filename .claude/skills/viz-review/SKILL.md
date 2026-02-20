---
name: viz-review
description: Review and enforce FPL visualization standards. Auto-invokes when writing matplotlib or chart rendering code.
---

# FPL Visualization Standards

Review chart code against our rendering standards in `src/alfred_fpl/bi/viz.py`.

## Required Standards

### Backend & Output
- **Always** use `matplotlib.use("Agg")` — headless, no display
- Output format: **PNG only**
- Always `plt.close(fig)` after saving — prevent memory leaks
- Return `Path` to saved file, never display inline

### Deterministic Rendering
- **DPI**: 150 (fixed, never vary)
- **Figure size**: (10, 6) default, adjust height for heatmaps
- **Font size**: 10pt body, 13pt title (bold)
- **Grid**: alpha=0.3, always on
- **Tight layout**: `fig.tight_layout()` + `bbox_inches="tight"` on save

### Color Palette (in order)
```python
COLORS = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan
]
```
- Use `COLORS[i % len(COLORS)]` — never hardcode colors
- Heatmaps: `cmap="RdYlGn_r"` (red=hard, green=easy for FDR)

### Chart Type Selection
| Data Shape | Chart Type | Function |
|-----------|-----------|----------|
| Time series (GW-by-GW) | Line | `render_line` |
| Rankings / comparisons | Bar (horizontal) | `render_bar(horizontal=True)` |
| Team × GW grid (FDR) | Heatmap | `render_heatmap` |
| Multi-player multi-metric | Grouped bar | `render_comparison` |

### Common Issues to Flag
- Missing `plt.close(fig)` — memory leak
- Using `plt.show()` — will error in headless
- Hardcoded colors instead of COLORS list
- Missing title or axis labels
- Not sorting data before plotting (line charts)
- DPI != 150
- Using seaborn (not in our stack, not whitelisted in executor)
- Using `_home_team_id_label` or raw UUID columns — use `home_team_name`/`away_team_name` (enriched columns)
- Using `itertuples()` with wrong attribute names — prefer column-based rename+concat pattern

### Heatmap Data Prep (Proven Pattern)

FDR heatmaps require unstacking fixtures (each row has home AND away data) into a team × GW grid:

```python
# CORRECT: rename+concat pattern (tested, reliable)
home = df_fixtures[['home_team_name', 'gameweek', 'home_difficulty']].rename(
    columns={'home_team_name': 'team', 'home_difficulty': 'difficulty'})
away = df_fixtures[['away_team_name', 'gameweek', 'away_difficulty']].rename(
    columns={'away_team_name': 'team', 'away_difficulty': 'difficulty'})
all_rows = pd.concat([home, away])
pivot = all_rows.pivot_table(index='team', columns='gameweek', values='difficulty', aggfunc='mean')
render_heatmap(pivot, title='Fixture Difficulty', cmap='RdYlGn_r', vmin=1, vmax=5)
```

**Why this pattern:** Fixtures have one row per match with both teams' data. The LLM's instinct is to iterate with `iterrows()` or `itertuples()` and build dicts — this is fragile (attribute name mismatches). The rename+concat pattern is vectorized, readable, and proven in production.

## When Reviewing Code

For $ARGUMENTS, check:
1. Uses our `render_*` functions from `bi/viz.py` (preferred over raw matplotlib)
2. If raw matplotlib: follows all standards above
3. Charts have descriptive titles
4. Axes are labeled with human-readable names (not column names)
5. Line charts: data sorted by x-axis
6. Bar charts: horizontal for >5 categories (label readability)
7. Heatmaps: annotation text color adapts to background (white on dark, black on light)
