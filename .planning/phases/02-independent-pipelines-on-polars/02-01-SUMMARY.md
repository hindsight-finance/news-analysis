---
phase: 02-independent-pipelines-on-polars
plan: 01
subsystem: data-pipeline
tags: [polars, parquet, timestamp-lookup, with_row_index, group_by, matplotlib, forward-returns]

# Dependency graph
requires:
  - phase: 01-primary-pipeline-on-polars
    provides: "main.py load_data() ns/UTC normalization template; exploration.py group_by/agg + matplotlib boundary template"
provides:
  - "forward_returns.py ported to polars (pandas-free, searchsorted-free)"
  - "Pure-polars exact-match timestamp lookup (with_row_index + inner-join) reusable by injection.py (02-02)"
  - "charts/forward_returns/forward_returns_by_event.csv + 20 per-horizon PNGs regenerated from polars"
affects: [02-02-injection, phase-03-tests, phase-04-drop-pandas]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-polars exact-match lookup: build_timestamp_index() collapses all event+horizon timestamps to a {ts: idx} dict via with_row_index + inner-join (one pass over 5.3M rows)"
    - "us->ns cast_time_unit on both join keys before equality (D-05 silent-drop guard)"
    - "Positional window via nq.slice(release_idx+1, future_idx-release_idx) preserving [release_idx+1, future_idx] inclusive (D-07)"
    - "is_not_nan (not is_not_null) to exclude np.nan flat-direction rows (D-09)"

key-files:
  created: []
  modified:
    - "forward_returns.py - full pandas->polars port (data layer + summaries + charts + run)"

key-decisions:
  - "Used Option B (vectorized inner-join of all wanted timestamps) for the pure-polars lookup, collapsed to a {ts: idx} dict consumed in the per-event loop"
  - "Kept the per-event/per-horizon python loop shape; only the lookup mechanism changed to pure-polars"
  - "Printed summaries via with_columns(pl.col(pl.Float64).round(4)) under pl.Config(tbl_rows=-1) instead of DataFrame.round to avoid touching non-float columns"
  - "Committed regenerated chart/CSV outputs alongside the code change, mirroring Phase-1 precedent (dc750d5)"

patterns-established:
  - "build_timestamp_index() pure-polars lookup is the shared construct injection.py (02-02) will reuse (D-02/D-03)"

requirements-completed: [MIGRATE-04]

# Metrics
duration: 14min
completed: 2026-06-07
---

# Phase 2 Plan 01: forward_returns.py polars port Summary

**forward_returns.py runs entirely on polars: a pandas-free, searchsorted-free pipeline that resolves candle lookups with a with_row_index + inner-join exact-match, preserves the positional MFE/MAE window, and computes summaries via group_by/agg — producing forward_returns_by_event.csv (23,935 rows) plus 20 per-horizon charts.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-07T04:18:00Z
- **Completed:** 2026-06-07T04:32:45Z
- **Tasks:** 2
- **Files modified:** 1 source file (+ regenerated chart/CSV artifacts)

## Accomplishments
- Replaced `np.searchsorted`/`find_sorted_pos` with a pure-polars exact-match lookup (`build_timestamp_index`): every event datetime and every horizon offset is resolved to an `nq` row index in a single `with_row_index` + inner-join pass, collapsed into a `{timestamp: idx}` dict.
- Guarded the D-05 µs→ns landmine: both `nq.DateTime_UTC` and the events key are `dt.cast_time_unit("ns")` before any join/equality — `build_forward_returns` returns 23,935 non-empty rows (events are NOT silently dropped).
- Preserved methodology semantics exactly: exact-match-or-skip (D-04, inner-join misses drop = old `None` → `continue`), positional `[release_idx+1, future_idx]` window via `nq.slice` (D-07), and the `np.nan` flat-direction sentinel carried into the helpers unchanged.
- Ported `summarize_returns`/`summarize_path_profiles` to `group_by/agg` (win_rate/continuation_rate as `(pl.col(...) > 0).mean() * 100`; quantiles via `.quantile`) with the D-09 `is_not_nan` exclusion of flat-direction NaN rows.
- Ported all four `plot_*` functions and `run()`/`write_outputs` to polars, feeding matplotlib via `.to_numpy()` at the boundary and writing the CSV via `write_csv`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Port forward_returns.py data layer (load, pure-polars lookup, build_forward_returns)** - `7ff6441` (feat)
2. **Task 2: Port forward_returns.py summaries, charts, and run() to polars** - `6038153` (refactor)

**Plan metadata:** (this SUMMARY + STATE/ROADMAP) committed separately.

## Files Created/Modified
- `forward_returns.py` - Full pandas→polars port: `normalize_nq`/`normalize_events` (replace `ensure_utc`/`normalize_nq_columns`), `build_timestamp_index` (replaces `timestamp_ns_utc`/`find_sorted_pos`), polars `build_forward_returns`, `group_by/agg` summaries, polars `plot_*`, and polars `run()`/`write_outputs`.
- `charts/forward_returns/forward_returns_by_event.csv` - Regenerated 23,935-row output from the polars pipeline.
- `charts/forward_returns/*.png` - 20 per-horizon charts (4 chart types × 5 horizons) regenerated; 7 PNGs changed, the rest byte-identical.

## Decisions Made
- **Lookup construct (Option B):** Chose the vectorized inner-join of all wanted timestamps (event + every horizon offset) over a per-event `with_row_index` + filter, then collapsed the match to a `{ts: idx}` dict consumed by the existing per-event loop. One join pass over 5.3M rows; no per-event full-frame scan.
- **Printed-table rounding:** Used `with_columns(pl.col(pl.Float64).round(4))` rather than `DataFrame.round(4)` so the round is scoped to float columns only (avoids touching `horizon_minutes`/`count`/`news_candle_direction`). Output parity is not required (PROJECT decision), so cosmetic display choices are free.
- **Artifact commit:** Committed regenerated `charts/forward_returns/` outputs with the Task 2 code change, matching the Phase-1 precedent where the exploration/causal port commits included their regenerated charts (`dc750d5`).

## Deviations from Plan

None - plan executed exactly as written. (One in-task adjustment: an early grep failure was caused by the literal tokens `np.searchsorted`/`join_asof` appearing in a docstring; reworded the docstring to "numpy searchsorted"/"as-of/nearest-match join" so the acceptance grep passes. No behavior change.)

## Issues Encountered
- **Acceptance grep tripped on documentation text:** The Task 1 acceptance `grep -nE "...np\.searchsorted|join_asof..."` matched my explanatory docstring (which described what the code does NOT use). Reworded the docstring to avoid the literal forbidden substrings; the lookup code itself never used either construct. Resolved before the Task 1 commit.

## User Setup Required
None - no external service configuration required. Raw inputs read read-only via `pl.read_parquet(use_pyarrow=False)`; data/ never written.

## Next Phase Readiness
- `build_timestamp_index` is the shared pure-polars exact-match lookup that plan 02-02 (`injection.py`, MIGRATE-05) must reuse (D-02/D-03). Note: injection's 10-minute window stays a **time-bounded** filter (D-06), not the positional slice used here.
- `main.py` remains the lone numpy-`searchsorted` holdout by design (D-03) — do NOT "helpfully" revert this file for consistency.
- pandas is still installed (removed in Phase 4); `forward_returns.py` now contains zero `import pandas`.

## Self-Check: PASSED

- FOUND: `forward_returns.py`
- FOUND: `charts/forward_returns/forward_returns_by_event.csv`
- FOUND: `.planning/phases/02-independent-pipelines-on-polars/02-01-SUMMARY.md`
- FOUND commit: `7ff6441` (Task 1)
- FOUND commit: `6038153` (Task 2)

---
*Phase: 02-independent-pipelines-on-polars*
*Completed: 2026-06-07*
