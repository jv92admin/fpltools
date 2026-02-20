"""FPL chart rendering — deterministic matplotlib output.

All rendering uses the Agg backend (headless, no display). Charts are
saved as PNG files to a temp directory and the path is returned.

Design principles:
- Deterministic: fixed DPI, figsize, font sizes, colormap
- Headless: Agg backend, no plt.show()
- Clean: always close figures to prevent memory leaks
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Headless backend — must be set before importing pyplot

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DPI = 150
FIGSIZE = (10, 6)
FONT_SIZE = 10
TITLE_SIZE = 13
COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]
GRID_ALPHA = 0.3


def _output_path(output_dir: Path | str | None, prefix: str) -> Path:
    """Resolve output file path."""
    if output_dir:
        d = Path(output_dir)
        d.mkdir(parents=True, exist_ok=True)
    else:
        d = Path(tempfile.mkdtemp(prefix="fpl_charts_"))
    return d / f"{prefix}.png"


def _apply_style(ax, title: str | None = None):
    """Apply consistent styling to an axis."""
    ax.grid(True, alpha=GRID_ALPHA)
    if title:
        ax.set_title(title, fontsize=TITLE_SIZE, fontweight="bold", pad=12)
    ax.tick_params(labelsize=FONT_SIZE)


# ---------------------------------------------------------------------------
# Chart types
# ---------------------------------------------------------------------------

def render_line(
    df: pd.DataFrame,
    x: str,
    y: str,
    hue: str | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Render a line chart. Good for time series (form, price, points over GWs).

    Args:
        df: DataFrame with the data.
        x: Column for x-axis (e.g., 'gameweek').
        y: Column for y-axis (e.g., 'total_points').
        hue: Column to group lines by (e.g., 'web_name' for multi-player comparison).
        title: Chart title.
        xlabel: X-axis label (default: column name).
        ylabel: Y-axis label (default: column name).
        output_dir: Directory for output PNG. Default: temp directory.

    Returns:
        Path to the rendered PNG file.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    if hue and hue in df.columns:
        for i, (name, group) in enumerate(df.groupby(hue)):
            group = group.sort_values(x)
            ax.plot(
                group[x], group[y],
                marker="o", markersize=4,
                color=COLORS[i % len(COLORS)],
                label=str(name), linewidth=2,
            )
        ax.legend(fontsize=FONT_SIZE, framealpha=0.9)
    else:
        df_sorted = df.sort_values(x)
        ax.plot(
            df_sorted[x], df_sorted[y],
            marker="o", markersize=4,
            color=COLORS[0], linewidth=2,
        )

    ax.set_xlabel(xlabel or x, fontsize=FONT_SIZE)
    ax.set_ylabel(ylabel or y, fontsize=FONT_SIZE)
    _apply_style(ax, title)

    path = _output_path(output_dir, "line")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def render_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    horizontal: bool = False,
    output_dir: Path | str | None = None,
) -> Path:
    """Render a bar chart. Good for rankings and comparisons.

    Args:
        df: DataFrame with the data.
        x: Column for categories (e.g., 'web_name').
        y: Column for values (e.g., 'total_points').
        title: Chart title.
        xlabel: X-axis label.
        ylabel: Y-axis label.
        horizontal: If True, render horizontal bars (good for long category names).
        output_dir: Directory for output PNG.

    Returns:
        Path to the rendered PNG file.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    colors = [COLORS[i % len(COLORS)] for i in range(len(df))]

    if horizontal:
        ax.barh(df[x].astype(str), df[y], color=colors)
        ax.set_xlabel(ylabel or y, fontsize=FONT_SIZE)
        ax.set_ylabel(xlabel or x, fontsize=FONT_SIZE)
        ax.invert_yaxis()  # Highest rank at top
    else:
        ax.bar(df[x].astype(str), df[y], color=colors)
        ax.set_xlabel(xlabel or x, fontsize=FONT_SIZE)
        ax.set_ylabel(ylabel or y, fontsize=FONT_SIZE)
        plt.xticks(rotation=45, ha="right")

    _apply_style(ax, title)

    path = _output_path(output_dir, "bar")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def render_heatmap(
    df: pd.DataFrame,
    title: str | None = None,
    cmap: str = "RdYlGn_r",
    vmin: float = 1,
    vmax: float = 5,
    annot: bool = True,
    output_dir: Path | str | None = None,
) -> Path:
    """Render a heatmap. Good for fixture difficulty grids (team x gameweek).

    The DataFrame should be pivoted: index = teams, columns = gameweeks,
    values = FDR ratings.

    Args:
        df: Pivoted DataFrame (index=row labels, columns=column labels, values=numeric).
        title: Chart title.
        cmap: Matplotlib colormap. Default RdYlGn_r (red=hard, green=easy).
        vmin: Minimum value for color scale.
        vmax: Maximum value for color scale.
        annot: Whether to annotate cells with values.
        output_dir: Directory for output PNG.

    Returns:
        Path to the rendered PNG file.
    """
    n_rows = len(df)
    height = max(4, n_rows * 0.4 + 2)
    fig, ax = plt.subplots(figsize=(max(8, len(df.columns) * 0.8 + 2), height), dpi=DPI)

    im = ax.imshow(
        df.values.astype(float),
        cmap=cmap, vmin=vmin, vmax=vmax,
        aspect="auto",
    )

    # Axis labels
    ax.set_xticks(range(len(df.columns)))
    ax.set_xticklabels(df.columns, fontsize=FONT_SIZE - 1, rotation=45, ha="right")
    ax.set_yticks(range(len(df.index)))
    ax.set_yticklabels(df.index, fontsize=FONT_SIZE - 1)

    # Annotate cells
    if annot:
        for i in range(len(df.index)):
            for j in range(len(df.columns)):
                val = df.iloc[i, j]
                color = "white" if val > 3.5 else "black"
                ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                        fontsize=FONT_SIZE - 1, color=color, fontweight="bold")

    fig.colorbar(im, ax=ax, shrink=0.8, label="FDR (1=easy, 5=hard)")
    _apply_style(ax, title)

    path = _output_path(output_dir, "heatmap")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def render_comparison(
    dfs: dict[str, pd.DataFrame],
    metrics: list[str],
    title: str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Render a grouped bar comparison chart.

    Shows multiple metrics side-by-side for named entities (e.g., players).

    Args:
        dfs: Dict mapping entity name → DataFrame with metric columns.
            Each DataFrame should have exactly one row (the summary).
        metrics: List of column names to compare.
        title: Chart title.
        output_dir: Directory for output PNG.

    Returns:
        Path to the rendered PNG file.
    """
    import numpy as np

    names = list(dfs.keys())
    n_metrics = len(metrics)
    n_entities = len(names)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    bar_width = 0.8 / n_entities
    x = np.arange(n_metrics)

    for i, name in enumerate(names):
        df = dfs[name]
        values = [df[m].iloc[0] if m in df.columns else 0 for m in metrics]
        offset = (i - n_entities / 2 + 0.5) * bar_width
        ax.bar(
            x + offset, values,
            width=bar_width, label=name,
            color=COLORS[i % len(COLORS)],
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=FONT_SIZE, rotation=30, ha="right")
    ax.legend(fontsize=FONT_SIZE)
    _apply_style(ax, title)

    path = _output_path(output_dir, "comparison")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path
