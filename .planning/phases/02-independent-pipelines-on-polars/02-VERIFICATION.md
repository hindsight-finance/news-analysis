---
phase: 02-independent-pipelines-on-polars
verified: 2026-06-07T00:00:00Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 2: Independent Pipelines on Polars — Verification Report

**Phase Goal:** The two independent raw-data pipelines (forward_returns.py, injection.py) run on polars, with the pandas/numpy timestamp-lookup optimization replaced by a polars equivalent.
**Verified:** 2026-06-07
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `python3 forward_returns.py` exits 0 and writes `charts/forward_returns/forward_returns_by_event.csv` (ROADMAP SC 1) | VERIFIED | CSV present; 23,935 data rows; header confirmed. Commits 7ff6441 + 6038153. |
| 2 | `forward_returns.py` writes per-horizon PNGs: raw_by_direction, direction_normalized, mae_mfe_by_direction, normalized_mae_mfe_scatter (ROADMAP SC 1) | VERIFIED | 20 PNGs in `charts/forward_returns/`: 4 types × 5 horizons (15m/30m/45m/60m/90m). |
| 3 | `forward_returns.py` lookup path is pure-polars: no `np.searchsorted` and no `import pandas` (ROADMAP SC 2 / D-01) | VERIFIED | `grep -nE "import pandas|from pandas|np\.searchsorted|join_asof" forward_returns.py` returns 0 matches. `with_row_index` + inner-join present. |
| 4 | Release and future candle lookups are exact-match — events whose exact minute is absent are skipped, no `join_asof` / nearest-match (D-04) | VERIFIED | `build_timestamp_index` uses `how="inner"` with no `join_asof`. Misses drop, reproducing the old `None -> continue` behavior. |
| 5 | nq `DateTime_UTC` and event `datetime_utc` normalized to ns/UTC before any equality/join key — events NOT silently dropped (D-05) | VERIFIED | `normalize_nq` casts to ns; `normalize_events` casts to ns. `build_forward_returns(ev, nq)` returns 23,935 rows (events are not all dropped). |
| 6 | Window aggregation preserves positional `[release_idx+1, future_idx]` semantics via row index (D-07) | VERIFIED | `nq.slice(release_idx + 1, future_idx - release_idx)` at line 167. Comment confirms inclusive coverage. |
| 7 | Summaries computed via polars `group_by/agg`; direction-normalized rows excluded via `is_not_nan` (D-08, D-09) | VERIFIED | `group_by` + `agg` in `summarize_returns`/`summarize_path_profiles`. `is_not_nan` on lines 220, 238. Runtime check: 0 flat rows leak through the normalized filter. |
| 8 | `python3 injection.py` exits 0 and writes per-event histogram PNGs to `charts/` (ROADMAP SC 3) | VERIFIED | 67 PNGs present in `charts/`. Commits 869a59d + d16aced. |
| 9 | `injection.py` release-candle range/volume and 10-minute range computed in polars (ROADMAP SC 3) | VERIFIED | `get_release_candle_data` reads candle via `nq.row(idx, named=True)`. `get_10min_range` uses `nq.filter(pl.col("DateTime_UTC").is_between(...))`. |
| 10 | `injection.py` release-candle lookup uses pure-polars exact-match replacing the linear boolean-mask scan (D-02) | VERIFIED | `build_release_index` with `with_row_index` + `inner` join. No per-event `nq[nq[...] == ...]` scan. |
| 11 | Release-candle lookup is exact-match-or-None — no `join_asof` / nearest-match (D-04) | VERIFIED | `ts_to_idx.get(event_time)` returns `None` on miss; `get_release_candle_data` returns `None` on miss. No `join_asof` in file. |
| 12 | 10-minute window is TIME-bounded filter on `DateTime_UTC` inclusive `[event_time, event_time+9min]`, NOT a positional +9-row slice (D-06) | VERIFIED | `is_between(event_time, end_time, closed="both")` at injection.py line 107. `end_time = event_time + timedelta(minutes=9)`. |
| 13 | nq `DateTime_UTC` and event `datetime_utc` normalized to ns/UTC before equality — events NOT silently dropped (D-05) | VERIFIED | `load_data` casts both columns to ns. PLAN verification check: 4797 event minutes match nq (non-zero). |
| 14 | `matplotlib.use("Agg")` appears before `import matplotlib.pyplot` in injection.py (D-10) | VERIFIED | Lines 9-10: `import matplotlib; matplotlib.use("Agg")` then `import matplotlib.pyplot as plt`. Positional assertion confirmed in code. |
| 15 | `injection.py` keeps `main()` entry shape — no `run()`/argparse added (D-11) | VERIFIED | `def main` present, `if __name__ == "__main__": main()` present. No `argparse` or `def run(` found. |

**Score:** 15/15 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `forward_returns.py` | Polars port of forward-returns pipeline; `pl.read_parquet` | VERIFIED | 411 lines; `import polars as pl`; no pandas; contains `build_timestamp_index`, `build_forward_returns`, `summarize_returns`, four `plot_*` functions, `run()`. |
| `charts/forward_returns/forward_returns_by_event.csv` | Per-event/per-horizon rows written from polars frame | VERIFIED | 23,935 data rows; columns include `event_type`, `horizon_minutes`, `news_candle_direction`, `raw_forward_return_pct`, direction-normalized columns, MFE/MAE columns. |
| `injection.py` | Polars port of injection range/histogram pipeline; Agg-before-pyplot; pure-polars exact-match lookup | VERIFIED | 228 lines; `import polars as pl`; no pandas; `matplotlib.use("Agg")` at line 10 before pyplot; `build_release_index`, `get_release_candle_data`, `get_10min_range`. |
| `charts/*.png` | Per-event release-candle + 10-minute range histogram PNGs | VERIFIED | 67 PNGs in `charts/`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `forward_returns.py` | `data/nq_1m.parquet` | `pl.read_parquet(use_pyarrow=False)` | WIRED | `run()` calls `pl.read_parquet(input_nq, use_pyarrow=False)` |
| `forward_returns.py build_forward_returns` | `nq DateTime_UTC row index` | `with_row_index` + inner-join exact-match | WIRED | `build_timestamp_index` builds `nq.with_row_index("idx").select(["DateTime_UTC", "idx"])`, inner-joins wanted timestamps, collapses to dict |
| `injection.py` | `data/nq_1m.parquet` | `pl.read_parquet(use_pyarrow=False)` | WIRED | `load_data()` calls `pl.read_parquet(DATA_DIR / "nq_1m.parquet", use_pyarrow=False)` |
| `injection.py get_release_candle_data` | `nq DateTime_UTC row index` | `with_row_index` + inner-join exact-match | WIRED | `build_release_index` builds `nq.with_row_index("idx").select(...)`, inner-joins, collapses to dict; `get_release_candle_data` consumes via `ts_to_idx.get(event_time)` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `forward_returns.py` (CSV + PNGs) | `df` (pl.DataFrame of rows) | `build_forward_returns(ev, nq)` → per-event/per-horizon loop over 5,067 events | Yes — 23,935 rows returned from real parquet inputs | FLOWING |
| `injection.py` (PNGs) | `release_ranges`, `release_volumes`, `ten_min_ranges` | `get_release_candle_data` + `get_10min_range` per event occurrence | Yes — 67 PNGs written for real event types | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `build_forward_returns` returns non-empty (D-05 guard) | `python3 -c "... df=fr.build_forward_returns(ev,nq); assert df.height>0"` | 23,935 rows | PASS |
| D-09: flat rows excluded from direction-normalized summaries | `... flat_count=(norm_check.get_column('news_candle_direction')=='flat').sum()` | 0 | PASS |
| D-05 injection: event minutes match nq | PLAN verification check via join | 4797 event minutes match | PASS |
| D-10: Agg before pyplot in injection.py | positional index check | `a < b` True | PASS |
| No forbidden patterns in forward_returns.py | `grep -nE "import pandas|np\.searchsorted|join_asof"` | exit 1 (no matches) | PASS |
| No argparse/run() in injection.py | `grep -n "argparse|def run("` | no matches | PASS |
| CSV row count | `wc -l charts/forward_returns/forward_returns_by_event.csv` | 23,936 lines (header + 23,935 rows) | PASS |
| Charts exist: 20 PNGs in forward_returns/ | `ls charts/forward_returns/*.png \| wc -l` | 20 | PASS |
| Charts exist: 67 PNGs in charts/ | `ls charts/*.png \| wc -l` | 67 | PASS |
| Commits exist | `git log --oneline 7ff6441 6038153 869a59d d16aced` | All 4 commits present | PASS |

---

### Probe Execution

No probe scripts defined for this phase.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MIGRATE-04 | 02-01-PLAN.md | `forward_returns.py` runs on polars, including a polars replacement for the `np.searchsorted` timestamp-lookup optimization | SATISFIED | Pure-polars `build_timestamp_index` (with_row_index + inner-join) replaces `find_sorted_pos`/`np.searchsorted`; pandas absent; CSV + 20 PNGs produced; 23,935 rows. |
| MIGRATE-05 | 02-02-PLAN.md | `injection.py` runs on polars — range calculation and histogram inputs use polars | SATISFIED | `build_release_index` (pure-polars exact-match), `get_10min_range` (polars `is_between`), `get_release_candle_data` (polars `nq.row`); pandas absent; 67 PNGs produced. |

---

### Deferred Items

Items correctly absent — intentionally deferred to later phases.

| Item | Deferred To | Decision |
|------|------------|----------|
| `main.py` lookup re-port to pure-polars | Out of scope / future cleanup | D-03: main.py keeps numpy-searchsorted holdout by design; accepted divergence |
| `injection.py` `run()`/argparse entry point | STRUCT-03, future milestone | D-11: entry-point restructure is deferred; main() shape preserved |
| VALID-02 skipped-event counting | Future milestone | Silent skip/None behavior retained; observable count deferred |
| Shared-utils extraction (IN-01) | Future milestone | Utility duplication is a known documented anti-pattern; extraction is STRUCT-01 |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `forward_returns.py` | 213-214, 228-229 | Quantile default changed: polars `nearest` vs pandas `linear` (WR-01 from REVIEW.md) | INFO | Per verification scope notes: explicitly ACCEPTED. Output parity not required (project constraint). p25/p75 values shift slightly; mean/median unaffected. Noted in REVIEW.md. |
| Both files | 94-129, 60-80 | Index-builder logic duplicated (IN-01 from REVIEW.md) | INFO | Known anti-pattern per CLAUDE.md; STRUCT-01 extraction is a future milestone item. Not a correctness issue. |

No TBD/FIXME/XXX/TODO/HACK debt markers found in either modified file.

---

### Human Verification Required

None — all verification items for this phase are programmatically verifiable.

---

### Gaps Summary

No gaps. All 15 must-haves are verified against the actual codebase. Both MIGRATE-04 and MIGRATE-05 are satisfied. All methodology constraints (D-04 through D-11) hold in the implemented code.

The two code review warnings (WR-01 quantile interpolation, WR-02 dict-zip duplicate behavior) are pre-triaged advisory items per the verification scope notes and do not constitute phase-2 goal failures.

---

_Verified: 2026-06-07_
_Verifier: Claude (gsd-verifier)_
