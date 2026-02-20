# FPL Tools

Data infrastructure + Alfred domain for a Fantasy Premier League BI agent. Users ask FPL questions, Alfred fetches data, writes Python, executes it, and returns tables + charts.

## What's In This Repo

| Layer | What | Key Files |
|-------|------|-----------|
| **Data pipeline** | FPL API → Supabase (14 tables, UUID FKs) | `src/pipeline.py`, `sql/001_schema.sql` |
| **Domain scaffold** | DomainConfig for Alfred (23 methods, 6 subdomains, 15 entities) | `src/alfred_fpl/domain/` |
| **BI library** | Pandas analytics, matplotlib charts, sandboxed Python executor | `src/alfred_fpl/bi/` |
| **Custom tools** | `fpl_analyze` + `fpl_plot` registered via alfredagain 2.1.0 | `src/alfred_fpl/domain/__init__.py` |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/jv92admin/fpltools.git
cd fpltools
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env: SUPABASE_URL, SUPABASE_KEY

# Test (no Supabase needed)
pytest tests/ -v              # 111 tests

# Sync data
python scripts/sync.py --test       # verify connections
python scripts/sync.py --bootstrap  # sync reference data
python scripts/sync.py --gw 25     # sync a specific gameweek
```

## Data Model

### Reference Tables
- `teams` — 20 Premier League clubs
- `positions` — GKP, DEF, MID, FWD
- `gameweeks` — 38 gameweeks per season
- `players` — ~700 players with current stats
- `leagues` — Mini-leagues

### Fact Tables
- `fixtures` — Match results and FDR ratings
- `player_gameweeks` — Player stats per gameweek
- `player_snapshots` — Price/ownership snapshots over time
- `squads` — Manager team selections (15 slots per GW)
- `transfers` — Historical transfers
- `manager_seasons` — GW-by-GW manager progression
- `league_standings` — League table snapshots

### User-Owned Tables (RLS)
- `manager_links` — Links auth users to FPL manager IDs
- `watchlist` — Player watchlist
- `transfer_plans` — Planned transfers

## Architecture

See [docs/architecture/overview.md](docs/architecture/overview.md) for the full system diagram.

```
User question → Alfred Core (UNDERSTAND → THINK → ACT → REPLY)
                  │
                  ├── READ: db_read → CRUD middleware → Supabase
                  ├── ANALYZE: fpl_analyze → sandboxed executor → pandas
                  └── GENERATE: fpl_plot → sandboxed executor → matplotlib → PNG
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [Architecture Overview](docs/architecture/overview.md) | System diagram, data flow, doc map |
| [Domain Integration](docs/architecture/domain-integration.md) | DomainConfig, custom tools, middleware |
| [BI Execution](docs/architecture/bi-execution.md) | Executor, analytics, visualization |
| [Roadmap](docs/roadmap.md) | Current phase and what's next |
| [FPL API Reference](docs/reference/fpl-api.md) | FPL API endpoints and response shapes |

## License

MIT
