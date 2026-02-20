"""FPL contextual examples for Act prompts.

Examples teach the LLM which tables to query, what filters to use, and
what Python patterns to write in ANALYZE steps. They are the highest-impact
thing we can tune — a concrete example of "midfielders under 8m" teaches
more than any generic instruction.

Examples are selected by subdomain + step_type and optionally refined by
step_description keywords.
"""


def get_contextual_examples(
    subdomain: str,
    step_type: str,
    step_description: str = "",
    prev_subdomain: str | None = None,
) -> str:
    """Get contextual examples for a subdomain and step type.

    For ANALYZE steps, routes on description prefix:
    - "FPL Assessment:" → domain intelligence examples (data quality, filtering)
    - "Compute:" → Python computation examples (pandas, analytics helpers)
    - No prefix → generic subdomain:analyze examples (backward compatible)
    """
    # Try description-based routing for analyze steps
    if step_type == "analyze" and step_description:
        desc_lower = step_description.lower()
        if desc_lower.startswith("fpl assessment"):
            key = f"{subdomain}:analyze:assessment"
            if key in _EXAMPLES:
                return _EXAMPLES[key]
        elif desc_lower.startswith("compute"):
            key = f"{subdomain}:analyze:compute"
            if key in _EXAMPLES:
                return _EXAMPLES[key]

    # Default: subdomain:step_type
    key = f"{subdomain}:{step_type}"
    examples = _EXAMPLES.get(key, "")

    # Add cross-subdomain examples if stepping between subdomains
    if prev_subdomain and prev_subdomain != subdomain:
        cross_key = f"{prev_subdomain}->{subdomain}:{step_type}"
        cross = _EXAMPLES.get(cross_key, "")
        if cross:
            examples = f"{examples}\n\n{cross}" if examples else cross

    return examples


# ---------------------------------------------------------------------------
# Example bank — keyed by "subdomain:step_type"
# ---------------------------------------------------------------------------

_EXAMPLES: dict[str, str] = {
    # === SQUAD ===
    "squad:read": (
        '## Squad Read Examples\n\n'
        '### Show current squad\n'
        'User: "show my team"\n'
        'Action: db_read on squads\n'
        'Filters: manager_id eq <primary_manager>, gameweek eq <current_gw>\n'
        'Note: manager_id is auto-injected by middleware if missing. '
        'Order by slot asc.\n\n'
        '### Who is captain\n'
        'User: "who\'s my captain?"\n'
        'Action: db_read on squads\n'
        'Filters: manager_id eq <primary_manager>, gameweek eq <current_gw>, '
        'is_captain eq true\n'
        'Note: Quick mode — single row result.'
    ),
    "squad:analyze": (
        '## Squad Analyze Examples\n\n'
        '### Squad composition analysis\n'
        'DataFrames from READ steps are available as `df_squads` and `df_players`.\n'
        'Enriched squad has: player_name, player_price, player_form, player_total_points.\n'
        'Position requires merging with df_players.\n'
        '```python\n'
        '# Compute formation: merge squad with players for position\n'
        'starting = df_squads[df_squads["slot"] <= 11].copy()\n'
        'bench = df_squads[df_squads["slot"] > 11].copy()\n'
        'starting_full = starting.merge(\n'
        '    df_players[["id", "position"]], left_on="player_id", right_on="id", how="left"\n'
        ')\n'
        'pos_counts = starting_full["position"].value_counts()\n'
        'formation = "-".join(str(pos_counts.get(p, 0)) for p in ["DEF", "MID", "FWD"])\n'
        'squad_value = starting["player_price"].sum()\n'
        'bench_pts = bench["player_total_points"].sum()\n'
        'print(f"Formation: {formation}, Squad value: {squad_value:.1f}m")\n'
        'print(f"Points on bench: {bench_pts}")\n'
        '```\n'
        'Note: df_squads enriched view has player_name/player_price/player_form/player_total_points. '
        'For position, merge with df_players on player_id → id.'
    ),

    # === SCOUTING ===
    "scouting:read": (
        '## Scouting Read Examples\n\n'
        '### Filtered player search\n'
        'User: "cheap midfielders under 6m"\n'
        'Action: db_read on players\n'
        'Filters: position_id eq <MID_uuid>, price lte 6.0\n'
        'Order: total_points desc\n'
        'Limit: 20\n'
        'Note: Resolve "midfielders" to position_id UUID. '
        'Always include a price or position filter on players table.\n\n'
        '### Player GW stats for comparison\n'
        'User: "compare Salah and Saka"\n'
        'Step 1: db_read on players, filters: web_name ilike "%Salah%"\n'
        'Step 2: db_read on players, filters: web_name ilike "%Saka%"\n'
        'Step 3: db_read on player_gameweeks, filters: '
        'player_id in [<salah_id>, <saka_id>], gameweek gte <current_gw - 5>\n'
        'Note: player_gameweeks REQUIRES a player_id or gameweek filter.'
    ),
    "scouting:analyze": (
        '## Scouting Analyze Examples\n\n'
        'DataFrames from READ steps are available as `df_players`, `df_player_gameweeks`, `df_fixtures`.\n'
        'Enriched players has: web_name, team, position, price, total_points, form, etc.\n\n'
        '### Points per million ranking\n'
        '```python\n'
        'df = df_players.copy()\n'
        'df["pts_per_m"] = df["total_points"] / df["price"]\n'
        'result = rank_by(df, "pts_per_m", n=10)\n'
        'print(result[["rank", "web_name", "team", "price", "total_points", "pts_per_m"]].to_string(index=False))\n'
        '```\n\n'
        '### Rolling form from GW stats\n'
        '```python\n'
        '# Use add_rolling_mean helper instead of manual rolling\n'
        'df = add_rolling_mean(df_player_gameweeks, "total_points", window=3, group_by="player_id")\n'
        '# Compute form trend (up/down/flat per player)\n'
        'trend = compute_form_trend(df)\n'
        'print(trend.to_string(index=False))\n'
        '```\n\n'
        '### Fixture difficulty run\n'
        '```python\n'
        '# Use compute_fixture_difficulty helper for a specific team\n'
        'fdr = compute_fixture_difficulty(df_fixtures, team_id=target_team_id, n_gws=5)\n'
        'print(fdr.to_string(index=False))\n'
        '\n'
        '# Or build full FDR grid manually from enriched fixtures (has home_team_name, away_team_name)\n'
        'home = df_fixtures[["home_team_name", "gameweek", "home_difficulty"]].rename(\n'
        '    columns={"home_team_name": "team", "home_difficulty": "fdr"})\n'
        'away = df_fixtures[["away_team_name", "gameweek", "away_difficulty"]].rename(\n'
        '    columns={"away_team_name": "team", "away_difficulty": "fdr"})\n'
        'fdr_df = pd.concat([home, away])\n'
        'avg_fdr = fdr_df.groupby("team")["fdr"].mean().sort_values()\n'
        '```'
    ),

    # === MARKET ===
    "market:read": (
        '## Market Read Examples\n\n'
        '### Transfer history\n'
        'User: "what transfers has Vinay made?"\n'
        'Action: db_read on transfers\n'
        'Filters: manager_id eq <vinay_manager_id>\n'
        'Note: Resolve "Vinay" via manager_links.label ilike or '
        'league_standings.manager_name ilike. FK-enrich player_in_id and player_out_id.\n\n'
        '### Price trend\n'
        'User: "Salah price history"\n'
        'Action: db_read on player_snapshots\n'
        'Filters: player_id eq <salah_uuid>\n'
        'Order: gameweek asc\n'
        'Note: player_snapshots REQUIRES a player_id filter.'
    ),
    "market:analyze": (
        '## Market Analyze Examples\n\n'
        'DataFrames from READ steps: `df_players` (enriched with team, position), '
        '`df_player_snapshots`, `df_fixtures`.\n\n'
        '### Transfer replacement comparison\n'
        '```python\n'
        '# Filter candidates by position\n'
        'candidates = df_players[df_players["position"] == "FWD"].copy()\n'
        'candidates["pts_per_m"] = candidates["total_points"] / candidates["price"]\n'
        '# Composite score: normalize form + value\n'
        'candidates["form_norm"] = candidates["form"] / candidates["form"].max()\n'
        'candidates["value_norm"] = candidates["pts_per_m"] / candidates["pts_per_m"].max()\n'
        'candidates["score"] = candidates["form_norm"] + candidates["value_norm"]\n'
        'result = rank_by(candidates, "score", n=5)\n'
        'print(result[["rank", "web_name", "team", "price", "form", "pts_per_m", "score"]].to_string(index=False))\n'
        '```\n\n'
        '### Price velocity analysis\n'
        '```python\n'
        '# Use compute_price_velocity helper on snapshot data\n'
        'velocity = compute_price_velocity(df_player_snapshots)\n'
        'risers = velocity[velocity["direction"] == "rising"].nlargest(5, "velocity")\n'
        'print(risers.to_string(index=False))\n'
        '```'
    ),

    # === LEAGUE ===
    "league:read": (
        '## League Read Examples\n\n'
        '### League table\n'
        'User: "show the league table"\n'
        'Action: db_read on league_standings\n'
        'Filters: league_id eq <user_league>, gameweek eq <current_gw>\n'
        'Order: rank asc\n'
        'Note: Quick mode candidate. league_id auto-injected by middleware.\n\n'
        '### Rivalry data gathering\n'
        'User: "how am I doing vs Vinay?"\n'
        'Step 1: db_read league_standings for both managers, filter gameweek gte <current_gw - 5>\n'
        'Step 2: db_read squads for both managers, filter gameweek eq <current_gw>\n'
        'Step 3: db_read players for all player_ids in both squads\n'
        'Step 4: db_read fixtures for next 3 GWs'
    ),
    "league:analyze": (
        '## League Analyze Examples\n\n'
        'DataFrames from READ steps: `df_squads` (both managers), `df_players`, '
        '`df_league_standings`.\n\n'
        '### Differential analysis\n'
        '```python\n'
        '# Use compute_differentials helper for squad comparison\n'
        'diffs = compute_differentials(df_squads_mine, df_squads_rival, player_col="player_id")\n'
        '# Enrich differentials with player details\n'
        'diffs_enriched = diffs.merge(\n'
        '    df_players[["id", "web_name", "team", "form", "total_points"]],\n'
        '    left_on="player_id", right_on="id", how="left"\n'
        ')\n'
        'my_diffs = diffs_enriched[diffs_enriched["owner"] == "a"]\n'
        'rival_diffs = diffs_enriched[diffs_enriched["owner"] == "b"]\n'
        'print("My differentials:")\n'
        'print(my_diffs[["web_name", "team", "form"]].to_string(index=False))\n'
        '```\n\n'
        '### Points trajectory\n'
        '```python\n'
        'my_trend = df_league_standings[df_league_standings["manager_id"] == my_id].sort_values("gameweek")\n'
        'rival_trend = df_league_standings[df_league_standings["manager_id"] == rival_id].sort_values("gameweek")\n'
        '# Merge on gameweek to align rows safely\n'
        'merged = my_trend[["gameweek", "total_points"]].merge(\n'
        '    rival_trend[["gameweek", "total_points"]], on="gameweek", suffixes=("_me", "_rival")\n'
        ')\n'
        'if not merged.empty:\n'
        '    merged["gap"] = merged["total_points_me"] - merged["total_points_rival"]\n'
        '    gap_direction = "closing" if merged["gap"].iloc[-1] > merged["gap"].iloc[0] else "widening"\n'
        '    print(f"Gap trend: {gap_direction} (current gap: {merged[\'gap\'].iloc[-1]:+.0f})")\n'
        '# Line chart of points over time\n'
        'combined = pd.concat([my_trend.assign(who="me"), rival_trend.assign(who="rival")])\n'
        'render_line(combined, x="gameweek", y="total_points", hue="who", title="Points Trajectory")\n'
        '```'
    ),

    # === LIVE ===
    "live:read": (
        '## Live Read Examples\n\n'
        '### Live scorecard\n'
        'User: "how\'s this week going?"\n'
        'Step 1: db_read squads, filter manager_id + current GW\n'
        'Step 2: db_read player_gameweeks, filter gameweek eq <current_gw>, '
        'player_id in [<squad player_ids>]\n'
        'Step 3: db_read gameweeks, filter is_current eq true (for GW average)'
    ),
    "live:analyze": (
        '## Live Analyze Examples\n\n'
        'DataFrames from READ steps: `df_squads`, `df_player_gameweeks`.\n\n'
        '### Compute live total\n'
        '```python\n'
        '# Merge enriched squad with GW stats for current-GW points\n'
        '# Enriched squad has player_total_points; player_gameweeks has total_points (no collision)\n'
        'merged = df_squads.merge(df_player_gameweeks, on="player_id", suffixes=("", "_gw"))\n'
        'merged["effective_pts"] = merged["total_points"] * merged["multiplier"]\n'
        'starting = merged[merged["slot"] <= 11]\n'
        'bench = merged[merged["slot"] > 11]\n'
        'live_total = starting["effective_pts"].sum()\n'
        'bench_pts = bench["total_points"].sum()\n'
        'captain = starting[starting["is_captain"] == True]\n'
        'cap_pts = captain["effective_pts"].iloc[0] if not captain.empty else 0\n'
        'print(f"Live total: {live_total:.0f}, Captain: {cap_pts:.0f}, Bench: {bench_pts:.0f}")\n'
        '```'
    ),

    # === FIXTURES ===
    "fixtures:read": (
        '## Fixture Read Examples\n\n'
        '### Upcoming fixtures for a team\n'
        'User: "Arsenal fixtures"\n'
        'Action: db_read on fixtures\n'
        'Filters: home_team_id eq <arsenal_uuid> OR away_team_id eq <arsenal_uuid>, '
        'finished eq false\n'
        'Order: gameweek asc\n'
        'Note: May need two reads (one for home, one for away) if OR filters '
        'aren\'t supported. Then combine in ANALYZE.\n\n'
        '### Fixture difficulty grid\n'
        'User: "fixture difficulty next 5 GWs"\n'
        'Action: db_read on fixtures\n'
        'Filters: gameweek gte <current_gw>, gameweek lte <current_gw + 5>\n'
        'Limit: 50'
    ),
    "fixtures:analyze": (
        '## Fixture Analyze Examples\n\n'
        'DataFrames from READ steps: `df_fixtures` (enriched with `home_team_name`, `away_team_name` short names).\n\n'
        '### Team FDR ranking\n'
        '```python\n'
        '# Enriched fixtures have home_team_name and away_team_name (short names)\n'
        'home = df_fixtures[["home_team_name", "gameweek", "home_difficulty"]].rename(\n'
        '    columns={"home_team_name": "team", "home_difficulty": "fdr"})\n'
        'away = df_fixtures[["away_team_name", "gameweek", "away_difficulty"]].rename(\n'
        '    columns={"away_team_name": "team", "away_difficulty": "fdr"})\n'
        'fdr_df = pd.concat([home, away])\n'
        'avg_fdr = fdr_df.groupby("team")["fdr"].mean().sort_values()\n'
        'top_10 = avg_fdr.head(10)\n'
        'print("Easiest fixture runs:")\n'
        'for team, fdr in top_10.items():\n'
        '    print(f"  {team}: avg FDR = {fdr:.2f}")\n'
        '```\n\n'
        '### FDR heatmap\n'
        '```python\n'
        '# Unstack home/away into rows, then pivot to team x GW grid\n'
        'home = df_fixtures[["home_team_name", "gameweek", "home_difficulty"]].rename(\n'
        '    columns={"home_team_name": "team", "home_difficulty": "difficulty"})\n'
        'away = df_fixtures[["away_team_name", "gameweek", "away_difficulty"]].rename(\n'
        '    columns={"away_team_name": "team", "away_difficulty": "difficulty"})\n'
        'all_rows = pd.concat([home, away])\n'
        'pivot = all_rows.pivot_table(index="team", columns="gameweek", values="difficulty", aggfunc="mean")\n'
        'render_heatmap(pivot, title="Fixture Difficulty Heatmap", cmap="RdYlGn_r", vmin=1, vmax=5)\n'
        '```'
    ),

    # =========================================================================
    # ANALYZE SUB-TYPE EXAMPLES: Assessment (FPL domain intelligence)
    # =========================================================================

    "scouting:analyze:assessment": (
        '## Scouting Assessment — FPL Domain Intelligence\n\n'
        'Your job: clean and validate the player data BEFORE computation.\n'
        'Filter out noise, flag risks, ensure data quality.\n\n'
        '### Filter to relevant players\n'
        '```python\n'
        '# Start with READ step data\n'
        'df = df_players.copy()\n'
        '\n'
        '# CRITICAL: Exclude non-playing players (0 minutes = never selected)\n'
        'df = df[df["minutes"] > 0]\n'
        '\n'
        '# Exclude injured players\n'
        'if "status" in df.columns:\n'
        '    df = df[df["status"] != "i"]\n'
        '\n'
        '# Flag rotation risks (avg < 60 mins = not nailed)\n'
        'if "minutes" in df.columns:\n'
        '    df["rotation_risk"] = df["minutes"] < 60 * df.get("appearances", 1)\n'
        '\n'
        '# Flag players with news (yellow/red flags)\n'
        'if "news" in df.columns:\n'
        '    df["has_news"] = df["news"].fillna("").str.len() > 0\n'
        '\n'
        'print(f"Filtered: {len(df)} active players from {len(df_players)} total")\n'
        'print(f"Rotation risks: {df[\"rotation_risk\"].sum() if \"rotation_risk\" in df.columns else \"N/A\"}")\n'
        '```\n\n'
        '**Key rules:**\n'
        '- ALWAYS filter `minutes > 0` for scouting — players with 0 mins are irrelevant\n'
        '- Check `status` column: "a" = available, "i" = injured, "u" = unavailable, "d" = doubtful\n'
        '- The `news` column has injury/suspension details — flag but don\'t exclude "d" (doubtful)\n'
        '- Output the FILTERED DataFrame for the Compute step to use'
    ),

    "fixtures:analyze:assessment": (
        '## Fixture Assessment — FPL Domain Intelligence\n\n'
        'Your job: validate fixture data and prepare it for computation.\n\n'
        '### Validate and prepare fixture data\n'
        '```python\n'
        'df = df_fixtures.copy()\n'
        '\n'
        '# Check GW range covers the requested window\n'
        'gw_range = df["gameweek"].unique()\n'
        'print(f"GWs available: {sorted(gw_range)}")\n'
        '\n'
        '# Check for blank GWs (teams with no fixture in a GW)\n'
        'all_teams = set(df["home_team_name"].unique()) | set(df["away_team_name"].unique())\n'
        'for gw in sorted(gw_range):\n'
        '    gw_teams = set(df[df["gameweek"] == gw]["home_team_name"]) | set(df[df["gameweek"] == gw]["away_team_name"])\n'
        '    blanks = all_teams - gw_teams\n'
        '    if blanks:\n'
        '        print(f"GW{gw} blanks: {blanks}")\n'
        '\n'
        '# Check for double GWs (teams with 2+ fixtures in a GW)\n'
        'home_counts = df.groupby(["home_team_name", "gameweek"]).size()\n'
        'away_counts = df.groupby(["away_team_name", "gameweek"]).size()\n'
        'doubles = home_counts[home_counts > 1] if len(home_counts[home_counts > 1]) > 0 else "None"\n'
        'print(f"Double GWs: {doubles}")\n'
        '\n'
        '# Verify enriched columns are populated\n'
        'assert "home_team_name" in df.columns, "Missing home_team_name enrichment"\n'
        'assert "away_team_name" in df.columns, "Missing away_team_name enrichment"\n'
        '```\n\n'
        '**Key rules:**\n'
        '- Use `home_team_name` and `away_team_name` (enriched short names), NOT UUID columns\n'
        '- FDR: `home_difficulty` when team is HOME, `away_difficulty` when AWAY\n'
        '- Flag blank and double GWs — they affect fixture difficulty calculations\n'
        '- Output validated data for the Compute step'
    ),

    "squad:analyze:assessment": (
        '## Squad Assessment — FPL Domain Intelligence\n\n'
        'Your job: structure and validate squad data before computation.\n\n'
        '### Prepare squad data\n'
        '```python\n'
        'df = df_squads.copy()\n'
        '\n'
        '# Separate starting XI from bench\n'
        'starting = df[df["slot"] <= 11].copy()\n'
        'bench = df[df["slot"] > 11].copy()\n'
        'print(f"Starting: {len(starting)}, Bench: {len(bench)}")\n'
        '\n'
        '# Identify captain and vice-captain\n'
        'captain = starting[starting["is_captain"] == True]\n'
        'vice = starting[starting["is_vice_captain"] == True]\n'
        'if not captain.empty:\n'
        '    print(f"Captain: {captain.iloc[0][\"player_name\"]} (x{captain.iloc[0][\"multiplier\"]})")\n'
        '\n'
        '# Flag players with news/injury concerns\n'
        'if "player_name" in df.columns and "news" in df_players.columns:\n'
        '    flagged = df_players[df_players["news"].fillna("").str.len() > 0]\n'
        '    squad_flagged = df[df["player_id"].isin(flagged["id"])]\n'
        '    if not squad_flagged.empty:\n'
        '        print(f"Squad injury flags: {len(squad_flagged)} players")\n'
        '\n'
        '# Check for missing prices\n'
        'if "player_price" in df.columns:\n'
        '    missing = df["player_price"].isna().sum()\n'
        '    if missing:\n'
        '        print(f"Warning: {missing} players missing price data")\n'
        '```\n\n'
        '**Key rules:**\n'
        '- Slots 1-11 = starting XI, 12-15 = bench (ordered by bench priority)\n'
        '- Enriched squad has: player_name, player_price, player_form, player_total_points\n'
        '- For position, merge with df_players on player_id → id'
    ),

    "league:analyze:assessment": (
        '## League Assessment — FPL Domain Intelligence\n\n'
        'Your job: validate league/rivalry data before computation.\n\n'
        '### Validate rivalry data\n'
        '```python\n'
        '# Check both managers present in standings\n'
        'managers = df_league_standings["manager_id"].unique()\n'
        'print(f"Managers in standings: {len(managers)}")\n'
        '\n'
        '# Check GW alignment between datasets\n'
        'standings_gws = sorted(df_league_standings["gameweek"].unique())\n'
        'squad_gws = sorted(df_squads["gameweek"].unique()) if "gameweek" in df_squads.columns else []\n'
        'print(f"Standings GWs: {standings_gws}")\n'
        'print(f"Squad GWs: {squad_gws}")\n'
        '\n'
        '# Identify shared vs differential players\n'
        'if len(df_squads) > 0 and "manager_id" in df_squads.columns:\n'
        '    mgr_ids = df_squads["manager_id"].unique()\n'
        '    if len(mgr_ids) >= 2:\n'
        '        squad_a = set(df_squads[df_squads["manager_id"] == mgr_ids[0]]["player_id"])\n'
        '        squad_b = set(df_squads[df_squads["manager_id"] == mgr_ids[1]]["player_id"])\n'
        '        shared = squad_a & squad_b\n'
        '        diff_a = squad_a - squad_b\n'
        '        diff_b = squad_b - squad_a\n'
        '        print(f"Shared: {len(shared)}, Manager A unique: {len(diff_a)}, Manager B unique: {len(diff_b)}")\n'
        '```\n\n'
        '**Key rules:**\n'
        '- Resolve manager names via league_standings.manager_name (denormalized)\n'
        '- manager_id is an integer FK, not UUID — don\'t try to enrich it\n'
        '- Align GW ranges before comparing trends'
    ),

    # =========================================================================
    # ANALYZE SUB-TYPE EXAMPLES: Compute (Python analytics)
    # =========================================================================

    "scouting:analyze:compute": (
        '## Scouting Compute — Python Analytics\n\n'
        'Your job: compute derived metrics, rank, and aggregate.\n'
        'Assume data has been filtered by the Assessment step.\n\n'
        '### Points per million ranking\n'
        '```python\n'
        'df = df_players.copy()\n'
        'df["pts_per_m"] = df["total_points"] / df["price"]\n'
        'result = rank_by(df, "pts_per_m", n=10)\n'
        'print(result[["rank", "web_name", "team", "price", "total_points", "pts_per_m"]].to_string(index=False))\n'
        '```\n\n'
        '### Composite score (form + value + fixtures)\n'
        '```python\n'
        '# Normalize metrics to 0-1 range for composite\n'
        'df["form_norm"] = df["form"] / df["form"].max() if df["form"].max() > 0 else 0\n'
        'df["value_norm"] = df["pts_per_m"] / df["pts_per_m"].max() if df["pts_per_m"].max() > 0 else 0\n'
        'df["composite"] = df["form_norm"] * 0.4 + df["value_norm"] * 0.6\n'
        'result = rank_by(df, "composite", n=10)\n'
        'print(result[["rank", "web_name", "team", "price", "form", "pts_per_m", "composite"]].to_string(index=False))\n'
        '```\n\n'
        '### Rolling form from GW stats\n'
        '```python\n'
        'df = add_rolling_mean(df_player_gameweeks, "total_points", window=3, group_by="player_id")\n'
        'trend = compute_form_trend(df)\n'
        'print(trend.to_string(index=False))\n'
        '```\n\n'
        '**Available helpers:** `rank_by(df, metric, n)`, `add_rolling_mean(df, col, window, group_by)`, '
        '`compute_form_trend(df)`, `compute_fixture_difficulty(df, team_id, n_gws)`'
    ),

    "fixtures:analyze:compute": (
        '## Fixture Compute — Python Analytics\n\n'
        'Your job: compute FDR aggregations, pivots, and rankings.\n'
        'Assume fixture data has been validated by the Assessment step.\n\n'
        '### Team FDR ranking\n'
        '```python\n'
        'home = df_fixtures[["home_team_name", "gameweek", "home_difficulty"]].rename(\n'
        '    columns={"home_team_name": "team", "home_difficulty": "fdr"})\n'
        'away = df_fixtures[["away_team_name", "gameweek", "away_difficulty"]].rename(\n'
        '    columns={"away_team_name": "team", "away_difficulty": "fdr"})\n'
        'fdr_df = pd.concat([home, away])\n'
        'avg_fdr = fdr_df.groupby("team")["fdr"].mean().sort_values()\n'
        'print("Easiest fixture runs:")\n'
        'for team, fdr in avg_fdr.head(10).items():\n'
        '    print(f"  {team}: avg FDR = {fdr:.2f}")\n'
        '```\n\n'
        '### FDR heatmap grid (for GENERATE step)\n'
        '```python\n'
        'home = df_fixtures[["home_team_name", "gameweek", "home_difficulty"]].rename(\n'
        '    columns={"home_team_name": "team", "home_difficulty": "difficulty"})\n'
        'away = df_fixtures[["away_team_name", "gameweek", "away_difficulty"]].rename(\n'
        '    columns={"away_team_name": "team", "away_difficulty": "difficulty"})\n'
        'all_rows = pd.concat([home, away])\n'
        'pivot = all_rows.pivot_table(index="team", columns="gameweek", values="difficulty", aggfunc="mean")\n'
        '# Output pivot for GENERATE step or print directly\n'
        'print(pivot.to_string())\n'
        '```\n\n'
        '**Key:** Use `home_team_name`/`away_team_name` (enriched), NOT UUID columns. '
        'Use `home_difficulty` when team is HOME, `away_difficulty` when AWAY.'
    ),

    "squad:analyze:compute": (
        '## Squad Compute — Python Analytics\n\n'
        'Your job: compute squad metrics, formation, and value analysis.\n'
        'Assume squad data has been structured by the Assessment step.\n\n'
        '### Formation and squad value\n'
        '```python\n'
        'starting = df_squads[df_squads["slot"] <= 11].copy()\n'
        'bench = df_squads[df_squads["slot"] > 11].copy()\n'
        '\n'
        '# Formation: merge with players for position\n'
        'starting_full = starting.merge(\n'
        '    df_players[["id", "position"]], left_on="player_id", right_on="id", how="left"\n'
        ')\n'
        'pos_counts = starting_full["position"].value_counts()\n'
        'formation = "-".join(str(pos_counts.get(p, 0)) for p in ["DEF", "MID", "FWD"])\n'
        '\n'
        '# Squad value\n'
        'squad_value = starting["player_price"].sum()\n'
        'bench_value = bench["player_price"].sum()\n'
        'bench_pts = bench["player_total_points"].sum()\n'
        '\n'
        'print(f"Formation: {formation}")\n'
        'print(f"Starting XI value: £{squad_value:.1f}m, Bench: £{bench_value:.1f}m")\n'
        'print(f"Points on bench: {bench_pts}")\n'
        '```\n\n'
        '**Key:** Enriched squad has player_name, player_price, player_form, player_total_points. '
        'For position, merge with df_players on player_id → id.'
    ),

    "league:analyze:compute": (
        '## League Compute — Python Analytics\n\n'
        'Your job: compute differentials, trajectories, and ownership analysis.\n'
        'Assume data has been validated by the Assessment step.\n\n'
        '### Differential analysis\n'
        '```python\n'
        'diffs = compute_differentials(df_squads_mine, df_squads_rival, player_col="player_id")\n'
        'diffs_enriched = diffs.merge(\n'
        '    df_players[["id", "web_name", "team", "form", "total_points"]],\n'
        '    left_on="player_id", right_on="id", how="left"\n'
        ')\n'
        'my_diffs = diffs_enriched[diffs_enriched["owner"] == "a"]\n'
        'rival_diffs = diffs_enriched[diffs_enriched["owner"] == "b"]\n'
        'print("My differentials:")\n'
        'print(my_diffs[["web_name", "team", "form"]].to_string(index=False))\n'
        '```\n\n'
        '### Points trajectory\n'
        '```python\n'
        'my_trend = df_league_standings[df_league_standings["manager_id"] == my_id].sort_values("gameweek")\n'
        'rival_trend = df_league_standings[df_league_standings["manager_id"] == rival_id].sort_values("gameweek")\n'
        'merged = my_trend[["gameweek", "total_points"]].merge(\n'
        '    rival_trend[["gameweek", "total_points"]], on="gameweek", suffixes=("_me", "_rival")\n'
        ')\n'
        'if not merged.empty:\n'
        '    merged["gap"] = merged["total_points_me"] - merged["total_points_rival"]\n'
        '    gap_direction = "closing" if merged["gap"].iloc[-1] > merged["gap"].iloc[0] else "widening"\n'
        '    print(f"Gap trend: {gap_direction} (current gap: {merged[\'gap\'].iloc[-1]:+.0f})")\n'
        '```\n\n'
        '**Available helpers:** `compute_differentials(squad_a, squad_b)`, '
        '`rank_by(df, metric, n)`, `add_rolling_mean(df, col, window)`'
    ),
}
