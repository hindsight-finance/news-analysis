# Phase 1: Primary Pipeline on Polars - Research

**Researched:** 2026-06-07
**Domain:** pandas→polars DataFrame-engine migration of a numeric research pipeline (parquet I/O, timezone-aware timestamp lookups, scikit-learn boundary)
**Confidence:** HIGH

## Summary

This phase ports three scripts — `main.py` (the sweep engine), `exploration.py`, and `causal_analysis.py` — from pandas to polars while keeping the intermediate `data/sweep_analysis_results.parquet` data contract byte-compatible in *schema* (not in exact values — no parity required). All findings below were verified by running code against the **actually installed** polars 1.40.1 and the **real** data files, which is more authoritative for "what does this version do" than published docs.

The single most important architectural insight: **the sweep methodology kernel in `main.py` (lines 211–287) is already pure numpy** — `np.argmax`, boolean masks, array slicing, division. It is engine-agnostic. The pandas→polars port only touches the **I/O boundary** (load parquet, look up candles, extract columns to numpy, build the output DataFrame). The numpy compute kernel should be preserved **verbatim**. This bounds the risk surface: methodology integrity is protected by *not rewriting* the part that encodes the methodology.

Three concrete landmines were verified and will silently corrupt data or drift the contract if missed: (1) `nq_1m.parquet` stores timestamps in **microseconds** (`us`) while `economic_events.parquet` and the output contract use **nanoseconds** (`ns`) — mixing them breaks `searchsorted` exact-match lookups; (2) polars infers **different dtypes** than pandas when building a DataFrame from a list of dicts containing `None` (e.g. `pre_candle_volume` → `Int64` in polars vs `Float64` in the existing contract); (3) polars `DataFrame` has **no `.attrs`**, so the `nq.attrs['utc_values']` lookup-cache mechanism must be replaced by explicitly threading the arrays through the call chain.

**Primary recommendation:** Keep the numpy methodology kernel unchanged; port only the I/O boundary; construct the output parquet with an **explicit, pinned schema** (column order + dtypes) so the data contract cannot drift; and force every timestamp to `ns int64` before any `searchsorted`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Raw parquet read (`nq_1m`, `economic_events`) | Data I/O (polars native reader) | — | polars reads these directly; no pyarrow needed (ENV-02) |
| Timezone normalization (UTC, ET derivation) | DataFrame engine (polars `.dt`) | stdlib `datetime`/`zoneinfo` for scalars | column ops in polars; per-event scalar math in stdlib to stay pandas-free |
| Candle lookup by timestamp | Compute (numpy `searchsorted`) | DataFrame engine (extract column) | keep numpy searchsorted — Phase-2 owns any polars-native replacement |
| Sweep methodology (direction, target, MAE, box) | **Compute kernel (numpy)** | — | already numpy; engine-agnostic; **port verbatim** |
| Session-context feature extraction | Compute (scalar) + DataFrame engine (row lookup) | stdlib `datetime` | per-event row access + wall-clock arithmetic |
| Output contract write (`sweep_analysis_results.parquet`) | Data I/O (polars `write_parquet`) | — | explicit schema pins the contract |
| Win-rate / quartile / MAE aggregation | DataFrame engine (polars `group_by`/`agg`) | — | exploration + causal data handling |
| Quartile binning (`qcut`) | DataFrame engine (polars `qcut`) | — | display/reporting bins, not methodology-critical |
| Model training (RF / Tree / LogReg) | **ML boundary (scikit-learn + numpy)** | DataFrame engine (feature build) | MIGRATE-03: explicit `polars → numpy` at `.fit()` |
| Charting | Presentation (matplotlib) | DataFrame engine (extract series) | matplotlib consumes numpy/lists |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| polars | 1.40.1 | DataFrame engine — replaces pandas for all tabular ops and parquet I/O | Project-locked engine (STATE.md decision); native Rust parquet reader; lazy + eager APIs |
| numpy | 1.26.4 | Methodology kernel (`searchsorted`, `argmax`, masks); ML array boundary | Already the compute substrate; **unchanged** by this port |
| scikit-learn | 1.8.0 | RF / DecisionTree / LogisticRegression / StandardScaler / LabelEncoder / cross_val_score | Models receive numpy; engine swap does not touch them |
| matplotlib | 3.6.3 | All chart output; `Agg` backend | Engine-agnostic; consumes numpy/lists |

All four are already installed and pinned (verified via import). **No new packages are installed in this phase.**

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `datetime` / `zoneinfo` | Py 3.12 | Scalar wall-clock arithmetic (end-of-day, session anchor times) | Replaces per-scalar `pd.Timestamp` / `pd.Timedelta` to stay pandas-free |
| pandas | 2.1.4 | **Still installed** (removed only in Phase 4) | Must NOT be imported by the ported scripts (MIGRATE goal); present so the un-ported `forward_returns.py`/`injection.py`/tests keep running |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| numpy `searchsorted` for candle lookup | polars `Series.search_sorted` or join/filter | Over-engineering for Phase 1; the objective explicitly scopes a polars-native searchsorted replacement to **Phase 2** (`forward_returns.py`). Keep numpy here. |
| Explicit output schema | Rely on polars dict-inference | Inference drifts dtypes (see Pitfall 2) — **rejected**; pin the schema |
| stdlib datetime for scalars | `pd.Timestamp` for scalar math | `pd.Timestamp` reintroduces pandas into the engine path — avoid |

**Installation:** None required — verified present:
```bash
python3 -c "import polars, numpy, sklearn, matplotlib; print(polars.__version__)"  # 1.40.1
```

## Package Legitimacy Audit

**N/A — this phase installs no external packages.** All four runtime dependencies (polars 1.40.1, numpy 1.26.4, scikit-learn 1.8.0, matplotlib 3.6.3) are already installed and pinned in the project environment and were confirmed by direct import. pandas 2.1.4 remains installed (removed in Phase 4) but must not be imported by the ported scripts. No slopcheck run needed because no `pip install` occurs. The dependency-manifest work (ENV-01) is explicitly Phase 4.

## Architecture Patterns

### System Architecture Diagram

```
                    data/economic_events.parquet      data/nq_1m.parquet
                    (datetime_utc=ns, title, ...)      (datetime_utc=US!, OHLCV)
                              │                                 │
                              ▼                                 ▼
                    ┌───────────────────────────────────────────────────┐
                    │  load_data()  [polars native read; no pyarrow]     │
                    │  - rename datetime_utc → DateTime_UTC              │
                    │  - derive DateTime_ET (UTC→America/New_York→naive) │
                    │  - sort by DateTime_UTC                            │
                    │  - build ns int64 lookup arrays (utc, et)  ◄── replaces nq.attrs cache
                    └───────────────────────────────────────────────────┘
                              │ events rows          │ nq (polars) + lookup arrays (numpy ns)
                              ▼                       ▼
        for each event ──►  analyze_event(nq, lookups, event_time, title)
                    ┌───────────────────────────────────────────────────┐
                    │  I/O boundary (CHANGES):                           │
                    │   get_release_candle → np.searchsorted → nq.row()  │
                    │   get_candles_until_eod → slice → get_column().to_numpy()
                    │  ─────────────────────────────────────────────────│
                    │  METHODOLOGY KERNEL (UNCHANGED numpy):             │
                    │   high/low sweep · first-target · synthetic box ·  │
                    │   MAE-before-reversal · argmax timing              │
                    │  ─────────────────────────────────────────────────│
                    │  get_session_context → scalar ET lookups          │
                    └───────────────────────────────────────────────────┘
                              │ list[dict] (one per resolved event)
                              ▼
                    pl.DataFrame(results, schema=CONTRACT_SCHEMA)  ◄── pins 21 cols + dtypes
                              │
                              ▼
                    data/sweep_analysis_results.parquet  (THE CONTRACT)
                              │
                ┌─────────────┴──────────────┐
                ▼                              ▼
        exploration.py                 causal_analysis.py
        group_by/agg · qcut ·          filter · build_features ·
        win-rate charts                polars→numpy → sklearn models
                ▼                              ▼
        charts/exploration/*.png       charts/causal/*.png + event_stats.csv
```

### Component Responsibilities (port-impact)
| Component | File:lines | Port action |
|-----------|-----------|-------------|
| `ensure_utc` | main.py:24-29 | polars: `.dt.replace_time_zone("UTC")` if naive else `.dt.convert_time_zone("UTC")` |
| `timestamp_ns_utc` | main.py:32-39 | scalar → `int` ns from a tz-aware datetime; stdlib |
| `find_sorted_pos` | main.py:42-47 | **UNCHANGED** (pure numpy) |
| `add_lookup_tables` | main.py:50-54 | replace `nq.attrs[...]` with returned numpy arrays (polars has no `.attrs`) |
| `load_data` | main.py:57-77 | polars read + rename + derive ET + sort; return arrays explicitly |
| `get_release_candle` | main.py:80-88 | searchsorted (unchanged) + `nq.row(pos, named=True)` |
| `get_candles_until_eod` | main.py:91-122 | slice + stdlib datetime for EOD; returns polars DF |
| `get_candle_at_time` | main.py:125-133 | searchsorted on et array + `nq.row(pos, named=True)` |
| `get_session_context` | main.py:136-190 | scalar stdlib datetime; dict access on rows |
| `analyze_event` | main.py:193-315 | **kernel unchanged**; only column→numpy extraction changes |
| `main` (write) | main.py:333-336 | `pl.DataFrame(results, schema=...).write_parquet(...)` |
| summary prints | main.py:340-393 | port `groupby().agg()` → polars (display only) |
| `compute_win_rates` | exploration.py:23-42 | `group_by().agg()` with expressions; `.where`→`pl.when` |
| `qcut_with_fallback_labels` | exploration.py:45-52 / causal:31-38 | `Series.qcut(q, labels=..., allow_duplicates=True)` |
| `build_features` | causal_analysis.py:48-73 | build polars DF via `select`/`with_columns`; LabelEncoder on `.to_numpy()` |
| model training | causal_analysis.py:154-240 | **explicit `X.to_numpy()` / `y.to_numpy()` at `.fit()`** |

### Pattern 1: Preserve the numpy kernel, port only the boundary
**What:** Extract polars columns to numpy at the function boundary, run the existing numpy methodology unchanged, build results back into polars.
**When to use:** Every methodology-bearing function in `main.py`.
**Example:**
```python
# Source: verified against polars 1.40.1 runtime
# BEFORE (pandas): subsequent['High'].to_numpy()
# AFTER (polars):
subsequent = nq.slice(start_idx + 1, end_pos - (start_idx + 1))   # returns pl.DataFrame
if subsequent.is_empty():                                          # was: subsequent.empty
    return None
highs = subsequent.get_column("High").to_numpy()                  # float64 ndarray — identical
lows  = subsequent.get_column("Low").to_numpy()
times = subsequent.get_column("DateTime_UTC").to_numpy()          # datetime64[us] (see Pitfall 1)
# --- lines 215-287 of main.py run UNCHANGED from here ---
```

### Pattern 2: Pin the output contract with an explicit schema
**What:** Build the result DataFrame with a hard-coded ordered schema so dtypes never drift.
**When to use:** The `main()` write step (replaces `pd.DataFrame(results)` + `to_parquet`).
**Example:**
```python
# Source: schema read directly from existing data/sweep_analysis_results.parquet (polars 1.40.1)
import polars as pl
CONTRACT_SCHEMA = {
    "event_type": pl.String,
    "event_datetime": pl.Datetime("ns", "UTC"),       # ◄ would drift to us without this
    "release_time": pl.String,
    "data_high": pl.Float64,
    "data_low": pl.Float64,
    "range": pl.Float64,
    "range_pct": pl.Float64,
    "first_sweep": pl.String,
    "time_to_first_sweep": pl.Float64,
    "opposite_swept": pl.Boolean,
    "time_to_opposite_sweep": pl.Float64,
    "synthetic_box_breached": pl.Boolean,
    "first_target_hit": pl.String,
    "mae_before_reversal": pl.Float64,
    "pre_candle_range_pct": pl.Float64,
    "pre_candle_volume": pl.Float64,                   # ◄ would drift to Int64 without this
    "dist_from_midnight_open_pct": pl.Float64,
    "dist_from_6pm_open_pct": pl.Float64,
    "gap_6pm_pct": pl.Float64,
    "gap_6pm_direction": pl.String,
    "release_volume": pl.Int64,
}
df = pl.DataFrame(results, schema=CONTRACT_SCHEMA)     # results = list[dict], one per event
df.write_parquet(OUTPUT_FILE)                          # native writer; no index kwarg, no pyarrow
```
Column order above matches the dict-construction order in `analyze_event` (base dict then `result.update(session_context)`), which matches the on-disk contract.

### Pattern 3: Explicit polars→numpy at the scikit-learn boundary (MIGRATE-03)
**What:** Convert once, at `.fit()`/`cross_val_score`, keeping the column-name list for plots/importance.
**Example:**
```python
# Source: verified — StandardScaler/LabelEncoder accept polars .to_numpy() (polars 1.40.1)
features: pl.DataFrame = build_features(df)     # polars
feature_names = features.columns                # keep for plot_tree / importance labels
X = features.to_numpy()                          # ndarray — THE boundary
y = df.get_column("target").to_numpy()          # ndarray
rf.fit(X, y)
cross_val_score(model, X, y, cv=folds)
X_scaled = StandardScaler().fit_transform(X)
lr.fit(X_scaled, y)
# rf.feature_importances_ aligns positionally to feature_names
```
LabelEncoder inputs also cross the boundary explicitly: `LabelEncoder().fit_transform(df.get_column("event_type").to_numpy())`.

### Anti-Patterns to Avoid
- **Rewriting the numpy kernel "in polars":** It is already numpy and encodes the methodology. Rewriting it in polars expressions adds risk for zero benefit and violates the "protect the methodology" mandate.
- **Letting `pl.DataFrame(results)` infer dtypes:** drifts the contract (Int64/us). Always pass `schema=`.
- **Reusing `pd.Timestamp`/`pd.Timedelta` for scalar math because pandas is still installed:** reintroduces pandas into the engine path. Use stdlib `datetime`/`timedelta`.
- **Mixing `us` and `ns` integer timestamps in one `searchsorted`:** off-by-1000x; silent wrong lookups.
- **Assuming polars `group_by` preserves order:** it does not (see Pitfall 5).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Quantile binning with duplicate edges | custom percentile/bisect bucketing | `Series.qcut(q, labels=..., allow_duplicates=True)` | polars handles collapsed bins internally (verified) |
| Sorted exact-match candle lookup | manual bisect loop | `np.searchsorted` on the extracted ns array | already correct, fast, methodology-preserving |
| UTC↔ET conversion | manual offset math | `.dt.convert_time_zone` / `.dt.replace_time_zone` (columns); `zoneinfo` (scalars) | DST-correct |
| One-hot event encoding | manual dummy columns | `DataFrame.to_dummies(columns=[...])` | verified present |
| Categorical→int encoding for models | manual maps | scikit-learn `LabelEncoder` on `.to_numpy()` | preserves exact existing encoding semantics |

**Key insight:** The methodology already delegates the hard numeric parts to numpy. The port's job is to *not break* that delegation, not to reimplement it.

## Runtime State Inventory

This is a code port, not a string rename, but the canonical question still applies: *after every script is updated, what runtime state still holds old/incompatible data?*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/sweep_analysis_results.parquet` (307 KB, written by the **pandas** version) is the live contract artifact consumed by `exploration.py`/`causal_analysis.py`. | Regenerate by running ported `main.py`; verify schema equals the 21-column `CONTRACT_SCHEMA`. The raw inputs (`nq_1m.parquet`, `economic_events.parquet`) are **read-only / irreplaceable** — must not be modified. |
| Live service config | None — pure local scripts, no external services, no daemons. | None. |
| OS-registered state | None — no cron/systemd/Task Scheduler entries; scripts run via `python3 <file>`. | None — verified (no scheduler references in repo). |
| Secrets / env vars | None — CLAUDE.md confirms no env vars, no `.env`. | None. |
| Build artifacts | No `pyproject.toml`/`setup.py`/egg-info; no compiled packages. Stale outputs are only regenerated PNGs under `charts/{exploration,causal}/` and the intermediate parquet. | None blocking; chart PNGs overwrite on each run. |

**Nothing found** in Live service config, OS-registered state, and Secrets — verified by repo inspection and CLAUDE.md (no env vars, no services).

## Common Pitfalls

### Pitfall 1: Microsecond vs nanosecond timestamp units (HIGH severity)
**What goes wrong:** `nq_1m.parquet.datetime_utc` is `Datetime(us)`; `economic_events.parquet.datetime_utc` and the contract are `Datetime(ns)`. The old pandas code forced everything to ns via `.to_numpy(dtype='datetime64[ns]')` and `.value`. A naive polars `cast(pl.Int64)` on the `us` column yields **microseconds**, 1000× smaller than the `ns` event integer — `searchsorted` then never finds a match and every event is silently dropped.
**Why it happens:** polars preserves the on-disk time unit; pandas re-resolved it.
**How to avoid:** Force ns before any int cast / searchsorted:
```python
# verified equivalent (polars 1.40.1):
ts_ns = nq.select(pl.col("DateTime_UTC").dt.cast_time_unit("ns").cast(pl.Int64)).to_series().to_numpy()
# numpy route also matches exactly:
ts_ns = nq.get_column("DateTime_UTC").to_numpy().astype("datetime64[ns]").astype("int64")
```
Do the same for the event lookup key and the naive-ET array. The `times` array extracted for timing math is `datetime64[us]` — convert with `.astype('datetime64[ns]')` or compute deltas via the ns integers.
**Warning signs:** `main.py` prints "Successfully analyzed 0 events" or far fewer than the pandas run.

### Pitfall 2: Dict→DataFrame dtype inference drift (HIGH severity for contract)
**What goes wrong:** Building the output from `list[dict]` with `None` values infers different dtypes than pandas. Verified:
| Column | pandas (existing contract) | polars naive inference |
|--------|---------------------------|------------------------|
| `pre_candle_volume` | `Float64` (None→NaN upcasts int) | `Int64` |
| `event_datetime` | `Datetime(ns, UTC)` | `Datetime(us, UTC)` |
**Why it happens:** polars keeps nullable `Int64` (no float upcast) and defaults python `datetime` to `us`.
**How to avoid:** Pass the explicit `CONTRACT_SCHEMA` (Pattern 2). Functionally the consumers `fill_null(0)` these columns so Int64 would not crash, but "data contract intact" is a phase success criterion — pin it.
**Warning signs:** `pl.read_parquet("...").schema` differs from the 21-column table in this doc.

### Pitfall 3: polars `DataFrame` has no `.attrs` (HIGH severity)
**What goes wrong:** `main.py` caches `nq.attrs['utc_values']` / `['et_values']` and reads them inside `get_release_candle`, `get_candles_until_eod`, `get_candle_at_time`. Verified: `hasattr(pl.DataFrame, "attrs") == False`. Direct port crashes.
**Why it happens:** polars has no per-frame metadata dict.
**How to avoid:** Compute the two ns int64 arrays once in `load_data` and **thread them explicitly** through the call chain (e.g. a small `lookups = {"utc_values": ..., "et_values": ...}` dict, or a `NamedTuple`, passed alongside `nq`). This changes the signatures of the four lookup functions and `analyze_event` — a small, mechanical, **required** change. (Shared-utils extraction is deferred to STRUCT-01, so keep these inline per script.)
**Warning signs:** `AttributeError: 'DataFrame' object has no attribute 'attrs'`.

### Pitfall 4: `qcut` fallback is effectively dead code in polars (LOW severity, behavior change)
**What goes wrong:** pandas `pd.qcut` raises `"Bin labels must be one fewer..."` when duplicate edges collapse bins; the existing code catches that and retries without labels. Verified: polars `Series.qcut(q, labels=[...], allow_duplicates=True)` **does not raise** on collapsed bins — it returns the full label set and simply assigns only the labels that map to real bins (e.g. `['Q1','Q4']` for two-valued data), dtype `Categorical`.
**Why it happens:** polars resolves duplicate quantile breaks internally rather than erroring.
**How to avoid:** Port `qcut_with_fallback_labels` to a one-liner `series.qcut(q, labels=labels, allow_duplicates=True)`; the `except ValueError` branch becomes unreachable (keep a defensive fallback only if desired). These bins are **display/reporting only** (range/time/midnight quartiles) — not used in the methodology or model features — so exact bin edges need not match pandas. Note the result is `Categorical`, and downstream `group_by` on it will only show bins that actually occur.
**Warning signs:** none functionally; quartile labels/edges differ numerically from pandas (acceptable — no parity).

### Pitfall 5: `group_by` does not preserve order; `value_counts` returns a DataFrame (MEDIUM severity)
**What goes wrong:** pandas `groupby` sorts by key by default; polars `group_by` returns groups in hash order (verified: `['c','a','b']`). Also `Series.value_counts()` returns a 2-column **DataFrame** `(value, "count")`, not an index-keyed Series.
**Why it happens:** different defaults.
**How to avoid:**
- Add explicit `.sort(...)` where deterministic output matters (most call sites already `.sort_values(...)` afterward; preserve those). Use `group_by(..., maintain_order=True)` only where insertion order is wanted.
- Rewrite `exploration.py:184-185`:
```python
# BEFORE (pandas):
# common_times = df["release_time"].value_counts()
# common_times = common_times[common_times >= 10].index.tolist()
# AFTER (polars, verified):
vc = df["release_time"].value_counts()                  # cols: ["release_time", "count"]
common_times = vc.filter(pl.col("count") >= 10)["release_time"].to_list()
```
**Warning signs:** printed tables in a different row order (cosmetic); `KeyError`/attribute errors on `.index`.

### Pitfall 6: `fill_null` ≠ `fillna` (MEDIUM severity)
**What goes wrong:** pandas `.fillna(0)` fills both `None` and float `NaN`. polars distinguishes them: `fill_null(0)` does **not** touch `NaN` (verified: `[1.0, None, NaN, 4.0].fill_null(0)` → `[1.0, 0.0, NaN, 4.0]`).
**Why it happens:** polars treats null and NaN as separate.
**How to avoid:** The session-context missing values are python `None` → polars `null`, so `fill_null(0)` is correct for `build_features`. But guard divisions that can produce `NaN` (e.g. divide-by-zero on `Open`/`range`) — if any appear, add `.fill_nan(0)` as well. In this code the divisors (`Open`, `range_size` after a `> 0` guard) are effectively non-zero, so the risk is low but worth a check.
**Warning signs:** `NaN` leaking into model features / correlations.

### Pitfall 7: Timezone localization of constructed wall-clock times (LOW–MEDIUM severity)
**What goes wrong:** `get_candles_until_eod` builds a naive 16:00 ET timestamp and localizes ET→UTC; session context builds 08:29 / 00:00 / 18:00 / 16:59 ET anchors. pandas `tz_localize` defaults to raising on ambiguous/nonexistent (DST) times.
**Why it happens:** DST transitions create ambiguous (fall-back) and nonexistent (spring-forward) wall times at ~02:00 ET.
**How to avoid:** All constructed anchors here are at 16:00 / 16:59 / 18:00 / 00:00 / 08:29 — **none fall in the 02:00 DST gap**, so localization is safe. Port scalar localization with stdlib: `naive_et.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)`. (polars column-level `.dt.replace_time_zone` exposes `ambiguous`/`non_existent` params if ever needed.) Convert the resulting UTC instant to ns for the searchsorted side.
**Warning signs:** `ZoneInfo`/`pytz` ambiguity exceptions (would only appear if anchor times change).

## Code Examples

### Port `ensure_utc` (column-level tz normalization)
```python
# Source: verified pattern, polars 1.40.1
def ensure_utc(col: str) -> pl.Expr:
    # if the column is tz-naive -> stamp UTC; if tz-aware -> convert to UTC
    # (choose per-column based on dtype.time_zone; events are already ns/UTC, nq is us/UTC)
    return pl.col(col).dt.convert_time_zone("UTC")   # for already-tz-aware inputs
# For a possibly-naive column:
#   pl.col(col).dt.replace_time_zone("UTC")          # naive -> UTC (no shift)
```

### Derive naive ET from UTC (replaces main.py:68)
```python
# Source: verified — yields Datetime(us, tz=None); cast to ns where used as int key
nq = nq.with_columns(
    pl.col("DateTime_UTC")
      .dt.convert_time_zone("America/New_York")
      .dt.replace_time_zone(None)
      .alias("DateTime_ET")
)
```

### Build the two ns lookup arrays (replaces nq.attrs)
```python
# Source: verified — np.searchsorted exact-match confirmed on 5.3M-row real array
utc_values = nq.get_column("DateTime_UTC").to_numpy().astype("datetime64[ns]").astype("int64")
et_values  = nq.get_column("DateTime_ET").to_numpy().astype("datetime64[ns]").astype("int64")
# find_sorted_pos(...) stays byte-for-byte identical (pure numpy)
```

### Iterate events (replaces main.py:325 `.iterrows()`)
```python
# Source: verified — iter_rows(named=True) yields dicts
for event in events.iter_rows(named=True):
    result = analyze_event(nq, lookups, event["datetime_utc"], event["title"])
    if result is not None:
        results.append(result)
```

### Port `compute_win_rates` group aggregation (exploration.py:23-42)
```python
# Source: verified polars group_by/agg + when/then for the pandas .where()
def compute_win_rates(df: pl.DataFrame, group_cols: list[str], min_count: int = 0) -> pl.DataFrame:
    g = (
        df.group_by(group_cols)                      # nulls kept by default (== dropna=False)
          .agg(
              pl.len().alias("total"),
              (pl.col("first_target_hit") == "box").sum().alias("momentum_wins"),
              (pl.col("first_target_hit") == "opposite").sum().alias("reversal_wins"),
          )
          .with_columns((pl.col("momentum_wins") + pl.col("reversal_wins")).alias("resolved"))
          .filter(pl.col("total") >= min_count)
          .with_columns(
              pl.when(pl.col("resolved") > 0)
                .then(pl.col("momentum_wins") / pl.col("resolved") * 100)
                .otherwise(None).alias("momentum_rate"),
              pl.when(pl.col("resolved") > 0)
                .then(pl.col("reversal_wins") / pl.col("resolved") * 100)
                .otherwise(None).alias("reversal_rate"),
          )
    )
    return g
```

### Port `build_features` gap-direction map (causal_analysis.py:60-61)
```python
# Source: verified replace_strict with default + return_dtype
features = features.with_columns(
    pl.col("gap_6pm_direction")
      .replace_strict({"up": 1, "down": 0, "flat": -1}, default=-1, return_dtype=pl.Int64)
      .alias("gap_direction_encoded")
)
# numeric NA fills: pl.col("pre_candle_range_pct").fill_null(0), etc.
```

### CSV / clip / one-hot ports
```python
df.write_csv(path)                                   # was: to_csv(path, index=False)
pl.col("mae_before_reversal").clip(upper_bound=10)   # was: .clip(upper=10)
df.to_dummies(columns=["event_type"])                # was: pd.get_dummies(df["event_type"], prefix="event")
                                                     #   note: names "event_type_X" vs pandas "event_X" (readable-tree only)
df.filter(pl.col("first_target_hit").is_not_null())  # was: df[df["first_target_hit"].notna()]
```

## State of the Art

| Old Approach (pandas) | Current Approach (polars 1.40.1) | Impact |
|--------------|------------------|--------|
| `pd.read_parquet` (pyarrow engine) | `pl.read_parquet` (native Rust reader, `use_pyarrow=False` default) | pyarrow not required in read path (ENV-02) |
| `df.attrs['k'] = v` metadata cache | no `.attrs` — thread arrays explicitly | Pitfall 3 |
| `groupby(...).agg(named=lambda)` | `group_by(...).agg(<expr>)` | lambdas → expressions (faster, vectorized) |
| `pd.qcut(..., duplicates="drop")` + ValueError fallback | `Series.qcut(..., allow_duplicates=True)` | fallback unreachable; returns Categorical |
| `Series.value_counts()` → indexed Series | → 2-col DataFrame `(value, count)` | `.index`/`>=` idioms must change |
| `.fillna(0)` (null+NaN) | `.fill_null(0)` (null only) | add `.fill_nan` if NaN possible |
| `.iterrows()` | `.iter_rows(named=True)` | dict rows |
| `df.iloc[a:b]` / `.empty` | `df.slice(a, n)` / `.is_empty()` | slicing + emptiness |

**Deprecated/outdated for this codebase:**
- Per-scalar `pd.Timestamp`/`pd.Timedelta` inside the engine path: replace with stdlib `datetime`/`timedelta` to keep pandas out of the ported scripts (MIGRATE goal), even though pandas stays installed until Phase 4.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `times` array timing math (`time_to_first_sweep`, `time_to_opposite_sweep`) can be computed pandas-free via numpy `datetime64[ns]` / epoch-ns ints without changing results | Pitfall 1 / kernel | LOW — arithmetic is unit-preserving; verify minute deltas match a sample run |
| A2 | The `to_dummies` column-name change (`event_type_X` vs `event_X`) only affects the printed "readable" decision-tree feature names, not any methodology or saved CSV schema | Code Examples | LOW — readable tree is print-only (causal_analysis.py:232-240) |
| A3 | `pre_candle_volume` as `Float64` vs `Int64` does not affect consumer correctness (both `fill_null(0)` then feed models), so pinning to the contract `Float64` is purely for schema fidelity | Pitfall 2 | LOW — consumers tolerate either; contract fidelity is the only driver |

**No `[ASSUMED]` package or version claims** — every library/version and API behavior in this document was verified by executing code against the installed environment and reading the real parquet schemas.

## Open Questions (RESOLVED)

1. **Existing pytest suite goes red during Phase 1.**  _RESOLVED: see 01-01-PLAN.md (smoke harness)._
   - What we know: `tests/test_main_data_loading.py` and `tests/test_analysis_scripts.py` import the Phase-1 scripts and assert **pandas** semantics (`.loc`, `.iloc`, `nq.attrs["utc_values"]`, `pd.Timestamp(...).value`, `Series.isna()`). After the port these assertions break. Porting the suite is **TEST-01 = Phase 3** (explicitly out of scope here).
   - What's unclear: whether the planner wants the suite left red (expected by roadmap sequencing) or wants a thin Phase-1 smoke check added.
   - Recommendation: Do **not** use the existing pytest suite as the Phase-1 success signal. Validate Phase 1 by **integration smoke runs** (see Validation Architecture). Accept the unit suite staying red until Phase 3; note it in the plan so a red `pytest` is not mistaken for a regression.

2. **`load_data` signature change ripples to callers.**  _RESOLVED: see 01-02-PLAN.md Task 1 (3-tuple + lookups dict)._
   - What we know: removing `nq.attrs` forces threading `lookups` through `analyze_event` and the three lookup helpers.
   - What's unclear: exact shape (extra positional arg vs `NamedTuple` vs returning a 3-tuple from `load_data`).
   - Recommendation: Return `(events, nq, lookups)` from `load_data` and pass `lookups` explicitly. Keep it inline per `main.py` (shared-utils extraction is deferred STRUCT-01).

3. **`forward_returns.py` / `injection.py` still import pandas after Phase 1.**  _RESOLVED: no action required (Phase 2 scope)._
   - What we know: They are Phase 2; pandas stays installed.
   - Impact on Phase 1: none, as long as the three ported scripts contain **no `import pandas`** and write the contract polars-side.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all | ✓ | 3.12.3 | — |
| polars | engine (read/write/agg) | ✓ | 1.40.1 | — |
| numpy | methodology kernel + ML boundary | ✓ | 1.26.4 | — |
| scikit-learn | causal models | ✓ | 1.8.0 | — |
| matplotlib | charts (Agg) | ✓ | 3.6.3 | — |
| pyarrow | **not required** for polars read/write path | ✓ (present) | 23.0.1 | native reader (no fallback needed) |
| pandas | must stay installed (Phase 4 removes) | ✓ | 2.1.4 | — (must not be imported by ported scripts) |
| `data/nq_1m.parquet` | `main.py` raw input | ✓ | 57 MB, `datetime_utc` = `Datetime(us, UTC)` | none — **irreplaceable, read-only** |
| `data/economic_events.parquet` | `main.py` raw input | ✓ | `datetime_utc` = `Datetime(ns, UTC)`, only `datetime_utc`+`title` used | none — **irreplaceable, read-only** |
| `data/sweep_analysis_results.parquet` | contract (regenerated) | ✓ | 21 cols (schema in this doc) | regenerated by ported `main.py` |

**Missing dependencies with no fallback:** none — full toolchain present.
**Missing dependencies with fallback:** none. **ENV-02 answer:** polars' native Rust parquet reader reads both raw inputs directly (verified with `use_pyarrow=False`); the only dependency to pin for reads/writes is **`polars==1.40.1`** — pyarrow is **not** in the polars read/write path.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (`pytest.ini`/`pyproject.toml`/`setup.cfg` absent) — run from project root |
| Quick run command | `python3 -m pytest tests -q` |
| Full suite command | `python3 -m pytest tests -q` |

**Critical caveat:** the existing pytest suite is **pandas-based** and asserts pandas-only semantics on the very functions being ported (`tests/test_main_data_loading.py`, `tests/test_analysis_scripts.py`). It **will fail under the Phase-1 port by design** — porting it is TEST-01 (Phase 3). Therefore the Phase-1 validation signal is **integration smoke**, not the unit suite.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MIGRATE-01 | `main.py` runs on polars, writes the 21-col contract, methodology intact | integration smoke + schema assert | `python3 main.py && python3 -c "import polars as pl; s=pl.read_parquet('data/sweep_analysis_results.parquet').schema; assert len(s)==21; assert str(s['event_datetime'])=='Datetime(time_unit=\'ns\', time_zone=\'UTC\')'; assert str(s['release_volume'])=='Int64'; print('contract OK', pl.read_parquet('data/sweep_analysis_results.parquet').height,'rows')"` | ❌ Wave 0 (smoke harness) |
| ENV-02 | polars reads raw inputs with no pandas in read path | smoke | `python3 -c "import polars as pl; pl.read_parquet('data/nq_1m.parquet', use_pyarrow=False); pl.read_parquet('data/economic_events.parquet', use_pyarrow=False); print('native read OK')"` + `grep -L "import pandas" main.py` | ✅ (one-liner) |
| MIGRATE-02 | `exploration.py` runs on polars, writes charts + summary CSV | integration smoke | `python3 exploration.py && test -f charts/exploration/summary_by_event.csv && ls charts/exploration/*.png` | ❌ Wave 0 |
| MIGRATE-03 | `causal_analysis.py` runs on polars, models trained via polars→numpy, writes CSV + charts | integration smoke | `python3 causal_analysis.py && test -f charts/causal/event_stats.csv && ls charts/causal/*.png` | ❌ Wave 0 |
| (all) | no pandas import in the three ported scripts | static check | `! grep -nE "^[[:space:]]*import pandas|^[[:space:]]*from pandas" main.py exploration.py causal_analysis.py` | ✅ (grep) |

### Sampling Rate
- **Per task commit:** the relevant one-liner above for the script touched (e.g. `python3 main.py` + schema assert).
- **Per wave merge:** full pipeline `python3 main.py && python3 exploration.py && python3 causal_analysis.py` runs clean + the no-pandas grep across all three.
- **Phase gate:** all three scripts run end-to-end on polars; contract schema asserts pass; `grep` finds zero `import pandas` in the three files. (The pandas unit suite is **expected red** until Phase 3 — do not gate on it.)

### Wave 0 Gaps
- [ ] A minimal **integration smoke harness** (shell or a tiny `pytest` marked separate from the pandas suite) that runs the three scripts against the real `data/` and asserts: contract schema == 21-col `CONTRACT_SCHEMA`, non-zero row count, expected chart/CSV files exist. This is the Phase-1 signal because the existing unit suite is pandas-bound and Phase-3-owned.
- [ ] No framework install needed (pytest present); no `conftest.py` exists and none is required for smoke.
- [ ] Note for the plan: do **not** attempt to port `tests/` here (TEST-01 = Phase 3).

## Sources

### Primary (HIGH confidence)
- **Runtime introspection of installed polars 1.40.1** (most authoritative for "what this version does"): verified `read_parquet(use_pyarrow=False)`, `Series.qcut(quantiles, *, labels, left_closed, allow_duplicates, include_breaks)`, `Series.search_sorted`, `DataFrame.iter_rows(named=)`, `DataFrame.row(named=)`, `.slice`/`.is_empty`, `.to_dummies`, `replace_strict`, `pl.corr`, `Expr.clip(lower_bound, upper_bound)`, absence of `DataFrame.attrs`, dict→DataFrame dtype inference, `fill_null` vs `fill_nan`, `group_by` ordering, `value_counts` shape, tz `convert_time_zone`/`replace_time_zone`/`cast_time_unit`, matplotlib accepting polars Series.
- **Direct schema reads** of `data/economic_events.parquet`, `data/nq_1m.parquet`, `data/sweep_analysis_results.parquet` (the contract) via `pl.scan_parquet(...).collect_schema()`.
- **Source files** `main.py`, `exploration.py`, `causal_analysis.py`, `tests/test_main_data_loading.py`, `tests/test_analysis_scripts.py` (read fully).
- **Project docs** `./CLAUDE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`.

### Secondary (MEDIUM confidence)
- None required — runtime introspection superseded the need for external docs on this version.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed by import; no new installs.
- Architecture (kernel-preserving port + explicit-schema contract): HIGH — schema read from disk; kernel is demonstrably numpy.
- Pitfalls (us/ns, dtype drift, no `.attrs`, qcut, group_by order, fill_null): HIGH — each reproduced by executing code against installed polars 1.40.1 and the real data.
- Validation (smoke-not-unit): HIGH — confirmed by reading the pandas-bound test files.

**Research date:** 2026-06-07
**Valid until:** 2026-07-07 (stable; polars pinned at 1.40.1, no fast-moving external deps). Re-verify only if polars is upgraded.
