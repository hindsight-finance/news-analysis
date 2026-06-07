---
phase: 02-independent-pipelines-on-polars
reviewed: 2026-06-07T00:00:00Z
depth: quick
files_reviewed: 2
files_reviewed_list:
  - forward_returns.py
  - injection.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-07
**Depth:** quick
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the pandas->polars port of `forward_returns.py` and `injection.py` (diff `790a0c0..HEAD`).
The migration is correct on every domain-critical axis I was asked to weight, which I verified
against the pre-port pandas source and with small polars reproductions:

- **ns/UTC precision normalization** is applied on BOTH sides before equality/join in both files
  (`normalize_nq`/`normalize_events` and `load_data`, plus a redundant-but-safe cast inside the
  index builders). The us->ns landmine is avoided; no silent event drop.
- **Exact-match lookup is exact-match**: `how="inner"` with no as-of/nearest join; misses drop and
  reproduce the old `None -> continue` / `if candle.empty: return None` behavior.
- **forward_returns positional window** `nq.slice(release_idx + 1, future_idx - release_idx)` is
  off-by-one-correct: I confirmed it yields rows `[release_idx+1 .. future_idx]` inclusive, matching
  the old `nq.iloc[release_pos + 1:future_pos + 1]`.
- **injection 10-minute window** is a TIME-bounded inclusive `is_between(event_time, +9min, closed="both")`
  filter, not a positional +9-row slice (D-06 satisfied); `row(0)` reference open is correct because
  the source frame is sorted.
- **NaN handling** uses `is_not_nan` (not `is_not_null`); I confirmed `np.nan` from the list-of-dicts
  lands as float NaN and that `is_not_nan` drops it while `is_not_null` would not. Correct.

Two warnings remain (a silent numeric divergence in quantile method, and an unguarded reliance on
nq timestamp uniqueness that changes which row wins on a duplicate), plus two maintainability notes.

## Warnings

### WR-01: Quantile interpolation silently changed (p25/p75 shift)

**File:** `forward_returns.py:213-214`, `forward_returns.py:228-229`
**Issue:** `pl.col(...).quantile(0.25)` / `quantile(0.75)` use polars' default
`interpolation="nearest"`, whereas the pre-port pandas `Series.quantile(0.25/0.75)` used the default
`interpolation="linear"`. I reproduced the divergence directly: for `[1,2,3,4]`, polars q0.25 = `2.0`
but pandas q0.25 = `1.75`. The reported `p25`/`p75` columns in both `raw_summary` and
`normalized_summary` will therefore shift for every horizon/direction group. This is a methodology
summary statistic in research code; the change is silent and undocumented (the `.median()`/`.mean()`
calls are unaffected, so the drift is easy to miss).
**Fix:** Make the interpolation explicit to match prior behavior:
```python
pl.col("raw_forward_return_pct").quantile(0.25, interpolation="linear").alias("p25"),
pl.col("raw_forward_return_pct").quantile(0.75, interpolation="linear").alias("p75"),
```
(apply the same to the `normalized_summary` p25/p75). If `nearest` is intentionally preferred, note
it in the docstring so the choice is deliberate rather than an accident of the default.

### WR-02: Lookup picks the LAST matching nq row on duplicate timestamps (was FIRST)

**File:** `forward_returns.py:122-129`, `injection.py:70-80`
**Issue:** The index builders inner-join `wanted` (deduped) against `nq_keys` and collapse with
`dict(zip(timestamps, idx))`. If `nq.DateTime_UTC` ever contains a duplicate minute, the join emits
multiple rows for that key and `dict(zip(...))` keeps the LAST one (verified: `dict(zip(["k","k"],[1,2])) == {"k":2}`).
The pre-port `np.searchsorted(..., side="left")` deterministically returned the FIRST occurrence.
nq is *expected* to be unique-per-minute, but nothing in the port guards or asserts this, so a future
data hiccup would silently (a) select a different candle than the legacy pipeline and (b) inflate the
intermediate `matched` frame via row multiplication before the dict dedups it.
**Fix:** Make the uniqueness explicit and deterministic, e.g. dedup the nq keys keeping the first
occurrence before the join:
```python
nq_keys = (
    nq.with_row_index("idx")
      .select(["DateTime_UTC", "idx"])
      .unique(subset="DateTime_UTC", keep="first")
)
```
or add an assertion that `nq_keys.height == nq_keys.select("DateTime_UTC").n_unique()` so a duplicate
fails loudly instead of silently changing the selected candle.

## Info

### IN-01: Index-builder logic duplicated across the two ports

**File:** `forward_returns.py:94-129` (`build_timestamp_index`) and `injection.py:60-80` (`build_release_index`)
**Issue:** The two builders are near-identical (row-index + select + cast-ns + inner-join + dict-zip),
and the ns/UTC normalization is also duplicated between `normalize_nq`/`normalize_events` and
`injection.load_data`. CLAUDE.md already flags utility duplication as a known anti-pattern; the port
reproduces and slightly grows it. Not a correctness issue, but every fix (e.g. WR-02) must now be
applied in two places.
**Fix:** Extract a shared `build_timestamp_index(events_keys, nq, offsets=())` helper into a small
module both scripts import, so lookup semantics live in one place.

### IN-02: Horizon offset computed two different ways for the same lookup key

**File:** `forward_returns.py:116` (`pl.col("datetime_utc") + pl.duration(minutes=horizon)`) vs `forward_returns.py:157` (`event_time + timedelta(minutes=int(horizon))`)
**Issue:** The dict KEY for a horizon is built with polars `pl.duration`, but the lookup is performed
with Python `datetime + timedelta`. They agree today (whole-minute, DST-free UTC instants, exact in
both ns and us), so lookups hit. But it is two sources of truth for the same value: if either side's
precision/tz handling ever drifts, the key would miss and the row would be silently dropped (no error)
rather than failing visibly — a quiet way to lose research samples.
**Fix:** Derive the lookup key from the same construction as the dict (or, after extracting per IN-01,
resolve future indices through the shared builder) so there is a single offset code path.

---

_Reviewed: 2026-06-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
