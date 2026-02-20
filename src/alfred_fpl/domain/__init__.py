"""FPL Domain Configuration.

Implements all 23 abstract methods of DomainConfig plus critical optional
overrides for the FPL BI agent domain.

Usage:
    from alfred_fpl.domain import FPL_DOMAIN

    table = FPL_DOMAIN.type_to_table["player"]  # "players"

Architecture:
    - READ steps: fetch data via db_read with per-table guardrails (middleware)
    - ANALYZE steps: write Python (pandas) against fetched data
    - GENERATE steps: structure output as tables/comparisons/artifacts
    - REPLY: narrative commentary on structured output

The two-tier data model:
    - Small results (<=15 rows): full entity-registered records in context
    - Large results (>15 rows): data card (schema + sample + stats) in context,
      full DataFrame available to Python executor
"""

import logging
from pathlib import Path
from typing import Any, Callable

from alfred.domain.base import (
    DomainConfig,
    EntityDefinition,
    SubdomainDefinition,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Entities (from Questionnaire Q2)
#
# CONTRACT: type_name should match table.rstrip("s") where possible.
# CONTRACT: Every table with UUID FK columns needs an EntityDefinition.
# =============================================================================

ENTITIES: dict[str, EntityDefinition] = {
    # --- Core reference data ---
    "players": EntityDefinition(
        type_name="player",
        table="players",
        primary_field="web_name",
        fk_fields=["team_id", "position_id"],
        complexity="high",
        label_fields=["web_name"],
        detail_tracking=True,
    ),
    "teams": EntityDefinition(
        type_name="team",
        table="teams",
        primary_field="short_name",
        fk_fields=[],
        label_fields=["short_name"],
    ),
    "positions": EntityDefinition(
        type_name="position",
        table="positions",
        primary_field="short_name",
        fk_fields=[],
        label_fields=["short_name"],
    ),
    "gameweeks": EntityDefinition(
        type_name="gw",
        table="gameweeks",
        primary_field="name",
        fk_fields=[],
        label_fields=["name"],
    ),
    "leagues": EntityDefinition(
        type_name="league",
        table="leagues",
        primary_field="name",
        fk_fields=[],
        label_fields=["name"],
    ),
    # --- Fixtures ---
    "fixtures": EntityDefinition(
        type_name="fix",
        table="fixtures",
        primary_field="home_team_id",
        fk_fields=["home_team_id", "away_team_id"],
        label_fields=["home_team_id", "away_team_id"],
    ),
    # --- Squad / performance ---
    "squads": EntityDefinition(
        type_name="squad",
        table="squads",
        primary_field="player_id",
        fk_fields=["player_id"],
        label_fields=["player_id"],
    ),
    "player_gameweeks": EntityDefinition(
        type_name="pgw",
        table="player_gameweeks",
        primary_field="player_id",
        fk_fields=["player_id"],
        label_fields=["player_id"],
    ),
    "player_snapshots": EntityDefinition(
        type_name="snap",
        table="player_snapshots",
        primary_field="player_id",
        fk_fields=["player_id"],
        label_fields=["player_id"],
    ),
    # --- Transfer tracking ---
    "transfers": EntityDefinition(
        type_name="xfer",
        table="transfers",
        primary_field="player_in_id",
        fk_fields=["player_in_id", "player_out_id"],
        label_fields=["player_in_id", "player_out_id"],
    ),
    "transfer_plans": EntityDefinition(
        type_name="plan",
        table="transfer_plans",
        primary_field="player_in_id",
        fk_fields=["player_in_id", "player_out_id"],
        label_fields=["player_in_id", "player_out_id"],
    ),
    # --- League standings ---
    "league_standings": EntityDefinition(
        type_name="standing",
        table="league_standings",
        primary_field="manager_name",
        fk_fields=[],
        label_fields=["manager_name", "team_name"],
    ),
    # --- Manager seasons (GW-by-GW progression) ---
    "manager_seasons": EntityDefinition(
        type_name="mszn",
        table="manager_seasons",
        primary_field="manager_name",
        fk_fields=[],
        label_fields=["manager_name"],
    ),
    # --- User-owned ---
    "manager_links": EntityDefinition(
        type_name="mgr",
        table="manager_links",
        primary_field="label",
        fk_fields=[],
        label_fields=["label"],
    ),
    "watchlist": EntityDefinition(
        type_name="watch",
        table="watchlist",
        primary_field="player_id",
        fk_fields=["player_id"],
        label_fields=["player_id"],
    ),
}


# =============================================================================
# Subdomains (from Questionnaire Q3)
# =============================================================================

SUBDOMAINS: dict[str, SubdomainDefinition] = {
    "squad": SubdomainDefinition(
        name="squad",
        primary_table="squads",
        related_tables=[
            "players", "teams", "positions",
            "gameweeks", "manager_seasons", "manager_links",
        ],
        description=(
            "Squad browsing and analysis. View current 15-player squad, "
            "check formation, captain choices, bench order, squad value. "
            "Users say: 'show my team', 'who's my captain', 'my bench'."
        ),
    ),
    "scouting": SubdomainDefinition(
        name="scouting",
        primary_table="players",
        related_tables=[
            "teams", "positions", "player_gameweeks",
            "player_snapshots", "fixtures", "gameweeks", "watchlist",
        ],
        description=(
            "Player exploration and comparison. Search by stats, form, "
            "fixtures, ownership, price. Compare players with derived metrics "
            "(pts/m, rolling form, fixture difficulty). "
            "Users say: 'midfielders under 8m', 'compare Salah and Saka', "
            "'who has the best form', 'add to watchlist'."
        ),
    ),
    "market": SubdomainDefinition(
        name="market",
        primary_table="player_snapshots",
        related_tables=[
            "players", "teams", "transfers",
            "transfer_plans", "manager_seasons",
        ],
        description=(
            "Transfer market activity. Historical transfers, planned moves, "
            "price tracking, ownership trends, team value management. "
            "Users say: 'Vinay's transfers', 'who should I bring in', "
            "'Salah price history', 'plan a transfer'."
        ),
    ),
    "league": SubdomainDefinition(
        name="league",
        primary_table="league_standings",
        related_tables=[
            "leagues", "squads", "manager_seasons",
            "players", "teams", "gameweeks", "manager_links",
        ],
        description=(
            "Mini-league standings and rivalry analysis. Rank comparison, "
            "points gap, differential picks, captain divergence, chip timing. "
            "Users say: 'show the league table', 'how am I doing vs Vinay', "
            "'who are my rivals', 'league standings'."
        ),
    ),
    "live": SubdomainDefinition(
        name="live",
        primary_table="player_gameweeks",
        related_tables=[
            "squads", "players", "teams",
            "fixtures", "gameweeks", "manager_links",
        ],
        description=(
            "Live gameweek performance. Real-time points, bonus projection, "
            "auto-sub scenarios, comparison vs GW average and rivals. "
            "Users say: 'how's this week going', 'live points', "
            "'what's the average', 'bonus projections'."
        ),
    ),
    "fixtures": SubdomainDefinition(
        name="fixtures",
        primary_table="fixtures",
        related_tables=["teams", "gameweeks"],
        description=(
            "Fixture schedule and difficulty analysis. Upcoming matches, "
            "FDR ratings, fixture difficulty runs, blank/double gameweeks. "
            "Users say: 'Arsenal fixtures', 'easiest fixtures next 5 GWs', "
            "'fixture difficulty', 'any doubles coming up'."
        ),
    ),
}


# =============================================================================
# Handoff result model
# =============================================================================

def _get_handoff_result_model():
    from pydantic import BaseModel, Field
    from typing import Literal

    class FPLHandoffResult(BaseModel):
        summary: str = Field(description="Session summary.")
        action: Literal["save", "update", "close"] = Field(
            description="Recommended follow-up action."
        )
        action_detail: str = Field(description="What specifically to do.")

    return FPLHandoffResult


# =============================================================================
# FPLConfig — implements all 23 abstract methods
# =============================================================================

class FPLConfig(DomainConfig):
    """FPL domain configuration for Alfred's BI agent.

    Delegates to submodules:
    - schema.py: fallback schemas, field enums, semantic notes, registry
    - crud_middleware.py: integer FK bridge, auto-injection, guardrails
    - formatters.py: strip fields, record formatting, data cards
    - prompts/: system prompt, personas, examples
    """

    # === Core Properties (3 abstract) ===

    @property
    def name(self) -> str:
        return "fpl"

    @property
    def entities(self) -> dict[str, EntityDefinition]:
        return ENTITIES

    @property
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        return SUBDOMAINS

    # === Prompt / Persona (2 abstract) ===

    def get_persona(self, subdomain: str, step_type: str) -> str:
        from alfred_fpl.domain.prompts.personas import get_persona_for_subdomain
        return get_persona_for_subdomain(subdomain, step_type)

    def get_examples(
        self,
        subdomain: str,
        step_type: str,
        step_description: str = "",
        prev_subdomain: str | None = None,
    ) -> str:
        from alfred_fpl.domain.prompts.examples import get_contextual_examples
        return get_contextual_examples(
            subdomain=subdomain,
            step_type=step_type,
            step_description=step_description,
            prev_subdomain=prev_subdomain,
        )

    # === Schema / FK (11 abstract) ===

    def get_table_format(self, table: str) -> dict[str, Any]:
        return {}

    def get_empty_response(self, subdomain: str) -> str:
        from alfred_fpl.domain.schema import EMPTY_RESPONSES
        return EMPTY_RESPONSES.get(subdomain, "No data found.")

    def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]:
        """FK field -> (target_table, name_column) for lazy enrichment.

        CONTRACT: UUID FKs ONLY. manager_id and league_id are integers
        and are excluded — they cause silent failure in core's UUID-based
        WHERE id IN (values) enrichment. Integer FKs are handled by
        middleware post_read and denormalized name columns.
        """
        return {
            "team_id": ("teams", "short_name"),
            "position_id": ("positions", "short_name"),
            "home_team_id": ("teams", "short_name"),
            "away_team_id": ("teams", "short_name"),
            "player_id": ("players", "web_name"),
            "player_in_id": ("players", "web_name"),
            "player_out_id": ("players", "web_name"),
        }

    def get_field_enums(self) -> dict[str, dict[str, list[str]]]:
        from alfred_fpl.domain.schema import FIELD_ENUMS
        return FIELD_ENUMS

    def get_semantic_notes(self) -> dict[str, str]:
        from alfred_fpl.domain.schema import SEMANTIC_NOTES
        return SEMANTIC_NOTES

    def get_fallback_schemas(self) -> dict[str, str]:
        """Load-bearing: our Supabase does NOT have get_table_columns RPC.

        These schemas are the LLM's only view of table structure. They must
        include column names, types, and semantic comments because the LLM
        uses them to write both CRUD filters AND Python (pandas) code.
        """
        from alfred_fpl.domain.schema import FALLBACK_SCHEMAS
        return FALLBACK_SCHEMAS

    def get_scope_config(self) -> dict[str, dict]:
        return {}

    def get_user_owned_tables(self) -> set[str]:
        from alfred_fpl.domain.crud_middleware import USER_OWNED_TABLES
        return USER_OWNED_TABLES

    def get_uuid_fields(self) -> set[str]:
        from alfred_fpl.domain.crud_middleware import UUID_FIELDS
        return UUID_FIELDS

    def get_subdomain_registry(self) -> dict[str, dict]:
        from alfred_fpl.domain.schema import SUBDOMAIN_REGISTRY
        return SUBDOMAIN_REGISTRY

    def get_subdomain_examples(self) -> dict[str, str]:
        """CONTRACT: Must return dict[str, str], NOT dict[str, list[str]]."""
        from alfred_fpl.domain.schema import SUBDOMAIN_EXAMPLES
        return SUBDOMAIN_EXAMPLES

    # === Entity Processing (4 abstract) ===

    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        if "player_in_id" in artifact and "player_out_id" in artifact:
            if "created_at" in artifact or "notes" in artifact:
                return "plan"
            return "xfer"
        if "player_id" in artifact and ("notes" in artifact or "target_price" in artifact):
            if "gameweek" not in artifact and "total_points" not in artifact:
                return "watch"
        if "player_id" in artifact and "gameweek" in artifact:
            if "total_points" in artifact or "minutes" in artifact:
                return "pgw"
            if "price" in artifact or "selected_by_percent" in artifact:
                return "snap"
            return "pgw"
        if "home_team_id" in artifact and "away_team_id" in artifact:
            return "fix"
        if any(k in artifact for k in ("web_name", "total_points", "price")):
            return "player"
        if "short_name" in artifact and len(artifact.get("short_name", "")) <= 3:
            return "team"
        if "manager_id" in artifact and "label" in artifact:
            return "mgr"
        if "league_id" in artifact and "name" in artifact:
            return "league"
        if "manager_name" in artifact and "rank" in artifact:
            return "standing"
        return "player"

    def compute_entity_label(
        self, record: dict, entity_type: str, ref: str
    ) -> str:
        """CONTRACT: never return empty string — return ref as fallback."""
        if entity_type == "player" and record.get("web_name"):
            return record["web_name"]
        if entity_type == "team" and record.get("short_name"):
            return record["short_name"]
        if entity_type == "position" and record.get("short_name"):
            return record["short_name"]
        if entity_type == "gw" and record.get("name"):
            return record["name"]
        if entity_type == "mgr" and record.get("label"):
            return record["label"]
        if entity_type == "league" and record.get("name"):
            return record["name"]
        if entity_type == "standing" and record.get("manager_name"):
            team = record.get("team_name", "")
            return f"{record['manager_name']} ({team})" if team else record["manager_name"]
        if entity_type == "mszn" and record.get("manager_name"):
            return record["manager_name"]
        for field in ("web_name", "short_name", "name", "label", "manager_name"):
            if record.get(field):
                return record[field]
        return ref

    def get_subdomain_aliases(self) -> dict[str, str]:
        return {
            "team": "squad", "my team": "squad", "pick": "squad",
            "picks": "squad", "captain": "squad", "bench": "squad",
            "lineup": "squad", "starting": "squad", "selection": "squad",
            "formation": "squad",
            "player": "scouting", "players": "scouting",
            "scout": "scouting", "stats": "scouting", "form": "scouting",
            "compare": "scouting", "watchlist": "scouting",
            "comparison": "scouting",
            "transfer": "market", "transfers": "market",
            "trades": "market", "buy": "market", "sell": "market",
            "price": "market", "prices": "market", "value": "market",
            "wildcard": "market", "free hit": "market",
            "mini-league": "league", "mini league": "league",
            "rival": "league", "rivals": "league", "standings": "league",
            "league_standings": "league", "league standings": "league",
            "h2h": "league", "head to head": "league",
            "differential": "league", "differentials": "league",
            "gameweek": "live", "gw": "live", "points": "live",
            "bonus": "live", "bps": "live", "autosub": "live",
            "live": "live", "score": "live",
            "squads": "squad", "manager_seasons": "squad",
            "player_gameweeks": "scouting", "player_snapshots": "market",
            "player_transfers": "market", "transfers_in": "market",
            "fixture": "fixtures", "match": "fixtures",
            "matches": "fixtures", "fdr": "fixtures",
            "blank": "fixtures", "double": "fixtures",
            "dgw": "fixtures", "bgw": "fixtures",
        }

    def get_subdomain_formatters(self) -> dict[str, Callable]:
        from alfred_fpl.domain.formatters import (
            format_squad_summary,
            format_standings_summary,
        )
        return {
            "squad": format_squad_summary,
            "league": format_standings_summary,
        }

    # === Mode / Agent (2 abstract) ===

    @property
    def bypass_modes(self) -> dict[str, type]:
        return {}

    @property
    def default_agent(self) -> str:
        return "main"

    # === Handoff (1 abstract) ===

    def get_handoff_result_model(self) -> type:
        return _get_handoff_result_model()

    # === Database (1 abstract) ===

    def get_db_adapter(self):
        from alfred_fpl.db.client import get_client
        return get_client()

    # =========================================================================
    # Optional overrides (not abstract, but critical for FPL BI agent)
    # =========================================================================

    _middleware: "FPLMiddleware | None" = None

    def get_crud_middleware(self):
        """Singleton — preserves bridge dict state across CRUD calls."""
        if self._middleware is None:
            from alfred_fpl.domain.crud_middleware import FPLMiddleware
            self._middleware = FPLMiddleware()
        return self._middleware

    # =========================================================================
    # Prompt overrides — domain-specific Think, Understand, Reply guidance
    # =========================================================================

    def get_understand_prompt_content(self) -> str:
        from alfred_fpl.domain.prompts.understand_content import UNDERSTAND_PROMPT_CONTENT
        return UNDERSTAND_PROMPT_CONTENT

    def get_think_domain_context(self) -> str:
        from alfred_fpl.domain.prompts.think_injections import THINK_DOMAIN_CONTEXT
        return THINK_DOMAIN_CONTEXT

    def get_think_planning_guide(self) -> str:
        from alfred_fpl.domain.prompts.think_injections import THINK_PLANNING_GUIDE
        return THINK_PLANNING_GUIDE

    def get_act_prompt_content(self, step_type: str) -> str:
        from alfred_fpl.domain.prompts.act_content import get_act_content
        return get_act_content(step_type)

    def get_reply_prompt_content(self) -> str:
        from alfred_fpl.domain.prompts.reply_content import REPLY_PROMPT_CONTENT
        return REPLY_PROMPT_CONTENT

    def get_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent / "prompts" / "system.md"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return (
                "You are Alfred FPL, a Fantasy Premier League data analyst. "
                "You help managers make informed decisions using real FPL data."
            )

    def get_understand_system_prompt(self) -> str:
        """Override Understand system prompt to remove quick mode detection.

        FPL always uses full pipeline (Think → Act) — quick mode is disabled.
        Core's default includes "(3) detect quick mode for simple READ-ONLY queries"
        which we remove here.
        """
        return (
            "You are Alfred's MEMORY MANAGER. "
            "Your job: (1) resolve entity references to simple refs from the registry, "
            "(2) curate context (decide what older entities stay active with reasons). "
            "NEVER invent entity refs. Think has the raw message — "
            "you just resolve refs and curate context."
        )

    def get_filter_schema(self) -> str:
        """FPL-specific filter schema — replaces core's kitchen-oriented examples."""
        return """## Filter Syntax

Structure: `{"field": "<column>", "op": "<operator>", "value": <value>}`

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Exact match | `{"field": "gameweek", "op": "=", "value": 26}` |
| `!=` | Not equal | `{"field": "status", "op": "!=", "value": "u"}` |
| `>` `<` `>=` `<=` | Comparison | `{"field": "price", "op": "<=", "value": 8.0}` |
| `in` | Value in array | `{"field": "player_id", "op": "in", "value": ["player_1", "player_2"]}` |
| `not_in` | Exclude list | `{"field": "status", "op": "not_in", "value": ["i", "s"]}` |
| `ilike` | Pattern match (% = wildcard) | `{"field": "web_name", "op": "ilike", "value": "%Sal%"}` |
| `is_null` | Null check | `{"field": "news", "op": "is_null", "value": false}` |

"""

    def get_summarize_system_prompts(self) -> dict[str, str]:
        """FPL-specific summarize prompts — replaces kitchen examples."""
        return {
            "response_summary": (
                'Summarize what was accomplished in ONE sentence.\n'
                'Focus on: what action was taken, what was created/found/updated.\n\n'
                '**CRITICAL: Proposals ≠ Completed actions**\n'
                'If the text says "I\'ll do X" or "Here\'s my plan" or "Does this sound good?" '
                '— that\'s a PROPOSAL.\n'
                'Do NOT summarize proposals as completed actions.\n\n'
                '- Proposal: "I\'ll pull the fixture data" → Summary: "Proposed to fetch fixture data; '
                'awaiting confirmation."\n'
                '- Completed: "Done! Here\'s your squad:" → Summary: "Showed squad with 15 picks"\n\n'
                '**CRITICAL: Use EXACT entity names from the text.** Do NOT paraphrase or generalize.\n'
                'If the text says "Mohamed Salah", use that EXACT name.\n'
                'Do NOT make up names that sound similar but aren\'t in the original text.\n\n'
                'Good: "Showed top 5 midfielders by form: Salah, Palmer, Saka, Gordon, Mbeumo."\n'
                'Bad: "Showed the midfielders." (too vague)\n'
                'Bad: "Listed Mo Salah and others." (paraphrased name)\n\n'
                'Keep summaries specific with exact names or IDs when available.'
            ),
            "turn_compression": (
                'Summarize this conversation exchange in ONE brief sentence.\n'
                'Focus on: what the user asked, what action was taken, any entities created/modified.\n\n'
                '**CRITICAL: Proposals ≠ Completed actions**\n'
                'If Alfred says "I\'ll do X" or "Here\'s my plan" → that\'s a PROPOSAL, '
                'not a completed action.\n'
                '- Proposal: "I\'ll analyze the fixtures" → "User asked about fixtures; '
                'assistant proposed analysis plan"\n'
                '- Completed: "Here\'s the fixture heatmap" → "Assistant showed fixture difficulty '
                'heatmap for GW26-30"\n\n'
                'Use EXACT entity names from the text. Don\'t invent names.'
            ),
            "conversation_compression": (
                'Merge this conversation history into a brief summary.\n\n'
                'Focus on:\n'
                '- What data was explored (players, squads, fixtures, leagues)\n'
                '- Key entities mentioned (specific player names, teams, gameweeks)\n'
                '- Decisions or preferences expressed\n'
                '- Current thread (what the user is working toward)\n\n'
                'Drop:\n'
                '- Greetings and pleasantries\n'
                '- Repeated queries that were refined\n'
                '- Repetitive phrases\n\n'
                'Write as a single narrative: "User explored midfield options under £8m, '
                'compared Saka vs Palmer form trends, then checked Arsenal fixtures..."'
            ),
        }

    def get_entity_recency_window(self) -> int:
        """Evict data refs faster — squad reads alone register 15 entities."""
        return 1

    def get_tool_enabled_step_types(self) -> set[str]:
        """Enable tools in READ, WRITE, ANALYZE, and GENERATE steps.

        ANALYZE: Python execution via fpl_analyze + CRUD for mid-analysis fetching.
        GENERATE: Chart rendering via fpl_plot + CRUD for data lookups.
        """
        return {"read", "write", "analyze", "generate"}

    def get_custom_tools(self):
        """Register FPL-specific tools for ANALYZE and GENERATE steps.

        Two tools:
        - fpl_analyze: Execute Python analysis on FPL DataFrames
        - fpl_plot: Render matplotlib charts headlessly to PNG

        Requires alfredagain >= 2.1.0 (ToolDefinition support).
        """
        try:
            from alfred.domain.base import ToolDefinition
        except ImportError:
            logger.warning("ToolDefinition not available — alfredagain >= 2.1.0 required")
            return {}

        return {
            "fpl_analyze": ToolDefinition(
                name="fpl_analyze",
                description="Execute Python analysis on FPL DataFrames",
                params_schema=(
                    "`code` (str): Python code to execute. "
                    "DataFrames from prior READ steps are available as df_<table> "
                    "(e.g., df_players, df_fixtures, df_squads, df_player_gameweeks, "
                    "df_player_snapshots, df_league_standings, df_transfers). "
                    "Available analytics functions: "
                    "rank_by(df, metric, n=10, ascending=False, group_by=None), "
                    "add_rolling_mean(df, column, window=3, group_by=None), "
                    "compute_form_trend(df, player_col='player_id', gw_col='gameweek', "
                    "points_col='total_points', n_gws=5), "
                    "compute_fixture_difficulty(fixtures_df, team_id, n_gws=5), "
                    "compute_differentials(squad_a, squad_b, player_col='player_id'), "
                    "compute_price_velocity(snapshots_df). "
                    "Available chart functions: "
                    "render_bar(df, x, y, title=None, horizontal=False), "
                    "render_line(df, x, y, hue=None, title=None), "
                    "render_heatmap(df, title=None, cmap='RdYlGn_r'), "
                    "render_comparison(dfs={name: df}, metrics=[str], title=None). "
                    "pd (pandas) and np (numpy) are pre-loaded — do NOT import them. "
                    "`datasets` (list[str]): Table names to load "
                    "(e.g., ['players', 'fixtures']). All cached DataFrames are "
                    "also auto-loaded from prior READ steps."
                ),
                handler=self._execute_analysis,
            ),
            "fpl_plot": ToolDefinition(
                name="fpl_plot",
                description="Render a matplotlib chart headlessly to PNG",
                params_schema=(
                    "`code` (str): Python code that renders a chart. "
                    "All cached DataFrames from prior READ steps are available as df_<table>. "
                    "Chart functions: "
                    "render_bar(df, x, y, title=None, horizontal=False), "
                    "render_line(df, x, y, hue=None, title=None, ylabel=None), "
                    "render_heatmap(df, title=None, cmap='RdYlGn_r', vmin=1, vmax=5), "
                    "render_comparison(dfs={name: df}, metrics=[str], title=None). "
                    "pd, np, and all analytics functions are pre-loaded — do NOT import them. "
                    "`title` (str): Descriptive chart title."
                ),
                handler=self._execute_plot,
            ),
        }

    def _load_dataframes(
        self, dataset_refs: list[str], step_results: Any = None
    ) -> dict:
        """Load DataFrames from middleware cache for executor context.

        DataFrames are keyed as df_<table> (e.g., df_players, df_fixtures).
        Middleware captures them during post_read.
        """
        import pandas as pd

        middleware = self.get_crud_middleware()
        cache = middleware.get_dataframe_cache()
        context: dict[str, pd.DataFrame] = {}

        # Load explicitly requested datasets
        for ref in dataset_refs:
            if ref in cache:
                context[f"df_{ref}"] = cache[ref].copy()
            else:
                logger.warning("Dataset '%s' not in cache — was it read in a prior step?", ref)

        # Make all cached DataFrames available (LLM might reference any)
        for table_name, df in cache.items():
            key = f"df_{table_name}"
            if key not in context:
                context[key] = df.copy()

        # Enrich DataFrames with human-readable names from FK lookups
        self._enrich_dataframes(context, middleware)

        return context

    def _enrich_dataframes(self, context: dict, middleware: Any) -> None:
        """Add human-readable name columns to DataFrames with UUID FK columns.

        Resolves UUID FKs to names so LLM-generated Python can reference
        team names and player names directly instead of opaque UUIDs.
        """
        # Team UUID → short_name (from session bootstrap)
        team_map = getattr(middleware, '_team_map', {})

        # Enrich fixtures with team names
        if "df_fixtures" in context and team_map:
            df = context["df_fixtures"]
            if "home_team_id" in df.columns and "home_team_name" not in df.columns:
                df["home_team_name"] = df["home_team_id"].map(team_map).fillna("?")
                df["away_team_name"] = df["away_team_id"].map(team_map).fillna("?")

        # Build player map from cached players (if available)
        player_map: dict[str, str] = {}
        if "df_players" in context and "id" in context["df_players"].columns:
            pdf = context["df_players"]
            if "web_name" in pdf.columns:
                player_map = dict(zip(pdf["id"], pdf["web_name"]))

        # Enrich player_gameweeks with player names
        if "df_player_gameweeks" in context and player_map:
            df = context["df_player_gameweeks"]
            if "player_id" in df.columns and "player_name" not in df.columns:
                df["player_name"] = df["player_id"].map(player_map).fillna("?")

        # Enrich player_snapshots with player names
        if "df_player_snapshots" in context and player_map:
            df = context["df_player_snapshots"]
            if "player_id" in df.columns and "player_name" not in df.columns:
                df["player_name"] = df["player_id"].map(player_map).fillna("?")

    async def _execute_analysis(self, params: dict, user_id: str, ctx: Any) -> dict:
        """Handler for fpl_analyze tool — runs Python code against FPL DataFrames.

        Soft failure: returns error dict (LLM retries within MAX_TOOL_CALLS_PER_STEP).
        Hard failure: raises exception (becomes BlockedAction).
        """
        from alfred_fpl.bi.executor import execute

        code = params.get("code", "")
        dataset_refs = params.get("datasets", [])

        if not code or not code.strip():
            return {"error": "No code provided. Pass Python code in the `code` parameter."}

        # Load DataFrames from middleware cache
        step_results = getattr(ctx, "step_results", None)
        context = self._load_dataframes(dataset_refs, step_results)

        # Execute in sandbox
        result = execute(code, context)

        if result.error:
            return {"error": result.error, "traceback": result.error}

        response: dict[str, Any] = {}
        if result.stdout:
            response["stdout"] = result.stdout
        if result.result is not None:
            response["result_summary"] = str(result.result)[:500]
        if result.dataframes:
            response["dataframes"] = {
                name: df.head(10).to_string()
                for name, df in result.dataframes.items()
            }
        if result.charts:
            response["charts"] = [str(p) for p in result.charts]

        return response or {"stdout": "(no output)"}

    async def _execute_plot(self, params: dict, user_id: str, ctx: Any) -> dict:
        """Handler for fpl_plot tool — renders matplotlib charts to PNG.

        Returns file paths in result dict. Frontend renders them.
        """
        from alfred_fpl.bi.executor import execute

        code = params.get("code", "")
        title = params.get("title", "Chart")

        if not code or not code.strip():
            return {"error": "No code provided. Pass matplotlib code in the `code` parameter."}

        # Load all available DataFrames
        step_results = getattr(ctx, "step_results", None)
        context = self._load_dataframes([], step_results)

        # Execute in sandbox
        result = execute(code, context)

        if result.error:
            return {"error": result.error}

        response: dict[str, Any] = {"title": title}
        if result.charts:
            response["charts"] = [str(p) for p in result.charts]
        else:
            response["warning"] = (
                "No chart files were generated. Ensure the code calls "
                "render_line, render_bar, render_heatmap, or render_comparison."
            )
        if result.stdout:
            response["stdout"] = result.stdout

        return response

    def compute_entity_label_from_fks(
        self, entity_type: str, fk_labels: dict[str, str], ref: str
    ) -> str:
        """Build composite labels from resolved FK labels."""
        if entity_type == "fix":
            home = fk_labels.get("home_team_id", "")
            away = fk_labels.get("away_team_id", "")
            if home and away:
                return f"{home} v {away}"
        if entity_type in ("xfer", "plan"):
            pin = fk_labels.get("player_in_id", "")
            pout = fk_labels.get("player_out_id", "")
            if pin and pout:
                prefix = "Plan: " if entity_type == "plan" else ""
                return f"{prefix}{pout} → {pin}"
            if pin:
                return f"In: {pin}"
        return ref

    def infer_table_from_record(self, record: dict) -> str | None:
        if not isinstance(record, dict):
            return None
        if "web_name" in record:
            return "players"
        if "home_team_id" in record and "away_team_id" in record:
            return "fixtures"
        if "player_in_id" in record and "player_out_id" in record:
            return "transfer_plans" if "created_at" in record else "transfers"
        if "player_id" in record and "is_captain" in record:
            return "squads"
        if "player_id" in record and "gameweek" in record and "total_points" in record:
            return "player_gameweeks"
        if "player_id" in record and "selected_by_percent" in record:
            return "player_snapshots"
        if "player_id" in record and "notes" in record:
            return "watchlist"
        if "rank" in record and "manager_name" in record:
            return "league_standings"
        if "manager_id" in record and "label" in record:
            return "manager_links"
        if "short_name" in record and len(record.get("short_name", "")) <= 4:
            return "teams"
        return None

    def format_records_for_reply(
        self, records: list[dict], table_type: str | None, indent: int = 2
    ) -> str | None:
        """FPL-specific record formatting for Reply execution_summary.

        Formats player, squad, fixture, and standings records as clean
        domain-appropriate summaries instead of generic key-value dumps.
        Returns None for unrecognized record types (Core's generic fallback).
        """
        if not records or not isinstance(records[0], dict):
            return None

        prefix = " " * indent
        first = records[0]

        # Player records
        if table_type == "players" or ("web_name" in first and "price" in first):
            lines = []
            for r in records:
                name = r.get("web_name", "?")
                team = r.get("team_name", "")
                price = r.get("price", "?")
                pts = r.get("total_points", "")
                form = r.get("form", "")
                status = r.get("status", "a")
                parts = [f"{prefix}- {name}"]
                if team:
                    parts[0] += f" ({team})"
                parts[0] += f" — £{price}m"
                if pts:
                    parts.append(f"| {pts} pts")
                if form:
                    parts.append(f"| form {form}")
                if status and status != "a":
                    flags = {"i": "injured", "d": "doubtful", "s": "suspended", "u": "unavailable"}
                    parts.append(f"| {flags.get(status, status)}")
                    news = r.get("news", "")
                    if news:
                        parts.append(f"({news})")
                lines.append(" ".join(parts))
            return "\n".join(lines)

        # Squad records
        if table_type == "squads" or "is_captain" in first or "multiplier" in first:
            lines = []
            for r in records:
                name = r.get("_player_id_label") or r.get("web_name") or r.get("player_name") or "?"
                team = r.get("team_name", "")
                pos = r.get("position_name", "")
                slot = r.get("slot", 0)
                captain = " (C)" if r.get("is_captain") else ""
                vice = " (VC)" if r.get("is_vice_captain") else ""
                bench = ""
                if slot and slot >= 12:
                    bench = f" [Bench {slot - 11}]"
                parts = [f"{prefix}- {name}{captain}{vice}"]
                if pos:
                    parts.append(f"| {pos}")
                if team:
                    parts.append(f"| {team}")
                if bench:
                    parts.append(bench)
                lines.append(" ".join(parts))
            return "\n".join(lines)

        # League standings
        if table_type == "league_standings" or (
            "rank" in first and "manager_name" in first
        ):
            lines = []
            for r in records:
                rank = r.get("rank", "?")
                mgr = r.get("manager_name", "?")
                team_name = r.get("team_name", "")
                pts = r.get("total_points", "?")
                gw_pts = r.get("event_points", "")
                parts = [f"{prefix}- #{rank} {mgr}"]
                if team_name:
                    parts.append(f"({team_name})")
                parts.append(f"— {pts} pts")
                if gw_pts:
                    parts.append(f"(GW: {gw_pts})")
                lines.append(" ".join(parts))
            return "\n".join(lines)

        # Fixtures
        if table_type == "fixtures" or (
            "home_team_id" in first and "away_team_id" in first
        ):
            lines = []
            for r in records:
                home = r.get("home_team_name", r.get("home_team_id", "?"))
                away = r.get("away_team_name", r.get("away_team_id", "?"))
                gw = r.get("gameweek", "?")
                h_diff = r.get("home_difficulty", "")
                a_diff = r.get("away_difficulty", "")
                h_score = r.get("home_score")
                a_score = r.get("away_score")
                parts = [f"{prefix}- GW{gw}: {home} vs {away}"]
                if h_score is not None and a_score is not None:
                    parts.append(f"({h_score}-{a_score})")
                if h_diff and a_diff:
                    parts.append(f"[FDR: {h_diff}/{a_diff}]")
                lines.append(" ".join(parts))
            return "\n".join(lines)

        # Player gameweeks
        if table_type == "player_gameweeks":
            lines = []
            for r in records:
                name = r.get("_player_id_label") or r.get("web_name") or r.get("player_name") or "?"
                gw = r.get("gameweek", "?")
                pts = r.get("total_points", 0)
                mins = r.get("minutes", 0)
                goals = r.get("goals_scored", 0)
                assists = r.get("assists", 0)
                bonus = r.get("bonus", 0)
                detail_parts = []
                if mins:
                    detail_parts.append(f"{mins} min")
                if goals:
                    detail_parts.append(f"{goals}G")
                if assists:
                    detail_parts.append(f"{assists}A")
                if bonus:
                    detail_parts.append(f"{bonus}B")
                detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
                lines.append(f"{prefix}- GW{gw} {name}: {pts} pts{detail}")
            return "\n".join(lines)

        # Player snapshots (market data)
        if table_type == "player_snapshots":
            lines = []
            for r in records:
                name = r.get("_player_id_label") or r.get("web_name") or r.get("player_name") or "?"
                price = r.get("price", "?")
                tin = r.get("transfers_in_event", 0)
                tout = r.get("transfers_out_event", 0)
                own = r.get("selected_by_percent", "")
                parts = [f"{prefix}- {name} — £{price}m"]
                net = (tin or 0) - (tout or 0)
                if tin or tout:
                    parts.append(f"| net transfers: {net:+d}")
                if own:
                    parts.append(f"| {own}% owned")
                lines.append(" ".join(parts))
            return "\n".join(lines)

        return None  # Fall through to Core's generic formatter

    def get_strip_fields(self, context: str = "injection") -> set[str]:
        from alfred_fpl.domain.formatters import INJECTION_STRIP_FIELDS, REPLY_STRIP_FIELDS
        return REPLY_STRIP_FIELDS if context == "reply" else INJECTION_STRIP_FIELDS

    def get_act_subdomain_header(self, subdomain: str, step_type: str) -> str:
        from alfred_fpl.domain.prompts.personas import get_full_subdomain_content
        return get_full_subdomain_content(subdomain, step_type)

    async def get_domain_snapshot(self, user_id: str) -> str:
        """Build FPL session context + populate middleware bridges."""
        try:
            from alfred_fpl.db.client import get_client
            client = get_client()

            gw_resp = (
                client.table("gameweeks")
                .select("id, fpl_id, name, deadline_time, is_current, is_next, finished")
                .or_("is_current.eq.true,is_next.eq.true")
                .order("fpl_id")
                .limit(2)
                .execute()
            )
            gw_data = gw_resp.data or []

            mgr_resp = (
                client.table("manager_links")
                .select("id, label, fpl_manager_id, is_primary, league_id")
                .eq("user_id", user_id)
                .limit(10)
                .execute()
            )
            mgr_data = mgr_resp.data or []

            manager_bridge: dict[str, int] = {}
            league_bridge: dict[str, int] = {}
            primary_manager_id: int | None = None

            for mgr in mgr_data:
                uuid_id = mgr.get("id")
                fpl_id = mgr.get("fpl_manager_id")
                if uuid_id and fpl_id is not None:
                    manager_bridge[uuid_id] = fpl_id
                    if mgr.get("is_primary"):
                        primary_manager_id = fpl_id
                lid = mgr.get("league_id")
                if uuid_id and lid is not None:
                    league_bridge[uuid_id] = lid

            # Fallback: if no manager_links found (e.g., RLS blocks anon key),
            # use dev defaults from settings so squad scoping still works.
            if primary_manager_id is None:
                from alfred_fpl.config import settings as _s
                if _s.fpl_default_manager_id:
                    primary_manager_id = _s.fpl_default_manager_id
                    logger.info(
                        "No manager_links found; falling back to fpl_default_manager_id=%s",
                        primary_manager_id,
                    )
                if _s.fpl_default_league_id and not league_bridge:
                    league_bridge["_default"] = _s.fpl_default_league_id

            self.get_crud_middleware().set_bridges(
                manager_bridge, league_bridge, primary_manager_id
            )

            # Cache team UUID→short_name map for DataFrame enrichment
            team_resp = (
                client.table("teams")
                .select("id, short_name")
                .limit(30)
                .execute()
            )
            team_data = team_resp.data or []
            team_map = {t["id"]: t["short_name"] for t in team_data}
            self.get_crud_middleware().set_team_map(team_map)

            # Extract numeric GW IDs for explicit context
            current_gw: int | None = None
            next_gw: int | None = None
            for gw in gw_data:
                fpl_gw_id = gw.get("fpl_id")
                if gw.get("is_current") and fpl_gw_id is not None:
                    current_gw = fpl_gw_id
                elif gw.get("is_next") and fpl_gw_id is not None:
                    next_gw = fpl_gw_id

            # Store on middleware so Act can reference it
            if current_gw is not None:
                self.get_crud_middleware().current_gw = current_gw

            lines = ["## FPL Session Context"]
            if current_gw is not None:
                finished = any(
                    gw.get("is_current") and gw.get("finished") for gw in gw_data
                )
                lines.append(
                    f"**Current Gameweek: {current_gw}**"
                    f"{' (finished)' if finished else ''}"
                )
                if next_gw is not None:
                    lines.append(f"**Next Gameweek: {next_gw}**")
                lines.append(
                    f"Use GW {current_gw} as the reference point. "
                    f"\"Last 5 GWs\" = GW {current_gw - 4} to {current_gw}."
                )
            elif gw_data:
                for gw in gw_data:
                    status = ""
                    if gw.get("is_current"):
                        status = " (CURRENT - finished)" if gw.get("finished") else " (CURRENT)"
                    elif gw.get("is_next"):
                        status = " (NEXT)"
                    lines.append(
                        f"- {gw.get('name', 'GW?')}{status} "
                        f"| deadline: {gw.get('deadline_time', 'unknown')}"
                    )
            else:
                lines.append("- Gameweek data not yet loaded.")

            if mgr_data:
                lines.extend(["", "### Linked Managers"])
                for mgr in mgr_data:
                    tag = " (PRIMARY)" if mgr.get("is_primary") else ""
                    lines.append(
                        f"- {mgr.get('label', 'Manager')}{tag} "
                        f"(FPL ID: {mgr.get('fpl_manager_id', '?')})"
                    )
            else:
                if primary_manager_id is not None:
                    lines.extend([
                        "", "### Linked Managers",
                        f"- My Team (PRIMARY) (FPL ID: {primary_manager_id})",
                    ])
                else:
                    lines.extend(["", "No FPL managers linked yet."])

            return "\n".join(lines)
        except Exception as e:
            logger.warning("Failed to build FPL domain snapshot: %s", e)
            return ""

    def detect_detail_level(self, entity_type: str, record: dict) -> str | None:
        if entity_type == "player":
            if "player_gameweeks" in record or "player_snapshots" in record:
                return "full"
            return "summary"
        return None

    def get_priority_fields(self) -> list[str]:
        return [
            "web_name", "short_name", "name", "label",
            "price", "total_points", "form", "position",
            "gameweek", "minutes", "goals_scored", "assists",
            "clean_sheets", "bonus", "selected_by_percent",
            "ict_index", "rank", "notes",
        ]


# =============================================================================
# Singleton
# =============================================================================

FPL_DOMAIN = FPLConfig()
