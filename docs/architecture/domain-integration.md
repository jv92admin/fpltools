# Domain Integration

How the FPL domain plugs into Alfred Core. Covers DomainConfig, custom tools, CRUD middleware, and DataFrame flow.

## DomainConfig: FPLConfig

**File:** `src/alfred_fpl/domain/__init__.py`
**Singleton:** `FPL_DOMAIN = FPLConfig()`

FPLConfig implements all 23 abstract methods of `DomainConfig` (from `alfred.domain.base`). The full method list is in the [alfred-api skill](../../.claude/skills/alfred-api/SKILL.md).

### Key Overrides

| Method | Value | Why |
|--------|-------|-----|
| `get_tool_enabled_step_types()` | `{"read", "write", "analyze", "generate"}` | Enable custom tools in ANALYZE + GENERATE |
| `get_entity_recency_window()` | `1` | Aggressive eviction — squad reads register 15 entities |
| `get_crud_middleware()` | `FPLMiddleware()` (singleton) | Integer FK bridge, auto-injection, row limits |
| `get_custom_tools()` | `{"fpl_analyze": ..., "fpl_plot": ...}` | Python execution + chart rendering |

## Custom Tools (alfredagain >= 2.1.0)

Registered via `get_custom_tools()` → `dict[str, ToolDefinition]`.

### fpl_analyze

- **Purpose:** Execute Python analysis against FPL DataFrames
- **Params:** `code` (str), `datasets` (list[str])
- **Handler:** `FPLConfig._execute_analysis`
- **Returns:** `{"stdout", "result_summary", "dataframes", "charts"}` or `{"error", "traceback"}`

### fpl_plot

- **Purpose:** Render matplotlib charts headlessly to PNG
- **Params:** `code` (str), `title` (str)
- **Handler:** `FPLConfig._execute_plot`
- **Returns:** `{"title", "charts", "stdout"}` or `{"error"}`

### Handler Contract

```python
# Signature (from alfred.domain.base)
async def handler(params: dict, user_id: str, ctx: ToolContext) -> Any

# ToolContext provides:
ctx.step_results       # Results from prior steps (for DataFrame lookup)
ctx.registry           # SessionIdRegistry for ref/UUID translation
ctx.current_step_results  # Tool results from current step so far
ctx.state              # Full pipeline state (read-only by convention)
```

### Error Handling

| Strategy | How | When |
|----------|-----|------|
| **Soft failure** | Return `{"error": msg}` | Code syntax errors, runtime errors, bad data. LLM sees the error and retries (up to `MAX_TOOL_CALLS_PER_STEP=3`). |
| **Hard failure** | Raise an exception | Unrecoverable errors. Becomes `BlockedAction`, step terminates. |

## CRUD Middleware

**File:** `src/alfred_fpl/domain/crud_middleware.py`
**Class:** `FPLMiddleware(CRUDMiddleware)`

Must be singleton — `get_crud_middleware()` returns same instance every call. Preserves bridge dict state and DataFrame cache across CRUD calls within a session.

### pre_read Pipeline

```
LLM emits db_read params
  → Strip null filter values
  → Translate UUID refs → integer IDs (manager_id, league_id)
  → Auto-inject primary manager_id on manager-scoped tables
  → Auto-inject league_id on league-scoped tables
  → Enforce required filters on high-volume tables (player_gameweeks, player_snapshots)
  → Apply default row limits (players=20, fixtures=30, squads=15, etc.)
  → Apply headline column selection (strip noise from large tables)
```

### post_read Pipeline

```
Records return from Supabase
  → Cache as DataFrame (self._dataframe_cache[table] = pd.DataFrame(records))
  → Return records unchanged
```

### Integer FK Bridge

The FPL schema has integer FKs (`manager_id`, `league_id`) that core's UUID-based enrichment cannot handle. The middleware maintains bridge dicts:

```python
self._manager_bridge: dict[str, int]  # UUID → FPL integer manager_id
self._league_bridge: dict[str, int]   # UUID → FPL integer league_id
```

Populated at session start by `get_domain_snapshot()` from `manager_links` table.

## DataFrame Session Cache

Data flows from READ steps to ANALYZE/GENERATE steps through the middleware cache:

```
READ step
  → db_read fetches records from Supabase
  → middleware.post_read() caches pd.DataFrame(records) keyed by table name

ANALYZE step
  → LLM calls fpl_analyze with datasets: ["players", "fixtures"]
  → _load_dataframes() pulls from middleware cache
  → Executor receives context: {"df_players": DataFrame, "df_fixtures": DataFrame}

GENERATE step
  → LLM calls fpl_plot
  → All cached DataFrames automatically available as df_<table>
```

### Cache Semantics

- **Key:** Table name (e.g., `"players"`, `"fixtures"`)
- **Value:** `pd.DataFrame` from most recent read of that table
- **Lifetime:** Per-session (middleware is singleton)
- **Overwrites:** Last read of same table wins
- **Clear:** `middleware.clear_dataframe_cache()` between sessions

## Subdomains

| Name | Primary Table | What It Handles |
|------|--------------|-----------------|
| squad | squads | Squad browsing, formation, captain, bench order |
| scouting | players | Player search, comparison, form, watchlist |
| market | player_snapshots | Transfers, price tracking, ownership trends |
| league | league_standings | Mini-league standings, rivalry, differentials |
| live | player_gameweeks | Live GW performance, bonus, auto-sub |
| fixtures | fixtures | Schedule, FDR, blank/double gameweeks |

## Tests

- **25 domain contract tests** (`tests/test_domain.py`) — entity wiring, FK safety, schema completeness
- **26 custom tools tests** (`tests/test_custom_tools.py`) — registration, cache, handlers, error paths
