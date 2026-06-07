# Codebase Concerns

**Analysis Date:** 2026-06-07

## Tech Debt

**Duplicated utility functions across scripts:**
- Issue: `ensure_utc`, `timestamp_ns_utc`, and `find_sorted_pos` are copy-pasted verbatim between `main.py` (lines 24–47) and `forward_returns.py` (lines 25–53). Separately, `qcut_with_fallback_labels` is duplicated between `exploration.py` (line 45) and `causal_analysis.py` (line 31).
- Files: `main.py`, `forward_returns.py`, `exploration.py`, `causal_analysis.py`
- Impact: Bug fixes or behavior changes must be applied in multiple places. The two copies of `ensure_utc` and friends have already diverged slightly in docstring/formatting and will drift further over time.
- Fix approach: Extract shared utilities into a `utils.py` module and import from there. Tests import from `exploration` today, so the `qcut_with_fallback_labels` test will need its import updated.

**CWD-dependent default paths in three scripts:**
- Issue: `forward_returns.py` (lines 19–21), `exploration.py` (lines 19–20), and `causal_analysis.py` (lines 27–28) define default paths as `Path("data/...")` and `Path("charts/...")` relative to the current working directory. Running these scripts from any directory other than the project root silently resolves to wrong paths and raises a `FileNotFoundError`. By contrast, `main.py` and `injection.py` use `Path(__file__).parent / "data"`, which is CWD-independent.
- Files: `forward_returns.py`, `exploration.py`, `causal_analysis.py`
- Impact: Scripts fail silently when called from subdirectories, CI runners, or editor run buttons.
- Fix approach: Change `Path("data/...")` to `Path(__file__).parent / "data" / "..."` in all three scripts, matching the pattern in `main.py`.

**No dependency manifest:**
- Issue: There is no `requirements.txt`, `pyproject.toml`, `Pipfile`, or `environment.yml`. The project depends on pandas, numpy, matplotlib, and scikit-learn but has no machine-readable record of required packages or their versions.
- Files: project root (absent)
- Impact: Reproducing the environment requires manual inspection of imports. Collaborators or CI have no install target.
- Fix approach: Add a `requirements.txt` pinned to tested versions of `pandas`, `numpy`, `matplotlib`, `scikit-learn`, and `pytest`.

**Global warning suppression in causal analysis:**
- Issue: `causal_analysis.py` line 25 calls `warnings.filterwarnings("ignore")` with no category or module filter. This silences all warnings globally, including sklearn convergence warnings, pandas DeprecationWarnings, and data integrity alerts.
- Files: `causal_analysis.py`
- Impact: Silent model convergence failures, deprecated API usage, and data quality issues are hidden from the operator.
- Fix approach: Suppress only the specific known noise, e.g. `warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")`.

---

## Known Bugs

**Mixed `loc`/`iloc` usage with positional index in `get_candles_until_eod`:**
- Symptoms: Returns the wrong candle or raises `KeyError` if the NQ DataFrame has non-default integer labels.
- Files: `main.py` line 106
- Trigger: `start_idx` is the positional offset returned by `find_sorted_pos` (0-based integer). Line 106 uses `nq.loc[start_idx, 'DateTime_ET']` (label-based). This coincides with the positional index only because `load_data()` calls `reset_index(drop=True)`. If `get_candles_until_eod` is called with any filtered or non-reset DataFrame (e.g., from tests or future refactors), `loc` will silently access the wrong row or raise. Line 118 in the same function correctly uses `nq.iloc[start_idx + 1:end_pos]`.
- Workaround: Works in production because `load_data()` guarantees a reset index. Fragile under test or refactor.

**Prior session close hardcoded to 16:59 ET:**
- Symptoms: `gap_6pm_pct` and `gap_6pm_direction` are silently `None` for events on days where the 16:59 candle is absent (early closes, data gaps, holiday sessions).
- Files: `main.py` lines 181–185 (`get_session_context`)
- Trigger: The function assumes `get_candle_at_time(nq, prior_close_time)` will find a 16:59 ET candle. If that specific minute is missing, the condition `if prior_close_candle is not None` silently skips gap computation. `causal_analysis.py`'s `build_features` then imputes these as 0, distorting the logistic regression coefficients.
- Workaround: None. Affected events contribute incorrect zero-imputed gap features to model training.

---

## Performance Bottlenecks

**Python-level loop over events with per-event binary search (`main.py`, `forward_returns.py`):**
- Problem: `main.py` line 325 and `forward_returns.py` line 103 iterate over every event row via `iterrows()`. For each event, inner numpy operations scan forward candles.
- Files: `main.py`, `forward_returns.py`
- Cause: Per-row Python loop pattern rather than vectorized merge/join on the NQ frame.
- Impact: At current scale (hundreds of events, ~55MB NQ file) runtime is acceptable. As event history grows this becomes the dominant cost.
- Improvement path: Use `pd.merge_asof` to align events to the nearest candle timestamp, then use vectorized window operations rather than per-event loops.

**`injection.py` uses full boolean mask scan for every event:**
- Problem: `get_release_candle_data` (line 43) and `get_10min_range` (line 54–58) in `injection.py` perform `nq['DateTime_UTC'] == event_time` and time-range boolean masks against the entire 55MB NQ DataFrame on every event occurrence iteration.
- Files: `injection.py`
- Cause: No lookup acceleration (no binary search, no sorted-array index). Contrast with `main.py`'s `attrs`-based lookup tables.
- Improvement path: Apply the `add_lookup_tables`/`find_sorted_pos` pattern from `main.py`, or use `pd.merge_asof`.

---

## Fragile Areas

**`analyze_event` and `get_session_context` in `main.py`:**
- Files: `main.py` lines 136–315
- Why fragile: These two functions contain the project's core research logic — sweep detection, MAE calculation, synthetic box level computation, first-target classification, and all six session context features. They have zero direct unit tests.
- Safe modification: Any changes must be validated by running `main.py` end-to-end against real data and manually inspecting `sweep_analysis_results.parquet` output statistics.
- Test coverage: None. The only `main.py` tests cover `load_data`, `add_lookup_tables`, and `get_candles_until_eod`.

**`injection.py` is entirely untested:**
- Files: `injection.py`
- Why fragile: The script contains its own independent data loading (`load_data` at line 19), range calculation (`calculate_percentage_range`), and chart generation logic. It has no test coverage whatsoever and does not set the matplotlib `Agg` backend before importing `matplotlib.pyplot` (see Security section below), making it the most brittle script in the repository.
- Test coverage: Zero tests.

**No `conftest.py` and no pytest configuration:**
- Files: `tests/` directory
- Why fragile: All test imports rely on the tests being run from the project root with the root on `sys.path` (e.g., `from exploration import ...`). There is no `conftest.py`, no `pytest.ini`, and no `pyproject.toml` to configure `pythonpath`. Running `pytest` from any other directory or from an IDE with a different working directory will raise `ModuleNotFoundError`.
- Safe modification: Add a `conftest.py` at the project root (or configure `pythonpath = ["."]` in a `pyproject.toml`) to make imports path-independent.

---

## Security Considerations

**No input validation on parquet data sources:**
- Risk: All scripts load parquet files from `data/` without any schema validation. A malformed or tampered parquet file could cause silent data corruption (wrong column names, wrong dtypes) rather than a clear error.
- Files: `main.py` (`load_data`), `forward_returns.py` (`run`), `exploration.py` (`run`), `causal_analysis.py` (`load_resolved_results`), `injection.py` (`load_data`)
- Current mitigation: `main.py` has a column rename fallback (`datetime_utc` → `DateTime_UTC`) and timezone normalization. Other scripts have no schema checks.
- Recommendations: Add lightweight column presence assertions or a pandas schema validator (e.g., pandera) at data load time.

---

## Stale Artifacts

**Root-level output PNGs tracked in git:**
- Issue: `decision_tree.png`, `event_edge.png`, `event_edge_chart.png`, and `feature_importance.png` exist at the project root and are tracked in git (confirmed via `git ls-files`). These are stale outputs from before the organized `charts/causal/` output directory was introduced. The current code writes to `charts/causal/`, making these root-level files obsolete.
- Files: `decision_tree.png`, `event_edge.png`, `event_edge_chart.png`, `feature_importance.png` (all at project root)
- Impact: Repository clutter; risk of confusion when comparing old vs. new analysis outputs.
- Fix approach: Remove from git (`git rm decision_tree.png event_edge.png event_edge_chart.png feature_importance.png`) and add `*.png` to `.gitignore`, or at minimum add `*.png` to `.gitignore` so chart outputs are no longer tracked.

---

## Test Coverage Gaps

**`analyze_event` sweep detection logic:**
- What's not tested: The entire sweep detection, first-target classification, MAE calculation, and synthetic box level logic in `analyze_event`.
- Files: `main.py` lines 193–315
- Risk: Incorrect sweep direction selection (`high_pos <= low_pos` tie-breaking), off-by-one errors in `post_sweep` slicing, or wrong `mae_before_reversal` computation could silently corrupt `sweep_analysis_results.parquet` and all downstream analyses.
- Priority: High

**`get_session_context` feature extraction:**
- What's not tested: The 8:29 pre-news candle lookup, midnight open distance, 6pm open distance, and gap direction calculation.
- Files: `main.py` lines 136–190
- Risk: Incorrect feature values flow into `causal_analysis.py` model training without any validation signal.
- Priority: High

**`injection.py` end-to-end:**
- What's not tested: Range calculation, 10-minute window aggregation, histogram creation, and file output.
- Files: `injection.py`
- Risk: Silent regressions in the oldest analysis script; no guarantee outputs are correct.
- Priority: Medium

**`causal_analysis.run()` integration:**
- What's not tested: The full ML pipeline (Random Forest fit, Decision Tree fit, Logistic Regression fit, chart generation, CSV output).
- Files: `causal_analysis.py` lines 139–260
- Risk: Model pipeline failures (e.g., dimension mismatch after feature changes) are only discovered at runtime.
- Priority: Medium

---

*Concerns audit: 2026-06-07*
