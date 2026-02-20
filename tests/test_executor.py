"""Tests for the sandboxed Python executor."""

import pandas as pd
import pytest

from alfred_fpl.bi.executor import execute


class TestBasicExecution:
    def test_simple_expression(self):
        result = execute("x = 1 + 2")
        assert result.error is None
        assert result.dataframes.get("x") is None  # int, not DataFrame

    def test_print_captured(self):
        result = execute('print("hello world")')
        assert result.error is None
        assert "hello world" in result.stdout

    def test_multiline(self):
        code = """
a = [1, 2, 3]
b = sum(a)
print(f"sum = {b}")
"""
        result = execute(code)
        assert result.error is None
        assert "sum = 6" in result.stdout

    def test_empty_code(self):
        result = execute("")
        assert result.error == "Empty code string."

    def test_duration_tracked(self):
        result = execute("x = 1")
        assert result.duration_ms >= 0


class TestPandasAccess:
    def test_create_dataframe(self):
        code = 'df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})'
        result = execute(code)
        assert result.error is None
        assert "df" in result.dataframes
        assert len(result.dataframes["df"]) == 3

    def test_context_dataframes(self):
        context_df = pd.DataFrame({"x": [10, 20, 30]})
        code = """
total = df_input["x"].sum()
print(f"total = {total}")
"""
        result = execute(code, context={"df_input": context_df})
        assert result.error is None
        assert "total = 60" in result.stdout

    def test_pandas_operations(self):
        code = """
df = pd.DataFrame({
    "player": ["Salah", "Saka", "Haaland"],
    "points": [180, 150, 170],
    "price": [13.5, 10.2, 14.0],
})
df["pts_per_m"] = df["points"] / df["price"]
top = df.nlargest(2, "pts_per_m")
print(top["player"].tolist())
"""
        result = execute(code)
        assert result.error is None
        assert "Saka" in result.stdout  # Best pts/m

    def test_numpy_access(self):
        code = """
arr = np.array([1, 2, 3, 4, 5])
print(f"mean = {np.mean(arr)}")
"""
        result = execute(code)
        assert result.error is None
        assert "mean = 3.0" in result.stdout


class TestAnalyticsFunctions:
    def test_add_rolling_mean(self):
        code = """
df = pd.DataFrame({
    "gw": [1, 2, 3, 4, 5],
    "pts": [5, 8, 3, 10, 7],
})
df = add_rolling_mean(df, "pts", window=3)
print(df["pts_rolling_3"].tolist())
"""
        result = execute(code)
        assert result.error is None
        assert "df" in result.dataframes
        assert "pts_rolling_3" in result.dataframes["df"].columns

    def test_rank_by(self):
        code = """
df = pd.DataFrame({
    "name": ["a", "b", "c", "d"],
    "score": [10, 30, 20, 40],
})
top = rank_by(df, "score", n=2)
print(top["name"].tolist())
"""
        result = execute(code)
        assert result.error is None
        assert "top" in result.dataframes

    def test_compute_differentials(self):
        code = """
squad_a = pd.DataFrame({"player_id": ["p1", "p2", "p3"]})
squad_b = pd.DataFrame({"player_id": ["p1", "p4", "p5"]})
diff = compute_differentials(squad_a, squad_b)
unique_a = diff[diff["owner"] == "a"]
print(f"unique to a: {len(unique_a)}")
"""
        result = execute(code)
        assert result.error is None
        assert "unique to a: 2" in result.stdout


class TestChartRendering:
    def test_render_line_produces_chart(self):
        code = """
df = pd.DataFrame({
    "gw": [1, 2, 3, 4, 5],
    "pts": [5, 8, 3, 10, 7],
})
path = render_line(df=df, x="gw", y="pts", title="Test Line")
print(f"chart: {path}")
"""
        result = execute(code)
        assert result.error is None
        assert len(result.charts) == 1
        assert result.charts[0].exists()
        assert result.charts[0].stat().st_size > 0

    def test_render_bar_produces_chart(self):
        code = """
df = pd.DataFrame({
    "name": ["A", "B", "C"],
    "score": [10, 20, 15],
})
path = render_bar(df=df, x="name", y="score")
"""
        result = execute(code)
        assert result.error is None
        assert len(result.charts) == 1


class TestSafety:
    def test_blocked_os_import(self):
        result = execute("import os")
        assert result.error is not None
        assert "not allowed" in result.error

    def test_blocked_subprocess(self):
        result = execute("import subprocess")
        assert result.error is not None

    def test_blocked_sys(self):
        result = execute("import sys")
        assert result.error is not None

    def test_blocked_open(self):
        result = execute('f = open("/etc/passwd")')
        assert result.error is not None
        assert "not allowed" in result.error

    def test_blocked_eval(self):
        result = execute('eval("1+1")')
        assert result.error is not None

    def test_blocked_exec(self):
        result = execute('exec("x = 1")')
        assert result.error is not None

    def test_blocked_dunder_import(self):
        result = execute('__import__("os")')
        assert result.error is not None

    def test_syntax_error(self):
        result = execute("def foo(")
        assert result.error is not None

    def test_runtime_error(self):
        result = execute("x = 1 / 0")
        assert result.error is not None
        assert "ZeroDivisionError" in result.error


class TestEdgeCases:
    def test_large_dataframe_capped(self):
        code = """
df = pd.DataFrame({"x": range(200000)})
print(f"rows: {len(df)}")
"""
        result = execute(code)
        assert result.error is None
        # The DataFrame in results should be capped
        if "df" in result.dataframes:
            assert len(result.dataframes["df"]) <= 100_000

    def test_underscore_vars_excluded(self):
        code = """
_private = pd.DataFrame({"a": [1]})
public = pd.DataFrame({"b": [2]})
"""
        result = execute(code)
        assert "_private" not in result.dataframes
        assert "public" in result.dataframes

    def test_context_not_recaptured(self):
        """Context DataFrames should not appear in result.dataframes."""
        ctx = pd.DataFrame({"x": [1]})
        code = "print(df_in['x'].sum())"
        result = execute(code, context={"df_in": ctx})
        assert result.error is None
        assert "df_in" not in result.dataframes
