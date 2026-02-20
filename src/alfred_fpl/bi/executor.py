"""Sandboxed Python executor for LLM-generated code.

Executes Python code strings in a restricted environment with only safe globals.
Captures stdout, return values, DataFrames, and chart files.

Safety:
- Restricted builtins: no os, sys, subprocess, open, __import__
- Whitelisted globals: pandas, numpy, BI library functions
- Timeout protection (default 30s)
- Row limit on DataFrames (100k)
- Chart file limit (5)

Usage:
    from alfred_fpl.bi.executor import execute

    result = execute(
        code='df = pd.DataFrame({"a": [1,2,3]}); print(df.sum())',
        context={"df_players": players_df},
    )
    print(result.stdout)
    print(result.error)
"""

from __future__ import annotations

import io
import signal
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Result of executing a code string."""

    stdout: str = ""
    result: Any = None
    dataframes: dict[str, pd.DataFrame] = field(default_factory=dict)
    charts: list[Path] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ROWS = 100_000
MAX_CHARTS = 5
DEFAULT_TIMEOUT = 30

# Imports that are BLOCKED
_BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "httpx",
    "importlib", "ctypes", "signal", "threading", "multiprocessing",
    "pickle", "shelve", "marshal",
    "code", "codeop", "compileall",
})


# ---------------------------------------------------------------------------
# Safe builtins
# ---------------------------------------------------------------------------

def _make_safe_builtins() -> dict:
    """Create a restricted builtins dict."""
    import builtins

    allowed = {
        # Types
        "True", "False", "None",
        "int", "float", "str", "bool", "bytes",
        "list", "dict", "set", "tuple", "frozenset",
        "type", "object",
        # Functions
        "len", "range", "enumerate", "zip", "map", "filter",
        "sorted", "reversed", "min", "max", "sum", "abs", "round",
        "any", "all", "isinstance", "issubclass",
        "print", "repr", "str", "format",
        "hasattr", "getattr", "setattr",
        "iter", "next",
        "ValueError", "TypeError", "KeyError", "IndexError",
        "RuntimeError", "StopIteration", "AttributeError",
        "Exception", "ZeroDivisionError",
    }

    safe = {}
    for name in allowed:
        if hasattr(builtins, name):
            safe[name] = getattr(builtins, name)

    # Block dangerous builtins
    safe["__import__"] = _blocked_import
    safe["exec"] = _blocked("exec")
    safe["eval"] = _blocked("eval")
    safe["compile"] = _blocked("compile")
    safe["open"] = _blocked("open")
    safe["input"] = _blocked("input")
    safe["breakpoint"] = _blocked("breakpoint")
    safe["exit"] = _blocked("exit")
    safe["quit"] = _blocked("quit")

    return safe


def _blocked_import(name, *args, **kwargs):
    """Blocked __import__ — only allows pre-approved modules."""
    base = name.split(".")[0]
    if base in _BLOCKED_MODULES:
        raise ImportError(
            f"Import of '{name}' is not allowed in the sandbox. "
            f"Available modules: pandas (pd), numpy (np), and FPL BI functions."
        )
    raise ImportError(
        f"Import of '{name}' is not allowed. "
        f"Use the pre-loaded variables: pd, np, and FPL BI functions."
    )


def _blocked(name):
    """Return a function that raises when called."""
    def _fn(*args, **kwargs):
        raise RuntimeError(f"'{name}' is not allowed in the sandbox.")
    return _fn


# ---------------------------------------------------------------------------
# Safe globals
# ---------------------------------------------------------------------------

def _make_safe_globals(
    context: dict[str, pd.DataFrame] | None = None,
    chart_dir: Path | None = None,
) -> dict:
    """Build the globals dict for the sandbox."""
    from alfred_fpl.bi import analytics, viz

    safe = {
        "__builtins__": _make_safe_builtins(),
        # Core libraries
        "pd": pd,
        "np": np,
        # Analytics functions
        "add_rolling_mean": analytics.add_rolling_mean,
        "compute_form_trend": analytics.compute_form_trend,
        "compute_fixture_difficulty": analytics.compute_fixture_difficulty,
        "compute_differentials": analytics.compute_differentials,
        "compute_price_velocity": analytics.compute_price_velocity,
        "rank_by": analytics.rank_by,
        # Viz functions (with chart_dir baked in)
        "render_line": lambda *a, **kw: viz.render_line(*a, **{**kw, "output_dir": chart_dir}),
        "render_bar": lambda *a, **kw: viz.render_bar(*a, **{**kw, "output_dir": chart_dir}),
        "render_heatmap": lambda *a, **kw: viz.render_heatmap(*a, **{**kw, "output_dir": chart_dir}),
        "render_comparison": lambda *a, **kw: viz.render_comparison(*a, **{**kw, "output_dir": chart_dir}),
    }

    # Inject context (DataFrames + simple values like dicts, lists, scalars)
    if context:
        for name, val in context.items():
            if isinstance(val, pd.DataFrame):
                if len(val) > MAX_ROWS:
                    val = val.head(MAX_ROWS)
                safe[name] = val
            elif isinstance(val, (dict, list, tuple, str, int, float, bool, set)):
                safe[name] = val
            elif hasattr(val, 'item'):
                # numpy scalars (int64, float64, etc.) — convert to Python native
                safe[name] = val.item()

    return safe


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

def execute(
    code: str,
    context: dict[str, pd.DataFrame] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> ExecutionResult:
    """Execute a Python code string in a sandboxed environment.

    Args:
        code: Python code to execute.
        context: Pre-loaded DataFrames available by name (e.g., {"df_players": df}).
        timeout_seconds: Maximum execution time.

    Returns:
        ExecutionResult with captured output, DataFrames, charts, and errors.
    """
    start = time.monotonic()
    result = ExecutionResult()

    # Validate input
    if not code or not code.strip():
        result.error = "Empty code string."
        return result

    # Create temp dir for charts
    chart_dir = Path(tempfile.mkdtemp(prefix="fpl_exec_"))

    # Build sandbox — single namespace so comprehensions/generators can see
    # all variables (avoids Python exec scoping gotcha with separate dicts)
    safe_globals = _make_safe_globals(context=context, chart_dir=chart_dir)
    input_names = set(safe_globals.keys())  # Track pre-existing names

    # Capture stdout
    old_stdout = sys.stdout
    captured = io.StringIO()

    try:
        sys.stdout = captured

        # Set timeout (Unix only — on Windows, skip timeout)
        if hasattr(signal, "SIGALRM"):
            def _timeout_handler(signum, frame):
                raise TimeoutError(f"Execution timed out after {timeout_seconds}s")
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_seconds)

        try:
            # Compile and execute
            compiled = compile(code, "<llm_code>", "exec")
            exec(compiled, safe_globals)
        except TimeoutError as e:
            result.error = str(e)
        except MemoryError:
            result.error = "Out of memory. Try reducing data size or computation scope."
        except Exception as e:
            tb = traceback.format_exc()
            # Strip sandbox internals from traceback
            lines = tb.split("\n")
            clean_lines = [l for l in lines if "<llm_code>" in l or not l.strip().startswith("File")]
            # Keep the exception type + message at the end
            if lines:
                clean_lines.append(lines[-1])
            result.error = "\n".join(clean_lines).strip() or f"{type(e).__name__}: {e}"
        finally:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)  # Cancel timeout

    finally:
        sys.stdout = old_stdout

    result.stdout = captured.getvalue()
    result.duration_ms = int((time.monotonic() - start) * 1000)

    # Collect new DataFrames created by the code (not pre-existing)
    for name, val in safe_globals.items():
        if (
            isinstance(val, pd.DataFrame)
            and not name.startswith("_")
            and name not in input_names  # Only new variables
        ):
            if len(val) > MAX_ROWS:
                val = val.head(MAX_ROWS)
            result.dataframes[name] = val

    # Collect chart files
    chart_files = sorted(chart_dir.glob("*.png"))[:MAX_CHARTS]
    result.charts = chart_files

    # Try to capture the last expression value
    # (If the code ends with an expression, capture it)
    if not result.error:
        try:
            lines = code.strip().split("\n")
            last_line = lines[-1].strip()
            # Check if last line is a simple expression (not an assignment)
            if last_line and "=" not in last_line and not last_line.startswith(("import", "from", "for", "if", "while", "def", "class", "with", "try", "print")):
                result.result = eval(last_line, safe_globals)
        except Exception:
            pass  # Not critical — last expression capture is best-effort

    return result
