# Reply: Core PM → FPL Domain Team

**From:** Alfred-core PM
**To:** FPL domain team
**Date:** 2026-02-19
**Status:** Shipped in `alfredagain 2.1.0`

---

## Summary

Everything you asked for in your handoff is now live. `pip install alfredagain==2.1.0` (you already have it).

Two new DomainConfig extension points ship in this release:

1. **`get_tool_enabled_step_types()`** — controls WHEN tools are available per step type
2. **`get_custom_tools()`** — registers domain-specific tools alongside built-in CRUD

These are the two orthogonal axes you need: WHEN (step types) and WHICH (tool names).

---

## Answers to Your Open Questions

| # | Your Question | Answer |
|---|---------------|--------|
| 1 | **Tool registration** — `get_custom_tools()` on DomainConfig? | Yes, exactly this. Ships as `get_custom_tools() -> dict[str, ToolDefinition]`. Your "Alternative" proposal (section 3 of your handoff) is what we built. |
| 2 | **DataFrame passing** — how does data move from READ to executor? | Domain-side concern. Your CRUD middleware captures DataFrames during READ (before JSON serialization), stashes them in a session-scoped cache. Your custom tool handler pulls from that cache via `ToolContext.step_results`. No core change needed. |
| 3 | **Image/file return** — how do charts come back? | Domain handler returns file paths in the result dict. Frontend renders them. No new `StreamEvent` type needed for MVP. Tool results are JSON-serializable dicts — put paths or base64 strings in them. |
| 4 | **Step type control** — per-tool or per-step-type? | `get_tool_enabled_step_types()` gates ALL tools (CRUD + custom) per step type. Override to `{"read", "write", "analyze", "generate"}` to get your custom tools in ANALYZE and GENERATE steps. Per-tool-per-step filtering is deferred — you get all registered tools in all tool-enabled step types. |
| 5 | **Error recovery** — retry in Act or replan in Think? | Domain handler chooses. Return an error dict for soft failure (LLM retries within `MAX_TOOL_CALLS_PER_STEP=3` in the same Act step). Raise an exception for hard failure (becomes `BlockedAction`, step terminates). Your "max 2 retry" pattern maps to this — the LLM sees the error in context and can fix the code. |
| 6 | **Timeline** | Now. |

---

## How to Use It

### Step 1: Enable tools in ANALYZE and GENERATE steps

```python
def get_tool_enabled_step_types(self) -> set[str]:
    return {"read", "write", "analyze", "generate"}
```

### Step 2: Register your tools

```python
from alfred.domain.base import ToolDefinition, ToolContext

def get_custom_tools(self) -> dict[str, ToolDefinition]:
    return {
        "fpl_analyze": ToolDefinition(
            name="fpl_analyze",
            description="Execute Python analysis on FPL DataFrames",
            params_schema="`code` (str): Python code, `datasets` (list[str]): DataFrame refs to load",
            handler=self._execute_analysis,
        ),
        "fpl_plot": ToolDefinition(
            name="fpl_plot",
            description="Render a matplotlib chart headlessly to PNG",
            params_schema="`code` (str): matplotlib code, `title` (str): chart title",
            handler=self._execute_plot,
        ),
    }
```

### Step 3: Implement handlers

Handler signature: `async (params: dict, user_id: str, context: ToolContext) -> Any`

```python
async def _execute_analysis(self, params: dict, user_id: str, ctx: ToolContext) -> dict:
    code = params["code"]
    dataset_refs = params.get("datasets", [])

    # Load DataFrames from your session cache (domain-side)
    dfs = self._load_dataframes(dataset_refs, ctx.step_results)

    # Run in your sandboxed executor (domain-side)
    result = await self._executor.run(code, dfs)

    if result.error:
        # Soft failure — return error dict, LLM retries
        return {"error": result.error, "traceback": result.traceback}

    return {
        "stdout": result.stdout,
        "result_summary": str(result.result)[:500],
        "dataframes": {name: df.head().to_string() for name, df in result.dataframes.items()},
    }
```

`ToolContext` gives you:
- `ctx.registry` — SessionIdRegistry for ref/UUID translation if needed
- `ctx.step_results` — results from prior steps (for DataFrame lookup)
- `ctx.current_step_results` — tool results from current step so far
- `ctx.state` — full pipeline state (read-only by convention)

### What the LLM sees

When tools are enabled for a step type, Act prompts automatically include:
- `crud.md` (built-in CRUD reference)
- A **Domain Tools Reference** table generated from your `ToolDefinition` descriptions
- The decision template with your custom tools as options:
  ```
  - Execute Python analysis on FPL DataFrames → {"action": "tool_call", "tool": "fpl_analyze", "params": {...}}
  ```

---

## Where to Find the Code

Since you have `alfredagain==2.1.0` installed, the source is in your venv. Key files:

| What | Where (in `alfredagain` package) |
|------|----------------------------------|
| `ToolDefinition` + `ToolContext` dataclasses | `alfred/domain/base.py` — search for `class ToolDefinition` |
| `get_custom_tools()` default method | `alfred/domain/base.py` — search for `get_custom_tools` |
| Custom tool dispatch logic | `alfred/graph/nodes/act.py` — search for `custom_tools` |
| Decision prompt injection | `alfred/prompts/injection.py` — search for `custom_tools` |
| Domain implementation guide | `alfred-core` repo: `docs/architecture/domain-implementation-guide.md` § "Custom Tools" |

To browse the installed source:

```bash
python -c "import alfred; print(alfred.__file__)"
# → .../site-packages/alfred/__init__.py
# Browse that directory for the modules above
```

---

## What Core Does vs What You Own

| Concern | Core | FPL Domain |
|---------|------|------------|
| Tool registration | `get_custom_tools()` protocol | Tool definitions + handler implementations |
| Tool dispatch | Routes by name, creates `ToolContext` | — |
| Step type gating | `get_tool_enabled_step_types()` protocol | Override to include analyze/generate |
| Prompt injection | Generates "Domain Tools Reference" table | `description` + `params_schema` strings |
| Error handling | Soft failure (retry) vs hard failure (BlockedAction) | Handler chooses which to use |
| Sandboxing | — | Executor implementation, builtins whitelist |
| DataFrame storage | — | Session cache, middleware capture |
| Chart rendering | — | Matplotlib Agg backend, file management |
| Result formatting | Generic JSON truncation in context | Return dict structure |

---

## What Does NOT Change

- CRUD tools (`db_read`, `db_create`, `db_update`, `db_delete`) — unchanged, always available in tool-enabled steps
- `MAX_TOOL_CALLS_PER_STEP` (3) — applies to ALL tools equally (CRUD + custom)
- Kitchen domain — unaffected, `get_custom_tools()` returns `{}` by default
- Your existing 25 tests — should still pass, no breaking changes
