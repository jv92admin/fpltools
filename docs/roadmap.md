# Alfred FPL — Roadmap

## Vision

A BI engineer on demand. The user asks an FPL question, Alfred fetches data, writes Python, executes it, and returns tables + charts. A dynamic Jupyter notebook experience powered by LLM intelligence.

---

## Where We Are

### Done: Data Infrastructure
- [x] Database schema (14 tables in Supabase) — `sql/001_schema.sql`
- [x] Data pipeline (FPL API → Supabase with UUID FK resolution) — `src/pipeline.py`
- [x] FPL API client — `src/fpl_client.py`
- [x] CLI sync tool — `scripts/sync.py`

### Done: Domain Scaffold
- [x] 15 entity definitions (player, team, fixture, squad, etc.)
- [x] 6 subdomains (squad, scouting, market, league, live, fixtures)
- [x] All 23 DomainConfig abstract methods implemented
- [x] CRUD middleware (integer FK bridge, auto-injection, row limits, headline columns)
- [x] Per-step personas for READ / ANALYZE / GENERATE
- [x] Fallback schemas (load-bearing — LLM's only view of table structure)
- [x] 31 contract enforcement tests passing
- [x] Handoff doc for core PM

### Done: BI Library
- [x] `bi/data_access.py` — QuerySpec → DataFrame from Supabase
- [x] `bi/analytics.py` — Rolling stats, differentials, rankings (pure pandas)
- [x] `bi/viz.py` — matplotlib headless rendering → PNG
- [x] `bi/schemas.py` — Pandera validation
- [x] `bi/executor.py` — Sandboxed Python execution (restricted builtins, 30s timeout)
- [x] 60 BI tests passing (analytics + viz + schemas + executor)

### Done: Core Integration Wiring
- [x] `get_custom_tools()` — registers `fpl_analyze` and `fpl_plot` via ToolDefinition
- [x] `_execute_analysis` handler — Python code → executor → structured results
- [x] `_execute_plot` handler — matplotlib code → executor → chart file paths
- [x] DataFrame session cache in middleware (post_read → cache → tool handlers)
- [x] `get_tool_enabled_step_types()` includes "generate"
- [x] 26 custom tools integration tests (all passing with alfredagain 2.1.0)

### Done: Phase 0 — alfredagain 2.3.0 Upgrade
- [x] Upgraded from 2.1.0 to 2.3.0
- [x] Migrated from monkey-patching to official domain hooks
- [x] All prompt hooks wired: get_understand_prompt_content, get_think_domain_context, get_think_planning_guide, get_act_prompt_content, get_reply_prompt_content, get_summarize_system_prompts
- [x] format_records_for_reply — custom formatting for players, squads, fixtures, standings, player_gameweeks, player_snapshots

### Done: Phase 1-2 — E2E Smoke Testing
- [x] chat_runner.py — 12-conversation eval harness
- [x] Prompt logging (ALFRED_LOG_PROMPTS) for detailed trace inspection
- [x] Ran full eval across 12 conversations, identified failure patterns

### Done: Phase 3 — ANALYZE Sub-Type Routing
- [x] Two-phase ANALYZE pattern: Think plans "FPL Assessment:" + "Compute:" prefixes
- [x] Description-based example routing in `get_contextual_examples()`
- [x] 8 new example entries (4 assessment + 4 compute across scouting, fixtures, squad, league)
- [x] Think Planning Guide updated with two-phase patterns + trigger phrases
- [x] 6 routing unit tests

### Done: Phase 3b — Critical Fixes from E2E
- [x] **order_dir fix**: Act prompt taught `ascending` (bool) but Core uses `order_dir` ("asc"/"desc"). Pydantic silently dropped unknown field → all queries sorted ascending (worst-first). Fixed param name + added to worked example + persona default sort hint.
- [x] **GW context seeding**: `get_domain_snapshot()` now surfaces explicit `Current Gameweek: N` and `"Last 5 GWs" = GW X to Y` so Think/Act don't guess from calendar date.
- [x] **Squad format_records_for_reply fix**: Squad records showed `?` for all players because formatter looked for `web_name` (missing from squads table). Fixed to check `_player_id_label` (Core's FK enrichment) first.
- [x] **fpl_plot import fix**: GENERATE prompt strengthened with bold `**NEVER use import statements**`, negative example (`❌ import pandas` vs `✅ pd.DataFrame`), and bar chart worked example. test11 now generates charts successfully.
- [x] **Gameweek auto-injection on squads**: Middleware injected `manager_id` but not `gameweek` on squads reads. With multiple GWs synced, `ORDER BY slot LIMIT 15` returned 15 copies of slot=1 from different GWs (only 3 unique GKPs). Added `GW_SCOPED_TABLES` and auto-injection of `gameweek = current_gw` in `pre_read()`. All 15 unique players now resolve correctly.

### Done: Phase 4 — Re-Validation (12/12 Clean)
- [x] Re-ran full 12-conversation eval after all Phase 3b fixes
- [x] **test1**: 15 unique players with correct names (was: 3 repeated GKPs)
- [x] **test7**: Correct GW22-26 filter, full form analysis (was: `gameweek >= 34`)
- [x] **test11**: Bar chart generated successfully (was: sandbox crash on imports)
- [x] **test5**: Returns cheap forwards with 5GW stats (was: "no forwards qualify")
- [x] **test10**: Full captain ranking with form + FDR composite (was: 3 players only)
- [x] Pipeline coverage: 10 ANALYZE, 4 GENERATE, 4 charts across 12 tests
- [x] 117 unit tests passing

---

## What's Next

### Phase 5: Quality Polish
- [ ] Add price, form, total_points to squad execution summary (requires ANALYZE or second read)
- [ ] Improve Reply integration with ANALYZE output (test4 rival comparison — blocked by rival squad data)
- [ ] Expand eval to cover edge cases (multi-turn memory, entity resolution across turns)
- [ ] Consider syncing rival squad data for league comparison features

### Phase 6: UI / Artifact Display
- [ ] Chart file path → frontend rendering (PNG display)
- [ ] DataFrame summary display (tables in chat)
- [ ] Streaming: partial results while executor runs

---

## Core Feedback (to cascade to alfredagain PM)

1. **`DbReadParams.order_dir` default should be `"desc"`** — "asc" default means silent failure when domains teach wrong param name. Most domain queries want "top N" not "bottom N".
2. **Act should surface Core's param schema** — Auto-generate param reference from Pydantic model schema so domain prompts can't teach wrong param names.
3. **Wire `BlockedAction` → replan** — `suggested_next: "replan"` exists in state.py but `should_continue_act()` routes all BlockedActions to "reply". No graph edge from Act back to Think.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Question                         │
├─────────────────────────────────────────────────────────┤
│              Alfred Core Pipeline                        │
│   UNDERSTAND → THINK → ACT (loop) → REPLY → SUMMARIZE  │
├─────────────────────────────────────────────────────────┤
│                   Act Steps                              │
│                                                          │
│   READ           ANALYZE           GENERATE              │
│   ┌────────┐     ┌────────────┐    ┌───────────────┐    │
│   │db_read │     │fpl_analyze │    │fpl_plot        │    │
│   │(CRUD)  │     │(pandas)    │    │(matplotlib)   │    │
│   └────┬───┘     └─────┬──────┘    └──────┬────────┘    │
│        │               │                  │              │
├────────┼───────────────┼──────────────────┼──────────────┤
│        │          FPL Domain Layer         │              │
│        ▼               ▼                  ▼              │
│   ┌─────────┐    ┌──────────┐      ┌──────────┐        │
│   │Middleware│    │ Executor │      │ Executor │        │
│   │(guards) │    │(sandbox) │      │(sandbox) │        │
│   └────┬────┘    └────┬─────┘      └────┬─────┘        │
│        │              │                  │               │
│        ▼              ▼                  ▼               │
│   ┌─────────┐    ┌──────────┐      ┌──────────┐        │
│   │Supabase │    │BI Library│      │ viz.py   │        │
│   │ (data)  │    │(pandas)  │      │(charts)  │        │
│   └─────────┘    └──────────┘      └──────────┘        │
└─────────────────────────────────────────────────────────┘
```

---

## Test Summary (117 tests)

| Suite | Count | What it covers |
|-------|-------|----------------|
| `test_domain.py` | 31 | Domain wiring + contract enforcement + example routing |
| `test_bi_analytics.py` | 17 | Analytics functions (rolling, rankings, differentials) |
| `test_bi_viz.py` | 8 | Chart rendering (line, bar, heatmap, comparison) |
| `test_bi_schemas.py` | 9 | Pandera DataFrame validation |
| `test_executor.py` | 26 | Sandbox security + execution |
| `test_custom_tools.py` | 26 | Tool registration + handlers + DataFrame cache |

---

## Eval Results (Phase 4 — 12/12 Pass)

| Test | Turns | Steps | Time | Notes |
|------|-------|-------|------|-------|
| test1: Quick Squad View | 1 | READ | 17s | 15 unique players, slots 1-15 |
| test2: Scout + Compare | 2 | READ+ANALYZE | 54s | Semenyo vs Rice, 5GW comparison |
| test3: Fixture Analysis | 1 | READ+ANALYZE+GENERATE | 55s | FDR table + heatmap chart |
| test4: League Rivalry | 2 | READ+ANALYZE | 42s | Standings + squad (rival data unavailable) |
| test5: Transfer Planning | 2 | READ+ANALYZE | 60s | Cheap forwards with 5GW stats |
| test6: Market Trends | 1 | READ | 41s | Transfer-in rankings |
| test7: Player Form | 2 | READ+ANALYZE | 87s | Top 10 MIDs + GW22-26 form trends |
| test8: Fixture Heatmap | 1 | READ+ANALYZE+GENERATE | 24s | Heatmap (80KB) |
| test9: Value Comparison | 2 | READ+ANALYZE | 66s | PPM: Thiago 19.0, Calvert-Lewin 17.3 |
| test10: Captain Data | 2 | READ+ANALYZE | 114s | Form + FDR composite ranking |
| test11: Transfer Replace | 2 | READ+ANALYZE+GENERATE | 103s | Bar chart (31KB) |
| test12: Full Pipeline | 1 | READ+ANALYZE+GENERATE | 18s | Heatmap (80KB) |

**Totals:** 10 ANALYZE, 4 GENERATE, 4 charts

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| FK handling | Integer FK bridge in middleware, NOT in enrich map | Core's UUID enrichment silently fails on integer FKs |
| Data tier | ≤15 rows full context, >15 rows data card | Prevent context explosion while keeping LLM informed |
| Row limits | Per-table (players=20, pgw=50, etc.) | Balance between data richness and token cost |
| ANALYZE tools | Tool-enabled (`{"read", "write", "analyze", "generate"}`) | ANALYZE + GENERATE need Python execution |
| Entity window | 1 (aggressive eviction) | Squad reads alone register 15 entities |
| Execution model | Sandboxed exec() with restricted builtins | Safe enough for LLM-generated code, no container overhead |
| Chart rendering | matplotlib Agg backend → PNG | Deterministic, headless, well-supported |
| Core integration | `get_custom_tools()` via ToolDefinition (alfredagain 2.1.0→2.3.0) | Domain registers tools, core dispatches + creates ToolContext |
| ANALYZE sub-types | Description-based example routing via `get_examples(step_description)` | Two-phase pattern (assessment + compute) without Core changes |
| Sort default | Teach `order_dir: "desc"` in Act prompt + persona hint | Most FPL queries want "top N" — ascending sorts return bench fodder |
| GW context | Explicit `Current Gameweek: N` in domain snapshot | Prevents LLM from guessing GW from calendar date |
| GW scoping | Auto-inject `gameweek=current_gw` on squads reads | Multi-GW data without scoping returns wrong slots |

---

## Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| alfredagain>=2.3.0 | Core orchestration + hooks + custom tools | Installed (2.3.0) |
| supabase>=2.0.0 | Database client | Installed |
| pandas>=2.0.0 | DataFrames for analytics | Installed |
| matplotlib>=3.7.0 | Chart rendering | Installed |
| numpy>=1.24.0 | Numeric operations | Installed |
| pandera>=0.18.0 | DataFrame validation | Installed |
