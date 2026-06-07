---
phase: 01-primary-pipeline-on-polars
plan: 01
subsystem: testing
tags: [polars, parquet, smoke-test, data-contract, migration, validation]

# Dependency graph
requires: []
provides:
  - "smoke/phase1_smoke.py — pandas-free Phase-1 integration smoke harness with per-check CLI"
  - "Independently-encoded 21-column CONTRACT_SCHEMA (dtype strings) as the live data-contract gate"
  - "no-pandas static scan over main.py / exploration.py / causal_analysis.py"
  - "native raw-input read check (use_pyarrow=False) and exploration/causal output-existence checks"
affects:
  - 01-02-primary-pipeline-port
  - 01-03
  - 01-04
  - phase-2-independent-pipelines

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Integration smoke harness kept SEPARATE from the pandas tests/ suite (smoke/ dir)"
    - "Pinned dtype-STRING contract assertion to catch silent us/ns and Int64/Float64 drift"
    - "Pandas-import regex built from parts so the harness file is itself pandas-free"

key-files:
  created:
    - smoke/phase1_smoke.py
  modified: []

key-decisions:
  - "Phase-1 validation signal is integration smoke, not the pandas unit suite (expected red until Phase 3 / TEST-01)"
  - "EXPECTED_SCHEMA encoded independently in the harness (NOT imported from main.py, which is still pandas at Wave 1)"
  - "Assert dtype strings (not just column count) so a us/ns or Int64 drift fails loudly"

patterns-established:
  - "smoke/ harness directory distinct from tests/ — default `pytest tests` run untouched"
  - "Per-check CLI (--check contract|read|nopandas|exploration|causal|all) every later port task gates on"

requirements-completed: [ENV-02]

# Metrics
duration: 9min
completed: 2026-06-07
---

# Phase 01 Plan 01: Phase-1 Integration Smoke Harness Summary

**Pandas-free polars-migration smoke harness (`smoke/phase1_smoke.py`) that independently encodes the 21-column CONTRACT_SCHEMA, validates the live data contract + native raw reads today, and exposes the per-check CLI gate every downstream Phase-1 port task depends on.**

## Performance

- **Duration:** ~9 min
- **Completed:** 2026-06-07
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments

- Created `smoke/` (a NEW directory, distinct from `tests/`) with `smoke/phase1_smoke.py`, importing only `polars`, `argparse`, `re`, `sys`, `pathlib` — zero pandas.
- Encoded a module-level `EXPECTED_SCHEMA` with exactly 21 entries in on-disk order, asserting dtype STRINGS so the drift-prone `event_datetime` (ns/UTC), `pre_candle_volume` (Float64), and `release_volume` (Int64) cannot silently drift.
- Implemented five check functions (`check_contract`, `check_read`, `check_nopandas`, `check_exploration`, `check_causal`) plus an argparse CLI with `--check {contract,read,nopandas,exploration,causal,all}` that prints `SMOKE OK: <check>` / `SMOKE FAIL: <message>` and exits 0/1.
- Verified the harness behaves as the Wave-1 gate: `contract` and `read` pass green against the live on-disk artifacts; `nopandas` correctly fails (the three scripts still import pandas at Wave 1) and will flip green as they are ported.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the Phase-1 integration smoke harness (smoke/phase1_smoke.py)** - `a04f8e1` (feat)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `smoke/phase1_smoke.py` - Standalone pandas-free Phase-1 smoke harness: 21-col contract schema assert, native raw-parquet read check, no-pandas static scan, exploration/causal output-existence checks, per-check CLI.

## Decisions Made

- None beyond the plan — followed the plan as specified. The harness encodes the contract schema independently (not imported from `main.py`) exactly because `main.py` is still pandas at Wave 1, per RESEARCH guidance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded a docstring that contained the literal substring "import pandas"**
- **Found during:** Task 1 (harness verification)
- **Issue:** A function docstring read "...assert none of the Phase-1 scripts import pandas." which caused the acceptance check `! grep -nE "import pandas|from pandas" smoke/phase1_smoke.py` to return a match, violating the "harness itself is pandas-free" criterion. (The actual import scan already used a parts-built regex `(?:import|from)\s+pandas\b`, so only the prose was at fault.)
- **Fix:** Reworded the docstring to "...assert none of the Phase-1 scripts pull in pandas."
- **Files modified:** smoke/phase1_smoke.py
- **Verification:** `grep -nE "import pandas|from pandas" smoke/phase1_smoke.py` now returns nothing; `contract` and `read` checks still pass.
- **Committed in:** `a04f8e1` (part of Task 1 commit — fix applied before the commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Cosmetic prose fix required to satisfy a stated acceptance criterion. No scope creep; functional logic unchanged.

## Issues Encountered

None. Pre-verified against the real environment before writing: polars 1.40.1 present; live `data/sweep_analysis_results.parquet` has exactly 21 cols / height 4792 matching `EXPECTED_SCHEMA`; both raw inputs read natively with `use_pyarrow=False`; all five exploration/causal output files already present from the prior pandas run.

## Acceptance Criteria Verification

- `python3 smoke/phase1_smoke.py --check contract` → exit 0 (`SMOKE OK: contract`).
- `python3 smoke/phase1_smoke.py --check read` → exit 0 (`SMOKE OK: read`).
- `python3 smoke/phase1_smoke.py --check nopandas` → exit 1 (EXPECTED at Wave 1 — flags `main.py:10`, `exploration.py:16`, `causal_analysis.py:18`; flips green as scripts are ported).
- `grep -nE "import pandas|from pandas" smoke/phase1_smoke.py` → no output (harness is pandas-free).
- `EXPECTED_SCHEMA` has exactly 21 entries; `smoke/` is a new directory distinct from `tests/`; `tests/` untouched; no `conftest.py` added.

## Next Phase Readiness

- The Phase-1 gate is live: plans 01-02 / 01-03 / 01-04 (the actual script ports) can now validate against `python3 smoke/phase1_smoke.py --check <check>` after each port.
- Expected behavior as ports land: `--check nopandas` flips from fail→pass once all three scripts are pandas-free; `--check contract` stays green only if the regenerated parquet keeps the pinned 21-col schema (catching dtype drift).
- The pandas `tests/` suite remains untouched and is expected RED until Phase 3 (TEST-01) — do NOT gate Phase 1 on it.

## Self-Check: PASSED

- FOUND: `smoke/phase1_smoke.py`
- FOUND: `.planning/phases/01-primary-pipeline-on-polars/01-01-SUMMARY.md`
- FOUND: commit `a04f8e1`

---
*Phase: 01-primary-pipeline-on-polars*
*Completed: 2026-06-07*
