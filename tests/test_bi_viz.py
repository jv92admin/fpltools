"""Tests for BI visualization — headless chart rendering."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from alfred_fpl.bi.viz import render_bar, render_comparison, render_heatmap, render_line


@pytest.fixture
def output_dir():
    with tempfile.TemporaryDirectory(prefix="fpl_test_charts_") as d:
        yield Path(d)


@pytest.fixture
def line_df():
    return pd.DataFrame({
        "gameweek": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],
        "total_points": [8, 5, 12, 3, 9, 6, 7, 4, 10, 5],
        "web_name": ["Salah"] * 5 + ["Saka"] * 5,
    })


@pytest.fixture
def bar_df():
    return pd.DataFrame({
        "web_name": ["Salah", "Saka", "Haaland", "Palmer", "Watkins"],
        "total_points": [180, 150, 170, 140, 130],
    })


@pytest.fixture
def heatmap_df():
    return pd.DataFrame(
        {
            "GW26": [2, 4, 3, 5, 1],
            "GW27": [3, 2, 4, 3, 2],
            "GW28": [4, 1, 2, 2, 3],
        },
        index=["ARS", "CHE", "LIV", "MCI", "TOT"],
    )


class TestRenderLine:
    def test_creates_png(self, line_df, output_dir):
        path = render_line(line_df, x="gameweek", y="total_points", output_dir=output_dir)
        assert path.exists()
        assert path.suffix == ".png"
        assert path.stat().st_size > 0

    def test_with_hue(self, line_df, output_dir):
        path = render_line(
            line_df, x="gameweek", y="total_points", hue="web_name",
            title="Points Comparison", output_dir=output_dir,
        )
        assert path.exists()
        assert path.stat().st_size > 1000  # Should be a real chart

    def test_with_labels(self, line_df, output_dir):
        path = render_line(
            line_df, x="gameweek", y="total_points",
            xlabel="Gameweek", ylabel="Points",
            output_dir=output_dir,
        )
        assert path.exists()


class TestRenderBar:
    def test_creates_png(self, bar_df, output_dir):
        path = render_bar(bar_df, x="web_name", y="total_points", output_dir=output_dir)
        assert path.exists()
        assert path.suffix == ".png"

    def test_horizontal(self, bar_df, output_dir):
        path = render_bar(
            bar_df, x="web_name", y="total_points",
            horizontal=True, title="Top Scorers",
            output_dir=output_dir,
        )
        assert path.exists()
        assert path.stat().st_size > 1000


class TestRenderHeatmap:
    def test_creates_png(self, heatmap_df, output_dir):
        path = render_heatmap(heatmap_df, title="Fixture Difficulty", output_dir=output_dir)
        assert path.exists()
        assert path.suffix == ".png"
        assert path.stat().st_size > 1000

    def test_without_annotations(self, heatmap_df, output_dir):
        path = render_heatmap(heatmap_df, annot=False, output_dir=output_dir)
        assert path.exists()


class TestRenderComparison:
    def test_creates_png(self, output_dir):
        dfs = {
            "Salah": pd.DataFrame({"form": [8.1], "price": [13.5], "total_points": [180]}),
            "Saka": pd.DataFrame({"form": [6.5], "price": [10.2], "total_points": [150]}),
        }
        path = render_comparison(
            dfs, metrics=["form", "price", "total_points"],
            title="Salah vs Saka", output_dir=output_dir,
        )
        assert path.exists()
        assert path.suffix == ".png"
        assert path.stat().st_size > 1000
