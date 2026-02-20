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
    """Get contextual examples for a subdomain and step type."""
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
        '# Or build full FDR grid manually from enriched fixtures (has home_team, away_team)\n'
        'rows = []\n'
        'for _, fix in df_fixtures.iterrows():\n'
        '    rows.append({"team": fix["home_team"], "gw": fix["gameweek"], "fdr": fix["home_difficulty"]})\n'
        '    rows.append({"team": fix["away_team"], "gw": fix["gameweek"], "fdr": fix["away_difficulty"]})\n'
        'fdr_df = pd.DataFrame(rows)\n'
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
        'DataFrames from READ steps: `df_fixtures` (enriched with home_team, away_team short names).\n\n'
        '### Team FDR ranking\n'
        '```python\n'
        '# Enriched fixtures already have team short names (home_team, away_team)\n'
        'rows = []\n'
        'for _, fix in df_fixtures.iterrows():\n'
        '    rows.append({"team": fix["home_team"], "gw": fix["gameweek"], "fdr": fix["home_difficulty"]})\n'
        '    rows.append({"team": fix["away_team"], "gw": fix["gameweek"], "fdr": fix["away_difficulty"]})\n'
        'fdr_df = pd.DataFrame(rows)\n'
        'avg_fdr = fdr_df.groupby("team")["fdr"].mean().sort_values()\n'
        'top_10 = avg_fdr.head(10)\n'
        'print("Easiest fixture runs:")\n'
        'for team, fdr in top_10.items():\n'
        '    print(f"  {team}: avg FDR = {fdr:.2f}")\n'
        '```\n\n'
        '### FDR heatmap\n'
        '```python\n'
        '# Build FDR grid (self-contained)\n'
        'rows = []\n'
        'for _, fix in df_fixtures.iterrows():\n'
        '    rows.append({"team": fix["home_team"], "gw": fix["gameweek"], "fdr": fix["home_difficulty"]})\n'
        '    rows.append({"team": fix["away_team"], "gw": fix["gameweek"], "fdr": fix["away_difficulty"]})\n'
        'fdr_df = pd.DataFrame(rows)\n'
        'avg_fdr = fdr_df.groupby("team")["fdr"].mean().sort_values()\n'
        '# Pivot to team × GW grid for heatmap\n'
        'gws = sorted(fdr_df["gw"].unique())[:5]\n'
        'top_teams = avg_fdr.head(10).index.tolist()\n'
        'pivot = fdr_df[fdr_df["team"].isin(top_teams) & fdr_df["gw"].isin(gws)].pivot_table(\n'
        '    index="team", columns="gw", values="fdr", aggfunc="first"\n'
        ')\n'
        'pivot.columns = [f"GW{int(c)}" for c in pivot.columns]\n'
        'render_heatmap(pivot, title="Fixture Difficulty: Easiest 10 Teams")\n'
        '```'
    ),
}
