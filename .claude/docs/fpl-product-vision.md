# FPL Tools — Product Vision

## What are we building?

An AI-powered Fantasy Premier League companion that helps you beat your friends. You chat with it in natural language. It reads your FPL data, analyzes your league, and gives you actionable advice — who to captain, who to transfer, where your rivals are vulnerable.

We own the product. We design the data, the capabilities, and the user experience.

The LLM orchestration is handled by **Alfred Core** — a package we install that turns natural language into structured database operations. Alfred Core comes with its own docs, a proven UNDERSTAND → THINK → ACT pipeline, CRUD operations, multi-step planning, and analysis capabilities. We don't build the engine. We design what it does in the FPL domain.

## Who is this for?

FPL managers who want an edge in their mini-leagues. Personal-scale today (one user, one league), architected so others can sign up later. The emotional core is **rivalry** — beating the people you know.

## MVP focus: League Rivalry

If this product could only do one thing: **"How do I beat my rivals this week?"**

This is the highest-value wedge because it's:
- **Social** — about people you know, not abstract stats
- **Recurring** — relevant every gameweek, 38 weeks a year
- **Full-path** — exercises the entire data model end to end

### What a rivalry conversation looks like

```
User: "How am I doing vs Vinay?"

→ Look up both managers from manager_links
→ Pull league standings: rank, points gap, recent trajectory
→ Pull both squads: shared players, differentials, captains
→ Pull upcoming fixtures: who has the easier run
→ Respond: standings summary, key differentials, captain risk, suggested move
```

```
User: "What transfers would help me close the gap?"

→ Identify rival's high-performing differentials
→ Find affordable replacements in my squad
→ Check fixture difficulty for next 3 GWs
→ Respond: 2-3 ranked transfer options with reasoning
```

### Surfaces that grow from this wedge

Once rivalry works, adjacent capabilities fall out naturally:

1. **Squad review** — "How's my team doing?" (rivalry minus the rival)
2. **Transfer advice** — "Who should I bring in?" (extends rivalry: what closes the gap)
3. **Player scouting** — "Tell me about Salah" (supports transfer decisions)
4. **Live gameweek** — "How's this week going?" (rivalry in real-time)

## What Alfred Core gives us

Alfred Core is an LLM orchestration engine we install as a dependency. It handles:

- **UNDERSTAND** — Parses user messages into intent + entities
- **THINK** — Plans what data to fetch and what operations to run (can be single-step or multi-step)
- **ACT** — Executes CRUD operations against Supabase and formats responses
- **Quick mode** — Simple lookups skip the full pipeline
- **Multi-turn context** — Entities and references persist across conversation turns

**Our job** is to configure Alfred Core for the FPL domain:
- Define **subdomains** (scouting, rivalry, squad management, transfers)
- Define **entities** (players, teams, fixtures, managers, leagues)
- Write **prompt content** that teaches the LLM about FPL concepts and our schema
- Map **column names and filter patterns** so the LLM generates correct queries
- Design **capability boundaries** — what Alfred can do vs. what needs new skills

Alfred Core does not know FPL. We make it know FPL.

## Our data layer

### Stack
- **Supabase** — managed PostgreSQL with REST API, Auth, and Row Level Security
- **FPL API** — unofficial Fantasy Premier League API (public, no auth, ~100 req/min)
- **Pipeline** — Python script that syncs FPL API → Supabase, handles UUID FK resolution

### 14 tables in 3 layers

**Dimensions** (reference data, shared, pipeline-managed):

| Table | What it holds | ~Rows |
|-------|--------------|-------|
| `positions` | GKP, DEF, MID, FWD | 4 |
| `teams` | 20 Premier League clubs | 20 |
| `gameweeks` | 38 gameweeks per season | 38 |
| `leagues` | Mini-leagues being tracked | ~1 |
| `players` | All PL players | ~700 |
| `fixtures` | All season matches | ~380 |

**Facts + Manager subviews** (public data, scoped by integer manager_id):

| Table | What it holds |
|-------|--------------|
| `player_gameweeks` | Per-player per-GW stats (points, xG, bonus, ICT, etc.) |
| `player_snapshots` | Price/ownership time series |
| `squads` | Manager picks per GW (XI, captain, bench) |
| `transfers` | Manager transfer history (in/out, prices) |
| `manager_seasons` | Manager GW-by-GW progression (points, rank, bank, chips) |
| `league_standings` | League table snapshots per GW |

**User-owned** (private, RLS-protected by `auth.uid()`):

| Table | What it holds |
|-------|--------------|
| `manager_links` | Which FPL managers this user tracks (primary + rivals) |
| `watchlist` | Players the user is scouting |
| `transfer_plans` | Planned transfers (not yet executed on FPL) |

### Schema patterns that matter for capability design

- **UUID PKs everywhere** — Alfred queries by UUID, not FPL integer IDs
- **Denormalized names** — `manager_name`, `league_name`, `team_name` on subview tables so Alfred doesn't need JOINs for display
- **`manager_links` is the session bridge** — on login, read this table to know which managers to scope all queries to
- **User-owned tables are writable** — Alfred can INSERT/UPDATE/DELETE watchlist and transfer_plans. Everything else is read-only (pipeline-managed).

### Column naming (critical for Alfred config)

The FPL API uses different field names than our schema. Alfred must query the schema names, never the API names.

| FPL API field | Schema column | Notes |
|---------------|--------------|-------|
| `now_cost` | `price` | API: tenths (60). Schema: millions (6.0) |
| `element_type` | `position_id` | API: integer. Schema: UUID FK |
| `team` | `team_id` | API: integer. Schema: UUID FK |
| `event` | `gameweek` | FPL calls gameweeks "events" |
| `element` | `player_id` | FPL calls players "elements" |
| `entry` | `manager_id` | FPL calls managers "entries" |

### Running the pipeline

```bash
python scripts/sync.py --test          # verify connections
python scripts/sync.py --bootstrap     # sync reference data
python scripts/sync.py --gw 25        # sync gameweek 25
python scripts/sync.py --from-gw 1    # backfill all gameweeks
```

## Capability design: what we need to build

These are the FPL-specific capabilities we design on top of Alfred Core. Each one is a combination of prompt engineering, subdomain configuration, and potentially new skills.

### Built with Alfred Core's existing CRUD + ANALYZE

| Capability | User says | Data touched |
|-----------|-----------|-------------|
| League standings | "Show me the league table" | `league_standings`, `manager_links` |
| Rival comparison | "How am I doing vs Vinay?" | `league_standings`, `squads`, `players`, `fixtures` |
| Squad review | "Show my team" | `squads`, `players`, `player_gameweeks` |
| Player lookup | "Tell me about Salah" | `players`, `player_gameweeks`, `fixtures` |
| Transfer history | "What transfers has Vinay made?" | `transfers`, `players` |
| Watchlist | "Add Salah to my watchlist" | `watchlist` (WRITE) |
| Transfer planning | "Plan: sell Haaland, buy Salah in GW26" | `transfer_plans` (WRITE) |

### Needs prompt engineering + domain reasoning (ANALYZE)

| Capability | User says | What Alfred reasons about |
|-----------|-----------|--------------------------|
| Captain advice | "Who should I captain?" | Form, fixtures, ownership, differential value |
| Transfer advice | "Who should I bring in?" | Squad gaps, fixture runs, price, rival differentials |
| Differential analysis | "What are my differentials vs the league?" | Squad overlap across league members |
| Fixture planning | "Which defenders have good fixtures?" | FDR, rotation risk, clean sheet probability |

### May need new skills beyond Alfred Core

| Capability | Why CRUD/ANALYZE isn't enough |
|-----------|-------------------------------|
| Expected points model | Needs statistical computation, not just LLM reasoning |
| Price change prediction | Needs transfer velocity data + threshold model |
| Optimal squad solver | Combinatorial optimization under budget/position constraints |
| Live gameweek tracking | Needs real-time polling, not batch sync |

These are future capabilities. Flag them, don't build them yet.

## Auth and user scoping

- **Supabase Auth** handles identity (email/password)
- **`manager_links`** bridges auth user → FPL manager IDs (primary + rivals)
- Alfred reads `manager_links` on session start to scope all queries
- **RLS** on user-owned tables. All other tables are public read.
- Demo user: `ryesvptest@gmail.com` with manager_links seeded

## Current state

| Component | Status |
|-----------|--------|
| Schema | Deployed to Supabase, all 14 tables |
| Pipeline | Working, all sync modes functional |
| Data | Reference tables populated, GW data synced |
| Demo user | Seeded with primary manager + 1 rival |
| Alfred Core integration | In progress (separate repo) |
| Frontend | None yet |

## What's next

1. **Finish Alfred domain config** — subdomains, entities, prompt content, filter patterns
2. **End-to-end test** — rivalry conversation from auth → manager_links → multi-table query → formatted response
3. **Scheduled sync** — automate pipeline after each GW deadline
4. **Backfill historical GWs** — enables trend analysis and form calculations
5. **Frontend** — chat UI that renders Alfred's responses

## Glossary

| Term | Meaning |
|------|---------|
| **GW** | Gameweek — one round of PL fixtures (38 per season) |
| **Manager** | An FPL player (human) who manages a fantasy team |
| **Mini-league** | A private league of friends competing against each other |
| **Differential** | A player owned by you but not your rival (or vice versa) |
| **Captain** | Player whose points are doubled that GW |
| **Chip** | Special power used once per season (wildcard, bench boost, triple captain, free hit) |
| **FDR** | Fixture Difficulty Rating (1-5 scale) |
| **xG** | Expected goals — statistical model of goal probability |
| **ICT** | Influence, Creativity, Threat — FPL's composite performance index |
| **BPS** | Bonus Points System — determines bonus point allocation |
| **RLS** | Row Level Security — Postgres access control per row |
| **Alfred Core** | LLM orchestration engine (installed dependency, not our code) |
| **UNDERSTAND/THINK/ACT** | Alfred Core's 3-stage pipeline for processing user messages |
