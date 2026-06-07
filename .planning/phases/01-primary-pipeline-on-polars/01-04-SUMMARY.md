---
phase: 01-primary-pipeline-on-polars
plan: 04
subsystem: causal-analysis
tags: [polars, scikit-learn, migration, numpy-boundary, feature-engineering, data-contract]

# Dependency graph
requires:
  - "01-02: polars main.py + pinned 21-col CONTRACT_SCHEMA (data/sweep_analysis_results.parquet)"
  - "01-01: smoke/phase1_smoke.py (--check causal | nopandas) as the Phase-1 gate"
provides:
  - "causal_analysis.py ported to polars: load_resolved_results, build_features (returns polars frame), run() with a single explicit polars->numpy boundary at .fit()/cross_val_score"
  - "MIGRATE-03 model boundary: features.to_numpy()/y.to_numpy() converted exactly once, retained feature_names for importance/coefficient/tree labels"
  - "All three Phase-1 scripts are now pandas-free (--check nopandas flips green)"
affects:
  - phase-3-test-suite-on-polars
  - phase-4-pandas-removal

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single explicit polars->numpy conversion at the scikit-learn boundary (MIGRATE-03)"
    - "Capture feature_names = features.columns BEFORE to_numpy() for positional importance/coef/tree labels"
    - "Compute CV fold count on the polars y Series (value_counts) BEFORE the numpy boundary; pass folds into print_cv_score"
    - "Session-context nulls cleared via fill_null(0) (NOT fillna) before the model boundary"
    - "qcut(allow_duplicates=True) Categorical display bins; group_by/agg + pl.when/then for event/gap/midnight stats"

key-files:
  created: []
  modified:
    - causal_analysis.py

key-decisions:
  - "cv_folds stays polars-only and is called once in run() on the polars y Series before to_numpy(); print_cv_score was refactored to receive the precomputed folds int, so a numpy array is never passed to cv_folds (avoids AttributeError: numpy.ndarray has no value_counts)"
  - "Correlations computed via float(np.corrcoef(feature.to_numpy(), y_np)[0,1]) per numeric feature — uses the same single numpy boundary, matches the original pandas .corr() semantics"
  - "Readable decision tree uses df.to_dummies(columns=['event_type']) — dummy names are now 'event_type_X' (was pandas 'event_X'); print-only per RESEARCH Assumptions A2, no CSV/schema impact"
  - "Committed the two regenerated tracked outputs (charts/causal/event_stats.csv, event_edge.png) with the port; the other 3 PNGs reproduced byte-identically under random_state=42"

patterns-established:
  - "Consumer port = read pinned contract via pl.read_parquet, engineer features in polars, cross to numpy ONCE at sklearn, retain column names for labels"

requirements-completed: [MIGRATE-03]

# Metrics
duration: 5min
completed: 2026-06-07
---

# Phase 01 Plan 04: Causal Analysis (causal_analysis.py) on Polars Summary

**Ported `causal_analysis.py` (the second contract consumer) from pandas to polars by keeping all data handling in polars and crossing to numpy exactly once at the scikit-learn boundary (`features.to_numpy()` / `y.to_numpy()` at `.fit()`/`cross_val_score`/`StandardScaler`/`LabelEncoder`), with retained `feature_names` driving importance/coefficient/decision-tree labels; the script trains RF / DecisionTree / LogisticRegression and regenerates `event_stats.csv` plus all causal charts with zero pandas imports.**

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-06-07
- **Tasks:** 2
- **Files modified:** 1 source file (causal_analysis.py); 2 tracked outputs regenerated

## Accomplishments

- **Task 1 — data + feature layer:** Swapped `import pandas as pd` → `import polars as pl` (numpy/sklearn/matplotlib `Agg`/`warnings.filterwarnings` unchanged — QUAL-01 deferred). `load_resolved_results` reads the pinned contract via `pl.read_parquet`, filters to resolved rows (`first_target_hit` not null), and adds an `Int64` `target`. `build_features` now RETURNS `(pl.DataFrame, pl.Series)` — the 12 features in their exact original order, so `features.columns` is a stable label list: the two `LabelEncoder` columns cross to numpy via `.to_numpy()` and are wrapped back into the polars frame; `gap_direction_encoded` via `replace_strict({"up":1,"down":0,"flat":-1}, default=-1)`; session-context nulls cleared with `fill_null(0)` (NOT `fillna`). `qcut_with_fallback_labels` collapses to `series.qcut(q, labels=..., allow_duplicates=True)`. `cv_folds` derives the per-class minimum from `y.value_counts()` (a polars 2-col DataFrame), staying polars-only.
- **Task 2 — model boundary + outputs:** `run()` computes `folds = cv_folds(y)` on the polars `y` Series FIRST, then establishes the single numpy boundary (`feature_names = features.columns`; `X = features.to_numpy()`; `y_np = y.to_numpy()`). `print_cv_score` was restructured to `print_cv_score(name, model, X, y_np, folds)` with its internal `cv_folds` call removed — so a numpy array is never passed to `cv_folds`. RF / DecisionTree / LogisticRegression fit on `X`/`y_np`; `importance` and `coefs` are polars frames built from `feature_names` aligned positionally to `rf.feature_importances_` / `lr.coef_[0]`. Correlations via `np.corrcoef`; `event_stats` / `gap_stats` / `midnight_stats` via `group_by/agg` + `pl.when/then`; `event_stats.write_csv(...)`; readable tree via `to_dummies`; print loops via `iter_rows(named=True)`. All pandas removed.
- **Result:** `python3 causal_analysis.py` runs to completion (no `AttributeError` at the numpy boundary; folds=5, RF CV 50.5% / Tree CV 50.5%), writes `charts/causal/event_stats.csv` + 4 PNGs. `--check causal`, `--check nopandas`, and `--check all` all exit 0 — all three Phase-1 scripts are now pandas-free.

## Task Commits

Each task was committed atomically:

1. **Task 1: Port the causal data + feature layer (load_resolved_results, build_features→polars, qcut, cv_folds)** - `426da91` (refactor)
2. **Task 2: Port run() model training (single polars→numpy boundary) + charts + event_stats.csv** - `e1f2356` (refactor)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `causal_analysis.py` - Full pandas→polars port of the causal consumer: polars contract read + feature engineering, a single explicit `features.to_numpy()`/`y.to_numpy()` boundary at the sklearn `.fit()`/`cross_val_score`, retained feature-name labels, `group_by/agg` stats, `to_dummies` readable tree, `iter_rows` prints. Zero pandas.
- `charts/causal/event_stats.csv` - Regenerated per-event edge ranking (tracked output).
- `charts/causal/event_edge.png` - Regenerated edge chart (tracked output). `feature_importance.png` / `decision_tree.png` / `logistic_coefficients.png` reproduced byte-identically under `random_state=42` (no diff to commit).

## Decisions Made

- **cv_folds ordering (the plan's Task 2 fix):** `cv_folds` uses `y.value_counts()`, which only exists on a polars Series. It is therefore called once in `run()` on the polars `y` BEFORE `y.to_numpy()`, and `print_cv_score` was changed to accept the precomputed `folds` int (its internal `cv_folds` call deleted). This is what prevents `AttributeError: 'numpy.ndarray' object has no attribute 'value_counts'`. The single `folds` value is reused for both `print_cv_score` call sites.
- **Single numpy boundary (MIGRATE-03):** Exactly one `features.to_numpy()` + `y.to_numpy()`, with `feature_names = features.columns` captured first so RF importance, LogReg coefficients, `plot_tree`, and `export_text` all index the feature list positionally. No polars frame is ever passed into `.fit()`/`cross_val_score`.
- **to_dummies naming (Assumptions A2):** the readable decision-tree dummy columns become `event_type_X` (vs pandas `event_X`). This is print-only (the readable tree feature names) and touches no CSV/schema, so it is accepted, not a defect.

## Deviations from Plan

None — the plan executed exactly as written. The two Task-2-explicit fixes (cv_folds-before-boundary ordering, `print_cv_score(folds)` signature) were prescribed by the plan and implemented as specified.

## Authentication Gates

None — pure local script port; no auth, no network, no package installs.

## Acceptance Criteria Verification

- `python3 causal_analysis.py` → exit 0; trains all models (folds=5, no `cv_folds`-on-numpy AttributeError); writes `charts/causal/event_stats.csv` + 4 PNGs.
- `python3 smoke/phase1_smoke.py --check causal` → `SMOKE OK: causal` (exit 0).
- `python3 smoke/phase1_smoke.py --check nopandas` → `SMOKE OK: nopandas` (exit 0) — all three ported scripts pandas-free.
- `python3 smoke/phase1_smoke.py --check all` → `SMOKE OK: all` (exit 0).
- `grep -nE "folds *= *cv_folds\(y\)"` → matches only the line inside `run()` (line 180), NOT inside `print_cv_score`; `grep -nE "def print_cv_score\(.*folds"` confirms the new signature.
- `grep -nE "features\.to_numpy\(\)|X = features.to_numpy"` → single conversion (line 185).
- `! grep -nE "^[[:space:]]*(import pandas|from pandas)" causal_analysis.py` → no output; `! grep -nE "pd\.get_dummies|\.iterrows\(|pd\."` → no output.
- `grep -n "replace_strict"` / `grep -n "fill_null"` confirm the gap-direction map and null filling (not `fillna`); `build_features` returns a 12-column polars frame + target with no null/NaN leaks (verified).

## Known Stubs

None — `causal_analysis.py` is fully wired end-to-end (pinned contract read → feature engineering → single numpy boundary → trained models → regenerated CSV + charts). No placeholders or empty data sources introduced.

## Next Phase Readiness

- MIGRATE-03 complete: all of Phase 1 (`main.py`, `exploration.py`, `causal_analysis.py`) now runs on polars; the 21-col data contract is intact and consumed polars-side by both consumers.
- `--check nopandas` is fully green — no `import pandas` remains in the three Phase-1 scripts. (`forward_returns.py` / `injection.py` still import pandas — Phase 2; pandas stays installed until Phase 4 / ENV-01.)
- The pandas `tests/` suite remains untouched and is expected RED until Phase 3 (TEST-01) — not a Phase-1 gate.
- Phase 1 is now 4/4 plans complete and ready for the phase verifier / transition to Phase 2.

## Self-Check: PASSED

- FOUND: `causal_analysis.py` (ported, pandas-free)
- FOUND: `charts/causal/event_stats.csv` (regenerated by the polars run)
- FOUND: commit `426da91` (Task 1)
- FOUND: commit `e1f2356` (Task 2)

---
*Phase: 01-primary-pipeline-on-polars*
*Completed: 2026-06-07*
