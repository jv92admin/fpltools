#!/usr/bin/env python3
"""
Non-interactive FPL conversation runner for eval/prompt iteration.

Usage:
    python scripts/chat_runner.py                    # Run all test conversations
    python scripts/chat_runner.py test1_squad        # Run specific test
    python scripts/chat_runner.py test1_squad test3   # Run multiple tests

Runs predefined multi-turn conversations through the real Alfred pipeline,
logs prompts, and prints results for inspection.

Prerequisites:
    - OPENAI_API_KEY in .env (required by alfred-core)
    - FPL_DEV_USER_ID in .env (Supabase auth user ID from seed_demo.py)
    - Supabase seeded with data (python scripts/sync.py --from-gw 22)

Prompt logs are written to prompt_logs/ for detailed inspection.
"""

import asyncio
import glob
import io
import os
import sys
import tempfile
import time
from pathlib import Path

# Fix Windows console encoding for Unicode (arrows, accents, etc.)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Enable prompt logging before any alfred imports
os.environ["ALFRED_LOG_PROMPTS"] = "1"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import alfred_fpl  # noqa: F401 — triggers domain registration

from alfred.graph.workflow import run_alfred
from alfred.memory.conversation import initialize_conversation


# ---------------------------------------------------------------------------
# Test conversations
# ---------------------------------------------------------------------------

TEST_CONVERSATIONS = {
    "test1_squad": {
        "name": "Test 1: Quick Squad View",
        "turns": [
            "show my squad",
        ],
    },
    "test2_scouting": {
        "name": "Test 2: Scout + Compare",
        "turns": [
            "show me midfielders under 8m",
            "compare the top 2",
        ],
    },
    "test3_fixtures": {
        "name": "Test 3: Fixture Analysis",
        "turns": [
            "which teams have the easiest fixtures next 5 GWs?",
        ],
    },
    "test4_league": {
        "name": "Test 4: League Rivalry",
        "turns": [
            "show my league standings",
            "compare my squad with the league leader",
        ],
    },
    "test5_transfers": {
        "name": "Test 5: Transfer Planning",
        "turns": [
            "show my squad",
            "who are the cheapest performing forwards?",
        ],
    },
    "test6_market": {
        "name": "Test 6: Market Trends",
        "turns": [
            "show me the most transferred-in players this week",
        ],
    },
    # ---- ANALYZE / GENERATE focused tests ----
    "test7_analyze_form": {
        "name": "Test 7: Player Form Analysis (ANALYZE)",
        "turns": [
            "show me the top 10 midfielders by total points",
            "analyze their form over the last 5 gameweeks",
        ],
    },
    "test8_fixture_heatmap": {
        "name": "Test 8: Fixture Heatmap (GENERATE)",
        "turns": [
            "show me a fixture difficulty heatmap for the next 5 gameweeks",
        ],
    },
    "test9_value_analysis": {
        "name": "Test 9: Value Comparison (ANALYZE)",
        "turns": [
            "show me forwards under 9m",
            "compare the top 3 by points per million",
        ],
    },
    # ---- Multi-step / ambitious tests ----
    "test10_captain_data": {
        "name": "Test 10: Captain Data View (READ+ANALYZE)",
        "turns": [
            "show my squad",
            "rank my starting players by form and fixture difficulty for the next gameweek",
        ],
    },
    "test11_replacement_search": {
        "name": "Test 11: Transfer Replacement (READ+ANALYZE+CHART)",
        "turns": [
            "show me defenders under 6m sorted by total points",
            "chart the top 5 by points per million as a bar chart",
        ],
    },
    "test12_full_pipeline": {
        "name": "Test 12: Full Pipeline (READ+ANALYZE+GENERATE)",
        "turns": [
            "which teams have the easiest fixtures next 5 gameweeks? show me a heatmap",
        ],
    },
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _check_recent_charts(since_ts: float) -> list[str]:
    """Find chart PNGs generated since the given timestamp."""
    chart_dir = tempfile.gettempdir()
    chart_paths = glob.glob(os.path.join(chart_dir, "fpl_exec_*", "*.png"))
    return [p for p in chart_paths if os.path.getmtime(p) >= since_ts]


def _detect_step_types(response: str, charts: list[str]) -> list[str]:
    """Detect which step types were used based on response content and artifacts."""
    types = ["READ"]  # Always at least a READ
    # Check for analysis indicators in response
    analysis_signals = [
        "pts_per_m", "pts/m", "points per million", "form trend",
        "rolling", "ranked", "comparison", "differential",
        "avg fdr", "average fdr", "fixture difficulty",
    ]
    if any(s in (response or "").lower() for s in analysis_signals):
        types.append("ANALYZE")
    if charts:
        types.append("GENERATE")
    return types


async def run_conversation(test_id: str, test: dict, user_id: str) -> dict:
    """Run a single multi-turn conversation and return results."""
    print(f"\n{'='*60}")
    print(f"  {test['name']}")
    print(f"{'='*60}")

    conversation = initialize_conversation()
    results = []

    for i, message in enumerate(test["turns"], 1):
        print(f"\n  [Turn {i}] You: {message}")
        start = time.time()

        try:
            response, conversation = await run_alfred(
                user_message=message,
                user_id=user_id,
                conversation=conversation,
            )
            elapsed = time.time() - start

            # Truncate for display
            display = response[:500] + "..." if len(response) > 500 else response
            print(f"  [Turn {i}] Alfred ({elapsed:.1f}s): {display}")

            # Check for chart artifacts
            charts = _check_recent_charts(start)
            if charts:
                print(f"  [Turn {i}] Charts generated: {len(charts)}")
                for c in charts:
                    size = os.path.getsize(c)
                    print(f"    -> {c} ({size:,} bytes)")

            results.append({
                "turn": i,
                "message": message,
                "response": response,
                "elapsed": elapsed,
                "error": None,
                "charts": charts,
            })

        except Exception as e:
            elapsed = time.time() - start
            print(f"  [Turn {i}] ERROR ({elapsed:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "turn": i,
                "message": message,
                "response": None,
                "elapsed": elapsed,
                "error": str(e),
                "charts": [],
            })

    return {"test_id": test_id, "name": test["name"], "results": results}


async def main():
    from alfred_fpl.config import settings
    user_id = settings.fpl_dev_user_id

    if not user_id:
        print("ERROR: FPL_DEV_USER_ID not set in .env")
        print("Run `python scripts/seed_demo.py` first, then add the user ID to .env")
        sys.exit(1)

    # Select which tests to run
    if len(sys.argv) > 1:
        test_ids = sys.argv[1:]
    else:
        test_ids = list(TEST_CONVERSATIONS.keys())

    print(f"FPL Chat Runner — {len(test_ids)} conversation(s)")
    print(f"User: {user_id[:8]}...")
    print(f"Prompt logs: prompt_logs/")

    all_results = []
    for test_id in test_ids:
        if test_id not in TEST_CONVERSATIONS:
            print(f"\nUnknown test: {test_id}")
            continue
        result = await run_conversation(test_id, TEST_CONVERSATIONS[test_id], user_id)
        all_results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    total_charts = 0
    analyze_count = 0
    generate_count = 0
    for r in all_results:
        turns = r["results"]
        errors = sum(1 for t in turns if t["error"])
        total_time = sum(t["elapsed"] for t in turns)
        charts = sum(len(t.get("charts", [])) for t in turns)
        total_charts += charts
        status = "PASS" if errors == 0 else f"FAIL ({errors} errors)"
        # Detect step types across all turns
        all_types = set()
        for t in turns:
            step_types = _detect_step_types(t.get("response", ""), t.get("charts", []))
            all_types.update(step_types)
        if "ANALYZE" in all_types:
            analyze_count += 1
        if "GENERATE" in all_types:
            generate_count += 1
        types_str = "+".join(sorted(all_types))
        chart_info = f" | {charts} chart(s)" if charts else ""
        print(f"  {r['name']}: {status} ({total_time:.1f}s) [{types_str}]{chart_info}")

    total_errors = sum(
        sum(1 for t in r["results"] if t["error"]) for r in all_results
    )
    print(f"\n  Pipeline coverage: {analyze_count} ANALYZE, {generate_count} GENERATE, {total_charts} charts")
    print(f"  Check prompt_logs/ for detailed LLM traces.")
    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
