<!-- GSD:project-start source:PROJECT.md -->
## Project

**News Analysis**

A Python research codebase that studies NQ (Nasdaq-100 futures) 1-minute price behavior around US economic news releases. The central research idea: after a news-release candle's high or low is swept, does price *reverse* to sweep the opposite side, or *continue* into a momentum box?

The current milestone — **Clean Foundation** — does not add research. It refactors, hardens, and restructures the existing scripts into a clean, tested, reproducible base that future research can safely build on. The research *idea* is preserved; the code around it is rebuilt for maintainability.

**Core Value:** The post-news-release sweep methodology is the asset. Everything in this project exists to keep that research correct, reproducible, and easy to extend. When tradeoffs arise, protect the integrity of the methodology and the raw data over code elegance or speed.

For this milestone specifically: a clean, hardened, well-tested foundation that leaves the research idea intact and runnable while making the codebase a place new research can grow.

### Constraints

- **Tech stack**: Stay on Python 3.12 + pandas/numpy/matplotlib/scikit-learn — no rewrite in another language.
- **Data**: Raw Parquet inputs are irreplaceable and gitignored — must not be deleted or modified by cleanup.
- **Methodology**: The sweep research idea must survive the refactor intact — code structure is disposable, the methodology is not.
- **Output parity**: No baseline diffing required — preserve the idea, not exact historical numbers; favor a clean result over byte-for-byte output parity.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - All analysis scripts and tests
## Runtime
- CPython 3.12.3
- pip (system-level; no lockfile, no `requirements.txt`, no `pyproject.toml`)
- Lockfile: missing — dependencies documented only in `README.md` prose
## Frameworks
- pandas 2.1.4 - Tabular data manipulation, parquet I/O, timezone-aware datetime handling
- numpy 1.26.4 - Array operations, sorted binary search (`np.searchsorted`), random number generation
- matplotlib 3.6.3 - All chart rendering; non-interactive `Agg` backend used in all analysis scripts
- scikit-learn 1.8.0 - `RandomForestClassifier`, `DecisionTreeClassifier`, `LogisticRegression`, `StandardScaler`, `LabelEncoder`, `cross_val_score` (used in `causal_analysis.py`)
- pytest 9.0.2 - Test runner; no config file (`pytest.ini` / `pyproject.toml` / `setup.cfg` absent); tests run with `python3 -m pytest tests -q`
- None detected — no build tooling, no virtual environment manager config (no `Pipfile`, `poetry.lock`, `.python-version`, or `venv`)
## Key Dependencies
- `pandas` 2.1.4 - Core data structure for all event and OHLCV data; parquet read/write via `read_parquet` / `to_parquet`; timezone conversion throughout
- `pyarrow` 23.0.1 - Parquet serialization backend for pandas; required for reading `data/economic_events.parquet`, `data/nq_1m.parquet`, and `data/sweep_analysis_results.parquet`
- `numpy` 1.26.4 - Fast sorted timestamp lookups (`np.searchsorted`) used as a performance optimization in `main.py` and `forward_returns.py`
- `scikit-learn` 1.8.0 - All ML models in `causal_analysis.py`; `n_jobs=-1` used in RandomForest (parallelism)
- `matplotlib` 3.6.3 - Every PNG chart output; `matplotlib.use("Agg")` called at module level in `causal_analysis.py`, `exploration.py`, and `forward_returns.py`
- `polars` 1.40.1 - Listed as a project dependency in `README.md`; not imported in any current script (available but unused)
- `zoneinfo` - Python 3.9+ stdlib; used in `main.py` for `America/New_York` timezone handling
## Configuration
- No environment variables used; no `.env` file
- All paths are relative `Path(__file__).parent / "data"` or hardcoded `Path("data/...")` defaults, making scripts CWD-sensitive when called with argparse defaults
- Data directory `data/` is gitignored
- No build configuration files detected
## Platform Requirements
- Python 3.12+ (uses `int | None` union syntax in function signatures, `from __future__ import annotations` in newer scripts)
- All listed packages installed system-wide or in active environment
- No OS-specific code; `zoneinfo` stdlib handles timezone data
- Not applicable — pure research/analysis scripts; no server, no deployment target
- Outputs are local files: `.parquet` in `data/`, `.png` and `.csv` in `charts/`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all source modules: `causal_analysis.py`, `forward_returns.py`, `exploration.py`, `injection.py`, `main.py`
- Test files prefixed `test_`: `tests/test_forward_returns.py`, `tests/test_analysis_scripts.py`, `tests/test_main_data_loading.py`
- `snake_case` throughout: `ensure_utc`, `build_forward_returns`, `plot_raw_by_direction`, `candle_direction`, `get_session_context`
- Plotting functions prefixed `plot_`: `plot_raw_by_direction`, `plot_direction_normalized`, `plot_mae_mfe_by_direction`
- Data-building functions prefixed `build_`: `build_forward_returns`, `build_summary_table`, `build_features`
- Entry point functions named `run()` in parameterized scripts (`forward_returns.py`, `exploration.py`, `causal_analysis.py`) and `main()` in `main.py`
- `snake_case` for local variables: `release_candle`, `data_high`, `first_sweep_pos`, `event_time`
- Loop variables follow data naming: `_, event` when iterating DataFrames with `.iterrows()`
- `UPPER_SNAKE_CASE` for module-level constants: `DATA_DIR`, `OUTPUT_FILE`, `TRADING_DAY_END`, `DEFAULT_HORIZONS`, `DEFAULT_EVENTS`, `DEFAULT_NQ`, `DEFAULT_OUTPUT_DIR`
- NQ price data uses `PascalCase` with underscores: `DateTime_UTC`, `DateTime_ET`, `Open`, `High`, `Low`, `Close`, `Volume`
- Analysis output columns use `snake_case`: `event_type`, `first_target_hit`, `raw_forward_return_pct`, `direction_normalized_mfe_pct`
- Events parquet uses lowercase: `datetime_utc`, `title`, `currency`, `impact`
## Code Style
- No formatter config file present (no `pyproject.toml`, `.flake8`, or `setup.cfg`)
- 4-space indentation throughout
- String quotes: double quotes in newer scripts (`forward_returns.py`, `exploration.py`, `causal_analysis.py`); single quotes in older scripts (`main.py`, `injection.py`)
- Trailing comma on last dict/list item in multi-line constructs (e.g., `rows.append({...})` in `forward_returns.py`)
- No linting config detected; no enforced rule set
## Import Organization
- Always set `matplotlib.use("Agg")` before `import matplotlib.pyplot as plt` in scripts that generate charts (`forward_returns.py`, `exploration.py`, `causal_analysis.py`)
- `injection.py` does not do this (older script)
- Used in `forward_returns.py`, `exploration.py`, `causal_analysis.py` — enables `X | Y` union type syntax and postponed evaluation
- Absent from `main.py` and `injection.py` — those use the same union syntax without the import (requires Python 3.10+)
- None. `pathlib.Path` used throughout; no string path concatenation
## Error Handling
- "Not found" returns `None` — callers guard with `if result is None: return None` or `if result is None: continue`. See `get_release_candle` in `main.py`, `find_sorted_pos` in `main.py` and `forward_returns.py`
- Empty DataFrame returns `pd.DataFrame()` when no data matches. See `get_candles_until_eod` in `main.py`
- Guard-and-return early at top of functions that depend on lookup results: `if release_candle is None: return None` in `analyze_event` (`main.py` line 198)
- Raise `ValueError` for invalid data state in the `run()` entry point: `raise ValueError("No forward return rows produced; check event/NQ timestamp alignment")` in `forward_returns.py` line 319
- Narrow `except ValueError` with string check, then unconditional `raise` for unexpected errors. Pattern used in both `qcut_with_fallback_labels` implementations (`exploration.py` lines 49–52, `causal_analysis.py` lines 35–38):
- `warnings.filterwarnings("ignore")` in `causal_analysis.py` to suppress sklearn convergence warnings globally — this is module-level and affects the whole script
## Logging
- Progress messages with `print(f"...")` in `main()` / `run()`: `"Loading data..."`, `f"Analyzing {len(events)} news events..."`, `f"Built {len(df)} event/horizon forward-return rows"`
- Results printed to stdout in tabular form via `.to_string()` at the end of `run()` functions
- No structured logging, no log levels, no timestamps in log output
## Comments
- Inline comments for non-obvious domain logic, especially timezone and index arithmetic in `main.py`: `# Get end of day timestamp (4:00 PM ET same day, or handle overnight)`, `# If event is after 4 PM, use next day's 4 PM`
- Section headers in `main()` output separated by `"=" * 60` banners
- No `# type: ignore` suppression annotations observed
- Single-line docstrings on all public utility functions in `main.py`
- Multi-line docstring on `get_session_context` in `main.py` (lists bullet points of what is extracted)
- Module-level docstring on every script explaining purpose
- Selective coverage in newer scripts: `forward_returns.py` has a docstring only on `direction_normalized_profile`; `exploration.py` on `compute_win_rates`, `qcut_with_fallback_labels`, `build_summary_table`; `causal_analysis.py` on `qcut_with_fallback_labels` and `build_features`
- Plot functions and `run()` functions generally have no docstrings
## Function Design
- Typed with `pd.DataFrame`, `pd.Series`, `pd.Timestamp`, `np.ndarray`, `Path`, `int`, `float`, `str`
- Default arguments used on `run()` entry-point functions to support both CLI invocation and direct import: `def run(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None`
- `horizons` passed as `tuple[int, ...]` for immutability; CLI conversion `tuple(args.horizons)` wraps the list
- `None` sentinel for "not found" cases (union return type `X | None`)
- Functions that modify DataFrames return the modified copy; they do not mutate in place (e.g., `normalize_nq_columns` in `forward_returns.py`)
- `dict` returned from `analyze_event` for flexible downstream `pd.DataFrame` construction
## Module Design
- Always call `.copy()` before mutating a passed-in DataFrame: `events = events.copy()` at the top of `build_forward_returns` (`forward_returns.py` line 97), `working = df.copy()` in exploration functions
- `.reset_index(drop=True)` after sort or filter operations to maintain clean integer index
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
```
## Component Responsibilities
| Component | Responsibility | File |
|-----------|----------------|------|
| Sweep Analyzer | Load raw data, identify sweep events, compute session context, save sweep results | `main.py` |
| Exploration | Read sweep results, compute win rates by event/time/range, produce visualizations | `exploration.py` |
| Causal Analysis | Engineer features, train ML models, rank predictive factors and event edges | `causal_analysis.py` |
| Forward Returns | Read raw data, compute multi-horizon return/MAE/MFE profiles by candle direction | `forward_returns.py` |
| Injection | Read raw data, generate per-event release-candle and 10-minute range histograms | `injection.py` |
## Pattern Overview
- No Python package structure; all scripts are importable modules at the root
- Two scripts read raw data directly (`main.py`, `forward_returns.py`); two scripts read the intermediate parquet artifact (`exploration.py`, `causal_analysis.py`); one script (`injection.py`) reads raw data for standalone range profiling
- Each script is independently runnable via `if __name__ == "__main__"` and exposes a callable `run()` or `main()` for testing and import
## Layers
- Purpose: Parquet files providing event calendar and OHLCV price history
- Location: `data/`
- Contains: `economic_events.parquet`, `nq_1m.parquet`, `sweep_analysis_results.parquet` (generated)
- Depends on: nothing
- Used by: `main.py`, `forward_returns.py`, `injection.py` (raw inputs); `exploration.py`, `causal_analysis.py` (sweep results)
- Purpose: Transform and analyze financial data; each script is a self-contained analysis unit
- Location: project root (`main.py`, `exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`)
- Contains: data loading, transformation, statistical analysis, and chart-writing logic
- Depends on: `data/` input files, pandas, numpy, matplotlib, scikit-learn
- Used by: `tests/`, CLI invocation
- Purpose: Charts (PNG) and tabular summaries (CSV/parquet) written per analysis run
- Location: `charts/causal/`, `charts/exploration/`, `charts/forward_returns/`, `data/`
- Contains: generated PNG charts and CSV/parquet result files
- Depends on: Analysis scripts
- Used by: external review (human inspection); intermediate parquet consumed by `exploration.py` and `causal_analysis.py`
## Data Flow
### Primary Pipeline (Sweep Analysis)
### Exploration and Causal Analysis
### Forward Returns (Independent Pipeline)
- No persistent application state. Each run is stateless: read files, compute, write outputs
- The NQ DataFrame carries lookup metadata in `nq.attrs['utc_values']` and `nq.attrs['et_values']` (integer arrays for binary-search lookups) — this is the only in-memory "state" passed between functions within a single run
## Key Abstractions
- Purpose: Normalize a datetime Series to timezone-aware UTC
- Examples: `main.py:24-29`, `forward_returns.py:25-29` (duplicated)
- Pattern: Check `.dt.tz`, localize if naive, convert if already aware
- Purpose: Binary-search exact match in a sorted int64 nanosecond timestamp array; returns positional index or `None`
- Examples: `main.py:42-47`, `forward_returns.py:49-53` (duplicated)
- Pattern: `np.searchsorted` then equality check
- Purpose: Cache sorted int64 timestamp arrays in `nq.attrs` so candle lookups avoid repeated DataFrame masks
- Examples: `main.py:50-54` (stored in attrs); `forward_returns.py:100` (local variable `utc_values`)
- Pattern: `.to_numpy(dtype='datetime64[ns]').astype('int64')`
- Purpose: Quantile-cut a series with graceful label truncation when duplicate bin edges reduce the number of bins
- Examples: `exploration.py:45-52`, `causal_analysis.py:31-38` (duplicated)
- Pattern: Try with labels, catch `ValueError` about bin-label count mismatch, retry without labels
- Purpose: Make each script both importable (for tests) and CLI-invocable
- Examples: `exploration.py:176-241`, `causal_analysis.py:139-271`, `forward_returns.py:309-344`
- Pattern: `run(input_path, output_dir, ...)` with default arguments; `parse_args()` maps CLI flags to those arguments; `if __name__ == "__main__": args = parse_args(); run(...)`
## Entry Points
- Location: `main.py:396-397`
- Triggers: `python3 main.py`
- Responsibilities: Run full sweep analysis; write `data/sweep_analysis_results.parquet`
- Location: `exploration.py:239-241`
- Triggers: `python3 exploration.py [--input PATH] [--output-dir PATH] [--event NAME]`
- Responsibilities: Generate exploratory charts and summary CSV to `charts/exploration/`
- Location: `causal_analysis.py:270-272`
- Triggers: `python3 causal_analysis.py [--input PATH] [--output-dir PATH]`
- Responsibilities: Train models, generate causal-factor charts and `event_stats.csv` to `charts/causal/`
- Location: `forward_returns.py:342-344`
- Triggers: `python3 forward_returns.py [--events PATH] [--nq PATH] [--output-dir PATH] [--horizons N ...]`
- Responsibilities: Compute multi-horizon forward returns; write charts and `forward_returns_by_event.csv`
- Location: `injection.py:174-175`
- Triggers: `python3 injection.py`
- Responsibilities: Generate per-event release-candle and 10-minute range histograms to `charts/`
## Architectural Constraints
- **No shared library:** Utility functions (`ensure_utc`, `find_sorted_pos`, `qcut_with_fallback_labels`) are duplicated verbatim across scripts rather than extracted to a shared module
- **Import path:** Tests import scripts from root (e.g., `from exploration import ...`); pytest must be run from the project root or with root on `sys.path`
- **Memory:** `data/nq_1m.parquet` (~57MB on disk, larger in memory) is loaded in full by any script that reads it; no chunked or lazy loading
- **Execution order:** `exploration.py` and `causal_analysis.py` depend on `data/sweep_analysis_results.parquet` produced by `main.py`; running them first will fail
- **Global state:** `main.py` uses module-level `DATA_DIR` and `OUTPUT_FILE` constants; tests monkeypatch `main.DATA_DIR` to redirect I/O to `tmp_path`
- **Circular imports:** None detected
## Anti-Patterns
### Utility function duplication
### `injection.py` uses linear scan instead of binary search
## Error Handling
- `get_release_candle()` returns `None` on miss; callers guard with `if release_candle is None: return None` (`main.py:197-199`)
- `forward_returns.py` uses `continue` to skip events where release or future candles are missing (`forward_returns.py:106-118`)
- `causal_analysis.py` uses `warnings.filterwarnings("ignore")` to suppress sklearn convergence warnings
- No custom exception types; no try/except blocks in analysis paths
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
