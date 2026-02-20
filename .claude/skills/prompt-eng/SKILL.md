---
name: prompt-eng
description: FPL prompt engineering expert. Use when writing, debugging, or tuning prompts for any pipeline node (Understand, Think, Act, Reply, Summarize). Knows the full prompt assembly chain, which files control what, and proven iteration patterns.
---

# FPL Prompt Engineering

Expert knowledge for writing and tuning prompts across the Alfred pipeline. Covers prompt assembly, file routing, debugging from logs, and iteration patterns learned from E2E testing.

## Pipeline Overview

```
User message
  → UNDERSTAND  (entity resolution, context curation)
  → THINK       (step planning: what to read, analyze, generate)
  → ACT (loop)  (execute each step: db_read, fpl_analyze, fpl_plot)
  → REPLY       (synthesize results into natural language)
  → SUMMARIZE   (compress turn for memory)
```

Each node gets a system prompt assembled from multiple sources. Understanding the assembly is key to debugging.

## Prompt Assembly per Node

### UNDERSTAND
**System prompt = Core scaffold + `get_understand_system_prompt()` + `understand_content.py`**

| Source | File | What it controls |
|--------|------|-----------------|
| System prompt override | `domain/__init__.py:get_understand_system_prompt()` | One-liner role description (we removed quick mode detection) |
| Full content | `prompts/understand_content.py` → `UNDERSTAND_PROMPT_CONTENT` | Entity resolution rules, curation signals, examples, output contract |

**Injection point:** `get_understand_prompt_content()` on DomainConfig returns the full Understand template.

**Key tuning levers:**
- Resolution examples (Example 1-6) — teach it how to map "that player" → `player_3`
- Curation signals table — when to retain vs demote vs drop entities
- Output contract JSON — schema for the structured output

### THINK
**System prompt = Core Think scaffold + `get_think_domain_context()` + `get_think_planning_guide()`**

| Source | File | What it controls |
|--------|------|-----------------|
| Domain context | `prompts/think_injections.py` → `THINK_DOMAIN_CONTEXT` | What Alfred is, philosophy, tone |
| Planning guide | `prompts/think_injections.py` → `THINK_PLANNING_GUIDE` | Subdomains, data layers, read/write patterns, step types, workflow patterns |

**Key tuning levers:**
- **Step type triggers** — the "Step Types and Tools" table controls whether Think plans READ-only or READ+ANALYZE+GENERATE
- **Workflow patterns** — "Complex Workflow Patterns" section shows multi-step chains. Add new patterns here to teach Think new planning strategies
- **ANALYZE patterns table** — "What ANALYZE does / What it does NOT do" — prevents Think from planning prediction steps
- **GENERATE patterns table** — "When to Plan" column controls chart generation triggers

**Common issue:** Think doesn't plan ANALYZE steps → Strengthen trigger phrases in the planning guide. Add explicit mappings: "compare" → ANALYZE, "trend" → ANALYZE, "heatmap" → GENERATE.

### ACT
**System prompt = `get_act_prompt_content(step_type)` + persona + examples**

| Source | File | What it controls |
|--------|------|-----------------|
| Full Act template | `prompts/act_content.py` → `get_act_content(step_type)` | Base principles + step-type-specific tools, rules, worked examples |
| Subdomain persona | `prompts/personas.py` → `get_persona_for_subdomain()` | Per-subdomain × per-step expert role |
| Contextual examples | `prompts/examples.py` → `get_contextual_examples()` | Few-shot examples keyed by `subdomain:step_type`, with description-based routing for analyze sub-types |
| Subdomain header | `domain/__init__.py:get_act_subdomain_header()` | Combines persona + semantic notes |

**Act content is split by step_type:**
- `_READ` = base + CRUD tools + read examples
- `_ANALYZE` = base + fpl_analyze tool + DataFrame reference + analytics functions + worked examples
- `_GENERATE` = base + fpl_plot tool + DataFrame reference + chart functions + worked examples
- `_WRITE` = base + CRUD tools + write rules

**Key tuning levers:**
- **DataFrame Column Reference** — CRITICAL. Lists exact enriched column names. If the LLM uses wrong column names, Python throws KeyError. Update this when enrichment changes.
- **Worked examples** — The highest-impact thing in Act. A concrete worked example of the heatmap unstack pattern teaches more than any instruction.
- **Personas** — Shape reasoning style. Scouting:analyze persona says "compute pts/£m, rank by composite". Fixtures:analyze says "pivot into team × GW FDR grid".
- **Contextual examples** — Few-shot examples selected by subdomain+step_type. Second highest impact after worked examples.

**Common issue:** LLM generates bad Python → Check DataFrame Column Reference is accurate, add a worked example for the failing pattern, check persona mentions the right helpers.

### REPLY
**System prompt = `get_system_prompt()` + `get_reply_prompt_content()`**

| Source | File | What it controls |
|--------|------|-----------------|
| System prompt | `prompts/system.md` | Alfred's identity and tone |
| Reply template | `prompts/reply_content.py` → `REPLY_PROMPT_CONTENT` | Formatting rules per subdomain, chart integration, analysis integration, what NOT to do |

**Key tuning levers:**
- **Subdomain formatting sections** — Squad, Scouting, Market, League, Live, Fixtures each have a template showing exactly how to format that data type
- **Chart integration** — Rules for when charts are present vs absent
- **Analysis integration** — How to narrate ANALYZE step output
- **"What NOT to Do"** — Negative examples (don't mention tools, don't predict, don't recommend)

**Common issue:** Reply doesn't use analysis output → Check execution_summary format in Core's `reply.py:_format_execution_summary()`. The analysis dict must flow through cleanly. Also check Reply's "Analysis Integration" section.

### SUMMARIZE
**System prompt = `get_summarize_system_prompts()` → `{"response_summary": ..., "turn_compression": ...}`**

| Source | File | What it controls |
|--------|------|-----------------|
| Both prompts | `domain/__init__.py:get_summarize_system_prompts()` | How turns are compressed for memory |

**Key tuning levers:**
- Proposal vs completed distinction — prevents "I'll do X" from being summarized as "did X"
- Exact entity name preservation — prevents "Salah" becoming "Mo" in summaries

## File Routing: "Where Do I Fix This?"

| Symptom | Root cause | File to edit |
|---------|-----------|-------------|
| Think plans READ-only when ANALYZE is needed | Missing trigger in planning guide | `prompts/think_injections.py` → THINK_PLANNING_GUIDE |
| Think plans too many steps | Workflow pattern too aggressive | `prompts/think_injections.py` → Complex Workflow Patterns |
| Act uses wrong column names | DataFrame Column Reference stale | `prompts/act_content.py` → _ANALYZE or _GENERATE |
| Act generates bad Python syntax | Missing worked example | `prompts/act_content.py` → Worked Examples |
| Act doesn't use analytics helpers | Persona doesn't mention them | `prompts/personas.py` → subdomain:analyze |
| Act queries wrong table | Read example misleading | `prompts/examples.py` → subdomain:read |
| Reply ignores analysis output | Reply template missing guidance | `prompts/reply_content.py` → Analysis Integration |
| Reply shows raw JSON instead of tables | Missing subdomain format | `prompts/reply_content.py` → Subdomain Formatting |
| Reply mentions tools/process | "What NOT to Do" insufficient | `prompts/reply_content.py` |
| Entity references break across turns | Understand curation wrong | `prompts/understand_content.py` |
| Kitchen-domain leaks in any node | Hook not implemented or Core fallback | `domain/__init__.py` → check `get_*()` method exists |
| ANALYZE ignores FPL domain logic | Missing assessment examples | `prompts/examples.py` → `{subdomain}:analyze:assessment` |
| ANALYZE Python is generic/wrong | Missing compute examples | `prompts/examples.py` → `{subdomain}:analyze:compute` |
| Think plans single ANALYZE when two needed | Missing two-phase pattern | `prompts/think_injections.py` → Two-Phase ANALYZE |
| Queries return wrong sort order | Param name mismatch with Core Pydantic model | `prompts/act_content.py` → tool param table, verify against `DbReadParams` |

## Debugging from prompt_logs/

Each eval run creates a timestamped directory under `prompt_logs/`. Files are numbered sequentially:

```
prompt_logs/20260220_104428/
  01_understand.md    ← Entity resolution output
  02_think.md         ← Step plan (READ/ANALYZE/GENERATE steps)
  03_act.md           ← First step execution (usually READ)
  04_act.md           ← Second step (maybe another READ)
  05_act.md           ← Third step (ANALYZE or GENERATE)
  06_reply.md         ← Final synthesis
  07_summarize.md     ← Turn compression
```

**Reading a log file:**
1. Check "System Prompt" section — is it FPL-specific or kitchen-leaked?
2. Check "User Prompt" section — what context did the node receive?
3. Check "Response" section — what did the LLM produce?
4. For Act: look at tool calls in the response — correct tool? correct params? correct column names?
5. For Act errors: look at tool result — KeyError? Empty DataFrame? Timeout?

**Multi-turn conversations:** Each turn adds more numbered files. Turn 2 starts where Turn 1 left off.

## Iteration Patterns (Proven)

### Pattern 1: Column Name Alignment
**Problem:** LLM uses `_home_team_id_label` (entity display column) instead of `home_team_name` (enriched DataFrame column).
**Fix:** Added DataFrame Column Reference section to both ANALYZE and GENERATE in `act_content.py`. Explicit: "Use `home_team_name` (NOT `_home_team_id_label`)".
**Lesson:** When enrichment adds/changes columns, ALWAYS update the Column Reference in act_content.py.

### Pattern 2: Worked Example > Instruction
**Problem:** Heatmap generation failed 3 times with wrong column names and wrong pivot pattern.
**Fix:** Replaced the broken worked example with a complete, tested code snippet showing the exact unstack → concat → pivot_table → render_heatmap flow.
**Lesson:** One correct worked example teaches more than paragraphs of instructions. Make worked examples self-contained and copy-pasteable.

### Pattern 3: Negative Examples in "What NOT to Do"
**Problem:** Reply says "I queried the database and found..." or "I recommend you captain Salah".
**Fix:** Explicit negative list in reply_content.py: "Don't mention tools", "Don't predict", "Don't recommend".
**Lesson:** LLMs respond well to explicit "never do X" lists. Put them near the end of the prompt where they have high recency weight.

### Pattern 4: Persona Drives Tool Selection
**Problem:** Act doesn't use `compute_fixture_difficulty()` helper for fixture analysis.
**Fix:** Updated fixtures:analyze persona to explicitly mention the helper and when to use it.
**Lesson:** Personas are where you mention specific functions. The Act base template mentions tools exist; the persona says which ones to use for this subdomain.

### Pattern 5: Think Trigger Phrases
**Problem:** "compare the top 2" doesn't trigger an ANALYZE step — Think plans READ-only.
**Fix:** Added explicit trigger mappings to THINK_PLANNING_GUIDE: compare → ANALYZE, trend → ANALYZE, heatmap → GENERATE.
**Lesson:** Think needs explicit signal words mapped to step types. Implicit reasoning ("comparison needs computation") isn't reliable.

### Pattern 6: Description-Based Example Routing (ANALYZE Sub-Types)
**Problem:** ANALYZE steps need both FPL domain intelligence AND Python computation, but get the same generic examples regardless of intent.
**Fix:** Think plans two analyze steps with description prefixes. `get_examples()` detects the prefix and returns different worked examples.
**Convention:** "FPL Assessment:" → domain examples, "Compute:" → Python examples.
**Key format:** `{subdomain}:analyze:assessment`, `{subdomain}:analyze:compute`
**Lesson:** `get_examples(step_description)` is the ONLY Act hook that receives the step description. Use it as the primary routing mechanism. System prompt and persona are the same for all analyze steps — examples are where sub-types diverge.

### Pattern 7: Param Name Verification Against Core Pydantic Models
**Problem:** Act prompt taught `ascending` (bool, default false) for sort direction. Core's `DbReadParams` uses `order_dir` (Literal "asc"/"desc", default "asc"). Pydantic silently drops unknown fields, so every query defaulted to ascending sort — returning bench fodder first instead of top performers.
**Fix:** Renamed param in act_content.py to match Core's exact field name (`order_dir`), added `"order_dir": "desc"` to worked example, added default sort hint to scouting:read persona.
**Impact:** test9 went from comparing 0-minute £4.5m players to comparing Thiago (133pts), João Pedro (132pts), Bowen (120pts). Time dropped from 80s to 43s.
**Lesson:** ALWAYS verify that param names taught in Act prompts match Core's actual Pydantic model field names. Pydantic `model_init` silently drops unknown fields — no error, no warning. Check `alfred/tools/crud.py:DbReadParams` for db_read params. When adding worked examples, use exact param names from the model.

## Prompt Quality Checklist

When writing or reviewing any prompt file:

1. **No kitchen references** — search for "milk", "eggs", "recipe", "Mediterranean", "chickpea"
2. **Correct column names** — match enriched DataFrame columns, not raw DB or entity labels
3. **Worked examples are self-contained** — can be copy-pasted into executor and run
4. **Negative examples present** — explicit "don't do X" for common failure modes
5. **Step type boundaries respected** — READ prompts don't mention fpl_analyze, ANALYZE prompts don't mention db_read
6. **Personas mention specific helpers** — analytics functions, chart functions by name
7. **Examples use FPL entities** — player names (Salah, Haaland), team names (ARS, LIV), not generic "item_1"
8. **Output contracts are JSON** — structured schemas, not prose descriptions
9. **Tool param names match Core Pydantic models** — verify against `DbReadParams`, `DbWriteParams` etc. Pydantic silently drops unknown fields

## Hook Coverage (alfredagain 2.3.x)

| Hook | FPL implements? | File |
|------|----------------|------|
| `get_system_prompt()` | Yes | `prompts/system.md` |
| `get_understand_system_prompt()` | Yes | `domain/__init__.py` |
| `get_understand_prompt_content()` | Yes | `prompts/understand_content.py` |
| `get_think_domain_context()` | Yes | `prompts/think_injections.py` |
| `get_think_planning_guide()` | Yes | `prompts/think_injections.py` |
| `get_act_prompt_content(step_type)` | Yes | `prompts/act_content.py` |
| `get_reply_prompt_content()` | Yes | `prompts/reply_content.py` |
| `get_filter_schema()` | Yes (2.3.0) | `domain/__init__.py` |
| `get_summarize_system_prompts()` | Yes (2.3.0) | `domain/__init__.py` |
| `get_persona()` | Yes | `prompts/personas.py` |
| `get_examples()` | Yes | `prompts/examples.py` |
| `format_records_for_reply()` | Yes | `domain/__init__.py` (players, squads, fixtures, standings, pgw, snapshots) |

When working on $ARGUMENTS, identify which pipeline node is involved, find the controlling file from the tables above, read the current content, and apply the iteration patterns.
