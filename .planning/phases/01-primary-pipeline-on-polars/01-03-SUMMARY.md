---
phase: 01-primary-pipeline-on-polars
plan: 03
subsystem: exploration
tags: [polars, parquet, migration, data-contract, group_by, qcut, value_counts, matplotlib-boundary]

# Dependency graph
requires:
  - "01-02: main.py polars port + pinned 21-col CONTRACT_SCHEMA (data/sweep_analysis_results.parquet)"
  - "01-01: smoke/phase1_smoke.py (--check exploration|nopandas) as the Phase-1 gate"
provides:
  - "exploration.py ported to polars: group_by/agg win-rate aggregation, qcut(allow_duplicates=True), matplotlib fed via .to_numpy()/.to_list() at the boundary, write_csv"
  - "Regenerated charts/exploration/*.png + summary_by_event.csv on the polars contract"
affects:
  - 01-04-causal-port
  - phase-2-independent-pipelines

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-script polars port = swap engine at read/aggregate/extract/write only; matplotlib stays, fed numpy/lists at the boundary"
    - "group_by/agg with pl.len() + (col==v).sum() + pl.when/then/otherwise replaces groupby + lambda + .where()"
    - "Series.qcut(q, labels=..., allow_duplicates=True) (Categorical) replaces pd.qcut + dead ValueError fallback"
    - "value_counts() consumed as a 2-col DataFrame (value, count); filter(count>=N).to_list()"
    - "join (not merge), filter/is_in/is_not_null (not boolean-mask/notna), write_csv (not to_csv index=False)"

key-files:
  created: []
  modified:
    - exploration.py

key-decisions:
  - "Sort by reversal_rate with nulls_last=True in plot_event_win_rates to match pandas sort_values NaN-last ordering (display-only; rates are null when an event_type has 0 resolved outcomes)"
  - "Printed tables now use polars' native DataFrame repr (select([...]) then print) instead of pandas to_string(index=False) -- row order is hash-order (RESEARCH Pitfall 5, cosmetic-only); win-rate values are explicit-agg, not order-dependent"
  - "qcut_with_fallback_labels collapsed to a one-line Series.qcut(allow_duplicates=True); the pandas except-ValueError fallback is unreachable in polars (RESEARCH Pitfall 4); these range/timing quartile bins are display-only"

patterns-established:
  - "matplotlib boundary: every plotted series crosses via get_column(col).to_numpy() / .to_list(); clip(upper=N) -> clip(upper_bound=N)"

requirements-completed: [MIGRATE-02]

# Metrics
duration: 4min
completed: 2026-06-07
---

# Phase 01 Plan 03: Exploration (exploration.py) on Polars Summary

**Ported `exploration.py` (consumer #1) from pandas to polars by swapping the engine at read/aggregate/extract/write while keeping matplotlib — `group_by/agg` + `pl.when/then` win-rate math, `qcut(allow_duplicates=True)` quartile bins, every plotted series fed via `.to_numpy()`/`.to_list()` at the chart boundary, and `write_csv` — consuming the pinned 21-col contract and regenerating all four chart PNGs plus `summary_by_event.csv` with zero pandas imports.**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-06-07
- **Tasks:** 2
- **Files modified:** 1 source (exploration.py) + regenerated chart/CSV outputs

## Accomplishments

- **Task 1 — aggregation layer:** Swapped `import pandas as pd` for `import polars as pl`. Ported `compute_win_rates` to `group_by(group_cols).agg(pl.len(), (col=="box").sum(), (col=="opposite").sum())` + `pl.when(resolved>0).then(...).otherwise(None)` for the rates (replaces the pandas `groupby` lambdas and `.where`); polars `group_by` keeps null groups by default, matching the old `dropna=False`. Collapsed `qcut_with_fallback_labels` to a one-line `series.qcut(q, labels=labels, allow_duplicates=True)` returning a Categorical (the pandas ValueError fallback is unreachable in polars). Ported `build_summary_table` to `group_by("event_type").agg(...)` + `with_columns` for `resolved`/`momentum_rate`/`reversal_rate`/`edge` + `sort("edge", descending=True)` + `select` of the original 8 columns.
- **Task 2 — plots + run():** Ported all four `plot_*` functions to feed matplotlib at the boundary (`get_column(col).to_numpy()` / `.to_list()`), replaced `.clip(upper=N)` with `.clip(upper_bound=N)`, `.merge(...)` with `.join(...)`, and `groupby(...).mean()` with `group_by(...).agg(...)`. Ported `run()` to `pl.read_parquet`, rewrote the common-times block as `value_counts()` (2-col DataFrame) -> `filter(count>=10).to_list()` -> `df.filter(is_in(...))`, replaced boolean-mask access with `filter`/`is_not_null`, `to_csv(index=False)` with `write_csv`, and printed tables via polars' native repr. Removed pandas entirely.
- **Result:** `python3 exploration.py` runs end-to-end on polars (exit 0), regenerates the win-rate / release-timing / range-quartile / MAE chart PNGs and `summary_by_event.csv` (8 columns intact), and `python3 smoke/phase1_smoke.py --check exploration` exits 0. The `--check nopandas` scan now flags **only** `causal_analysis.py` (01-04 scope) — `exploration.py` is clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: Port the exploration aggregation layer (compute_win_rates, qcut helper, build_summary_table)** - `21ac9b3` (refactor)
2. **Task 2: Port the exploration plot functions + run() orchestration** - `dc750d5` (refactor)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `exploration.py` - Full pandas->polars port: `group_by/agg` win-rate + summary aggregation, `qcut(allow_duplicates=True)`, matplotlib fed numpy/lists at the boundary, `value_counts` 2-col-DataFrame idiom, `join`/`filter`/`is_not_null`, `write_csv`. Zero pandas.
- `charts/exploration/summary_by_event.csv` - Regenerated per-event summary (8 cols: event_type, n, momentum_rate, reversal_rate, edge, median_mae, avg_time_to_sweep, avg_range_pct).
- `charts/exploration/momentum_vs_reversal_by_event.png`, `win_rate_by_range_quartile.png` (+ `momentum_vs_reversal_by_release_time.png`, `mae_distribution.png` byte-identical) - Regenerated chart outputs.

## Decisions Made

- **NaN-last sort fidelity:** `plot_event_win_rates` sorts by `reversal_rate` with `nulls_last=True` so events with 0 resolved outcomes (null rate) land at the end, matching pandas `sort_values` semantics. Display-only.
- **Printed-table order is cosmetic:** Tables now render via polars' native DataFrame repr in hash group order (RESEARCH Pitfall 5). Win-rate numbers are computed by explicit aggregation, not row order, so this is purely visual — accepted (threat T-01-31).
- **qcut fallback removed:** polars never raises on collapsed quantile bins, so the one-line `qcut(allow_duplicates=True)` is correct; these range/timing quartile bins are display-only, not methodology-critical (no parity required).

## Deviations from Plan

None - plan executed exactly as written. Both tasks ported the functions specified, all acceptance criteria and the plan-level verification passed on the first end-to-end run. (The regenerated, git-tracked chart/CSV outputs were committed alongside the Task 2 source change as the plan's promised artifacts.)

## Authentication Gates

None - pure local script port; no auth, no network, no package installs.

## Acceptance Criteria Verification

- `python3 exploration.py` -> exit 0; regenerates all four PNGs + `summary_by_event.csv`.
- `test -f charts/exploration/summary_by_event.csv` -> present; `ls charts/exploration/*.png` -> 4 PNGs.
- `python3 smoke/phase1_smoke.py --check exploration` -> `SMOKE OK: exploration` (exit 0).
- `! grep -nE "^[[:space:]]*(import pandas|from pandas)" exploration.py` -> no output.
- `! grep -nE "\.merge\(|\.iterrows\(|\.notna\(|pd\." exploration.py` -> no output.
- Task 1 direct call: `compute_win_rates(df, ["event_type"])` returns a polars DataFrame with `{total, resolved, momentum_rate, reversal_rate}`; `build_summary_table(df)` returns a polars DataFrame (height 67) sorted by `edge` desc; `qcut_with_fallback_labels` returns a Categorical Series on `range_pct` and `time_to_first_sweep` without raising.
- `grep -n "allow_duplicates=True" exploration.py` -> present in the qcut helper.
- `--check nopandas` now flags only `causal_analysis.py` (01-04); `exploration.py` no longer flagged.

## Known Stubs

None - `exploration.py` is fully wired end-to-end (contract read -> polars aggregation -> matplotlib charts + CSV). No placeholders or empty data sources introduced.

## Threat Flags

None - no new network endpoints, auth paths, file-access patterns, or schema changes introduced. The script reads the pinned contract via `pl.read_parquet` and overwrites regenerable outputs under `charts/exploration/` (threat register T-01-30 mitigated, T-01-31 accepted).

## Next Phase Readiness

- The 21-col contract is proven to survive the engine swap on consumer #1: exploration's win-rate / quartile / MAE outputs regenerate cleanly on polars.
- `causal_analysis.py` (01-04) remains the last pandas-flagged Phase-1 script; once ported, `--check nopandas` flips fully green.
- The pandas `tests/` suite is untouched and expected RED until Phase 3 (TEST-01) - not a Phase-1 gate.
- pandas stays installed until Phase 4 (ENV-01) - by design.

## Self-Check: PASSED

- FOUND: `exploration.py` (ported, pandas-free)
- FOUND: `charts/exploration/summary_by_event.csv` (regenerated, 8 cols)
- FOUND: `charts/exploration/momentum_vs_reversal_by_event.png` (regenerated)
- FOUND: commit `21ac9b3` (Task 1)
- FOUND: commit `dc750d5` (Task 2)

---
*Phase: 01-primary-pipeline-on-polars*
*Completed: 2026-06-07*
