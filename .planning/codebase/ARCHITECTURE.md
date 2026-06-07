<!-- refreshed: 2026-06-07 -->
# Architecture

**Analysis Date:** 2026-06-07

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                          Raw Inputs (data/)                          │
│   `data/economic_events.parquet`    `data/nq_1m.parquet`             │
└────────┬──────────────────────────────────┬─────────────────────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────────┐          ┌──────────────────────────────┐
│    `injection.py`   │          │          `main.py`            │
│ Per-event range     │          │ Sweep analysis: detects       │
│ histograms          │          │ high/low sweeps + reversal    │
│ → charts/ (root)    │          │ → data/sweep_analysis_        │
└─────────────────────┘          │   results.parquet             │
                                 └────────────┬─────────────────┘
                                              │
              ┌───────────────────────────────┴──────────────────────┐
              ▼                                                        ▼
┌─────────────────────────┐                         ┌─────────────────────────────┐
│     `exploration.py`    │                         │     `causal_analysis.py`    │
│ Win-rate breakdowns,    │                         │ ML models (RandomForest,    │
│ MAE distributions,      │                         │ DecisionTree, Logistic),    │
│ timing quartiles        │                         │ feature importance,         │
│ → charts/exploration/   │                         │ event edge rankings         │
└─────────────────────────┘                         │ → charts/causal/            │
                                                     └─────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       `forward_returns.py`                           │
│ Reads raw inputs directly; computes 15m/30m/45m/60m/90m forward      │
│ returns, MAE/MFE profiles, direction-normalized distributions        │
│ → charts/forward_returns/                                            │
└──────────────────────────────────────────────────────────────────────┘
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

**Overall:** Linear ETL pipeline — flat script collection with no shared library or package

**Key Characteristics:**
- No Python package structure; all scripts are importable modules at the root
- Two scripts read raw data directly (`main.py`, `forward_returns.py`); two scripts read the intermediate parquet artifact (`exploration.py`, `causal_analysis.py`); one script (`injection.py`) reads raw data for standalone range profiling
- Each script is independently runnable via `if __name__ == "__main__"` and exposes a callable `run()` or `main()` for testing and import

## Layers

**Data Input Layer:**
- Purpose: Parquet files providing event calendar and OHLCV price history
- Location: `data/`
- Contains: `economic_events.parquet`, `nq_1m.parquet`, `sweep_analysis_results.parquet` (generated)
- Depends on: nothing
- Used by: `main.py`, `forward_returns.py`, `injection.py` (raw inputs); `exploration.py`, `causal_analysis.py` (sweep results)

**Analysis Scripts:**
- Purpose: Transform and analyze financial data; each script is a self-contained analysis unit
- Location: project root (`main.py`, `exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`)
- Contains: data loading, transformation, statistical analysis, and chart-writing logic
- Depends on: `data/` input files, pandas, numpy, matplotlib, scikit-learn
- Used by: `tests/`, CLI invocation

**Output Layer:**
- Purpose: Charts (PNG) and tabular summaries (CSV/parquet) written per analysis run
- Location: `charts/causal/`, `charts/exploration/`, `charts/forward_returns/`, `data/`
- Contains: generated PNG charts and CSV/parquet result files
- Depends on: Analysis scripts
- Used by: external review (human inspection); intermediate parquet consumed by `exploration.py` and `causal_analysis.py`

## Data Flow

### Primary Pipeline (Sweep Analysis)

1. Load raw inputs — `main.load_data()` reads `data/economic_events.parquet` and `data/nq_1m.parquet`; attaches sorted integer timestamp arrays to `nq.attrs` via `add_lookup_tables()` (`main.py:50-54`)
2. Per-event sweep analysis — `main.analyze_event()` uses `find_sorted_pos()` binary search to locate the release candle, scans EOD candles via `get_candles_until_eod()`, and computes sweep direction, timing, MAE, and session context (`main.py:193-315`)
3. Save intermediate results — `df.to_parquet(OUTPUT_FILE)` writes `data/sweep_analysis_results.parquet` (`main.py:336`)

### Exploration and Causal Analysis

1. Load sweep results — `pd.read_parquet("data/sweep_analysis_results.parquet")`
2. Compute grouped statistics — `compute_win_rates()` in `exploration.py:23-42`; `build_features()` + sklearn model training in `causal_analysis.py:48-73`
3. Write charts and CSVs — `fig.savefig()` to `charts/exploration/` or `charts/causal/`

### Forward Returns (Independent Pipeline)

1. Load raw inputs — `pd.read_parquet()` for events and NQ in `forward_returns.run()` (`forward_returns.py:315`)
2. Build per-event per-horizon rows — `build_forward_returns()` computes raw and direction-normalized returns and MAE/MFE for each event × horizon combination (`forward_returns.py:92-156`)
3. Write outputs — `write_outputs()` saves CSV and per-horizon PNGs to `charts/forward_returns/` (`forward_returns.py:295-306`)

**State Management:**
- No persistent application state. Each run is stateless: read files, compute, write outputs
- The NQ DataFrame carries lookup metadata in `nq.attrs['utc_values']` and `nq.attrs['et_values']` (integer arrays for binary-search lookups) — this is the only in-memory "state" passed between functions within a single run

## Key Abstractions

**`ensure_utc(series)`:**
- Purpose: Normalize a datetime Series to timezone-aware UTC
- Examples: `main.py:24-29`, `forward_returns.py:25-29` (duplicated)
- Pattern: Check `.dt.tz`, localize if naive, convert if already aware

**`find_sorted_pos(values, value)`:**
- Purpose: Binary-search exact match in a sorted int64 nanosecond timestamp array; returns positional index or `None`
- Examples: `main.py:42-47`, `forward_returns.py:49-53` (duplicated)
- Pattern: `np.searchsorted` then equality check

**`add_lookup_tables(nq)` / inline `utc_values`:**
- Purpose: Cache sorted int64 timestamp arrays in `nq.attrs` so candle lookups avoid repeated DataFrame masks
- Examples: `main.py:50-54` (stored in attrs); `forward_returns.py:100` (local variable `utc_values`)
- Pattern: `.to_numpy(dtype='datetime64[ns]').astype('int64')`

**`qcut_with_fallback_labels(series, q, labels)`:**
- Purpose: Quantile-cut a series with graceful label truncation when duplicate bin edges reduce the number of bins
- Examples: `exploration.py:45-52`, `causal_analysis.py:31-38` (duplicated)
- Pattern: Try with labels, catch `ValueError` about bin-label count mismatch, retry without labels

**`run()` / `parse_args()` pattern:**
- Purpose: Make each script both importable (for tests) and CLI-invocable
- Examples: `exploration.py:176-241`, `causal_analysis.py:139-271`, `forward_returns.py:309-344`
- Pattern: `run(input_path, output_dir, ...)` with default arguments; `parse_args()` maps CLI flags to those arguments; `if __name__ == "__main__": args = parse_args(); run(...)`

## Entry Points

**`main.py` (CLI):**
- Location: `main.py:396-397`
- Triggers: `python3 main.py`
- Responsibilities: Run full sweep analysis; write `data/sweep_analysis_results.parquet`

**`exploration.py` (CLI):**
- Location: `exploration.py:239-241`
- Triggers: `python3 exploration.py [--input PATH] [--output-dir PATH] [--event NAME]`
- Responsibilities: Generate exploratory charts and summary CSV to `charts/exploration/`

**`causal_analysis.py` (CLI):**
- Location: `causal_analysis.py:270-272`
- Triggers: `python3 causal_analysis.py [--input PATH] [--output-dir PATH]`
- Responsibilities: Train models, generate causal-factor charts and `event_stats.csv` to `charts/causal/`

**`forward_returns.py` (CLI):**
- Location: `forward_returns.py:342-344`
- Triggers: `python3 forward_returns.py [--events PATH] [--nq PATH] [--output-dir PATH] [--horizons N ...]`
- Responsibilities: Compute multi-horizon forward returns; write charts and `forward_returns_by_event.csv`

**`injection.py` (CLI):**
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

**What happens:** `ensure_utc`, `find_sorted_pos`, and `qcut_with_fallback_labels` are copy-pasted across two or more scripts
**Why it's wrong:** Bug fixes or behavior changes must be applied in multiple places; divergence already exists (e.g., `forward_returns.py` builds `utc_values` as a local variable; `main.py` stores it in `nq.attrs`)
**Do this instead:** Extract to a shared `utils.py` at project root and import from there

### `injection.py` uses linear scan instead of binary search

**What happens:** `injection.py:43-44` uses a boolean mask (`nq['DateTime_UTC'] == event_time`) for every candle lookup
**Why it's wrong:** O(n) scan on every event against the full ~57MB NQ DataFrame; `main.py` solved this with `find_sorted_pos` on a sorted int64 array
**Do this instead:** Apply the same `add_lookup_tables` + `find_sorted_pos` pattern from `main.py`

## Error Handling

**Strategy:** Fail-silent per event — if a candle is not found or data is missing, individual event records are skipped (return `None` or `continue`) and processing continues

**Patterns:**
- `get_release_candle()` returns `None` on miss; callers guard with `if release_candle is None: return None` (`main.py:197-199`)
- `forward_returns.py` uses `continue` to skip events where release or future candles are missing (`forward_returns.py:106-118`)
- `causal_analysis.py` uses `warnings.filterwarnings("ignore")` to suppress sklearn convergence warnings
- No custom exception types; no try/except blocks in analysis paths

## Cross-Cutting Concerns

**Logging:** `print()` statements only; no logging framework
**Validation:** Input validation is implicit (parquet schema is trusted); `forward_returns.run()` raises `ValueError` if output DataFrame is empty (`forward_returns.py:319`)
**Authentication:** Not applicable — all data is local

---

*Architecture analysis: 2026-06-07*
