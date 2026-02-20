# Handoff: Alfred FPL Domain → Core PM

**From:** FPL domain team
**To:** Alfred-core PM
**Date:** 2026-02-19
**Status:** Domain scaffold complete, BI library in progress

---

## What We've Built

An Alfred domain package (`alfred-fpl`) for Fantasy Premier League analysis. The domain scaffold is complete and tested:

- **15 entity definitions** (players, teams, fixtures, squads, standings, etc.)
- **6 subdomains** (squad, scouting, market, league, live, fixtures)
- **All 23 DomainConfig methods** implemented
- **CRUD middleware** handling integer FK translation, auto-injection of manager/league scoping, per-table row limits, headline column selection
- **Per-step personas** that guide the LLM's behavior in READ, ANALYZE, and GENERATE steps
- **25 passing tests** covering wiring and contract enforcement

The domain teaches Alfred *what FPL is*. What's missing is the ability to *compute* — to run Python code during analysis.

---

## What We Need From Core

### The Problem

FPL analysis requires computation the LLM can't do in its head:
- Rolling 5-GW form averages
- Squad differential identification (merge two 15-player squads, find unique picks)
- Fixture difficulty runs (average FDR over next N gameweeks per team)
- Price velocity (rate of price change from snapshot time series)
- Points-per-million rankings with positional filtering

Today's ANALYZE step is LLM-only reasoning. The LLM can describe what *should* be computed, but it can't execute the computation. We need a way for ANALYZE steps to run Python.

### The Ideal Flow

**READ (Limited, Targeted)**
The LLM issues `db_read` calls via the existing CRUD tools. Middleware enforces guardrails:
- Per-table row limits (players=20, fixtures=30, player_gameweeks=50)
- Headline column selection (strip 40-column tables to ~15 relevant columns)
- Auto-injected scoping filters (manager_id, league_id)
- Required filter enforcement on high-volume tables

The LLM sees a **data card** in its context — column names, a 5-row sample, and numeric ranges. This is enough to write correct Python. The actual full DataFrames are held in session state by reference name (e.g., `df_squads`, `df_player_gameweeks`).

**ANALYZE (Python Execution)**
The LLM writes a Python code block that operates on the DataFrames from READ. The code runs in a **sandboxed executor** with:
- Whitelisted globals: `pandas` (as `pd`), `numpy` (as `np`), plus a small library of domain helper functions
- No filesystem, network, or import access
- 30-second timeout
- Max 100k rows per DataFrame

The executor returns an `ExecutionResult`:
```python
@dataclass
class ExecutionResult:
    stdout: str                           # captured print output
    result: Any                           # last expression value
    dataframes: dict[str, pd.DataFrame]   # named DataFrames produced
    charts: list[Path]                    # chart files rendered
    error: str | None                     # exception message if failed
    duration_ms: int                      # wall clock time
```

If execution fails, the error + traceback goes back to the LLM for retry (max 2 attempts).

**GENERATE (Structured Artifacts)**
The LLM writes a short matplotlib code block to render charts:
```python
render_line(df, x='gameweek', y='form', hue='web_name', title='Form Trend')
```
The executor runs it headlessly (Agg backend) → PNG file. The LLM also emits table artifacts (≤25 rows) and a 2-3 sentence narrative framing the insight.

REPLY assembles: narrative text + chart + table = one "notebook cell".

### What We Need: A `run_python` Tool (or Equivalent)

The simplest integration point: a new tool available in Act steps that executes a Python code string and returns results.

**Proposed tool contract:**
```
Tool: run_python
Input:
  code: str          # Python code to execute
  context: str[]     # names of DataFrames from prior steps to make available
Output:
  stdout: str
  result_summary: str
  dataframes: {name: preview}  # name → first 5 rows as text
  charts: str[]                # paths or base64 of rendered PNGs
  error: str | null
```

**What we provide (domain side):**
- The executor implementation (sandboxed `exec()` with restricted builtins)
- The safe globals whitelist (pandas, numpy, domain helpers)
- Pandera schema validation on DataFrames
- The domain helper library (analytics + viz functions)

**What we need from core:**
1. A way to register `run_python` as a tool available in Act steps (alongside db_read/db_create/etc.)
2. A mechanism to pass DataFrames from READ step results into the executor's context (by reference name, not serialized into the prompt)
3. A way to return chart files/images in tool results (currently tool results are JSON-serializable only)
4. Control over which step types can access `run_python` (we want it in ANALYZE and GENERATE, not READ)

### Alternative: Domain Tool Registration

If a generic `run_python` is too broad, an alternative is a **domain tool registration** mechanism:

```python
class DomainConfig:
    def get_custom_tools(self) -> dict[str, ToolDefinition]:
        """Domain-specific tools available in Act steps."""
        return {
            "fpl_analyze": ToolDefinition(
                description="Execute Python analysis on FPL data",
                input_schema={"code": "str", "context_dfs": "list[str]"},
                handler=self._execute_analysis,
            ),
            "fpl_plot": ToolDefinition(
                description="Render a chart from FPL data",
                input_schema={"code": "str"},
                handler=self._execute_plot,
            ),
        }
```

This keeps execution scoped to the domain and lets each domain define its own safe tool surface.

---

## Context Engineering Strategy

We're designing the prompt context so the LLM can write correct Python without seeing all the data:

| What LLM Sees | Purpose |
|----------------|---------|
| Fallback schemas (column names + types + semantics) | Write correct column references |
| Data card (5-row sample + numeric ranges) | Understand data distribution |
| Domain helper API reference | Know which functions are available |
| Persona (per-subdomain, per-step) | Scope the analysis approach |

The full DataFrames are NOT in the prompt — they're passed to the executor by reference. This prevents context explosion (a 50-row player_gameweeks result would be ~8k tokens if serialized).

---

## Example End-to-End Conversation

**User:** "Compare Salah and Saka over the last 5 gameweeks"

**UNDERSTAND** → routes to `scouting` subdomain

**THINK** → plans 3 steps:
1. READ: fetch player data for Salah and Saka
2. READ: fetch player_gameweeks for both, last 5 GWs
3. ANALYZE: compute rolling form, head-to-head comparison
4. GENERATE: render comparison chart + table

**ACT Step 1 (READ):**
```
db_read players where web_name in ('Salah', 'Saka')
→ 2 rows, saved as df_players
```

**ACT Step 2 (READ):**
```
db_read player_gameweeks where player_id in (salah_id, saka_id) and gameweek gte 20
→ 10 rows, saved as df_pgw
```

**ACT Step 3 (ANALYZE):**
```python
# LLM writes this code:
merged = df_pgw.merge(df_players[['id', 'web_name']], left_on='player_id', right_on='id')
comparison = merged.pivot_table(index='gameweek', columns='web_name',
    values=['total_points', 'minutes', 'goals_scored', 'assists', 'bonus'])
comparison['rolling_pts'] = merged.groupby('web_name')['total_points'].transform(
    lambda x: x.rolling(3, min_periods=1).mean()
)
print(comparison.to_string())
```
Executor runs it → returns DataFrame + stdout

**ACT Step 4 (GENERATE):**
```python
render_line(merged, x='gameweek', y='total_points', hue='web_name',
    title='Salah vs Saka: Points Over Last 5 GWs')
```
Executor renders → PNG chart

**REPLY:**
> Salah has outscored Saka 48-31 over the last 5 GWs. His 3-GW rolling average is 9.7 vs Saka's 6.3. Salah has been more consistent with 4/5 GWs scoring 8+ points.
>
> [Chart: line graph showing GW-by-GW points]
> [Table: side-by-side stats comparison]

---

## Open Questions for Core PM

1. **Tool registration**: Is a `get_custom_tools()` method on DomainConfig feasible? Or would you prefer a single `run_python` tool that all domains share?

2. **DataFrame passing**: How should large data move from READ results to the executor? Options:
   - Session state (like step_results today, but typed as DataFrames)
   - A shared memory/cache keyed by step index
   - Serialize to Parquet in temp directory, pass file paths

3. **Image/file return**: How should charts (PNG files) come back from tools? Options:
   - Base64-encoded in tool result JSON
   - File path that the frontend reads
   - A new `StreamEvent` type for binary artifacts

4. **Step type control**: Should `run_python` be available in all tool-enabled steps, or should there be a separate `get_python_enabled_step_types()`?

5. **Error recovery**: When Python execution fails, should the error go back to the same Act step for retry, or should it trigger a replan in Think?

6. **Timeline**: When might a tool registration or `run_python` hook be available? We're building the executor and BI library now so we're ready to plug in.

---

## What We're Building Now (No Core Changes Needed)

While waiting for the execution hook:

1. **BI Library** (`src/alfred_fpl/bi/`) — Pure Python, standalone:
   - `data_access.py` — QuerySpec → DataFrame from Supabase
   - `analytics.py` — rolling stats, differentials, rankings
   - `viz.py` — matplotlib headless → PNG
   - `schemas.py` — Pandera validation

2. **Python Executor** — Sandboxed exec() with restricted builtins

3. **Local Validation** — Jupyter notebook exercising the full stack end-to-end

This gives us:
- A validated tool surface the LLM will code against
- Working analytics patterns we can use to train our ANALYZE personas and examples
- A safe executor ready to plug into whatever hook core provides
