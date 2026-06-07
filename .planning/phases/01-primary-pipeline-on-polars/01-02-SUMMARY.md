---
phase: 01-primary-pipeline-on-polars
plan: 02
subsystem: sweep-engine
tags: [polars, parquet, migration, data-contract, numpy-kernel, timezone, sweep-methodology]

# Dependency graph
requires:
  - "01-01: smoke/phase1_smoke.py (--check contract|read|nopandas) as the Phase-1 gate"
provides:
  - "main.py ported to polars: native reads (use_pyarrow=False), threaded lookups dict (no .attrs), pinned CONTRACT_SCHEMA write"
  - "Regenerated data/sweep_analysis_results.parquet (21-col contract, 4792 rows) on polars"
  - "Module-level CONTRACT_SCHEMA (21 cols + dtypes) pinning the downstream data contract"
affects:
  - 01-03-exploration-port
  - 01-04-causal-port
  - phase-2-independent-pipelines

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Preserve the numpy methodology kernel verbatim; port only the I/O boundary"
    - "Pin the output contract with an explicit schema= dict (no dict-inference dtype drift)"
    - "Thread ns-int64 lookup arrays explicitly via a lookups dict (polars has no per-frame metadata cache)"
    - "Force microseconds->nanoseconds (.astype('datetime64[ns]')) before any searchsorted / timing delta"
    - "Scalar wall-clock anchors via stdlib datetime/zoneinfo to keep the engine path pandas-free"

key-files:
  created: []
  modified:
    - main.py

key-decisions:
  - "Anchored event_time as np.datetime64(timestamp_ns_utc(event_time), 'ns') for timing deltas (epoch-ns) instead of np.datetime64(tz_aware_dt) to avoid numpy's tz-aware-datetime deprecation; result is identical and pandas-free"
  - "Added `from __future__ import annotations` so the file stays importable across the two-commit split (lazy annotations) and to match the project's newer-script convention"
  - "Kept the unused box_hit_time/opposite_hit_time assignments (wrapper-stripped to raw datetime64) to preserve the kernel block 1:1"

patterns-established:
  - "Per-script polars port = swap engine at load/lookup/extract/write only; numpy compute kernel untouched"

requirements-completed: [MIGRATE-01, ENV-02]

# Metrics
duration: 13min
completed: 2026-06-07
---

# Phase 01 Plan 02: Primary Pipeline (main.py) on Polars Summary

**Ported `main.py` (the sweep engine) from pandas to polars by swapping only the I/O boundary — native parquet reads, explicitly-threaded ns-int64 lookups (no `.attrs`), dict-row candle access, and a pinned 21-column `CONTRACT_SCHEMA` write — while preserving the numpy sweep-methodology kernel verbatim; the regenerated contract is 4792 rows with zero pandas in `main.py`.**

## Performance

- **Duration:** ~13 min
- **Completed:** 2026-06-07
- **Tasks:** 2
- **Files modified:** 1 (main.py)

## Accomplishments

- **Task 1 — data + lookup layer:** Replaced `import pandas` with `import polars`; `load_data()` now reads both raw inputs natively (`pl.read_parquet(use_pyarrow=False)`, ENV-02), normalizes `DateTime_UTC` to UTC, derives naive `DateTime_ET`, sorts, and returns a 3-tuple `(events, nq, lookups)`. Deleted `add_lookup_tables`/`nq.attrs` entirely and thread a `lookups = {"utc_values", "et_values"}` dict of ns-int64 arrays. `timestamp_ns_utc` rewritten in stdlib (no float rounding); `find_sorted_pos` left byte-for-byte unchanged. The three candle helpers take `lookups` and return `nq.row(pos, named=True)` dicts / a polars slice.
- **Task 2 — kernel + context + write:** Ported `analyze_event`, `get_session_context`, and `main()`. The numpy methodology kernel (sweep direction, first-target classification, synthetic box, MAE, argmax timing) is preserved verbatim — the only edits in that block were removing `pd.Timestamp(...)` scalar wrappers (timing deltas now computed from `datetime64[ns]` via numpy). Added a module-level `CONTRACT_SCHEMA` (21 cols, exact order/dtypes) and write the output with `pl.DataFrame(results, schema=CONTRACT_SCHEMA).write_parquet(...)`, pinning `event_datetime`=Datetime(ns,UTC), `pre_candle_volume`=Float64, `release_volume`=Int64.
- **Result:** `python3 main.py` runs end-to-end on polars, prints `Successfully analyzed 4792 events`, and regenerates `data/sweep_analysis_results.parquet` with the exact 21-col contract — the row count matches the prior pandas run (4792) exactly, strong evidence the methodology is intact.

## Task Commits

Each task was committed atomically:

1. **Task 1: Port the data + lookup layer (load_data, lookups threading, candle helpers)** - `992d41b` (refactor)
2. **Task 2: Port analyze_event (kernel verbatim) + get_session_context + main() write with pinned CONTRACT_SCHEMA** - `9ad31c8` (refactor)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `main.py` - Full pandas->polars port of the sweep engine: native reads, threaded ns lookups (no `.attrs`), stdlib scalar anchors, verbatim numpy kernel, pinned `CONTRACT_SCHEMA` write.
- `data/sweep_analysis_results.parquet` - Regenerated 21-col / 4792-row contract (gitignored output; not committed).

## Decisions Made

- **event_time anchoring for timing deltas:** Used `np.datetime64(timestamp_ns_utc(event_time), "ns")` (epoch-ns) rather than `np.datetime64(event_time, "ns")` on the tz-aware datetime — numpy deprecates constructing datetime64 from tz-aware datetimes, and the epoch-ns route is unambiguous and matches the `times` array (UTC wall-clock naive ns). Same numeric result, fully pandas-free.
- **`from __future__ import annotations`:** Added so leftover `pd.` type annotations in not-yet-ported functions did not break import during the two-commit split, and to match the project convention for newer scripts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded comments/docstring that contained the literal substring "attrs"**
- **Found during:** Task 1 verification
- **Issue:** Explanatory comments mentioning the removed `nq.attrs` cache contained the literal substring `attrs`, tripping the acceptance grep `! grep -n "attrs" main.py` (same class of issue as 01-01's "import pandas" docstring).
- **Fix:** Reworded the prose to "per-frame metadata cache" / "threaded via the lookups dict" — no `attrs` substring remains.
- **Files modified:** main.py
- **Verification:** `! grep -n "attrs" main.py` returns nothing; `load_data()` + smoke `--check read` still green.
- **Committed in:** `992d41b` (fix applied before the Task 1 commit)

**2. [Rule 1 - Bug] Fixed a typo in the CONTRACT_SCHEMA comment ("pl.DataPolarsFrame")**
- **Found during:** Task 2
- **Issue:** A comment introducing `CONTRACT_SCHEMA` referenced a non-existent `pl.DataPolarsFrame(...)`.
- **Fix:** Corrected to `pl.DataFrame(...)`.
- **Files modified:** main.py
- **Committed in:** `9ad31c8`

---

**Total deviations:** 2 auto-fixed (both cosmetic prose/typo). No scope creep; methodology logic unchanged.
**Impact on plan:** None functional — required only to satisfy a stated acceptance grep and fix a comment typo.

## Authentication Gates

None — pure local script port; no auth, no network, no package installs.

## Acceptance Criteria Verification

- `python3 main.py` → exit 0, prints `Successfully analyzed 4792 events` (N>0; us/ns reconciled).
- `python3 smoke/phase1_smoke.py --check contract` → `SMOKE OK: contract` (21 cols in pinned order; `event_datetime`=Datetime(ns,UTC), `pre_candle_volume`=Float64, `release_volume`=Int64; height 4792 > 0).
- `python3 smoke/phase1_smoke.py --check read` → `SMOKE OK: read` (native `use_pyarrow=False` path).
- `python3 smoke/phase1_smoke.py --check nopandas` → still exit 1, but now flags **only** `exploration.py` and `causal_analysis.py` — `main.py` is no longer flagged (ports land in 01-03 / 01-04).
- `! grep -nE "^[[:space:]]*(import pandas|from pandas)|pd\.|nq\.attrs" main.py` → no output; `! grep -n "attrs" main.py` → no output.
- `CONTRACT_SCHEMA` is a module-level dict with exactly 21 entries; `load_data()` returns `(events, nq, lookups)` with ns-int64 (`> 10**18`) arrays.
- Manual spot-check: `first_sweep` ∈ {high, low}; `first_target_hit` ∈ {None, box, opposite}; `mae_before_reversal` ≥ 0; all `time_to_first_sweep` ≥ 0 — sane.

## Known Stubs

None — `main.py` is fully wired end-to-end (raw reads → kernel → pinned contract write). No placeholders or empty data sources introduced.

## Next Phase Readiness

- The data contract is regenerated on polars and pins the 21-col schema; `exploration.py` (01-03) and `causal_analysis.py` (01-04) can now port against the live contract.
- `--check nopandas` flips fully green once those two scripts are ported; it currently passes for `main.py` only.
- The pandas `tests/` suite remains untouched and is expected RED until Phase 3 (TEST-01) — not a Phase-1 gate.
- pandas stays installed until Phase 4 (ENV-01) — by design.

## Self-Check: PASSED

- FOUND: `main.py` (ported, pandas-free)
- FOUND: `data/sweep_analysis_results.parquet` (regenerated, 21 cols / 4792 rows)
- FOUND: `.planning/phases/01-primary-pipeline-on-polars/01-02-SUMMARY.md`
- FOUND: commit `992d41b` (Task 1)
- FOUND: commit `9ad31c8` (Task 2)

---
*Phase: 01-primary-pipeline-on-polars*
*Completed: 2026-06-07*
