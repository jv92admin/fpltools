# FPL Tools

A Fantasy Premier League companion app focused on **content** and **execution** — helping you plan smarter and enjoy the FPL experience more.

## Project Structure

```
fpltools/
├── src/                    # Core Python modules
│   ├── config.py           # Configuration management
│   ├── fpl_client.py       # FPL API client
│   ├── database.py         # Supabase database client
│   └── pipeline.py         # Data ingestion pipeline
├── scripts/                # Runnable scripts
│   ├── sync.py             # Main data sync script
│   └── test_fpl_api.py     # API test script (no DB needed)
├── sql/                    # Database migrations
│   └── 001_initial_schema.sql
├── references/             # Documentation & notes
├── requirements.txt
└── env.example             # Environment template
```

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/jv92admin/fpltools.git
cd fpltools

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy template
cp env.example .env

# Edit .env with your values:
# - SUPABASE_URL: From Supabase dashboard > Settings > API
# - SUPABASE_KEY: The "anon public" key
# - FPL_DEFAULT_LEAGUE_ID: Your mini-league ID (from FPL URL)
# - FPL_DEFAULT_MANAGER_ID: Your manager ID (optional, for testing)
```

> **Note:** The FPL_DEFAULT_* variables are development defaults. In a production 
> app with users, these would be stored per-user in the database.

### 3. Setup Database

1. Create a new project in [Supabase](https://supabase.com)
2. Go to SQL Editor
3. Run the contents of `sql/001_initial_schema.sql`

### 4. Test Connection

```bash
# Test FPL API (no database needed)
python scripts/test_fpl_api.py

# Test full connection (FPL + Supabase)
python scripts/sync.py --test
```

### 5. Run Sync

```bash
# Full sync (bootstrap + current gameweek)
python scripts/sync.py

# Bootstrap only (players, teams, fixtures)
python scripts/sync.py --bootstrap

# Specific gameweek
python scripts/sync.py --gameweek 15
```

## For Collaborators

Once you have access to the Supabase project:

1. Get the credentials from the project owner
2. Add them to your `.env` file
3. You can now query the database directly:
   - Via Supabase dashboard (SQL Editor)
   - Via Python (`src/database.py`)
   - Via Supabase REST API

The data pipeline runs on one machine and pushes to Supabase. Everyone queries the same data.

## Data Model

### Dimension Tables (Reference Data)
- `dim_teams` — 20 Premier League clubs
- `dim_positions` — GK, DEF, MID, FWD
- `dim_gameweeks` — 38 gameweeks per season
- `dim_players` — ~700 players with current stats

### Fact Tables (Time-Series Data)
- `fact_player_gw` — Player stats per gameweek
- `fact_fixtures` — Match results
- `fact_manager_picks` — Manager team selections
- `fact_league_standings` — League snapshots over time

## API Reference

### FPL Endpoints Used

| Endpoint | Description | Rate |
|----------|-------------|------|
| `bootstrap-static/` | All players, teams, gameweeks | Cache for hours |
| `event/{gw}/live/` | Live stats for all players | Per gameweek |
| `fixtures/` | All fixtures | Cache for hours |
| `entry/{id}/` | Manager profile | Per manager |
| `entry/{id}/event/{gw}/picks/` | Manager picks | Per manager/GW |
| `leagues-classic/{id}/standings/` | League standings | Paginated |

### Top Managers

To get top X managers from the overall league:

```python
from src.fpl_client import FPLClient

client = FPLClient()
top_100 = client.get_top_managers(100)
top_10k = client.get_top_managers(10000)  # ~200 API calls, rate limited
```

## Development

```bash
# Run tests
pytest

# Lint
pip install ruff
ruff check src/
```

## License

MIT

