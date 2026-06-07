---
status: issues_found
phase: 01-primary-pipeline-on-polars
depth: quick
files_reviewed: 4
critical: 0
warning: 4
info: 4
total: 8
reviewed: 2026-06-07
---

# Phase 1 Code Review: pandas→polars Primary Pipeline

**Depth:** quick (extended with targeted empirical verification against polars 1.40.1)
**Files reviewed:** 4 — `smoke/phase1_smoke.py`, `main.py`, `exploration.py`, `causal_analysis.py`
**Status:** issues_found — 0 Critical/Blocker · 4 Warning · 4 Info

## Summary

The correctness-critical migration paths hold up. Empirically confirmed against polars 1.40.1:

- The us→ns timestamp conversion is correct and robust whether the source column is `Datetime(us)` or `Datetime(ns)` — event-ns lookups match candle-ns exactly, so **no rows are silently dropped** (the run analyzes the full 4792 events, matching the prior pandas contract height).
- The numpy methodology kernel in `main.py` (sweep direction, first-target, MAE limit/normalization, argmax timing) is faithfully preserved.
- The single polars→numpy boundary in `causal_analysis.py` is ordered correctly: `cv_folds(y)` runs on the polars Series before `.to_numpy()`.
- `replace_strict({...}, default=-1)` for `gap_direction_encoded` maps null → -1 (verified), so `features.to_numpy()` does not inject NaN and `sklearn.fit()` will not crash on null gaps.

No BLOCKER-tier defect found. The findings below are robustness/quality regressions, not methodology-breaking bugs.

## Warnings

### WR-01: `build_summary_table` divides counts with no zero-resolved guard → NaN in summary CSV
**File:** `exploration.py:89-94`
For any `event_type` whose rows all have `first_target_hit` null, `resolved == 0`, and polars yields `0/0 = NaN`. `momentum_rate`/`reversal_rate`/`edge` become NaN, `summary_by_event.csv` shows `NaN`, and the `.sort("edge", descending=True)` ordering is corrupted by NaN. Inconsistent with `compute_win_rates` (lines 44-51) which guards with `pl.when(resolved > 0).then(...).otherwise(None)`.
**Fix:** Apply the same `pl.when(pl.col("resolved") > 0).then(...).otherwise(None)` guard to `momentum_rate` and `reversal_rate`.

### WR-02: `main()` summary divides by `n = df.height` with no `n == 0` guard → ZeroDivisionError
**File:** `main.py:378-398`
If `results` is empty, `first_high / n * 100` raises `ZeroDivisionError` — *after* the success message and contract write. Clean message preferred over raw traceback.
**Fix:** `n = df.height; if n == 0: print("No events analyzed; skipping summary statistics."); return`

### WR-03: Quartile / group_by output ordering is non-deterministic — quartile chart and printed tables are not in Q1→Q4 order
**File:** `exploration.py:150-175` (`plot_range_quartile_rates`), also `exploration.py:231-237`, `causal_analysis.py:263-274`
polars `group_by` does not preserve order by default (verified: `Q3,Q1,Q4,Q2` → `Q4,Q3,Q1,Q2`). pandas `groupby` sorted by key by default, so the port silently scrambled the ordering of an **ordinal** quartile axis — the range-quartile chart renders bars/x-labels in hash order rather than Q1(smallest)→Q4(largest), misleading the researcher. Same for the printed timing/midnight-distance/gap-direction quartile tables.
**Fix:** `.sort("range_quartile")` (the categorical preserves Q1<Q2<Q3<Q4) before plotting/printing, or pass `maintain_order=True` to the relevant `group_by` calls.
**Note:** This touches research-output integrity (the asset) — recommended to fix even though advisory.

### WR-04: ET binary-search array is not strictly sorted across DST fall-back
**File:** `main.py:119, 155-159` (`et_values`, `get_candle_at_time`)
`et_values` is the naive-ET column in UTC-sorted order; across the Nov DST fall-back ET wall-clock repeats 1:00–1:59, so the array has a descending run and `np.searchsorted` is undefined on it. Queried session-context times (08:29, 00:00, prior-day 18:00/16:59) lie outside the overlap so lookups typically resolve, but it is a latent hazard. **Pre-existing from the pandas code — not introduced by this port.**
**Fix:** Resolve session-context candles by computing each target's UTC instant via `ZoneInfo("America/New_York")` and reusing the strictly-sorted `utc_values` array instead of `et_values`.

## Info

### IN-01: Dead variables `box_hit_time` / `opposite_hit_time`
**File:** `main.py:285-287, 302, 305` — initialized/assigned but never read (not in the result dict). Remove, or add to the contract if intended outputs.

### IN-02: "Convert exactly once" comment contradicts the code
**File:** `causal_analysis.py:182-185` vs `235, 277-280` — `features.get_column(f).to_numpy()` (correlations) and `x_readable.to_numpy()` (readable tree) also cross the boundary. Harmless; reword the comment to "the primary model-fitting boundary."

### IN-03: `release_volume` feature lacks the `fill_null(0)` guard applied to peers
**File:** `causal_analysis.py:73` — every other numeric feature uses `.fill_null(0)` (lines 74-78); `release_volume` does not. A null `Volume` would upcast to float64 NaN and crash `sklearn.fit()`. Low likelihood; inconsistent with the defensive pattern.

### IN-04: `gap_6pm_direction == "flat"` and null collapse to the same encoding
**File:** `causal_analysis.py:69-71` — `replace_strict({"up":1,"down":0,"flat":-1}, default=-1)` maps both `"flat"` and null to `-1`, making a flat gap indistinguishable from a missing gap. Modeling-fidelity nuance; document or disambiguate if they should differ.

---

*Advisory review — does not block phase completion. To auto-apply: `/gsd-code-review 01 --fix` (Critical+Warning) or `--fix --all` (include Info).*
