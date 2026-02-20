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
- [x] 25 contract enforcement tests passing
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

---

## What's Next

### Phase 1: Context Engineering Refinement (Current)
*Train the LLM to write correct code using real patterns.*

- [ ] Update ANALYZE personas with validated pandas patterns
- [ ] Update ANALYZE examples with working code snippets from local testing
- [ ] Tune `params_schema` strings for fpl_analyze and fpl_plot (prompt surface)
- [ ] Test with hardcoded conversation loops (simulate LLM → code → execute)
- [ ] Run notebooks against live Supabase data

### Phase 2: End-to-End Validation (Current)
*Full pipeline integration with real Alfred execution.*

- [x] `pip install alfredagain==2.1.0` — installed, ToolDefinition + ToolContext confirmed
- [x] Verify `get_custom_tools()` registration works — 111/111 tests passing
- [ ] Run full conversation through Alfred pipeline (user question → data → Python → chart)
- [ ] Validate DataFrame flow end-to-end through live pipeline
- [ ] Test error recovery: soft failures (LLM retries) vs hard failures (BlockedAction)

### Phase 3: UI / Artifact Display
*Charts and tables rendered in the frontend.*

- [ ] Chart file path → frontend rendering (PNG display)
- [ ] DataFrame summary display (tables in chat)
- [ ] Streaming: partial results while executor runs

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

**Two execution paths coexist:**
- Quick factual queries ("who's my captain?") → CRUD reads → text reply
- Analytical queries ("compare form trends") → CRUD reads → Python execution → charts + tables

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
| Core integration | `get_custom_tools()` via ToolDefinition (alfredagain 2.1.0) | Domain registers tools, core dispatches + creates ToolContext |

---

## Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| alfredagain>=2.1.0 | Core orchestration + custom tools | Installed (2.1.0) |
| supabase>=2.0.0 | Database client | Installed |
| pandas>=2.0.0 | DataFrames for analytics | Installed |
| matplotlib>=3.7.0 | Chart rendering | Installed |
| numpy>=1.24.0 | Numeric operations | Installed |
| pandera>=0.18.0 | DataFrame validation | Installed |
