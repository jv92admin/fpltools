"""Smoke tests — verify FPL domain is wired correctly.

Two groups:
  1. Basic wiring (domain registered, entities/subdomains defined)
  2. Contract enforcement (catches implicit contract violations that fail
     silently at runtime — Section 11 of the domain implementation guide)
"""

from alfred.domain import get_current_domain


# ---------------------------------------------------------------------------
# Basic wiring
# ---------------------------------------------------------------------------

def test_domain_registered():
    domain = get_current_domain()
    assert domain.name == "fpl"


def test_entities_defined():
    domain = get_current_domain()
    assert len(domain.entities) == 15  # All 15 tables (14 + positions)


def test_subdomains_defined():
    domain = get_current_domain()
    assert len(domain.subdomains) == 6
    assert set(domain.subdomains.keys()) == {
        "squad", "scouting", "market", "league", "live", "fixtures"
    }


def test_subdomain_registry_matches():
    domain = get_current_domain()
    registry = domain.get_subdomain_registry()
    for name in domain.subdomains:
        assert name in registry, f"Subdomain '{name}' missing from registry"
        assert "tables" in registry[name]
        assert len(registry[name]["tables"]) > 0


def test_personas_not_empty():
    domain = get_current_domain()
    for name in domain.subdomains:
        for step_type in ("read", "analyze", "generate"):
            persona = domain.get_persona(name, step_type)
            assert persona, f"Subdomain '{name}' step '{step_type}' has empty persona"


def test_empty_responses_not_generic():
    domain = get_current_domain()
    for name in domain.subdomains:
        msg = domain.get_empty_response(name)
        assert msg != "No data found.", f"Subdomain '{name}' using generic empty response"


def test_system_prompt_loads():
    domain = get_current_domain()
    prompt = domain.get_system_prompt()
    assert "Alfred FPL" in prompt
    assert len(prompt) > 50


# ---------------------------------------------------------------------------
# Contract enforcement
# ---------------------------------------------------------------------------

def test_fk_enrich_map_targets_exist():
    """FK enrichment targets must be known entity tables."""
    domain = get_current_domain()
    fk_map = domain.get_fk_enrich_map()
    known_tables = {e.table for e in domain.entities.values()}
    for fk_field, (target_table, _) in fk_map.items():
        assert target_table in known_tables, (
            f"FK '{fk_field}' targets '{target_table}' which is not a known entity table"
        )


def test_fk_enrich_map_no_integer_fks():
    """FK enrichment map must only contain UUID FK fields.

    Integer FKs (manager_id, league_id) cause silent failure in core's
    UUID-based WHERE id IN (values) enrichment.
    """
    domain = get_current_domain()
    fk_map = domain.get_fk_enrich_map()
    uuid_fields = domain.get_uuid_fields()
    for fk_field in fk_map:
        assert fk_field in uuid_fields, (
            f"FK '{fk_field}' is in get_fk_enrich_map() but NOT in get_uuid_fields(). "
            f"If this is an integer FK, it will silently fail."
        )


def test_field_enum_values_are_strings():
    """All field enum values must be strings (core does ', '.join)."""
    domain = get_current_domain()
    for subdomain, fields in domain.get_field_enums().items():
        for field_name, values in fields.items():
            for v in values:
                assert isinstance(v, str), (
                    f"Enum value {v!r} for {subdomain}.{field_name} is not a string"
                )


def test_subdomain_examples_are_strings():
    """Subdomain examples must be strings, not lists."""
    domain = get_current_domain()
    for subdomain, examples in domain.get_subdomain_examples().items():
        assert isinstance(examples, str), (
            f"Subdomain example for '{subdomain}' is {type(examples).__name__}, not str"
        )


def test_semantic_notes_keyed_by_subdomain():
    """Semantic notes must be keyed by subdomain name."""
    domain = get_current_domain()
    notes = domain.get_semantic_notes()
    valid_subdomains = set(domain.subdomains.keys())
    for key in notes:
        assert key in valid_subdomains, (
            f"Semantic note key '{key}' is not a subdomain name. "
            f"Valid: {valid_subdomains}"
        )


def test_type_name_depluralization():
    """Verify type_name works with core's table.rstrip('s') fallback."""
    domain = get_current_domain()
    for table_name, entity_def in domain.entities.items():
        actual = domain.table_to_type.get(entity_def.table)
        assert actual == entity_def.type_name, (
            f"Entity '{table_name}': type_name='{entity_def.type_name}' but "
            f"table_to_type resolved to '{actual}'"
        )


def test_label_fields_in_fallback_schemas():
    """label_fields must appear in fallback schemas."""
    domain = get_current_domain()
    schemas = domain.get_fallback_schemas()
    if not schemas:
        return

    for table_name, entity_def in domain.entities.items():
        if not entity_def.label_fields:
            continue
        schema_str = schemas.get(entity_def.table, "")
        if not schema_str:
            continue
        for label_field in entity_def.label_fields:
            assert label_field in schema_str, (
                f"Entity '{table_name}': label_field '{label_field}' not in "
                f"fallback schema for '{entity_def.table}'"
            )


def test_fallback_schemas_include_id():
    """Every fallback schema must mention 'id' column."""
    domain = get_current_domain()
    schemas = domain.get_fallback_schemas()
    if not schemas:
        return
    for table, schema_str in schemas.items():
        assert "id" in schema_str, (
            f"Fallback schema for '{table}' does not mention 'id'"
        )


def test_middleware_singleton():
    """get_crud_middleware() must return the same instance."""
    domain = get_current_domain()
    mw1 = domain.get_crud_middleware()
    mw2 = domain.get_crud_middleware()
    if mw1 is None:
        return
    assert mw1 is mw2, "get_crud_middleware() returns a new instance each call"


def test_tool_enabled_includes_analyze():
    """ANALYZE steps need tool access for mid-analysis data fetching."""
    domain = get_current_domain()
    enabled = domain.get_tool_enabled_step_types()
    assert "analyze" in enabled, "ANALYZE not in tool_enabled_step_types"
    assert "read" in enabled
    assert "write" in enabled


def test_entity_recency_window_is_aggressive():
    """FPL should use window=1 (not default 2) due to high-volume reads."""
    domain = get_current_domain()
    assert domain.get_entity_recency_window() == 1


# ---------------------------------------------------------------------------
# FPL-specific entity checks
# ---------------------------------------------------------------------------

def test_player_entity_has_detail_tracking():
    domain = get_current_domain()
    player = domain.entities["players"]
    assert player.detail_tracking is True
    assert player.complexity == "high"


def test_fixture_entity_has_both_team_fks():
    domain = get_current_domain()
    fix = domain.entities["fixtures"]
    assert "home_team_id" in fix.fk_fields
    assert "away_team_id" in fix.fk_fields


def test_user_owned_tables_correct():
    domain = get_current_domain()
    owned = domain.get_user_owned_tables()
    assert "manager_links" in owned
    assert "watchlist" in owned
    assert "transfer_plans" in owned
    assert "players" not in owned
    assert "squads" not in owned


def test_compute_entity_label_player():
    domain = get_current_domain()
    label = domain.compute_entity_label({"web_name": "Salah"}, "player", "player_1")
    assert label == "Salah"


def test_compute_entity_label_fallback():
    domain = get_current_domain()
    label = domain.compute_entity_label({}, "player", "player_1")
    assert label == "player_1"  # Falls back to ref, never empty


def test_compute_entity_label_standing():
    domain = get_current_domain()
    label = domain.compute_entity_label(
        {"manager_name": "Vinay", "team_name": "Vinay FC"},
        "standing", "standing_1"
    )
    assert "Vinay" in label


def test_subdomain_aliases_cover_common_terms():
    domain = get_current_domain()
    aliases = domain.get_subdomain_aliases()
    assert aliases["rival"] == "league"
    assert aliases["captain"] == "squad"
    assert aliases["buy"] == "market"
    assert aliases["compare"] == "scouting"
    assert aliases["fdr"] == "fixtures"
    assert aliases["gw"] == "live"


# ---------------------------------------------------------------------------
# ANALYZE description-based example routing
# ---------------------------------------------------------------------------

from alfred_fpl.domain.prompts.examples import get_contextual_examples, _EXAMPLES


def test_examples_assessment_routing():
    """FPL Assessment prefix routes to assessment examples."""
    result = get_contextual_examples("scouting", "analyze", "FPL Assessment: filter active players")
    assert "minutes" in result.lower() or "filter" in result.lower()


def test_examples_compute_routing():
    """Compute prefix routes to compute examples."""
    result = get_contextual_examples("scouting", "analyze", "Compute: rank by pts per million")
    assert "pts_per_m" in result or "rank_by" in result


def test_examples_no_prefix_fallback():
    """No prefix falls back to generic subdomain:analyze."""
    result = get_contextual_examples("scouting", "analyze", "compare players by form")
    assert result  # Should return the existing scouting:analyze content


def test_examples_case_insensitive():
    """Prefix detection is case-insensitive."""
    lower = get_contextual_examples("scouting", "analyze", "fpl assessment: filter data")
    upper = get_contextual_examples("scouting", "analyze", "FPL Assessment: filter data")
    assert lower == upper


def test_examples_all_subdomains_have_assessment():
    """Every subdomain with analyze examples also has assessment variant."""
    for subdomain in ["scouting", "fixtures", "squad", "league"]:
        key = f"{subdomain}:analyze:assessment"
        assert key in _EXAMPLES, f"Missing {key}"


def test_examples_all_subdomains_have_compute():
    """Every subdomain with analyze examples also has compute variant."""
    for subdomain in ["scouting", "fixtures", "squad", "league"]:
        key = f"{subdomain}:analyze:compute"
        assert key in _EXAMPLES, f"Missing {key}"
