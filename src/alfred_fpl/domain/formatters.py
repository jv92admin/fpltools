"""FPL record formatting for prompt context and reply display.

Two contexts:
- Injection: records going INTO Act prompts (strip noise, compact format)
- Reply: records going TO the user (strip internal IDs, format for readability)

Data card format: when results exceed the context-friendly threshold (15 rows),
instead of injecting full entity records, produce a compact data card showing
schema + row count + sample rows + column stats. The full data is available
to the Python executor as a DataFrame.
"""

# Fields to strip from records BEFORE injecting into Act prompts
INJECTION_STRIP_FIELDS: set[str] = {
    "id",           # UUID PK — LLM uses refs, not raw UUIDs
    "user_id",      # Internal, auto-scoped by RLS
    "created_at",   # Noise for analysis
    "updated_at",
    "fpl_id",       # Internal mapping ID
    "code",         # FPL internal code on teams
    "snapshot_time", # Redundant with gameweek for most analysis
}

# Fields to strip from records before showing to the user
REPLY_STRIP_FIELDS: set[str] = INJECTION_STRIP_FIELDS | {
    "position_id",   # Show position name, not UUID
    "team_id",       # Show team name, not UUID
    "home_team_id",
    "away_team_id",
    "player_id",     # Show player name, not UUID
    "player_in_id",
    "player_out_id",
}

# Row count threshold: above this, produce a data card instead of full records
DATA_CARD_THRESHOLD = 15
DATA_CARD_SAMPLE_ROWS = 5


def format_squad_summary(records: list[dict]) -> str:
    """Format squad records as Starting XI + Bench with captain markers."""
    if not records:
        return "No squad data."

    starting = [r for r in records if (r.get("slot") or 0) <= 11]
    bench = [r for r in records if (r.get("slot") or 0) >= 12]

    # Sort by slot
    starting.sort(key=lambda r: r.get("slot", 0))
    bench.sort(key=lambda r: r.get("slot", 0))

    lines = ["**Starting XI**"]
    for r in starting:
        name = r.get("_player_id_label", r.get("player_id", "?"))
        captain = " (C)" if r.get("is_captain") else ""
        vice = " (VC)" if r.get("is_vice_captain") else ""
        lines.append(f"  {r.get('slot', '?')}. {name}{captain}{vice}")

    lines.append("\n**Bench**")
    for r in bench:
        name = r.get("_player_id_label", r.get("player_id", "?"))
        lines.append(f"  {r.get('slot', '?')}. {name}")

    return "\n".join(lines)


def format_standings_summary(records: list[dict]) -> str:
    """Format league standings as a ranked table."""
    if not records:
        return "No standings data."

    records.sort(key=lambda r: r.get("rank", 999))
    lines = ["| Rank | Manager | Team | Pts | GW Pts |", "| --- | --- | --- | --- | --- |"]
    for r in records:
        lines.append(
            f"| {r.get('rank', '?')} "
            f"| {r.get('manager_name', '?')} "
            f"| {r.get('team_name', '')} "
            f"| {r.get('total_points', 0)} "
            f"| {r.get('event_points', 0)} |"
        )
    return "\n".join(lines)


def format_record_for_context(record: dict, table: str | None = None) -> str:
    """Format a single record for Act prompt context (compact, stripped)."""
    stripped = {k: v for k, v in record.items() if k not in INJECTION_STRIP_FIELDS}
    parts = [f"{k}: {v}" for k, v in stripped.items() if v is not None]
    return " | ".join(parts)


def format_records_for_context(
    records: list[dict], table: str | None = None
) -> list[str]:
    """Format a list of records for Act prompt context."""
    return [format_record_for_context(r, table) for r in records]


def build_data_card(records: list[dict], table: str | None = None) -> str:
    """Build a compact data card for large result sets.

    Used when result count exceeds DATA_CARD_THRESHOLD. Shows the LLM
    enough to write correct Python code without flooding the context.
    """
    if not records:
        return "Empty result set."

    n = len(records)
    table_label = table or "query result"

    # Column names and types (infer from first record)
    columns = list(records[0].keys())
    col_info = ", ".join(columns)

    # Sample rows (first N)
    sample = records[:DATA_CARD_SAMPLE_ROWS]
    sample_lines = []
    for r in sample:
        stripped = {k: v for k, v in r.items() if k not in INJECTION_STRIP_FIELDS and v is not None}
        parts = [f"{k}: {v}" for k, v in list(stripped.items())[:8]]  # Max 8 fields per sample row
        sample_lines.append("  " + " | ".join(parts))

    # Numeric column stats (min/max for key numeric fields)
    stats_lines = []
    numeric_fields = ["price", "total_points", "form", "minutes", "goals_scored",
                      "assists", "selected_by_percent", "ict_index", "expected_goals",
                      "rank", "event_points", "home_difficulty", "away_difficulty",
                      "gameweek", "bonus", "bps", "value"]
    for field in numeric_fields:
        values = [r.get(field) for r in records if r.get(field) is not None]
        if values:
            try:
                nums = [float(v) for v in values]
                stats_lines.append(f"  {field}: range [{min(nums)}, {max(nums)}]")
            except (ValueError, TypeError):
                pass

    lines = [
        f"## Data available: {table_label} ({n} rows)",
        f"Columns: {col_info}",
        f"Sample (first {len(sample)}):",
        *sample_lines,
    ]
    if stats_lines:
        lines.append("Stats:")
        lines.extend(stats_lines[:6])  # Max 6 stat lines

    return "\n".join(lines)
