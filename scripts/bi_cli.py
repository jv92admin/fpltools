"""Quick CLI for testing BI library functions.

Usage:
    python scripts/bi_cli.py players --top 10 --metric total_points
    python scripts/bi_cli.py players --top 10 --metric form --position MID
    python scripts/bi_cli.py fixtures --team ARS --gws 5
    python scripts/bi_cli.py execute "df = rank_by(df_players, 'form', n=5); print(df[['web_name','form']])"
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def cmd_players(args):
    """List and rank players."""
    from alfred_fpl.bi.data_access import fetch_enriched, Filter
    from alfred_fpl.bi.analytics import rank_by

    filters = []
    if args.position:
        filters.append(Filter("position", "eq", args.position))

    df = fetch_enriched("players", filters=filters, limit=100)

    if df.empty:
        print("No players found.")
        return

    top = rank_by(df, args.metric, n=args.top)

    display_cols = ["rank", "web_name"]
    if "team" in top.columns:
        display_cols.append("team")
    if "position" in top.columns:
        display_cols.append("position")
    display_cols.extend(["price", args.metric])
    display_cols = [c for c in display_cols if c in top.columns]

    print(top[display_cols].to_string(index=False))

    if args.chart:
        from alfred_fpl.bi.viz import render_bar
        path = render_bar(
            top, x="web_name", y=args.metric,
            title=f"Top {args.top} Players by {args.metric}",
            horizontal=True,
        )
        print(f"\nChart saved: {path}")


def cmd_fixtures(args):
    """Show fixture difficulty for a team."""
    from alfred_fpl.bi.data_access import fetch_enriched, Filter, fetch_df, QuerySpec
    from alfred_fpl.bi.analytics import compute_fixture_difficulty

    # Find team by short_name
    teams = fetch_df(QuerySpec(
        table="teams",
        filters=[Filter("short_name", "ilike", f"%{args.team}%")],
    ))

    if teams.empty:
        print(f"Team '{args.team}' not found.")
        return

    team_id = teams.iloc[0]["id"]
    team_name = teams.iloc[0].get("short_name", args.team)
    print(f"Team: {team_name} ({team_id})")

    fixtures = fetch_enriched("fixtures", limit=200)
    if fixtures.empty:
        print("No fixtures found.")
        return

    fdr = compute_fixture_difficulty(fixtures, team_id, n_gws=args.gws)
    if fdr.empty:
        print("No upcoming fixtures found.")
        return

    display_cols = [c for c in ["gameweek", "opponent", "is_home", "fdr"] if c in fdr.columns]
    print(f"\nNext {args.gws} fixtures:")
    print(fdr[display_cols].to_string(index=False))


def cmd_execute(args):
    """Execute code in the sandbox."""
    from alfred_fpl.bi.executor import execute
    from alfred_fpl.bi.data_access import fetch_enriched

    context = {}
    if not args.no_data:
        print("Fetching player data for context...")
        df_players = fetch_enriched("players", limit=50)
        context["df_players"] = df_players
        print(f"  df_players: {len(df_players)} rows")

    print(f"\nExecuting:\n  {args.code}\n")
    result = execute(args.code, context=context)

    if result.error:
        print(f"ERROR: {result.error}")
    else:
        if result.stdout:
            print(result.stdout)
        if result.dataframes:
            for name, df in result.dataframes.items():
                print(f"\n[DataFrame: {name}] ({len(df)} rows)")
                print(df.head(10).to_string())
        if result.charts:
            for path in result.charts:
                print(f"\nChart: {path}")
        print(f"\n({result.duration_ms}ms)")


def main():
    parser = argparse.ArgumentParser(description="FPL BI CLI")
    subparsers = parser.add_subparsers(dest="command")

    # players
    p = subparsers.add_parser("players", help="Rank players by metric")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--metric", default="total_points")
    p.add_argument("--position", default=None, help="Filter by position (GKP/DEF/MID/FWD)")
    p.add_argument("--chart", action="store_true", help="Render bar chart")

    # fixtures
    p = subparsers.add_parser("fixtures", help="Show fixture difficulty for a team")
    p.add_argument("--team", required=True, help="Team short name (e.g., ARS, LIV)")
    p.add_argument("--gws", type=int, default=5, help="Number of gameweeks")

    # execute
    p = subparsers.add_parser("execute", help="Execute code in the sandbox")
    p.add_argument("code", help="Python code to execute")
    p.add_argument("--no-data", action="store_true", help="Skip loading player data")

    args = parser.parse_args()

    if args.command == "players":
        cmd_players(args)
    elif args.command == "fixtures":
        cmd_fixtures(args)
    elif args.command == "execute":
        cmd_execute(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
