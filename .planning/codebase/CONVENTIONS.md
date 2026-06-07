# Coding Conventions

**Analysis Date:** 2026-06-07

## Naming Patterns

**Files:**
- `snake_case.py` for all source modules: `causal_analysis.py`, `forward_returns.py`, `exploration.py`, `injection.py`, `main.py`
- Test files prefixed `test_`: `tests/test_forward_returns.py`, `tests/test_analysis_scripts.py`, `tests/test_main_data_loading.py`

**Functions:**
- `snake_case` throughout: `ensure_utc`, `build_forward_returns`, `plot_raw_by_direction`, `candle_direction`, `get_session_context`
- Plotting functions prefixed `plot_`: `plot_raw_by_direction`, `plot_direction_normalized`, `plot_mae_mfe_by_direction`
- Data-building functions prefixed `build_`: `build_forward_returns`, `build_summary_table`, `build_features`
- Entry point functions named `run()` in parameterized scripts (`forward_returns.py`, `exploration.py`, `causal_analysis.py`) and `main()` in `main.py`

**Variables:**
- `snake_case` for local variables: `release_candle`, `data_high`, `first_sweep_pos`, `event_time`
- Loop variables follow data naming: `_, event` when iterating DataFrames with `.iterrows()`

**Constants:**
- `UPPER_SNAKE_CASE` for module-level constants: `DATA_DIR`, `OUTPUT_FILE`, `TRADING_DAY_END`, `DEFAULT_HORIZONS`, `DEFAULT_EVENTS`, `DEFAULT_NQ`, `DEFAULT_OUTPUT_DIR`

**DataFrame Columns:**
- NQ price data uses `PascalCase` with underscores: `DateTime_UTC`, `DateTime_ET`, `Open`, `High`, `Low`, `Close`, `Volume`
- Analysis output columns use `snake_case`: `event_type`, `first_target_hit`, `raw_forward_return_pct`, `direction_normalized_mfe_pct`
- Events parquet uses lowercase: `datetime_utc`, `title`, `currency`, `impact`

## Code Style

**Formatting:**
- No formatter config file present (no `pyproject.toml`, `.flake8`, or `setup.cfg`)
- 4-space indentation throughout
- String quotes: double quotes in newer scripts (`forward_returns.py`, `exploration.py`, `causal_analysis.py`); single quotes in older scripts (`main.py`, `injection.py`)
- Trailing comma on last dict/list item in multi-line constructs (e.g., `rows.append({...})` in `forward_returns.py`)

**Linting:**
- No linting config detected; no enforced rule set

## Import Organization

**Order:**
1. `from __future__ import annotations` (when present — newer files only)
2. Standard library: `argparse`, `pathlib`, `datetime`, `warnings`, `zoneinfo`
3. Third-party: `matplotlib`, `numpy`, `pandas`, `sklearn`

**Matplotlib backend:**
- Always set `matplotlib.use("Agg")` before `import matplotlib.pyplot as plt` in scripts that generate charts (`forward_returns.py`, `exploration.py`, `causal_analysis.py`)
- `injection.py` does not do this (older script)

**`from __future__ import annotations`:**
- Used in `forward_returns.py`, `exploration.py`, `causal_analysis.py` — enables `X | Y` union type syntax and postponed evaluation
- Absent from `main.py` and `injection.py` — those use the same union syntax without the import (requires Python 3.10+)

**Path Aliases:**
- None. `pathlib.Path` used throughout; no string path concatenation

## Error Handling

**Patterns:**
- "Not found" returns `None` — callers guard with `if result is None: return None` or `if result is None: continue`. See `get_release_candle` in `main.py`, `find_sorted_pos` in `main.py` and `forward_returns.py`
- Empty DataFrame returns `pd.DataFrame()` when no data matches. See `get_candles_until_eod` in `main.py`
- Guard-and-return early at top of functions that depend on lookup results: `if release_candle is None: return None` in `analyze_event` (`main.py` line 198)
- Raise `ValueError` for invalid data state in the `run()` entry point: `raise ValueError("No forward return rows produced; check event/NQ timestamp alignment")` in `forward_returns.py` line 319
- Narrow `except ValueError` with string check, then unconditional `raise` for unexpected errors. Pattern used in both `qcut_with_fallback_labels` implementations (`exploration.py` lines 49–52, `causal_analysis.py` lines 35–38):
  ```python
  except ValueError as exc:
      if "Bin labels must be one fewer" not in str(exc):
          raise
      return pd.qcut(series, q, duplicates="drop")
  ```
- `warnings.filterwarnings("ignore")` in `causal_analysis.py` to suppress sklearn convergence warnings globally — this is module-level and affects the whole script

## Logging

**Framework:** `print()` — no logging library used

**Patterns:**
- Progress messages with `print(f"...")` in `main()` / `run()`: `"Loading data..."`, `f"Analyzing {len(events)} news events..."`, `f"Built {len(df)} event/horizon forward-return rows"`
- Results printed to stdout in tabular form via `.to_string()` at the end of `run()` functions
- No structured logging, no log levels, no timestamps in log output

## Comments

**When to Comment:**
- Inline comments for non-obvious domain logic, especially timezone and index arithmetic in `main.py`: `# Get end of day timestamp (4:00 PM ET same day, or handle overnight)`, `# If event is after 4 PM, use next day's 4 PM`
- Section headers in `main()` output separated by `"=" * 60` banners
- No `# type: ignore` suppression annotations observed

**Docstrings:**
- Single-line docstrings on all public utility functions in `main.py`
- Multi-line docstring on `get_session_context` in `main.py` (lists bullet points of what is extracted)
- Module-level docstring on every script explaining purpose
- Selective coverage in newer scripts: `forward_returns.py` has a docstring only on `direction_normalized_profile`; `exploration.py` on `compute_win_rates`, `qcut_with_fallback_labels`, `build_summary_table`; `causal_analysis.py` on `qcut_with_fallback_labels` and `build_features`
- Plot functions and `run()` functions generally have no docstrings

## Function Design

**Size:** Generally short, single-purpose functions (5–30 lines). The exception is `analyze_event` in `main.py` (~120 lines) which performs the full per-event sweep analysis pipeline.

**Parameters:**
- Typed with `pd.DataFrame`, `pd.Series`, `pd.Timestamp`, `np.ndarray`, `Path`, `int`, `float`, `str`
- Default arguments used on `run()` entry-point functions to support both CLI invocation and direct import: `def run(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None`
- `horizons` passed as `tuple[int, ...]` for immutability; CLI conversion `tuple(args.horizons)` wraps the list

**Return Values:**
- `None` sentinel for "not found" cases (union return type `X | None`)
- Functions that modify DataFrames return the modified copy; they do not mutate in place (e.g., `normalize_nq_columns` in `forward_returns.py`)
- `dict` returned from `analyze_event` for flexible downstream `pd.DataFrame` construction

## Module Design

**Exports:** No `__all__` defined. All functions are importable by name.

**Barrel Files:** None. Tests import directly from source modules: `from forward_returns import build_forward_returns`, `import main`

**Script Pattern (newer modules):**
```python
def run(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    ...

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ...
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.output_dir)
```
This pattern (`forward_returns.py`, `exploration.py`, `causal_analysis.py`) separates the runnable logic (`run()`) from CLI parsing, making functions testable without subprocess invocation.

**Older pattern (`main.py`, `injection.py`):** Uses `def main():` with hardcoded paths; no `argparse`. Less testable but `main.py` functions are imported directly in tests via `monkeypatch`.

**DataFrame Mutation Guard:**
- Always call `.copy()` before mutating a passed-in DataFrame: `events = events.copy()` at the top of `build_forward_returns` (`forward_returns.py` line 97), `working = df.copy()` in exploration functions
- `.reset_index(drop=True)` after sort or filter operations to maintain clean integer index

---

*Convention analysis: 2026-06-07*
