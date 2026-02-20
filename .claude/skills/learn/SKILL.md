---
name: learn
description: Capture a discovery from experimentation and propagate it to the right places — skills, domain prompts, tests. Use after finding a working analytics pattern, a new FPL insight, or a domain contract issue.
---

# Learn — Capture and Propagate Discoveries

When experimenting (Jupyter, CLI, evals), we discover things that should be codified. This skill routes a discovery to the right files.

## How to use

```
/learn "rolling 3-GW form is better than 5-GW for identifying streaks"
/learn "heatmap needs team short names not UUIDs on the y-axis"
/learn "manager_name ilike filter works better than exact match for name resolution"
```

## Routing Rules

Given a discovery about $ARGUMENTS, determine its category and propagate:

### 1. Analytics Pattern (pandas code that works)
**Update these files:**
- `.claude/skills/bi-code/SKILL.md` — Add to "Code Patterns" section
- `src/alfred_fpl/domain/prompts/examples.py` — Add to relevant `subdomain:analyze` examples
- `src/alfred_fpl/bi/analytics.py` — If it's a reusable function, add it

**Example:** "groupby player_id + rolling(3) on total_points gives cleaner trends than rolling(5)"
→ Update bi-code skill with the pattern
→ Add as ANALYZE example for scouting subdomain
→ Consider making default window=3 in `add_rolling_mean`

### 2. Visualization Insight (chart style that works)
**Update these files:**
- `.claude/skills/viz-review/SKILL.md` — Add to standards or common issues
- `src/alfred_fpl/domain/prompts/personas.py` — Update GENERATE personas
- `src/alfred_fpl/bi/viz.py` — If it's a rendering fix, update the code

**Example:** "horizontal bar charts need at least 0.5 inch per bar for readability"
→ Update viz-review with the guideline
→ Update GENERATE persona: "use horizontal bars when >5 categories"

### 3. FPL Domain Rule (scoring, strategy, data interpretation)
**Update these files:**
- `.claude/skills/fpl/SKILL.md` — Add to relevant section
- `src/alfred_fpl/domain/schema.py` — Update SEMANTIC_NOTES for the subdomain
- `src/alfred_fpl/domain/prompts/personas.py` — Update relevant READ/ANALYZE persona

**Example:** "FDR 1-2 = easy, 3 = neutral, 4-5 = hard — but home FDR is consistently ~0.5 easier than away"
→ Update fpl skill FDR section
→ Update fixtures SEMANTIC_NOTES
→ Update fixtures ANALYZE persona

### 4. Domain Contract Issue (something that breaks silently)
**Update these files:**
- `.claude/skills/alfred-api/SKILL.md` — Add to "Implicit Contracts" section
- `tests/test_domain.py` — Add a contract enforcement test
- `src/alfred_fpl/domain/__init__.py` — Fix the implementation if needed

**Example:** "compute_entity_label must never return empty string — breaks ref display"
→ Add to alfred-api contracts
→ Add test: `assert label != ""`
→ Verify our implementation has fallback to ref

### 5. Data Quality Issue (schema/pipeline finding)
**Update these files:**
- `src/alfred_fpl/bi/schemas.py` — Update Pandera validation
- `src/alfred_fpl/domain/schema.py` — Update FALLBACK_SCHEMAS if column semantics changed
- `.claude/skills/fpl/SKILL.md` — Note the data quirk

**Example:** "player_snapshots.price can be 0.0 for players who left the league"
→ Update Pandera schema: price range (0, 20) → allow 0
→ Note in fpl skill: "price=0 means player is no longer in the game"

### 6. Architecture / Documentation Change (new feature, structural change, integration)
**Update these files:**
- `docs/architecture/overview.md` — Update system diagram, data flow, or doc map
- `docs/architecture/domain-integration.md` — Update if DomainConfig, tools, or middleware changed
- `docs/architecture/bi-execution.md` — Update if executor, analytics, or viz changed
- `docs/roadmap.md` — Mark items done, add new phases/milestones
- `README.md` — Update data model, quick start, or architecture summary
- `CLAUDE.md` — Update key files, test counts, architecture diagram

**Example:** "wired fpl_analyze and fpl_plot custom tools via alfredagain 2.1.0"
→ Update architecture/overview.md system diagram (add custom tool paths)
→ Update architecture/domain-integration.md (add custom tools section)
→ Update roadmap.md (mark integration wiring as done)
→ Update README.md architecture section
→ Update CLAUDE.md test count and architecture diagram

## Process

For each discovery about $ARGUMENTS:

1. **Classify** — Which category above?
2. **Read** — Read the target files to understand current state
3. **Update skill** — Add the knowledge to the relevant `.claude/skills/*/SKILL.md`
4. **Update domain prompts** — Propagate to `prompts/personas.py` and/or `prompts/examples.py`
5. **Update code/tests** if applicable
6. **Run tests** — `pytest tests/ -v` to verify nothing broke

## Skill → Prompt Mapping (complete reference)

```
.claude/skills/bi-code/SKILL.md
  "Code Patterns" section
    → src/alfred_fpl/domain/prompts/examples.py
      Keys: "scouting:analyze", "league:analyze", "live:analyze", etc.

.claude/skills/viz-review/SKILL.md
  "Required Standards" section
    → src/alfred_fpl/domain/prompts/personas.py
      Step type: "generate" for all subdomains

.claude/skills/fpl/SKILL.md
  Domain rules sections
    → src/alfred_fpl/domain/schema.py
      SEMANTIC_NOTES dict, keyed by subdomain name
    → src/alfred_fpl/domain/prompts/personas.py
      Step type: "read" and "analyze" per subdomain

.claude/skills/alfred-api/SKILL.md
  "Implicit Contracts" section
    → tests/test_domain.py
      Contract enforcement test group

docs/architecture/*.md
  System diagrams, integration details, execution docs
    → README.md (summary view)
    → CLAUDE.md (key files, test counts, architecture diagram)
    → docs/roadmap.md (milestones, phases)
```

The skills are living documents. They evolve with every experiment. The domain prompts are their compiled output — what the LLM actually sees at runtime. Architecture docs are the system's memory — they must stay current with every structural change.
