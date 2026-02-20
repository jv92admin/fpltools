"""Alfred FPL — Fantasy Premier League BI agent domain.

Importing this package registers the FPL domain with Alfred's core engine.
"""

from alfred.domain import register_domain


def _register():
    from alfred_fpl.domain import FPL_DOMAIN
    register_domain(FPL_DOMAIN)

    # Patch core's FILTER_SCHEMA to use FPL examples instead of kitchen.
    # Must happen AFTER register_domain() so the module import succeeds.
    try:
        import alfred.tools.schema as _schema_mod

        _schema_mod.FILTER_SCHEMA = """## Filter Syntax

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
    except Exception:
        pass  # Core not installed or structure changed


_register()
