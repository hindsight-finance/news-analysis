---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Core Validation & Hardening
status: Phase 5 complete (awaiting milestone close)
last_updated: "2026-06-07T06:30:00.000Z"
last_activity: 2026-06-07 — Phase 5 executed as direct GSD fixes (9/9 requirements, 29/29 tests green)
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 0
  completed_plans: 0
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-07)

**Core value:** The post-news-release sweep methodology is the asset; everything serves keeping that research correct and easy to extend.
**Current focus:** v1.1 Phase 5 — Core Validation & Hardening (direct-execution; lock the sweep kernel under direct tests, fix the two validity bugs, clear hygiene debt)

## Current Position

Phase: Phase 5 — Core Validation & Hardening (complete, direct-execution)
Plan: Direct-execution (no per-phase plans) — 6 atomic fix commits
Status: All 9 requirements delivered. pytest 29/29 green (16 new tests). main.py smoke-run preserved the core methodology numbers (80.6% / 52.2% / 45.7%). Awaiting milestone close.
Last activity: 2026-06-07 — Phase 5 executed as direct GSD fixes (TEST-01/02/03, VALID-01/02/03, HYG-01/02, QUAL-01)

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 2 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 9min | 1 tasks | 1 files |
| Phase 01 P02 | 13min | 2 tasks | 1 files |
| Phase 01 P03 | 4min | 2 tasks | 1 files |
| Phase 01 P04 | 5min | 2 tasks | 1 files |
| Phase 02 P01 | 14min | 2 tasks | 1 files |
| Phase 02 P02 | 6min | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pivot the project to polars, dropping pandas — polars is the chosen DataFrame engine going forward
- Migrate-first — port the DataFrame layer before adding a unit-test net; methodology-integrity risk of porting untested core logic accepted
- No baseline / output parity for the migration — the idea matters, not reproducing exact pandas numbers; numeric drift from the engine swap is acceptable
- Defer shared-utils extraction, CWD-independent paths, package restructure, and validity-bug triage to Future (post-migration)
- Scope v1.1 to core-test coverage + the two real validity fixes + hygiene (no new research); harden the sweep kernel ported untested in v1.0
- Execute v1.1 as direct GSD fixes (no per-phase discuss/plan/execute) — small, mechanical, well-understood tasks; matches the v1.0 precedent of running mechanical phases directly
- `loc`/`iloc` validity bug treated as resolved by the polars migration (VALID-03 is confirm-and-close)
- [Phase 05]: v1.1 hardening delivered as 6 direct fixes — `analyze_event`/session-context/`injection.py` now directly tested (16 new tests, 29/29 suite); prior-close resolved via `get_last_candle_before` (no 16:59 hardcode, VALID-01); `analyze_event` takes an optional `drops` Counter and `main()` prints coverage (VALID-02); sklearn warnings scoped to ConvergenceWarning/UndefinedMetricWarning (QUAL-01); stale root PNGs removed + `/*.png` gitignored (HYG-01). `main.py` smoke-run preserved the core methodology numbers (gap features are context-only)
- [Phase ?]: Phase-1 validation signal is integration smoke (smoke/phase1_smoke.py), not the pandas unit suite (expected red until Phase 3 / TEST-01)
- [Phase ?]: main.py ported to polars: preserve numpy methodology kernel verbatim, port only the I/O boundary (load/lookup/extract/write)
- [Phase ?]: Pinned output via module-level CONTRACT_SCHEMA (21 cols, ns/UTC event_datetime, Int64 release_volume, Float64 pre_candle_volume) to stop dict-inference dtype drift
- [Phase ?]: Replaced nq.attrs lookup cache with an explicitly-threaded lookups dict of ns-int64 arrays (polars has no per-frame metadata)
- [Phase ?]: exploration.py polars port: win-rate/summary via group_by/agg + pl.when/then; qcut(allow_duplicates=True) Categorical bins (display-only); matplotlib fed via .to_numpy()/.to_list() at the boundary; printed-table order is cosmetic (hash group order), win-rate values are explicit-agg not order-dependent
- [Phase 01]: causal_analysis.py polars port (MIGRATE-03): single explicit polars->numpy boundary at .fit()/cross_val_score; feature_names captured before to_numpy() for importance/coef/tree labels; cv_folds computed once on the polars y Series before the boundary and passed into print_cv_score to avoid value_counts-on-numpy AttributeError; all three Phase-1 scripts now pandas-free
- [Phase ?]: [Phase 02]: forward_returns.py polars port (MIGRATE-04): pure-polars exact-match lookup via build_timestamp_index (with_row_index + inner-join of all event+horizon timestamps collapsed to a {ts: idx} dict) replaces np.searchsorted; us->ns cast_time_unit on both join keys before equality (D-05 guard, 23935 rows); positional window via nq.slice (D-07); is_not_nan (not is_not_null) for flat-direction NaN exclusion (D-09); build_timestamp_index is the shared lookup injection.py (02-02) reuses (D-02/D-03)

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Raw data (`data/nq_1m.parquet`, `data/economic_events.parquet`) is irreplaceable and gitignored — no phase may delete or modify it (standing constraint)

_v1.0 migration-sequencing blockers (pandas-until-Phase-4, main.py-before-consumers, mid-migration contract integrity) are all resolved — migration complete._

_Carried-forward tech debt: duplicated utils (`ensure_utc`, `find_sorted_pos`, `qcut_with_fallback_labels`) were NOT extracted this milestone — each script holds its own inline copy (STRUCT-01, deferred to next milestone)._

## Deferred Items

Items acknowledged and carried forward / out of this milestone's scope:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Structure | STRUCT-01/02/03: shared utils, CWD-independent paths, package layout | Deferred to post-v1.1 | 2026-06-07 |
| Research | RSRCH-01/02: validation/backtest harness, significance testing, new hypotheses | Deferred to a later research milestone | 2026-06-07 |
| Reproducibility | Data-fetching / ingestion pipeline | Deferred to v2 | 2026-06-07 |

## Session Continuity

Last session: 2026-06-07
Stopped at: Phase 5 complete — all 9 requirements delivered as direct GSD fixes (6 commits); suite 29/29 green
Resume file: None

## Operator Next Steps

- Phase 5 is complete (9/9 requirements, 29/29 tests green). Run `/gsd-complete-milestone` to archive v1.1 — or `/gsd-verify-work` for conversational UAT first.
- Optional follow-up (not done this milestone): regenerate the downstream charts/CSVs (`exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`) against the freshly rebuilt `sweep_analysis_results.parquet`.
