---
phase: 02-independent-pipelines-on-polars
plan: 02
subsystem: data-pipeline
tags: [polars, parquet, timestamp-lookup, with_row_index, is_between, matplotlib, injection, histograms]

# Dependency graph
requires:
  - phase: 01-primary-pipeline-on-polars
    provides: "main.py load_data() ns/UTC normalization template; exploration.py matplotlib boundary"
  - phase: 02-independent-pipelines-on-polars
    provides: "forward_returns.py build_timestamp_index pure-polars exact-match lookup (02-01) — the shared construct mirrored here (D-02/D-03)"
provides:
  - "injection.py ported to polars (pandas-free, headless-safe Agg guard)"
  - "Pure-polars exact-match release lookup (build_release_index) replacing the linear boolean-mask scan anti-pattern"
  - "Time-bounded 10-minute window via is_between (D-06), not a positional +9-row slice"
  - "Regenerated per-event release-candle + 10-minute histogram PNGs in charts/ (67 event types)"
affects: [phase-03-tests, phase-04-drop-pandas]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-polars exact-match lookup reused: build_release_index collapses all event timestamps to a {ts: idx} dict via with_row_index + inner-join (one pass over 5.3M rows), mirroring forward_returns.build_timestamp_index (D-02/D-03)"
    - "us->ns cast_time_unit on both join keys before equality (D-05 silent-drop guard)"
    - "10-minute window as a TIME-bounded is_between([t, t+9min], closed=both) filter, robust to missing minutes/gaps (D-06)"
    - "main() entry shape preserved — no run()/argparse (D-11, STRUCT-03 deferred)"

key-files:
  created: []
  modified:
    - "injection.py - full pandas->polars port (imports/Agg guard + load_data + exact-match lookup + range helpers + main() loop)"

key-decisions:
  - "Threaded a {ts: idx} dict (built once via build_release_index) into get_release_candle_data rather than a per-event full-frame filter — the dict resolves all releases in one inner-join, avoiding the D-02 O(n)-per-event scan"
  - "Kept get_10min_range as a full-frame is_between filter (benchmarked ~2.5ms/event, ~12s total) — D-06-compliant and matches the plan's (nq, event_time) signature; the optional bounded-neighborhood fast-path was unnecessary"
  - "Left create_histograms unchanged — accumulation lists are plain python and the helper values come back as python scalars, so np.median/np.mean/ax.hist need no polars->numpy conversion"
  - "Committed regenerated charts/*.png alongside the Task 2 code change, mirroring the 02-01 precedent (charts/ is tracked, not gitignored)"

patterns-established:
  - "Both Phase-2 independent pipelines (forward_returns.py, injection.py) now share the same pure-polars exact-match lookup construct (D-03); main.py remains the lone numpy-searchsorted holdout by design"

requirements-completed: [MIGRATE-05]

# Metrics
duration: 6min
completed: 2026-06-07
---

# Phase 2 Plan 02: injection.py polars port Summary

**injection.py runs entirely on polars: a pandas-free, headless-safe pipeline whose release-candle lookup is a pure-polars exact-match (with_row_index + inner-join) replacing the linear boolean-mask scan, with a time-bounded is_between 10-minute window — regenerating per-event range/volume histograms for 67 event types.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-07T04:36:59Z
- **Completed:** 2026-06-07T04:42:29Z
- **Tasks:** 2
- **Files modified:** 1 source file (+ 67 regenerated/new chart PNGs)

## Accomplishments
- Replaced the documented linear boolean-mask anti-pattern (`nq['DateTime_UTC'] == event_time`) with `build_release_index`: a pure-polars exact-match lookup that inner-joins every event datetime against `nq[[DateTime_UTC, idx]]` in one pass and collapses matches into a `{ts: idx}` dict — the same construct `forward_returns.py` uses (D-02/D-03/D-04).
- Guarded the D-05 µs→ns landmine: `load_data` renames `datetime_utc`→`DateTime_UTC`, branch-normalizes tz, and `dt.cast_time_unit("ns")` on both the nq column and the events key before any equality — 4797 of 5067 event minutes resolve (events are NOT silently dropped).
- Kept the 10-minute range a TIME-bounded `is_between([event_time, event_time+9min], closed="both")` filter (D-06), not a positional +9-row slice — robust to missing minutes/gaps.
- Added the headless `import matplotlib; matplotlib.use("Agg")` guard before `import matplotlib.pyplot` (D-10); the script is now pandas-free with `numpy` retained for the histogram stats.
- Preserved the `main()` entry shape with `if __name__ == "__main__": main()` and the silent-skip/None behavior — no `run()`/argparse (D-11), no skipped-event counting (VALID-02 deferred).
- Ran end-to-end (exit 0, ~54s): regenerated per-event histogram PNGs into `charts/` for 67 event types.

## Task Commits

Each task was committed atomically:

1. **Task 1: Port injection.py imports, load_data, exact-match lookup, and range functions** - `869a59d` (feat)
2. **Task 2: Port injection.py main() loop to polars (keep main() shape)** - `d16aced` (refactor)

**Plan metadata:** (this SUMMARY + STATE/ROADMAP/REQUIREMENTS) committed separately.

## Files Created/Modified
- `injection.py` - Full pandas→polars port: Agg-before-pyplot imports, polars `load_data` (rename + tz/ns normalization, D-05), new `build_release_index` (pure-polars exact-match lookup, D-02/D-03/D-04), `get_release_candle_data` consuming the `{ts: idx}` dict (None on miss, D-04), `get_10min_range` as an `is_between` time filter (D-06), and a polars `main()` loop (`get_column().unique().to_list()` / `filter` / `iter_rows`).
- `charts/*.png` - 67 per-event release-candle + 10-minute histogram PNGs regenerated from the polars pipeline (32 modified, 35 new event types now charted).

## Decisions Made
- **Lookup threading:** Built the `{ts: idx}` dict once in `main()` via `build_release_index` and threaded it into `get_release_candle_data(nq, ts_to_idx, event_time)`, mirroring how `build_forward_returns` consumes `build_timestamp_index`. This satisfies D-02 (no per-event full-frame scan) and D-03 (same mechanism as forward_returns).
- **10-min window construct:** Benchmarked the full-frame `is_between` at ~2.5 ms/event (~12 s across 5067 events), so the plan's primary `(nq, event_time)` form was kept; the optional bounded-neighborhood fast-path was not needed and would have complicated the D-06 time-predicate definition.
- **create_histograms untouched:** The accumulation lists stay plain python and the per-candle values return as python scalars from the helpers, so no `.to_numpy()`/`.to_list()` boundary change was required inside the histogram function.
- **Artifact commit:** Committed regenerated `charts/` PNGs with the Task 2 code change (charts/ is tracked, not gitignored), matching the 02-01 precedent.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- **Latent pre-existing bug confirmed and fixed (anticipated by the plan):** the old pandas `injection.py` accessed `nq['DateTime_UTC']` while the on-disk column is `datetime_utc` — the script would have raised a `KeyError` and could not run as-is. Task 1's instructed rename (`datetime_utc`→`DateTime_UTC`) resolves this; the polars port now runs end-to-end. This is why 35 event types are newly charted vs. the previously-tracked 60 PNGs (the prior tracked charts predate the column-name drift). Handled as planned work, not a deviation.

## User Setup Required
None - no external service configuration required. Raw inputs read read-only via `pl.read_parquet(use_pyarrow=False)`; `data/` is never written.

## Threat Flags
None - injection.py only reads the two parquet inputs read-only and writes PNGs to charts/; no new network/auth/schema surface. Threat-register mitigations are satisfied: D-05 ns/UTC cast (T-02-04), read-only parquet access never writing data/ (T-02-05), exact-match-or-None lookup + time-bounded window (T-02-06).

## Next Phase Readiness
- Both Phase-2 independent pipelines (`forward_returns.py`, `injection.py`) are now pandas-free and share the same pure-polars exact-match lookup (D-03). Phase 2 success criteria met.
- `main.py` remains the lone numpy-`searchsorted` holdout by design (D-03) — do NOT "helpfully" revert it for consistency.
- pandas is still installed (removed in Phase 4 / ENV-01); `injection.py` now contains zero `import pandas`.
- Deferred and untouched here: STRUCT-03 (`run()`/argparse for injection.py) and VALID-02 (skipped-event counting) — both intentionally left for post-migration.

## Self-Check: PASSED

- FOUND: `injection.py`
- FOUND: `charts/US Crude Oil Inventories.png`
- FOUND: `.planning/phases/02-independent-pipelines-on-polars/02-02-SUMMARY.md`
- FOUND commit: `869a59d` (Task 1)
- FOUND commit: `d16aced` (Task 2)

---
*Phase: 02-independent-pipelines-on-polars*
*Completed: 2026-06-07*
