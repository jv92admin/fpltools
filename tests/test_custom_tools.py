"""Tests for custom tool integration (alfredagain 2.1.0).

Verifies:
- get_custom_tools() returns fpl_analyze and fpl_plot
- get_tool_enabled_step_types() includes 'generate'
- DataFrame session cache in middleware
- _execute_analysis handler: runs code, returns results, handles errors
- _execute_plot handler: renders charts, handles errors
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from alfred_fpl.domain import FPL_DOMAIN
from alfred_fpl.domain.crud_middleware import FPLMiddleware


# ---------------------------------------------------------------------------
# Mock ToolContext (mimics alfred.domain.base.ToolContext)
# ---------------------------------------------------------------------------

@dataclass
class MockToolContext:
    step_results: Any = None
    registry: Any = None
    current_step_results: list = field(default_factory=list)
    state: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def _has_tool_definition():
    try:
        from alfred.domain.base import ToolDefinition
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_tool_definition(), reason="alfredagain >= 2.1.0 required")
def test_custom_tools_registered():
    tools = FPL_DOMAIN.get_custom_tools()
    assert "fpl_analyze" in tools
    assert "fpl_plot" in tools


@pytest.mark.skipif(not _has_tool_definition(), reason="alfredagain >= 2.1.0 required")
def test_custom_tools_have_required_fields():
    tools = FPL_DOMAIN.get_custom_tools()
    for name, tool in tools.items():
        assert tool.name == name
        assert tool.description
        assert tool.params_schema
        assert tool.handler is not None


def test_custom_tools_graceful_without_2_1():
    """get_custom_tools returns {} when ToolDefinition isn't available."""
    tools = FPL_DOMAIN.get_custom_tools()
    # Either {} (pre-2.1.0) or populated (2.1.0+) — both are valid
    assert isinstance(tools, dict)


def test_tool_enabled_step_types_includes_generate():
    step_types = FPL_DOMAIN.get_tool_enabled_step_types()
    assert step_types == {"read", "write", "analyze", "generate"}


# ---------------------------------------------------------------------------
# DataFrame session cache (middleware)
# ---------------------------------------------------------------------------

class TestDataFrameCache:

    def setup_method(self):
        self.middleware = FPLMiddleware()

    def test_cache_starts_empty(self):
        assert self.middleware.get_dataframe_cache() == {}

    def test_post_read_caches_dataframe(self):
        records = [
            {"id": "abc", "web_name": "Salah", "price": 13.2},
            {"id": "def", "web_name": "Saka", "price": 10.5},
        ]
        asyncio.get_event_loop().run_until_complete(
            self.middleware.post_read(records, "players", "user1")
        )
        cache = self.middleware.get_dataframe_cache()
        assert "players" in cache
        assert len(cache["players"]) == 2
        assert list(cache["players"].columns) == ["id", "web_name", "price"]

    def test_post_read_overwrites_on_same_table(self):
        records1 = [{"id": "a", "web_name": "Salah"}]
        records2 = [{"id": "b", "web_name": "Saka"}, {"id": "c", "web_name": "Haaland"}]

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.middleware.post_read(records1, "players", "u"))
        loop.run_until_complete(self.middleware.post_read(records2, "players", "u"))

        cache = self.middleware.get_dataframe_cache()
        assert len(cache["players"]) == 2  # Second read wins

    def test_cache_multiple_tables(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            self.middleware.post_read([{"id": "a"}], "players", "u")
        )
        loop.run_until_complete(
            self.middleware.post_read([{"id": "b"}], "fixtures", "u")
        )
        cache = self.middleware.get_dataframe_cache()
        assert "players" in cache
        assert "fixtures" in cache

    def test_empty_records_not_cached(self):
        asyncio.get_event_loop().run_until_complete(
            self.middleware.post_read([], "players", "u")
        )
        assert self.middleware.get_dataframe_cache() == {}

    def test_clear_cache(self):
        asyncio.get_event_loop().run_until_complete(
            self.middleware.post_read([{"id": "a"}], "players", "u")
        )
        self.middleware.clear_dataframe_cache()
        assert self.middleware.get_dataframe_cache() == {}


# ---------------------------------------------------------------------------
# _load_dataframes
# ---------------------------------------------------------------------------

class TestLoadDataframes:

    def setup_method(self):
        """Seed the middleware cache with sample data."""
        self.domain = FPL_DOMAIN
        middleware = self.domain.get_crud_middleware()
        middleware.clear_dataframe_cache()
        # Manually populate the cache (simulates post_read)
        middleware._dataframe_cache["players"] = pd.DataFrame([
            {"id": "a", "web_name": "Salah", "price": 13.2},
            {"id": "b", "web_name": "Saka", "price": 10.5},
        ])
        middleware._dataframe_cache["fixtures"] = pd.DataFrame([
            {"id": "x", "gameweek": 25, "home_team_id": "t1", "away_team_id": "t2"},
        ])

    def teardown_method(self):
        self.domain.get_crud_middleware().clear_dataframe_cache()

    def test_loads_requested_datasets(self):
        ctx = self.domain._load_dataframes(["players"])
        assert "df_players" in ctx
        assert len(ctx["df_players"]) == 2

    def test_loads_all_cached_even_if_not_requested(self):
        ctx = self.domain._load_dataframes(["players"])
        assert "df_fixtures" in ctx  # Not requested but still available

    def test_empty_refs_loads_all(self):
        ctx = self.domain._load_dataframes([])
        assert "df_players" in ctx
        assert "df_fixtures" in ctx

    def test_missing_dataset_logged_not_error(self):
        """Requesting a non-cached dataset doesn't raise — just logs a warning."""
        ctx = self.domain._load_dataframes(["nonexistent"])
        assert "df_nonexistent" not in ctx
        # But all cached data is still available
        assert "df_players" in ctx


# ---------------------------------------------------------------------------
# _execute_analysis handler
# ---------------------------------------------------------------------------

class TestExecuteAnalysis:

    def setup_method(self):
        self.domain = FPL_DOMAIN
        middleware = self.domain.get_crud_middleware()
        middleware.clear_dataframe_cache()
        middleware._dataframe_cache["players"] = pd.DataFrame([
            {"web_name": "Salah", "price": 13.2, "total_points": 180},
            {"web_name": "Saka", "price": 10.5, "total_points": 150},
            {"web_name": "Haaland", "price": 14.0, "total_points": 160},
        ])

    def teardown_method(self):
        self.domain.get_crud_middleware().clear_dataframe_cache()

    def _run(self, params, ctx=None):
        if ctx is None:
            ctx = MockToolContext()
        return asyncio.get_event_loop().run_until_complete(
            self.domain._execute_analysis(params, "user1", ctx)
        )

    def test_basic_analysis(self):
        result = self._run({
            "code": "print(df_players['web_name'].tolist())",
            "datasets": ["players"],
        })
        assert "error" not in result
        assert "Salah" in result.get("stdout", "")

    def test_returns_dataframes_preview(self):
        result = self._run({
            "code": "top = df_players.sort_values('total_points', ascending=False).head(2)",
            "datasets": ["players"],
        })
        assert "error" not in result
        assert "dataframes" in result
        assert "top" in result["dataframes"]

    def test_returns_stdout(self):
        result = self._run({
            "code": 'print("hello from analysis")',
            "datasets": [],
        })
        assert result["stdout"] == "hello from analysis\n"

    def test_soft_failure_on_code_error(self):
        result = self._run({
            "code": "x = 1 / 0",
            "datasets": [],
        })
        assert "error" in result
        assert "ZeroDivisionError" in result["error"]

    def test_empty_code_returns_error(self):
        result = self._run({"code": "", "datasets": []})
        assert "error" in result

    def test_analytics_functions_available(self):
        result = self._run({
            "code": "ranked = rank_by(df_players, 'total_points', n=2)\nprint(ranked['web_name'].tolist())",
            "datasets": ["players"],
        })
        assert "error" not in result
        assert "Salah" in result.get("stdout", "")

    def test_chart_paths_returned_when_generated(self):
        result = self._run({
            "code": "render_bar(df=df_players, x='web_name', y='total_points', title='Points')",
            "datasets": ["players"],
        })
        assert "error" not in result
        assert "charts" in result
        assert len(result["charts"]) > 0
        assert result["charts"][0].endswith(".png")


# ---------------------------------------------------------------------------
# _execute_plot handler
# ---------------------------------------------------------------------------

class TestExecutePlot:

    def setup_method(self):
        self.domain = FPL_DOMAIN
        middleware = self.domain.get_crud_middleware()
        middleware.clear_dataframe_cache()
        middleware._dataframe_cache["players"] = pd.DataFrame([
            {"web_name": "Salah", "price": 13.2, "total_points": 180},
            {"web_name": "Saka", "price": 10.5, "total_points": 150},
        ])

    def teardown_method(self):
        self.domain.get_crud_middleware().clear_dataframe_cache()

    def _run(self, params, ctx=None):
        if ctx is None:
            ctx = MockToolContext()
        return asyncio.get_event_loop().run_until_complete(
            self.domain._execute_plot(params, "user1", ctx)
        )

    def test_plot_returns_chart_path(self):
        result = self._run({
            "code": "render_bar(df=df_players, x='web_name', y='total_points', title='Top Players')",
            "title": "Top Players",
        })
        assert "error" not in result
        assert "charts" in result
        assert len(result["charts"]) > 0

    def test_plot_includes_title(self):
        result = self._run({
            "code": "render_bar(df=df_players, x='web_name', y='total_points')",
            "title": "My Chart",
        })
        assert result.get("title") == "My Chart"

    def test_plot_warning_on_no_chart(self):
        result = self._run({
            "code": "print('no chart here')",
            "title": "Nothing",
        })
        assert "warning" in result

    def test_plot_error_on_empty_code(self):
        result = self._run({"code": "", "title": "Empty"})
        assert "error" in result

    def test_plot_soft_failure(self):
        result = self._run({
            "code": "raise ValueError('bad plot')",
            "title": "Broken",
        })
        assert "error" in result
        assert "ValueError" in result["error"]
