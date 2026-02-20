# Architecture Overview

Alfred FPL is a BI agent domain built on [alfredagain](https://pypi.org/project/alfredagain/) (Alfred Core). Users ask FPL questions, Alfred fetches data, writes Python, executes it, and returns tables + charts.

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      User Question                           │
├─────────────────────────────────────────────────────────────┤
│                Alfred Core Pipeline                          │
│   UNDERSTAND → THINK → ACT (loop) → REPLY → SUMMARIZE      │
├─────────────────────────────────────────────────────────────┤
│                      Act Steps                               │
│                                                              │
│   READ              ANALYZE             GENERATE             │
│   ┌──────────┐      ┌──────────────┐   ┌──────────────┐    │
│   │ db_read  │      │ fpl_analyze  │   │ fpl_plot     │    │
│   │ (CRUD)   │      │ (Python)     │   │ (matplotlib) │    │
│   └────┬─────┘      └──────┬───────┘   └──────┬───────┘    │
│        │                   │                   │             │
├────────┼───────────────────┼───────────────────┼─────────────┤
│        │          FPL Domain Layer              │             │
│        ▼                   ▼                   ▼             │
│   ┌──────────┐      ┌──────────┐        ┌──────────┐       │
│   │Middleware │      │ Executor │        │ Executor │       │
│   │(guards)  │      │(sandbox) │        │(sandbox) │       │
│   │          │      │          │        │          │       │
│   │• FK      │      │• pd, np  │        │• render_ │       │
│   │  bridge  │      │• BI fns  │        │  funcs   │       │
│   │• limits  │      │• 30s     │        │• PNG out │       │
│   │• columns │      │  timeout │        │          │       │
│   └────┬─────┘      └────┬─────┘        └────┬─────┘       │
│        │    DataFrame     │                   │              │
│        │    cache ────────┘                   │              │
│        ▼                                      ▼              │
│   ┌──────────────────────────────────────────────┐          │
│   │              Supabase (14 tables)             │          │
│   └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Two Execution Paths

| Query Type | Example | Flow |
|-----------|---------|------|
| Quick factual | "Who's my captain?" | READ → REPLY |
| Analytical | "Compare Salah and Saka's form trends" | READ → ANALYZE → GENERATE → REPLY |

## Data Flow: READ → ANALYZE → GENERATE

1. **READ**: `db_read` fetches records from Supabase. Middleware enforces row limits, injects default filters, translates integer FKs. `post_read` caches records as DataFrames.
2. **ANALYZE**: `fpl_analyze` tool receives Python code from the LLM. Handler loads cached DataFrames into the sandboxed executor. Code runs against pd, np, and BI library functions.
3. **GENERATE**: `fpl_plot` tool receives matplotlib code. Executor renders charts headlessly (Agg backend) to PNG. File paths return in the result dict.

## Documentation Map

| Doc | What | When to read |
|-----|------|-------------|
| **[Domain Integration](domain-integration.md)** | DomainConfig, custom tools, middleware, DataFrame cache | Modifying domain methods or tool handlers |
| **[BI Execution](bi-execution.md)** | Executor sandbox, analytics functions, viz pipeline | Modifying analytics, chart rendering, or safety |
| **[Roadmap](../roadmap.md)** | Current phase, what's done, what's next | Planning work |
| **[FPL API Reference](../reference/fpl-api.md)** | FPL API endpoints, response shapes, rate limits | Working with the data pipeline |
| **[Handoff → Core PM](../decisions/handoff-core-pm.md)** | What we asked for from Alfred Core | Historical context |
| **[Core PM Reply](../decisions/handoff-core-reply.md)** | What core shipped (ToolDefinition API) | Understanding the integration contract |

## Key Numbers

- **14 tables** in Supabase (4 reference, 5 fact, 2 tracking, 3 user-owned)
- **15 entity definitions** with UUID FK resolution
- **6 subdomains**: squad, scouting, market, league, live, fixtures
- **23 abstract methods** + optional overrides on DomainConfig
- **2 custom tools**: `fpl_analyze` (Python), `fpl_plot` (matplotlib)
- **111 tests** passing (domain + BI + executor + integration)
