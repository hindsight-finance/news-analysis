---
phase: 01-primary-pipeline-on-polars
verified: 2026-06-07T00:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 1: Primary Pipeline on Polars — Verification Report

**Phase Goal:** The sweep-analysis pipeline (`main.py` → `exploration.py` + `causal_analysis.py`) runs end-to-end on polars, with the intermediate `sweep_analysis_results.parquet` data contract intact and the sweep methodology logic ported faithfully.
**Verified:** 2026-06-07
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Truths are drawn from the 4 ROADMAP success criteria (the contract) plus the PLAN frontmatter must_haves (supplementary detail). All 13 are VERIFIED.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Smoke harness validates the 21-column CONTRACT_SCHEMA against the contract parquet | VERIFIED | `python3 smoke/phase1_smoke.py --check contract` → `SMOKE OK: contract`; 21 cols, 4792 rows, `event_datetime`=Datetime(ns,UTC), `pre_candle_volume`=Float64, `release_volume`=Int64 |
| 2 | Harness reads both raw inputs natively (`use_pyarrow=False`) with no pandas | VERIFIED | `python3 smoke/phase1_smoke.py --check read` → `SMOKE OK: read` |
| 3 | Harness statically detects any `import pandas` in the three Phase-1 scripts | VERIFIED | `python3 smoke/phase1_smoke.py --check nopandas` → `SMOKE OK: nopandas`; zero matches |
| 4 | Harness detects presence of exploration and causal chart + CSV outputs | VERIFIED | `python3 smoke/phase1_smoke.py --check exploration` and `--check causal` both → `SMOKE OK` |
| 5 | `python3 main.py` on polars produces `data/sweep_analysis_results.parquet` with N>0 rows | VERIFIED | Contract has 4792 rows (matches pandas run exactly); `first_sweep` ∈ {high, low}; `mae_before_reversal` ≥ 0; `time_to_first_sweep` ≥ 0 |
| 6 | `main.py` has zero pandas imports; lookups dict replaces `nq.attrs` | VERIFIED | `grep -nE "import pandas|from pandas" main.py` → no output; `grep -n "attrs" main.py` → no output |
| 7 | 21-column CONTRACT_SCHEMA is a module-level dict in `main.py`; `pl.DataFrame(results, schema=CONTRACT_SCHEMA)` pins dtypes | VERIFIED | `len(main.CONTRACT_SCHEMA)` = 21; contract parquet schema matches exactly |
| 8 | Lookup arrays are nanosecond-scale int64 (us→ns conversion applied) | VERIFIED | `int(lk['utc_values'][0])` = 1275861600000000000 > 10^18; both arrays dtype=int64 |
| 9 | `exploration.py` runs on polars with zero pandas imports; `group_by/agg` + `qcut(allow_duplicates=True)` | VERIFIED | `grep -nE "import pandas" exploration.py` → no output; `grep -n "allow_duplicates=True" exploration.py` → line 65 |
| 10 | `exploration.py` writes `summary_by_event.csv` + all four chart PNGs | VERIFIED | `charts/exploration/summary_by_event.csv`, `momentum_vs_reversal_by_event.png`, `win_rate_by_range_quartile.png`, `momentum_vs_reversal_by_release_time.png`, `mae_distribution.png` all present |
| 11 | `causal_analysis.py` runs on polars with zero pandas imports | VERIFIED | `grep -nE "import pandas" causal_analysis.py` → no output |
| 12 | `causal_analysis.py` uses a single explicit polars→numpy boundary (`features.to_numpy()`) at `.fit()`; `cv_folds` runs on the polars `y` Series before the boundary | VERIFIED | `cv_folds(y)` at line 180; `X = features.to_numpy()` at line 185; `print_cv_score` signature takes pre-computed `folds` int |
| 13 | `causal_analysis.py` writes `event_stats.csv` + all four causal chart PNGs | VERIFIED | `charts/causal/event_stats.csv`, `feature_importance.png`, `logistic_coefficients.png`, `decision_tree.png`, `event_edge.png` all present |

**Score:** 13/13 truths verified

### Full Smoke Run

`python3 smoke/phase1_smoke.py --check all` → `SMOKE OK: all` (exit 0)

All five individual checks pass:
- `--check contract` → SMOKE OK
- `--check read` → SMOKE OK
- `--check nopandas` → SMOKE OK
- `--check exploration` → SMOKE OK
- `--check causal` → SMOKE OK

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `smoke/phase1_smoke.py` | Phase-1 smoke harness; 21-entry EXPECTED_SCHEMA; no pandas | VERIFIED | 219 lines; imports only `polars`, `argparse`, `re`, `sys`, `pathlib`; `EXPECTED_SCHEMA` has 21 entries; pandas-import regex built from parts to avoid literal match |
| `main.py` | Polars sweep engine; module-level CONTRACT_SCHEMA; lookups dict; no pandas | VERIFIED | `import polars as pl`; `CONTRACT_SCHEMA` = 21 entries; `load_data()` returns `(events, nq, lookups)`; no `nq.attrs`; no pandas |
| `data/sweep_analysis_results.parquet` | 21-col contract, 4792 rows, correct dtypes | VERIFIED | Schema matches EXPECTED_SCHEMA exactly; height=4792 > 0; all methodology columns sane |
| `exploration.py` | Polars port; group_by/agg; qcut(allow_duplicates=True); no pandas | VERIFIED | All pandas idioms replaced; `allow_duplicates=True` present; `value_counts()` 2-col idiom; `write_csv` |
| `charts/exploration/summary_by_event.csv` | Per-event summary (8 cols) | VERIFIED | File present |
| `charts/exploration/*.png` | 4 chart PNGs | VERIFIED | 4 PNGs present |
| `causal_analysis.py` | Polars port; single to_numpy() boundary; cv_folds before boundary; no pandas | VERIFIED | `folds = cv_folds(y)` at line 180 before `X = features.to_numpy()` at line 185; `replace_strict` and `fill_null` both present |
| `charts/causal/event_stats.csv` | Per-event edge ranking | VERIFIED | File present |
| `charts/causal/*.png` | 4 causal chart PNGs | VERIFIED | 4 PNGs present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `smoke/phase1_smoke.py` | `data/sweep_analysis_results.parquet` | `pl.read_parquet` + schema assert | WIRED | `check_contract` reads and asserts all 21 cols+dtypes |
| `smoke/phase1_smoke.py` | `main.py`, `exploration.py`, `causal_analysis.py` | regex scan for `import pandas\|from pandas` | WIRED | `check_nopandas` scans all three as text |
| `main.py load_data` | `data/nq_1m.parquet` + `data/economic_events.parquet` | `pl.read_parquet(use_pyarrow=False)` | WIRED | lines 85-86 in main.py |
| `main.py load_data` | `analyze_event` | `lookups = {"utc_values": ..., "et_values": ...}` | WIRED | 3-tuple return; lookups threaded to all helpers |
| `main.py main()` | `data/sweep_analysis_results.parquet` | `pl.DataFrame(results, schema=CONTRACT_SCHEMA).write_parquet` | WIRED | lines 363-366 |
| `exploration.py run()` | `data/sweep_analysis_results.parquet` | `pl.read_parquet` | WIRED | line 205 |
| `exploration.py plot_*` | matplotlib | `.to_numpy()` / `.to_list()` at boundary | WIRED | confirmed in plot functions |
| `causal_analysis.py build_features` | `run()` model training | `features.to_numpy()` / `y.to_numpy()` at `.fit()` | WIRED | lines 184-186; single boundary |
| `causal_analysis.py run()` | `data/sweep_analysis_results.parquet` | `pl.read_parquet` | WIRED | line 43 via `load_resolved_results` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `data/sweep_analysis_results.parquet` | 4792-row DataFrame | `pl.DataFrame(results, schema=CONTRACT_SCHEMA)` where `results` is built by `analyze_event` iterating all events | Yes — 4792 rows, methodology values sane | FLOWING |
| `charts/exploration/summary_by_event.csv` | `build_summary_table(df)` result | `group_by("event_type").agg(...)` on the 4792-row contract | Yes — 8-column summary, event-level aggregations | FLOWING |
| `charts/causal/event_stats.csv` | `event_stats` from `df.group_by("event_type").agg(...)` | Derived from `load_resolved_results` filtering the contract | Yes — per-event edge rankings | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Smoke harness exits 0 for all checks | `python3 smoke/phase1_smoke.py --check all` | `SMOKE OK: all` | PASS |
| No pandas imports in 3 scripts | `grep -nE "import pandas\|from pandas" main.py exploration.py causal_analysis.py` | no output | PASS |
| Contract has 4792 rows, 21 cols, correct dtypes | `pl.read_parquet(...).schema + height` | 4792 rows, all 21 dtypes match EXPECTED_SCHEMA | PASS |
| Lookup arrays are ns-scale | `int(lk['utc_values'][0]) > 10**18` | 1275861600000000000 > 10^18 | PASS |
| cv_folds before numpy boundary | `grep -n "folds = cv_folds\|X = features"` | line 180 (cv_folds) before line 185 (to_numpy) | PASS |
| Methodology values sane | `first_sweep` ∈ {high,low}; `mae_before_reversal` ≥ 0; `time_to_first_sweep` ≥ 0 | All checks True | PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes exist. The phase-declared validation signal is `smoke/phase1_smoke.py`.

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `smoke/phase1_smoke.py` | `python3 smoke/phase1_smoke.py --check all` | exit 0 — `SMOKE OK: all` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MIGRATE-01 | 01-02 | `main.py` sweep engine runs on polars; `sweep_analysis_results.parquet` produced; methodology preserved | SATISFIED | `main.py` is polars; contract has 4792 rows with exact 21-col schema; numpy kernel verbatim |
| MIGRATE-02 | 01-03 | `exploration.py` runs on polars — win-rate, release-timing, range-quartile, MAE computations | SATISFIED | `exploration.py` pandas-free; 4 PNGs + `summary_by_event.csv` present; `group_by/agg` + `qcut(allow_duplicates=True)` |
| MIGRATE-03 | 01-04 | `causal_analysis.py` runs on polars for data handling; explicit `polars → numpy` at sklearn boundary | SATISFIED | Single `features.to_numpy()` at line 185; `cv_folds` on polars `y` at line 180; all causal outputs present |
| ENV-02 | 01-01, 01-02 | polars reads raw parquet inputs directly; backend dependency resolved | SATISFIED | `pl.read_parquet(use_pyarrow=False)` for both inputs; smoke `--check read` exits 0 |

All 4 phase requirements satisfied. No orphaned requirements.

### Commit Verification

All 7 commits documented in the SUMMARYs exist in the repo:

| Commit | Summary | Plan |
|--------|---------|------|
| `a04f8e1` | feat: add Phase-1 polars migration smoke harness | 01-01 Task 1 |
| `992d41b` | refactor: port main.py data + lookup layer to polars | 01-02 Task 1 |
| `9ad31c8` | refactor: port analyze_event/session-context/main to polars | 01-02 Task 2 |
| `21ac9b3` | refactor: port exploration aggregation layer to polars | 01-03 Task 1 |
| `dc750d5` | refactor: port exploration plots + run() to polars | 01-03 Task 2 |
| `426da91` | refactor: port causal data + feature layer to polars | 01-04 Task 1 |
| `e1f2356` | refactor: port causal run() to single polars->numpy model boundary | 01-04 Task 2 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers in any of the 4 phase-modified files | — | None |

No debt markers found in `smoke/phase1_smoke.py`, `main.py`, `exploration.py`, or `causal_analysis.py`.

**Advisory items from 01-REVIEW.md (0 critical, 4 warnings, 4 info — all advisory, none blocking):**

These were flagged by the prior code review and are noted here for completeness. They do not block the phase goal.

- WR-01 (`exploration.py:89-94`): `build_summary_table` divides with no zero-resolved guard → NaN in summary CSV for event_types with all-null `first_target_hit`. `compute_win_rates` already guards with `pl.when(resolved>0)`, but `build_summary_table` does not. Advisory fix.
- WR-02 (`main.py:378-398`): `main()` summary prints divide by `n` with no `n==0` guard. Raises `ZeroDivisionError` only if `results` is empty. Advisory fix.
- WR-03 (`exploration.py:150-175`): polars `group_by` returns groups in hash order; quartile chart bars render in non-deterministic order (not Q1→Q4). Research-output quality concern but does not invalidate the methodology.
- WR-04 (`main.py:119,155-159`): `et_values` array may not be strictly sorted across DST fall-back (pre-existing, not introduced by this port). Session-context lookup times (08:29, 00:00, 18:00) are outside the 01:00–01:59 ambiguous window.

### Human Verification Required

None. All required verifications were completed programmatically:
- The VALIDATION.md "Manual-Only" spot-check (sane sweep/target/MAE values) was verified by direct parquet introspection: `first_sweep` ∈ {high, low} only, `first_target_hit` ∈ {None, box, opposite} only, `mae_before_reversal` ≥ 0 for all rows, `time_to_first_sweep` ≥ 0 for all rows.
- The numpy methodology kernel preservation was confirmed by reading `main.py` lines 242–317 directly: the compute block (sweep direction, first-target, MAE, synthetic box, argmax timing) is unchanged; only `pd.Timestamp(...)` scalar wrappers were replaced with numpy `datetime64[ns]` deltas.

### Deferred Items

Items out of scope for Phase 1, explicitly covered by later phases:

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | `forward_returns.py` and `injection.py` still import pandas | Phase 2 | Phase 2 goal: "Port `forward_returns.py` and `injection.py`"; MIGRATE-04, MIGRATE-05 |
| 2 | pytest `tests/` suite is RED (asserts pandas semantics) | Phase 3 | Phase 3 goal: "Port the pytest suite to polars and get it green"; TEST-01 |
| 3 | pandas still installed globally | Phase 4 | Phase 4 goal: "Remove all remaining pandas imports and pin pandas-free runtime"; MIGRATE-06, ENV-01 |

---

_Verified: 2026-06-07_
_Verifier: Claude (gsd-verifier)_
