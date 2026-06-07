---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Polars Migration
status: executing
last_updated: "2026-06-07T02:25:49.849Z"
last_activity: 2026-06-07
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 4
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-07)

**Core value:** The post-news-release sweep methodology is the asset; everything serves keeping that research correct and easy to extend.
**Current focus:** Phase 01 — primary-pipeline-on-polars

## Current Position

Phase: 01 (primary-pipeline-on-polars) — EXECUTING
Plan: 3 of 4
Status: Ready to execute
Last activity: 2026-06-07

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 9min | 1 tasks | 1 files |
| Phase 01 P02 | 13min | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pivot the project to polars, dropping pandas — polars is the chosen DataFrame engine going forward
- Migrate-first — port the DataFrame layer before adding a unit-test net; methodology-integrity risk of porting untested core logic accepted
- No baseline / output parity for the migration — the idea matters, not reproducing exact pandas numbers; numeric drift from the engine swap is acceptable
- Defer shared-utils extraction, CWD-independent paths, package restructure, and validity-bug triage to Future (post-migration)
- [Phase ?]: Phase-1 validation signal is integration smoke (smoke/phase1_smoke.py), not the pandas unit suite (expected red until Phase 3 / TEST-01)
- [Phase ?]: main.py ported to polars: preserve numpy methodology kernel verbatim, port only the I/O boundary (load/lookup/extract/write)
- [Phase ?]: Pinned output via module-level CONTRACT_SCHEMA (21 cols, ns/UTC event_datetime, Int64 release_volume, Float64 pre_candle_volume) to stop dict-inference dtype drift
- [Phase ?]: Replaced nq.attrs lookup cache with an explicitly-threaded lookups dict of ns-int64 arrays (polars has no per-frame metadata)

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Raw data (`data/nq_1m.parquet`, `data/economic_events.parquet`) is irreplaceable and gitignored — no phase may delete or modify it
- pandas must stay installed until Phase 4 — ENV-01 (drop pandas) and MIGRATE-06 (no `import pandas`) only land once every script and test is ported, or the codebase breaks mid-migration
- `main.py` (MIGRATE-01) must be ported before/with its consumers `exploration.py` + `causal_analysis.py` so the `sweep_analysis_results.parquet` data contract stays intact
- Duplicated utils (`ensure_utc`, `find_sorted_pos`, `qcut_with_fallback_labels`) are NOT extracted this milestone — each script's port includes porting its own inline copies

## Deferred Items

Items acknowledged and carried forward / out of this milestone's scope:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Structure | STRUCT-01/02/03: shared utils, CWD-independent paths, package layout | Deferred to post-migration | 2026-06-07 |
| Testing | TEST-FUT-01/02: direct core-logic tests, CWD-independent suite | Deferred to post-migration | 2026-06-07 |
| Quality/Validity | QUAL-01, VALID-01/02: scoped warnings, validity-bug triage | Deferred to post-migration | 2026-06-07 |
| Hygiene | HYG-01/02/03: PNG cleanup, notebook removal, README rewrite | Deferred to post-migration | 2026-06-07 |
| Reproducibility | REPRO-02: data-fetching / ingestion pipeline | Deferred to v2 | 2026-06-07 |

## Session Continuity

Last session: 2026-06-07T02:25:49.819Z
Stopped at: Completed 01-02-PLAN.md (main.py ported to polars; 21-col contract regenerated, 4792 rows)
Resume file: None
