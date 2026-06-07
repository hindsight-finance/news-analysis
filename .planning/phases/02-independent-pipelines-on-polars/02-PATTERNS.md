# Phase 2: Independent Pipelines on Polars - Pattern Map

**Mapped:** 2026-06-07
**Files analyzed:** 2 modified (`forward_returns.py`, `injection.py`)
**Analogs found:** 2 / 2 modified files have strong in-codebase analogs (Phase-1 polars ports). 1 sub-pattern (the pure-polars exact-match lookup construct) has **no** in-codebase analog and must be synthesized — see "No Analog Found".

> Both files being modified are pandas today; every analog is an **already-ported Phase-1 polars script** in the repo root (`main.py`, `exploration.py`, `causal_analysis.py`). The planner/executor should mirror those ports, NOT the current pandas source. The current pandas `forward_returns.py` / `injection.py` are the **methodology source of truth** (what behavior to preserve), not the style template.

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog(s) | Match Quality |
|---------------|------|-----------|-------------------|---------------|
| `forward_returns.py` | analysis script / data-transform pipeline (utility) | batch transform + file-I/O; per-event/per-horizon **exact-match lookup** (request-response sub-flow); positional-window reduce; `group_by/agg` summary | **lookup + load:** `main.py` · **aggregation (D-08):** `exploration.py` · **matplotlib boundary / numpy hand-off:** `exploration.py`, `causal_analysis.py` | role-match (lookup), **exact** (aggregation) |
| `injection.py` | analysis script / data-transform pipeline (utility) | batch transform + file-I/O; per-event **exact-match lookup** + **time-bounded window** filter; histogram output | **lookup + load + time window:** `main.py` · **matplotlib `Agg` + numpy boundary:** `forward_returns.py`/`exploration.py` (Agg), `exploration.py`/`causal_analysis.py` (boundary) | role-match |

**Data-flow note:** the lookup is the only "request-response"-shaped sub-flow (one event timestamp → one candle row, or `None`). D-04 requires it stay **exact-match** (skip on miss), D-05 requires **matched precision+tz** on both sides, D-06 (injection) / D-07 (forward_returns) constrain the surrounding window semantics. The construct is pure-polars (D-01/D-02), deliberately diverging from `main.py`'s numpy `searchsorted` (D-03 — **do not revert to numpy**).

---

## Pattern Assignments

### `forward_returns.py` (analysis pipeline; exact-match lookup + positional window + group_by summary)

**Primary analog:** `main.py` (load/normalize/lookup) + `exploration.py` (summary aggregation) + `exploration.py`/`causal_analysis.py` (matplotlib/numpy boundary).

#### 1. Load + UTC tz/precision normalization — mirror `main.py:load_data` (D-05)

The current pandas `normalize_nq_columns` / `ensure_utc` (`forward_returns.py:25-46`) and the `utc_values` numpy build (`forward_returns.py:100`) are replaced by `main.py`'s polars normalization. This is the **direct template** and it guards the µs→ns equality landmine.

**Analog — `main.py:85-119`:**
```python
events = pl.read_parquet(DATA_DIR / "economic_events.parquet", use_pyarrow=False)
nq = pl.read_parquet(DATA_DIR / "nq_1m.parquet", use_pyarrow=False)

if "DateTime_UTC" not in nq.columns and "datetime_utc" in nq.columns:
    nq = nq.rename({"datetime_utc": "DateTime_UTC"})

# naive -> stamp UTC; aware -> convert. Same branch for events.
if nq.schema["DateTime_UTC"].time_zone is None:
    nq = nq.with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC"))
else:
    nq = nq.with_columns(pl.col("DateTime_UTC").dt.convert_time_zone("UTC"))

if events.schema["datetime_utc"].time_zone is None:
    events = events.with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC"))
else:
    events = events.with_columns(pl.col("datetime_utc").dt.convert_time_zone("UTC"))

nq = nq.sort("DateTime_UTC")
```

**Critical (D-05 / RESEARCH Pitfall 1):** `nq_1m.parquet` is `Datetime(us, UTC)`, `economic_events.parquet` is `Datetime(ns, UTC)`. For a **pure-polars equality** lookup both sides must share unit AND tz. Before any `==`/join key, force a common unit with `pl.col("DateTime_UTC").dt.cast_time_unit("ns")` on the nq side (verified equivalent in `01-RESEARCH.md:240-246`). The old numpy path forced this via `.astype("datetime64[ns]")` (`main.py:118-119`); the pure-polars path must force it via `.dt.cast_time_unit("ns")` on **both** the event key and the nq column. **If skipped, every `==` fails and all events silently drop.**

#### 2. Exact-match lookup + positional window `[release_idx+1, future_idx]` (D-04, D-07)

Preserve today's semantics from the pandas source:
- exact-match-or-skip — `find_sorted_pos(...) is None: continue` (`forward_returns.py:105-107`, `116-117`),
- positional window — `nq.iloc[release_pos+1 : future_pos+1]` → `max(High)` / `min(Low)` (`forward_returns.py:121-125`).

The lookup mechanism becomes **pure-polars** (see "Shared Patterns → Pure-polars exact-match lookup"). Once a release/future **row index** is obtained, the positional window has a direct polars precedent:

**Analog (positional slice by index) — `main.py:149-152`:**
```python
length = end_pos - (start_idx + 1)
if length <= 0:
    return pl.DataFrame()
return nq.slice(start_idx + 1, length)   # was pandas nq.iloc[start_idx+1 : end_pos]
```
Map to `forward_returns.py`: `nq.slice(release_idx + 1, future_idx - release_idx)` covers `[release_idx+1, future_idx]` inclusive (length = `future_idx - release_idx`), then `.get_column("High").max()` / `.get_column("Low").min()`. The current `if window.empty: continue` (`forward_returns.py:122`) becomes `if window.is_empty(): continue` (RESEARCH State-of-the-Art table). Single-row extraction (release/future `Close`, `Open`) uses `nq.row(idx, named=True)` per `main.py:128`.

**Do NOT** use `join_asof`/nearest-match (D-04) — snapping corrupts methodology.

#### 3. Summary aggregations — mirror `exploration.py` group_by/agg (D-08, D-09)

Port `summarize_returns` (`forward_returns.py:159-186`) and `summarize_path_profiles` (`forward_returns.py:189-201`) using `exploration.py`'s established `group_by().agg(<expr>)` form. `win_rate`/`continuation_rate` = `(pl.col(...) > 0).mean() * 100`; quantiles via `pl.col(...).quantile(0.25/0.75)`.

**Analog — `exploration.py:75-96` (`build_summary_table`, the mean/median/derived-rate template):**
```python
df.group_by("event_type")
  .agg(
      pl.len().alias("n"),
      pl.col("mae_before_reversal").mean().alias("avg_mae"),
      pl.col("mae_before_reversal").median().alias("median_mae"),
      pl.col("range_pct").mean().alias("avg_range_pct"),
  )
  .with_columns(
      (pl.col("momentum") / pl.col("resolved") * 100).round(1).alias("momentum_rate"),
  )
  .sort("edge", descending=True)
  .select([...])      # explicit output column order
```

**Win-rate / when-then idiom — `exploration.py:43-52`:**
```python
.with_columns(
    pl.when(pl.col("resolved") > 0)
      .then(pl.col("momentum_wins") / pl.col("resolved") * 100)
      .otherwise(None)
      .alias("momentum_rate"),
)
```
For `forward_returns.py`, the per-group win_rate becomes `(pl.col("raw_forward_return_pct") > 0).mean() * 100` inside `.agg(...)` keyed on `["horizon_minutes", "news_candle_direction"]` (raw) and `["horizon_minutes"]` (normalized). D-08: printed row order is cosmetic — `group_by` does not preserve order (RESEARCH Pitfall 5); add `.sort("horizon_minutes", ...)` if a stable printed table is wanted.

**D-09 — preserve `.notna()` exclusion** of flat-direction NaN rows before the normalized/path summaries (`forward_returns.py:173`, `190`). Polars precedent for the filter-out-missing idiom:

**Analog — `causal_analysis.py:44`:**
```python
df = df.filter(pl.col("first_target_hit").is_not_null())
```
Caveat: direction-normalized columns hold float **NaN** (from `np.nan` in `direction_normalized_return`/`_profile`), not polars null. `.is_not_null()` does **not** drop NaN (RESEARCH Pitfall 6: `fill_null` ≠ `fillna`). Use `.filter(pl.col("direction_normalized_return_pct").is_not_nan())` (or `.is_finite()`), or have the pure-math helpers emit `None` instead of `np.nan` so `is_not_null()` works. The planner must pick one and keep the exclusion exact.

#### 4. Pure-math helpers — carry over unchanged (CONTEXT "Claude's Discretion")

`candle_direction` (`forward_returns.py:56-61`), `direction_normalized_return` (`:64-69`), `direction_normalized_profile` (`:72-89`) are pandas-free scalar math. Keep verbatim (only revisit the `np.nan` sentinel per the D-09 note above). No analog needed.

#### 5. Charts — extract polars → numpy/list at the matplotlib boundary

The current plot fns pass pandas Series straight into matplotlib and use pandas idioms (`df[df[...] == h]`, `.groupby(...)` at `:275`, `Series.median()`). Replace selection with `df.filter(pl.col("horizon_minutes") == h)`, and feed matplotlib via `.to_numpy()` / `.to_list()`.

**Analog — `exploration.py:116-119`:**
```python
ax.barh(y_pos, by_event.get_column("momentum_rate").to_numpy(), ...)
ax.set_yticklabels([f"{e} (n={int(t)})"
    for e, t in zip(by_event.get_column("event_type").to_list(),
                    by_event.get_column("resolved").to_list())])
```
**Analog — `causal_analysis.py:138` / `:235`** (per-column `.to_numpy()` into matplotlib / numpy math; `np.corrcoef(features.get_column(f).to_numpy(), y_np)`). `forward_returns.py`'s boxplots take a **list of arrays** — build it as `[hd.filter(pl.col("news_candle_direction")==d).get_column("raw_forward_return_pct").to_numpy() for d in directions]`. The pandas `for direction, subset in df.groupby(...)` at `:275` becomes a `for d in directions: subset = df.filter(pl.col("news_candle_direction")==d)` loop (RESEARCH Pitfall 5: polars `group_by` is unordered — iterate an explicit ordered list instead).

#### 6. Entry point — keep existing `run()`/argparse shape

`forward_returns.py` already has `run(...)` + `parse_args()` (`:309-344`). `exploration.py:203-271` is the matching polars precedent (read_parquet, mkdir, write_csv, print summaries). Swap `pd.read_parquet`→`pl.read_parquet`, `df.empty`→`df.is_empty()`, `df.to_csv(path, index=False)`→`df.write_csv(path)` (RESEARCH State-of-the-Art table), `.round(4).to_string(index=False)`→`print(df.round(4))` under `pl.Config(tbl_rows=-1)` (cf. `main.py:423`).

---

### `injection.py` (analysis pipeline; exact-match lookup + time-bounded window + histograms)

**Primary analog:** `main.py` (load/normalize/lookup + the time-window concept) + `forward_returns.py`/`exploration.py` (`Agg` import order) + `exploration.py`/`causal_analysis.py` (numpy boundary).

#### 1. Load + UTC normalization — mirror `main.py:load_data` (D-05)

The current `load_data` (`injection.py:19-32`) unconditionally `tz_localize('UTC')`s nq and conditionally localizes events — replace wholesale with `main.py:85-119`'s branch-on-`time_zone` normalization (same excerpt as forward_returns §1). Same µs→ns precision discipline applies before the lookup (D-05). Keep reads native: `pl.read_parquet(..., use_pyarrow=False)`.

#### 2. Exact-match release-candle lookup — pure-polars, replace the linear scan (D-02, D-04)

Current `get_release_candle_data` (`injection.py:40-51`) does `mask = nq['DateTime_UTC'] == event_time; nq[mask]` — the documented **linear boolean-mask anti-pattern** (CONCERNS.md). D-02 upgrades it to the **same pure-polars fast lookup** used by `forward_returns.py` (see Shared Patterns). Preserve exact-match-or-`None` (`injection.py:46-47` `if candle.empty: return None`) → `if <miss>: return None`. The percentage-range math (`calculate_percentage_range`, `:35-37`) is pure scalar math — carry over.

#### 3. 10-minute window — keep TIME-bounded filter, NOT positional +9 (D-06)

Current `get_10min_range` (`injection.py:54-68`) is `(nq['DateTime_UTC'] >= event_time) & (nq['DateTime_UTC'] <= event_time + 9min)`. D-06: this **stays a time-range filter** (robust to missing minutes/gaps), even though the release row is located by the fast index lookup. Pure-polars precedent for a bounded filter:

**Analog (membership/bounded filter) — `exploration.py:213`:**
```python
df.filter(pl.col("release_time").is_in(common_times))
```
Apply as `nq.filter(pl.col("DateTime_UTC").is_between(event_time, end_time))` (or `(pl.col >= a) & (pl.col <= b)`), inclusive on both ends to match `>= … <= …`. The conceptual time-window analog in the codebase is `main.py:get_candles_until_eod` (`:131-152`) — but that one is numpy/searchsorted; D-06's window must be **pure-polars filter**, not ported from main.py's numpy path. After filtering: `candles.get_column("High").max()`, `.get_column("Low").min()`, reference open via `candles.row(0, named=True)["Open"]` (cf. `main.py:138` `nq.row(start_idx, named=True)["DateTime_ET"]`), guard `if candles.is_empty(): return None`.

#### 4. `matplotlib.use("Agg")` before pyplot (D-10)

Current `injection.py:10` is `import matplotlib.pyplot as plt` with **no** `Agg` call (the lone headless-unsafe script). Add the guard exactly as every other script does.

**Analog — `forward_returns.py:13-15` (identical in `exploration.py:13-15`, `causal_analysis.py:14-16`):**
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
```

#### 5. Histogram data — extract polars → list/numpy at the boundary

`create_histograms` (`injection.py:71-126`) takes plain python `list`s (`release_ranges`, etc.) appended in `main()` and feeds `np.median`/`np.mean`/`ax.hist`. The accumulation lists stay plain python; only the per-candle values pulled from polars rows change (scalar `row[...]["High"]` access, cf. `main.py:138`). Where a whole column is charted, use `.to_numpy()`/`.to_list()` (cf. `exploration.py:116-119`). `np.median(...)`/`np.mean(...)` over python lists is unchanged.

#### 6. Entry point — KEEP `main()` shape, do NOT add `run()`/argparse (D-11)

`injection.py`'s `main()` (`:129-171`) and `if __name__ == "__main__": main()` (`:174-175`) stay as-is structurally. **Deliberately do NOT mirror** `exploration.py`/`forward_returns.py`'s `run()`+`parse_args()` here — that restructure is STRUCT-03, deferred. Port the body to polars (`events.iter_rows(named=True)` for the per-event loop, cf. `main.py:355`; `events.get_column("title").unique().to_list()` for the unique-titles loop, replacing `events['title'].unique()` at `:134`; `events.filter(pl.col("title") == event_name)` replacing `:142`). Cosmetic touch-ups (double quotes, `from __future__ import annotations`) are not required (D-11).

---

## Shared Patterns

### Pure-polars exact-match lookup (D-01, D-02, D-04, D-05) — the core shared construct

**Used by:** both `forward_returns.py` and `injection.py`, and they must use the **same** mechanism (D-03, internally consistent).
**Source:** NO existing in-codebase analog (see "No Analog Found"). `main.py`'s `find_sorted_pos` (`main.py:69-74`) shows the **semantics to preserve** but uses numpy `searchsorted` — Phase 2 **deliberately diverges** (D-03). The construct is left to planning (CONTEXT "Claude's Discretion"); two pure-polars options, built only from primitives already proven in this codebase:

**Semantics to preserve (from `main.py:69-74`, the numpy original being diverged from):**
```python
def find_sorted_pos(values, value):
    pos = int(np.searchsorted(values, value, side="left"))
    if pos < len(values) and values[pos] == value:
        return pos          # exact match -> row position
    return None             # miss -> caller does `continue` / `return None`
```

**Option A — `with_row_index` + equality `filter`** (gives a stable positional index for D-07's window):
```python
# build ONCE after load/sort/precision-normalize:
nq_idx = nq.with_row_index("idx")                      # NOTE: with_row_index NOT yet used anywhere in repo
# per event (exact-match; empty -> skip, preserving find_sorted_pos's None):
hit = nq_idx.filter(pl.col("DateTime_UTC") == event_ts)   # event_ts at SAME unit+tz (D-05)
if hit.is_empty():
    continue
release_idx = hit.row(0, named=True)["idx"]            # int row index -> nq.slice(release_idx+1, ...) for D-07
```

**Option B — inner-join a lookup-timestamps frame against `nq[["DateTime_UTC","idx"]]`** (vectorizes all events/horizons at once; precedent: `exploration.py:160` `.join(..., how="left")`):
```python
nq_keys = nq.with_row_index("idx").select(["idx", "DateTime_UTC"])
wanted  = events.select(pl.col("datetime_utc").alias("DateTime_UTC"))   # + horizon offsets
matched = wanted.join(nq_keys, on="DateTime_UTC", how="inner")         # inner == exact-match; misses drop (== `continue`)
```

**Both options REQUIRE (D-05):** the join/equality key and `nq.DateTime_UTC` at identical time-unit and tz. Normalize with `.dt.cast_time_unit("ns")` on the nq side (and ensure the event key is also ns/UTC) **before** the lookup — verified equivalent in `01-RESEARCH.md:240-246`. Inner-join / empty-filter both reproduce the "miss → skip" behavior (D-04) without `join_asof` (which would violate D-04). Whether to keep the per-event/per-horizon python loop or vectorize via Option B is the planner's call (CONTEXT "Claude's Discretion") as long as D-04…D-07 hold.

### UTC tz + µs→ns precision normalization (D-05)
**Source:** `main.py:85-119` (full excerpt in forward_returns §1).
**Apply to:** the `load_data`/load step of **both** files. The branch-on-`schema[...].time_zone` (naive→`replace_time_zone`, aware→`convert_time_zone`) and the explicit ns coercion are the single most important guard — skipping precision-match silently drops every event (RESEARCH Pitfall 1, severity HIGH).

### polars → numpy/list boundary for matplotlib & numpy math (MIGRATE / RESEARCH Pattern 3)
**Source:** `exploration.py:116-119` (`.to_numpy()`/`.to_list()` into matplotlib); `causal_analysis.py:184-186` (the explicit single `.to_numpy()` boundary) and `causal_analysis.py:235` (`np.corrcoef(col.to_numpy(), ...)`).
**Apply to:** every chart in `forward_returns.py` and `injection.py`, and any `np.median`/`np.mean`/`np.corrcoef` call. Polars frames have no `.attrs` and matplotlib wants numpy/lists — convert **at the boundary**, not earlier.
```python
ax.barh(y_pos, df.get_column("col").to_numpy(), ...)
labels = df.get_column("name").to_list()
```

### Native parquet reads
**Source:** `main.py:85-86`, `exploration.py:205`, `causal_analysis.py:43`.
**Apply to:** both files. `pl.read_parquet(path, use_pyarrow=False)` — no pandas, no pyarrow in the read path (ENV-02). Raw inputs are **read-only/irreplaceable** — never write back.

### pandas→polars idiom swaps (apply throughout both ports)
**Source:** `01-RESEARCH.md` State-of-the-Art table + RESEARCH Pitfalls.
| pandas (current) | polars (target) | Where it appears |
|---|---|---|
| `df.empty` | `df.is_empty()` | `forward_returns.py:122`, `injection.py:46,61` |
| `df.iloc[a:b]` | `df.slice(a, n)` | `forward_returns.py:121` |
| `df.iloc[0]` / `.iloc[pos]` | `df.row(0, named=True)` / `df.row(pos, named=True)` | `injection.py:49,66`, `forward_returns.py:109,118` |
| `for _, row in df.iterrows()` | `for row in df.iter_rows(named=True)` | `forward_returns.py:103`, `injection.py:148` |
| `series.unique()` | `df.get_column(c).unique().to_list()` | `injection.py:134` |
| `df[df[c]==v]` | `df.filter(pl.col(c)==v)` | `forward_returns.py:205,243,275`, `injection.py:142` |
| `df.to_csv(p, index=False)` | `df.write_csv(p)` | `forward_returns.py:297` |
| `.fillna` (null+NaN) | `.fill_null` (null only) — add `.fill_nan`/`is_not_nan` for the `np.nan` direction cols | D-09 cols in `forward_returns.py` |

---

## No Analog Found

| Sub-pattern | Role | Data Flow | Reason |
|-------------|------|-----------|--------|
| Pure-polars **exact-match timestamp lookup** (D-01/D-02/D-04) | utility (lookup) | request-response (ts → row / None) | The only existing lookup in the repo is `main.py`'s **numpy `searchsorted`** (`main.py:69-74,127,134,147,158`), which Phase 2 **deliberately diverges from** (D-03). `with_row_index`/polars `search_sorted` appear **nowhere** in the codebase (grep-confirmed). Planner must synthesize from the two options above using only proven primitives — `.join` (`exploration.py:160,235`), `.slice` (`main.py:152`), `.row(named=True)` (`main.py:128`), `.filter(...is_between/is_in)` (`exploration.py:213`). RESEARCH (`01-RESEARCH.md:53`) explicitly scoped this polars-native searchsorted replacement to **Phase 2**. |
| Pure-polars **time-bounded window** for the 10-min range (D-06) | utility (filter) | batch / time-range | `main.py:get_candles_until_eod` (`:131-152`) is the conceptual time-window analog but is **numpy/searchsorted**. The pure-polars `.filter(is_between(...))` form is new (closest primitive precedent: `exploration.py:213` `is_in`). |

These two are not blockers — the construct is small and bounded by D-04…D-07 plus the primitives listed. They are called out so the planner knows to **synthesize** rather than copy, and to **not** "helpfully" revert to `main.py`'s numpy pattern for consistency (CONTEXT "Specific Ideas").

---

## Metadata

**Analog search scope:** repo root `*.py` (`main.py`, `exploration.py`, `causal_analysis.py` = Phase-1 polars ports / analogs; `forward_returns.py`, `injection.py` = pandas files being modified / methodology source).
**Files scanned:** 5 source files (read in full) + grep sweep for `with_row_index`, polars `search_sorted`, `.join`, `.slice`, `.row`, `.filter`, `is_in`.
**Upstream context:** `02-CONTEXT.md` (D-01…D-11), `01-RESEARCH.md` (µs→ns Pitfall 1, no-`.attrs` Pitfall 3, `group_by` order Pitfall 5, `fill_null`≠`fillna` Pitfall 6, State-of-the-Art idiom table).
**Pattern extraction date:** 2026-06-07
**Read-only:** no source files modified; only this PATTERNS.md written.
</content>
</invoke>
