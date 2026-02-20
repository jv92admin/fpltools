# FPL Tools — Project Context

## What this repo is

Data infrastructure + Alfred domain package for an FPL (Fantasy Premier League) BI agent. This repo owns:
1. **Database schema** and **data pipeline** (FPL API → Supabase)
2. **Alfred FPL domain** — the DomainConfig that teaches Alfred what FPL is
3. **BI library** — pandas analytics, matplotlib charts, sandboxed Python executor

Alfred Core (`alfredagain` on PyPI, imported as `alfred`) is the orchestration engine. We don't modify it.

## Key files

### Data layer
- `sql/001_schema.sql` — Single source of truth for the database (14 tables)
- `src/pipeline.py` — Data pipeline: FPL API → Supabase (UUID FK resolution)
- `src/database.py` — Thin persistence layer (upsert methods)
- `src/fpl_client.py` — FPL API wrapper (HTTP client, data classes)
- `src/config.py` — Configuration from `.env`
- `scripts/sync.py` — CLI entry point for running syncs
- `scripts/seed_demo.py` — Seeds a demo auth user + manager_links

### Alfred domain (`src/alfred_fpl/`)
- `domain/__init__.py` — FPLConfig: all 23 DomainConfig methods + optional overrides
- `domain/schema.py` — Fallback schemas, field enums, semantic notes, subdomain registry
- `domain/crud_middleware.py` — Integer FK bridge, auto-injection, per-table guardrails
- `domain/formatters.py` — Record formatting, data cards (two-tier model)
- `domain/prompts/system.md` — System prompt
- `domain/prompts/personas.py` — Per-subdomain × per-step-type personas
- `domain/prompts/examples.py` — Contextual examples bank

### BI library (`src/alfred_fpl/bi/`)
- `bi/data_access.py` — QuerySpec → DataFrame from Supabase, enriched views
- `bi/analytics.py` — Rolling stats, differentials, fixture difficulty, rankings
- `bi/viz.py` — matplotlib headless rendering (line, bar, heatmap, comparison)
- `bi/schemas.py` — Pandera DataFrame validation
- `bi/executor.py` — Sandboxed Python executor for LLM-generated code

### Docs
- `.claude/docs/fpl-product-vision.md` — Product vision and schema reference
- `docs/architecture/overview.md` — System diagram, data flow, doc map (hub document)
- `docs/architecture/domain-integration.md` — DomainConfig, custom tools, middleware, DataFrame cache
- `docs/architecture/bi-execution.md` — Executor, analytics, viz, validation
- `docs/reference/fpl-api.md` — FPL API endpoints and response shapes
- `docs/decisions/handoff-core-pm.md` — Handoff to alfred-core PM (what we needed from core)
- `docs/decisions/handoff-core-reply.md` — Core PM reply: ships get_custom_tools() in alfredagain 2.1.0
- `docs/roadmap.md` — Current roadmap and milestones

### Tests (111 total)
- `tests/test_domain.py` — 25 domain contract tests
- `tests/test_bi_analytics.py` — 17 analytics function tests
- `tests/test_bi_viz.py` — 8 chart rendering tests
- `tests/test_bi_schemas.py` — 9 Pandera validation tests
- `tests/test_executor.py` — 26 executor sandbox tests
- `tests/test_custom_tools.py` — 26 custom tools integration tests (ToolDefinition, handlers, DataFrame cache)

## Conventions

- **Table names**: clean (e.g., `players`, `teams`). No `dim_`/`fact_` prefixes.
- **Primary keys**: UUID on every table (`id UUID PRIMARY KEY DEFAULT gen_random_uuid()`)
- **FPL API IDs**: stored as `fpl_id INTEGER` (natural key), never used as PK
- **FK columns**: UUID references (e.g., `team_id UUID REFERENCES teams(id)`)
- **Manager/league IDs**: integer `manager_id`/`league_id` on subview tables (managers are not in our DB)
- **Denormalized names**: `manager_name`, `league_name`, `team_name` on subview tables
- **Column naming**: schema uses domain-friendly names, NOT FPL API field names. `price` not `now_cost`. `gameweek` not `event`. `player_id` not `element`.

## Database: Supabase (PostgreSQL)

- Connection via Supabase Python SDK (REST API, not direct Postgres)
- Credentials in `.env`: `SUPABASE_URL`, `SUPABASE_KEY`
- RLS enabled on user-owned tables only (`manager_links`, `watchlist`, `transfer_plans`)
- All other tables are public read

## Running things

### Data pipeline
```bash
python scripts/sync.py --test          # verify connections
python scripts/sync.py --bootstrap     # sync reference data (positions, teams, players, fixtures)
python scripts/sync.py --gw 25        # sync a specific gameweek
python scripts/sync.py --from-gw 1    # backfill from GW 1 to current
```

### Tests
```bash
pytest tests/ -v                       # all 111 tests (no Supabase needed)
pytest tests/test_domain.py -v         # domain contract tests only
pytest tests/test_bi_analytics.py -v   # BI analytics only
pytest tests/test_executor.py -v       # executor sandbox only
```

### BI CLI
```bash
python scripts/bi_cli.py players --top 10 --metric form
python scripts/bi_cli.py players --top 5 --metric total_points --position MID --chart
python scripts/bi_cli.py fixtures --team ARS --gws 5
python scripts/bi_cli.py execute "top = rank_by(df_players, 'form', n=5); print(top[['web_name','form']])"
```

### Jupyter
```bash
jupyter notebook notebooks/bi_demo.ipynb
```

## Architecture

```
User question → Alfred Core Pipeline (UNDERSTAND → THINK → ACT → REPLY)
                    │
                    ├── READ: db_read via CRUD tools (middleware enforces guardrails)
                    ├── ANALYZE: fpl_analyze custom tool → sandboxed Python executor
                    └── GENERATE: fpl_plot custom tool → matplotlib charts → PNG paths
                    │
                    ▼
              FPL Domain Layer
              ├── DomainConfig (15 entities, 6 subdomains, 23 methods + custom tools)
              ├── CRUD Middleware (integer FK bridge, auto-injection, limits, DataFrame cache)
              └── BI Library (data_access, analytics, viz, executor)
                    │
                    ▼
              Supabase (14 tables)
```

## What NOT to do

- Do not rename schema columns to match FPL API field names
- Do not add integer FK columns — use UUID FKs, resolve in the pipeline
- Do not modify alfred-core or alfred-fpl-reference (read-only submodules)
- Do not modify `.env` values without checking `scripts/seed_demo.py`
- Do not put integer FKs (manager_id, league_id) in `get_fk_enrich_map()` — they cause silent failure in core's UUID enrichment
