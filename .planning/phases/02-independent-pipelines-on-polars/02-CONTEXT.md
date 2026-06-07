# Phase 2: Independent Pipelines on Polars - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Port the two **independent raw-data pipelines** — `forward_returns.py` and `injection.py` — from pandas to polars, including a pandas-free replacement for the `np.searchsorted` timestamp lookup (MIGRATE-04, MIGRATE-05).

Both scripts re-read the raw Parquet inputs directly and neither touches the `sweep_analysis_results.parquet` contract, so they are decoupled from Phase 1. In scope: the DataFrame-engine port of these two files only. Out of scope: the test suite (Phase 3), pandas removal + manifest pinning (Phase 4), and any STRUCT cleanup (shared-utils extraction, CWD-independent paths, package layout) which stays deferred.

</domain>

<decisions>
## Implementation Decisions

### Timestamp Lookup Strategy
- **D-01:** `forward_returns.py` replaces `np.searchsorted` / `find_sorted_pos` with a **pure-polars lookup** — no numpy in the lookup path, no pandas. (User chose this over mirroring `main.py`'s numpy pattern.)
- **D-02:** `injection.py` is **upgraded** from its slow linear boolean-mask scans (the documented anti-pattern) to the **same pure-polars fast lookup** as `forward_returns.py`.
- **D-03:** Both Phase-2 scripts use the **same** pure-polars lookup mechanism (internally consistent). `main.py` **keeps** its Phase-1 numpy-searchsorted-via-`lookups`-dict pattern — re-porting it is rework and **out of scope**. Accepted divergence: `main.py` is the lone numpy-searchsorted holdout.

### Methodology-Integrity Constraints (the lookups MUST preserve exact semantics)
- **D-04:** Release/future candle lookup MUST be **exact-match** (skip the event/horizon when the exact minute is absent), exactly as today's `find_sorted_pos` returns `None` → `continue`. Do **NOT** use `join_asof` / nearest-match — snapping to a neighbor candle would silently corrupt the methodology.
- **D-05:** Precision **and** timezone must match on both sides of any polars timestamp equality. The Phase-1 µs→ns landmine reappears here in **equality-join form**: if the event datetime is µs-precision and `nq` is ns (or tz differs), every `==` fails and **all events silently drop**. Normalize both to UTC at the same precision before comparing — mirror `main.py`'s `load_data()` normalization.
- **D-06:** `injection.py`'s 10-minute range stays **time-bounded** (`event_time` .. `event_time + 9min`, inclusive), **NOT** a positional `+9`-row slice. A positional slice changes behavior across missing minutes/gaps. The fast lookup may locate the release row by index, but the 10-min window must remain a time-range filter.
- **D-07:** `forward_returns.py`'s window aggregation (today `nq.iloc[release_pos+1 : future_pos+1]` → max High / min Low) is a **positional** window between the matched release and future rows. Preserve `[release_idx+1, future_idx]` positional-window semantics via the row index.

### Summary Aggregations (`forward_returns.py`)
- **D-08:** Port `summarize_returns` / `summarize_path_profiles` using `exploration.py`'s established polars `group_by/agg` pattern: `win_rate` / `continuation_rate` as `(pl.col(...) > 0).mean() * 100`; quantiles via `pl.col(...).quantile(0.25 / 0.75)`. Printed-table row order is cosmetic; values are explicit-agg, not order-dependent.
- **D-09:** Preserve the `.notna()` filtering on direction-normalized columns — flat-direction rows yield NaN and are excluded from the normalized/path summaries. Keep that exclusion in the polars port.

### injection.py Conventions
- **D-10:** Add `matplotlib.use("Agg")` **before** importing `pyplot` (headless-safety; matches every other script).
- **D-11:** Do **NOT** add `run()`/argparse or restructure the entry point — that's STRUCT-03, deferred to a Future milestone. Keep `injection.py`'s `main()` entry shape. Cosmetic touch-ups (double quotes, `from __future__ import annotations`) are not required — keep the port focused.

### Claude's Discretion
- The **exact pure-polars construction** is left to research/planning — `with_row_index` + filter, an inner-join of a lookup-timestamps frame against `nq[[DateTime_UTC, idx]]`, a hybrid, and whether to vectorize the per-event/per-horizon loop — **as long as it preserves D-04…D-07**. The user chose "pure-polars" as the strategy and did not constrain the specific construct.
- `forward_returns.py`'s pure-math helpers (`candle_direction`, `direction_normalized_return`, `direction_normalized_profile`) have no pandas dependency — carry them over essentially unchanged.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external ADRs/specs exist — the canonical references are the **Phase-1 code precedents** and the planning docs.

### Lookup pattern & migration pitfalls (code precedent)
- `main.py` — Phase-1 polars port. Read `load_data()` for tz/precision normalization and the µs→ns reconcile pitfall, and the `lookups`-dict + `find_sorted_pos` numpy pattern **that Phase 2 deliberately diverges from** (D-03). Also the `CONTRACT_SCHEMA` discipline for output dtype stability.
- `causal_analysis.py` — Phase-1 explicit `polars → numpy` boundary; reference for any numpy hand-off (e.g. matplotlib inputs).

### Summary/aggregation + matplotlib boundary (code precedent to follow)
- `exploration.py` — Phase-1 `group_by/agg` + `pl.when/then` summary pattern and the `.to_numpy()` / `.to_list()` matplotlib boundary. This is the direct template for D-08.

### Files being ported (methodology source of truth)
- `forward_returns.py` — current pandas implementation; the methodology to preserve.
- `injection.py` — current pandas implementation; the methodology to preserve.

### Planning docs
- `.planning/ROADMAP.md` (Phase 2 section) — goal + the 3 success criteria.
- `.planning/REQUIREMENTS.md` — MIGRATE-04, MIGRATE-05.
- `.planning/codebase/CONCERNS.md` and `.planning/codebase/CONVENTIONS.md` — document the `injection.py` linear-scan anti-pattern and the `matplotlib.use("Agg")` convention.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main.py:load_data()` UTC tz/precision normalization — reuse the same approach so pure-polars equality lookups match (guards D-05).
- `exploration.py` summary code — direct template for the `forward_returns.py` aggregation port (D-08).
- `forward_returns.py` pure-math helpers (`candle_direction`, `direction_normalized_return`, `direction_normalized_profile`) — pandas-free; carry over unchanged.

### Established Patterns
- Native polars reads: `pl.read_parquet(..., use_pyarrow=False)`.
- Thread state explicitly (polars frames have no `.attrs`); feed matplotlib via `.to_numpy()` / `.to_list()` at the boundary.
- Pin output dtypes where drift matters (CONTRACT_SCHEMA discipline) — relevant for `forward_returns_by_event.csv` if dtype stability is wanted.

### Integration Points
- Both scripts read `data/economic_events.parquet` + `data/nq_1m.parquet` directly; neither reads/writes `sweep_analysis_results.parquet` (fully decoupled from Phase 1).
- `forward_returns.py` writes `charts/forward_returns/` (CSV + 4 PNGs per horizon); `injection.py` writes `charts/` (one PNG per event type).

</code_context>

<specifics>
## Specific Ideas

- The user explicitly preferred a **true pure-polars lookup** over reusing `main.py`'s numpy `searchsorted`, knowingly accepting that `main.py` becomes the lone numpy holdout. Downstream agents should not "helpfully" revert `forward_returns.py`/`injection.py` to the numpy pattern for consistency with `main.py`.

</specifics>

<deferred>
## Deferred Ideas

- **Re-port `main.py`'s lookup to pure-polars** (full codebase lookup-pattern uniformity) — declined as Phase-1 rework. Revisit only if a later cleanup milestone wants total uniformity.
- **`injection.py` `run()`/argparse entry point + full convention alignment** — STRUCT-03, deferred to post-migration.
- **VALID-02 (report count of silently-skipped events)** — remains deferred; keep the silent skip/`None` behavior in both ports.

</deferred>

---

*Phase: 2-Independent Pipelines on Polars*
*Context gathered: 2026-06-07*
