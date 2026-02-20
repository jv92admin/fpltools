---
name: alfred-api
description: Alfred Core DomainConfig API expert. Use when implementing or modifying domain methods, middleware, entity definitions, or subdomain configuration.
---

# Alfred Core — DomainConfig API Reference

Reference for implementing domain methods. Core lives in `alfred-core/` (READ-ONLY). Our implementation is in `src/alfred_fpl/domain/`.

## DomainConfig — 23 Abstract Methods

### Core Properties (3)
```python
@property
def name(self) -> str                                    # "fpl"
@property
def entities(self) -> dict[str, EntityDefinition]        # 15 entities
@property
def subdomains(self) -> dict[str, SubdomainDefinition]   # 6 subdomains
```

### Prompt / Persona (2)
```python
def get_persona(self, subdomain: str, step_type: str) -> str
def get_examples(self, subdomain: str, step_type: str, step_description: str = "", prev_subdomain: str | None = None) -> str
```

**Description-based routing:** `step_description` enables sub-type routing within a step_type. FPL uses this for ANALYZE: "FPL Assessment:" prefix → domain examples, "Compute:" prefix → Python examples. Key format: `"{subdomain}:analyze:assessment"` or `"{subdomain}:analyze:compute"`. Fallback: no prefix match → uses generic `"{subdomain}:analyze"` key. This is the ONLY Act hook that receives the step description — use it as the primary routing mechanism for sub-types.

### Schema / FK (11)
```python
def get_table_format(self, table: str) -> dict[str, Any]
def get_empty_response(self, subdomain: str) -> str
def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]    # UUID FKs ONLY
def get_field_enums(self) -> dict[str, dict[str, list[str]]]  # all values must be strings
def get_semantic_notes(self) -> dict[str, str]                 # keyed by subdomain name
def get_fallback_schemas(self) -> dict[str, str]               # LOAD-BEARING for us
def get_scope_config(self) -> dict[str, dict]
def get_user_owned_tables(self) -> set[str]
def get_uuid_fields(self) -> set[str]
def get_subdomain_registry(self) -> dict[str, dict]
def get_subdomain_examples(self) -> dict[str, str]             # must be str, not list
```

### Entity Processing (4)
```python
def infer_entity_type_from_artifact(self, artifact: dict) -> str
def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str  # never empty
def get_subdomain_aliases(self) -> dict[str, str]
def get_subdomain_formatters(self) -> dict[str, Callable]
```

### Mode / Agent (2)
```python
@property
def bypass_modes(self) -> dict[str, type]   # {} for us (not using bypass)
@property
def default_agent(self) -> str              # "main"
```

### Handoff / DB (2)
```python
def get_handoff_result_model(self) -> type
def get_db_adapter(self)
```

## Custom Tools (alfredagain >= 2.1.0)

```python
from alfred.domain.base import ToolDefinition, ToolContext

def get_custom_tools(self) -> dict[str, ToolDefinition]:
    return {
        "fpl_analyze": ToolDefinition(
            name="fpl_analyze",
            description="Execute Python analysis on FPL DataFrames",
            params_schema="`code` (str): Python code, `datasets` (list[str]): DataFrame refs",
            handler=self._execute_analysis,
        ),
        "fpl_plot": ToolDefinition(
            name="fpl_plot",
            description="Render matplotlib chart to PNG",
            params_schema="`code` (str): matplotlib code, `title` (str): chart title",
            handler=self._execute_plot,
        ),
    }

# Handler signature: async (params: dict, user_id: str, ctx: ToolContext) -> Any
# ToolContext provides: ctx.step_results, ctx.registry, ctx.current_step_results, ctx.state
# Soft failure: return {"error": msg} — LLM retries (MAX_TOOL_CALLS_PER_STEP=3)
# Hard failure: raise exception — becomes BlockedAction, step terminates
```

## Critical Optional Overrides

```python
def get_crud_middleware(self) -> CRUDMiddleware | None     # SINGLETON — same instance each call
def get_system_prompt(self) -> str
def get_entity_recency_window(self) -> int                 # We use 1 (aggressive)
def get_tool_enabled_step_types(self) -> set[str]          # {"read", "write", "analyze", "generate"}
def compute_entity_label_from_fks(self, entity_type, fk_labels, ref) -> str
def infer_table_from_record(self, record: dict) -> str | None
def get_strip_fields(self, context: str = "injection") -> set[str]
def get_act_subdomain_header(self, subdomain: str, step_type: str) -> str
async def get_domain_snapshot(self, user_id: str) -> str
def detect_detail_level(self, entity_type: str, record: dict) -> str | None
def get_priority_fields(self) -> list[str]
```

## Prompt Override Hooks (alfredagain >= 2.3.0)

These hooks replace core's hardcoded prompts (which contain kitchen-domain examples) with domain-specific content. Each returns a string that replaces the core template entirely.

```python
# Replace core's filter schema examples (kitchen: "milk", "eggs" → FPL: "gameweek", "price")
def get_filter_schema(self) -> str:
    """Return full filter syntax reference with domain-specific examples."""
    return "## Filter Syntax\n| Operator | Example | ..."

# Replace core's Understand system prompt (removes quick mode detection for FPL)
def get_understand_system_prompt(self) -> str:
    """One-liner role description for Understand node."""
    return "You are Alfred's MEMORY MANAGER. Your job: (1) resolve entity references..."

# Replace core's Summarize prompts (kitchen: "I'll save the recipes" → FPL: "Showed squad")
def get_summarize_system_prompts(self) -> dict[str, str]:
    """Return two prompts: 'response_summary' and 'turn_compression'."""
    return {
        "response_summary": "Summarize what was accomplished in ONE sentence...",
        "turn_compression": "Summarize this conversation exchange in ONE brief sentence...",
    }

# Full prompt replacements (existed pre-2.3.0)
def get_act_prompt_content(self, step_type: str) -> str       # Replaces core's act base.md + crud.md + step_type.md
def get_reply_prompt_content(self) -> str                      # Replaces core's reply.md template
def get_understand_prompt_content(self) -> str                 # Replaces core's understand content
def get_think_domain_context(self) -> str                      # Injected into Think as <alfred_context>
def get_think_planning_guide(self) -> str                      # Injected into Think as planning reference
```

**Hook behavior:** Core checks `domain.get_*()` first. If it returns a truthy string, that replaces the core template. If falsy/empty, Core falls back to its built-in template (which has kitchen-domain examples).

**Caching note:** Reply hook result is cached at module level (`_REPLY_PROMPT` global in `reply.py`). Once set, it persists for the process lifetime. This is fine for single-domain processes but means you can't switch domains mid-process.

## EntityDefinition
```python
EntityDefinition(
    type_name="player",           # Must match table.rstrip("s") where possible
    table="players",
    primary_field="web_name",     # Used for search
    fk_fields=["team_id", "position_id"],
    complexity="high",            # Optional: "low"|"medium"|"high"
    label_fields=["web_name"],    # Fields used to build human-readable labels
    detail_tracking=True,         # Optional: enables detail-level tracking
)
```

## CRUDMiddleware
```python
class CRUDMiddleware(ABC):
    async def pre_read(self, params, user_id) -> ReadPreprocessResult
    async def pre_write(self, table, records) -> list[dict]
    async def post_read(self, records, table, user_id) -> list[dict]
    def deduplicate_batch(self, table, records) -> list[dict]
```

## Implicit Contracts (Section 11 of implementation guide)

1. **FK enrich map**: UUID FKs ONLY. Integer FKs (manager_id, league_id) cause silent failure
2. **Field enum values**: Must be strings (core does `', '.join`)
3. **Subdomain examples**: Must be `str`, not `list[str]`
4. **Semantic notes**: Must be keyed by subdomain name
5. **type_name**: Should match `table.rstrip("s")` (core's fallback)
6. **label_fields**: Must appear in fallback schemas
7. **Fallback schemas**: Must mention `id` column
8. **Middleware**: `get_crud_middleware()` must return same instance (singleton)
9. **Tool-enabled steps**: Include "analyze" and "generate" for Python execution + chart rendering
10. **Entity recency window**: Set to 1 for high-volume domains (squad = 15 entities)
11. **Custom tools**: `get_custom_tools()` returns `{}` by default — override to register domain tools
12. **DataFrame cache**: Middleware `post_read` stashes DataFrames for tool handlers via session cache
13. **DataFrame enrichment**: Raw DataFrames have UUID FK columns. LLM-generated code needs human-readable names. Enrich DataFrames BEFORE passing to executor (e.g., `home_team_id` UUID → `home_team_name` short string). Bootstrap the mapping at session start in `get_domain_snapshot()`.
14. **Reply prompt caching**: Core caches `_REPLY_PROMPT` at module level in `reply.py`. Once set, it persists for the process. Domain hook is only called once per process.
15. **Hook fallback**: All prompt hooks follow the pattern: Core calls `domain.get_*()`, if truthy uses it, otherwise falls back to built-in template. Return empty string to get Core's default.
16. **Example routing via step_description**: `get_examples()` receives the Think step description. Domain can parse prefixes/keywords to return different examples for the same step_type. This is the primary mechanism for analyze sub-typing (no Core changes needed).
17. **Act prompt param names must match Core Pydantic models**: Core unpacks LLM tool-call JSON directly into Pydantic models (e.g., `DbReadParams(**params)`). Pydantic **silently drops** unknown fields. If the Act prompt teaches `ascending` (bool) but the model field is `order_dir` (Literal), the LLM sends an unknown field that gets dropped and the default kicks in. Always verify param names in Act prompts against Core's actual Pydantic model fields in `alfred/tools/crud.py`. Key fields: `order_by` (str), `order_dir` ("asc"/"desc", default "asc"), `limit` (int), `filters` (list[dict]).

## Pipeline Flow
```
UNDERSTAND → THINK → ACT (loop) → REPLY → SUMMARIZE
                      │
            ┌─────────┼─────────┐
            READ    ANALYZE   GENERATE
            │         │          │
         db_read   fpl_analyze  fpl_plot
         (CRUD)    (+ CRUD)    (+ CRUD)
            │         │          │
         Middleware  Executor   Executor
         (guards)   (sandbox)  (sandbox)
```

When working on $ARGUMENTS, reference:
- Our implementation: `src/alfred_fpl/domain/__init__.py`
- Core protocol: `alfred-core/src/alfred/domain/base.py` (read-only)
- Tests: `tests/test_domain.py` (25 contract tests)
