# Brief: FPL Domain Spec for Alfred

## Context

You're designing the FPL (Fantasy Premier League) domain for Alfred, an
LLM orchestration engine that turns natural language into database
operations, analysis, and content generation. Alfred already powers a
kitchen/cooking domain — FPL is the second domain.

**Read this first:** `docs/bridge/alfred-domain-design-guide.md` — it
explains how Alfred works at a design level, what subdomains and entities
are, what all 6 operation types do (READ, WRITE, UPDATE, DELETE, ANALYZE,
GENERATE), and shows the kitchen domain as a complete worked example.

## How to Think About Alfred

Treat Alfred's core team as a product team you can make requests to.
Alfred currently supports:

- **CRUD** — read, write, update, delete against Supabase tables
- **ANALYZE** — LLM reasons about data already in context (no DB calls)
- **GENERATE** — LLM produces structured content for user approval before saving
- **Multi-step plans** — Think chains steps: READ → READ → ANALYZE → GENERATE
- **Quick mode** — simple lookups skip planning entirely
- **Multi-turn conversations** — entities persist across turns, iterative refinement

If FPL needs capabilities that don't fit these patterns, **flag them as
"capability requests"** — don't try to force them into CRUD. Examples:

- Running Python computations (expected points models, optimization)
- Calling external APIs (live FPL API for price changes, deadlines)
- Statistical analysis beyond what an LLM can do reliably in-context
- Any "skill" that requires domain-specific tooling beyond database reads/writes

These would require Alfred core extensions. Identifying them early is more
valuable than working around them.

## What We Need From You

### 1. Subdomain & Entity Proposal (rough)

Follow the YAML templates in the design guide. Don't over-polish — we want
the right *shape*, not perfect descriptions. For each subdomain:

- Name, primary table, related tables
- 1-2 sentence description (Think uses this to route)
- 3-5 common user queries (split: quick mode vs full pipeline)
- Key CRUD patterns (what does read/write look like here?)
- Aliases (informal names users say)

For each entity:

- type_name (short — refs appear everywhere), table, primary_field
- FK fields, complexity hint, whether to auto-include children
- Notes on what makes this entity interesting

### 2. FK Enrichment Map + User-Owned vs Reference Tables

Which FK fields exist, what they point to, which tables are per-user vs
shared reference data.

### 3. Five Test Conversations

Real conversations that would prove FPL works on Alfred. Each should be
2-3 turns showing a realistic user flow:

| # | Tests | Example Flow |
|---|-------|-------------|
| 1 | **Simple read (quick mode)** | "show my squad" → formatted squad display |
| 2 | **Filtered read** | "show midfielders under 8m" → filtered player list |
| 3 | **Multi-step analysis** | "who should I captain?" → read squad + fixtures → analyze → recommendation |
| 4 | **Write operation** | "make a transfer: sell X, buy Y" → update squad |
| 5 | **Generate (if applicable)** | "suggest a wildcard team" → generated squad → user approves/modifies → save |

For each: what the user says, what Alfred should do (step by step), what
a good response looks like, and what could go wrong.

### 4. Capability Gaps (Critical)

Where does FPL need something Alfred doesn't currently offer? Be specific:

- **Computation:** Does "who should I captain?" need a real expected-points
  calculation, or is LLM reasoning over stats good enough?
- **External data:** Does Alfred need to fetch live data (price changes,
  injury updates, deadline timers) or is the Supabase snapshot sufficient?
- **Complex analysis:** Are there workflows where LLM ANALYZE isn't
  reliable enough and you'd want deterministic Python logic?
- **Derived/virtual data:** Any "tables" that don't exist in the DB but
  should feel like they do? (e.g., "form" = rolling average of last 5 GW
  scores — computed, not stored)

Frame these as: "For [use case], Alfred would need [capability] because
[why CRUD/ANALYZE isn't enough]."

### 5. Semantic Notes + Field Enums

Domain rules the LLM must respect (budget constraints, squad rules,
transfer rules) and categorical fields with valid values.

## What NOT to Do

- Don't write Python code — you're producing a design spec
- Don't worry about prompt engineering — Alfred's core handles that
- Don't design the database schema from scratch — work from the existing
  Supabase tables
- Don't try to cover every FPL feature — start with the minimum that
  would make a useful conversation partner

## Definition of Done

A rough spec that lets the Alfred team:
1. Implement `FPLConfig` (the domain protocol — 24 required methods)
2. Run the 5 test conversations through the CLI
3. Know which core extensions to prioritize for FPL-specific capabilities