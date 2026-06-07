# Requirements: News Analysis — v1.1 Core Validation & Hardening

**Defined:** 2026-06-07
**Core Value:** The post-news-release sweep methodology is the asset; everything serves keeping that research correct and easy to extend.

> **Execution note:** This is a lean hardening milestone. Every requirement is executed as a **direct GSD fix** (atomic commit) — no per-phase discuss/plan/execute ceremony. The milestone artifacts (PROJECT.md / REQUIREMENTS.md / ROADMAP.md / STATE.md) are still maintained.
>
> **Emergent-fix allowance:** Issues discovered while doing the work below are in scope to fix on the spot, even without a pre-assigned REQ-ID. Anything larger gets captured as a todo rather than expanding this milestone.

## v1 Requirements

Requirements for v1.1. Each maps to a roadmap phase.

### Testing — lock in the core methodology

- [x] **TEST-01**: The sweep-detection core (`analyze_event` in `main.py`) is covered by direct tests that assert high/low sweep identification and reversal-vs-momentum (momentum-box) resolution on controlled fixtures — not just the loaders around it.
- [x] **TEST-02**: `main.py` session-context / gap features (`get_session_context`, the prior-close `gap_pct` path, release-candle extraction) are covered by direct tests on known inputs.
- [x] **TEST-03**: `injection.py`'s currently-untested functions (`build_release_index`, `get_release_candle_data`, `get_10min_range`, `calculate_percentage_range`) are covered by direct tests.

### Validity — triage and fix the known bugs

- [x] **VALID-01**: The hardcoded `16:59` ET prior-close assumption (`main.py:208`) is fixed so the prior-session close is resolved correctly rather than via a magic minute that silently misses on short/holiday sessions.
- [x] **VALID-02**: Events dropped because a release or required future candle is missing are **counted and reported** (e.g. a summary line) instead of being silently skipped via `return None` / `continue`, so analysis runs are honest about coverage.
- [x] **VALID-03**: Confirm the legacy `loc`/`iloc` mix in `get_candles_until_eod` is already resolved by the polars migration and record the closure (no `.loc`/`.iloc` remain repo-wide; a regression test already exists).
  - **Closure (2026-06-07):** Verified `grep -rn '\.loc\[|\.iloc\['` is empty repo-wide; `get_candles_until_eod` was rewritten to pure-polars positional slicing during v1.0, and `tests/test_main_data_loading.py::test_get_candles_until_eod_uses_lookup_without_timezone_compare_error` guards it. No code change needed — bug was eliminated by the migration.

### Hygiene & quality

- [x] **HYG-01**: The 4 stale root-level PNGs (`decision_tree.png`, `event_edge.png`, `event_edge_chart.png`, `feature_importance.png`) are removed and a chart-output tracking policy is set (charts belong under `charts/`, generated outputs gitignored).
- [x] **HYG-02**: `README.md` is brought current for the polars era (no stale pandas/pyarrow references; accurate run instructions and script inventory).
- [x] **QUAL-01**: The global `warnings.filterwarnings("ignore")` in `causal_analysis.py:25` is replaced with narrowly-scoped suppression (only the specific sklearn warning, only around the call that emits it).

## Future Requirements

Deferred beyond v1.1. Tracked, not in this roadmap.

### Structure

- **STRUCT-01**: Extract shared utilities into one module (kill the `ensure_utc` / `find_sorted_pos` / `qcut_with_fallback_labels` triplication)
- **STRUCT-02**: CWD-independent data and output paths across all scripts; CWD-independent test suite
- **STRUCT-03**: Clean package / project structure with a consistent entry-point pattern

### Research

- **RSRCH-01**: Validation / backtest harness and statistical-significance testing for the sweep methodology
- **RSRCH-02**: New research hypotheses or additional instruments

## Out of Scope

Explicitly excluded for v1.1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Shared-utils extraction / package restructure (STRUCT-*) | Structural refactor; keep v1.1 focused on test coverage + correctness, not moving code around |
| CWD-independent paths / test suite | Same — structural, deferred to a structure milestone |
| New research, backtest harness, significance testing | This milestone hardens the foundation; research extension comes after |
| Output / baseline parity vs old pandas numbers | Locked out since v1.0 — the idea matters, not reproducing exact historical numbers |
| Deleting or modifying raw data (`nq_1m.parquet`, `economic_events.parquet`) | Irreplaceable, gitignored, no fetcher exists |
| Data-fetching / ingestion pipeline | Candidate for a later reproducibility milestone |
| Rewrite in another language | Stay on Python 3.12 + polars |

## Traceability

Single phase — all v1.1 requirements map to it. Confirmed/updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | Phase 5 | Complete |
| TEST-02 | Phase 5 | Complete |
| TEST-03 | Phase 5 | Complete |
| VALID-01 | Phase 5 | Complete |
| VALID-02 | Phase 5 | Complete |
| VALID-03 | Phase 5 | Complete |
| HYG-01 | Phase 5 | Complete |
| HYG-02 | Phase 5 | Complete |
| QUAL-01 | Phase 5 | Complete |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0 ✓
- Complete: 9 / 9 ✓ (Phase 5 executed as direct GSD fixes)

---
*Requirements defined: 2026-06-07*
*Last updated: 2026-06-07 — Phase 5 complete; all 9 requirements delivered as direct fixes. Suite 29/29 green; main.py smoke-run preserved the core methodology numbers.*
