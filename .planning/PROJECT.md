# News Analysis

## What This Is

A Python research codebase that studies NQ (Nasdaq-100 futures) 1-minute price behavior around US economic news releases. The central research idea: after a news-release candle's high or low is swept, does price *reverse* to sweep the opposite side, or *continue* into a momentum box?

As of **v1.0 (Polars Migration, shipped 2026-06-07)**, the codebase runs on **polars** — pandas has been dropped entirely across all five scripts and the test suite. The research *idea* and methodology were preserved through the port; only the underlying data-handling library changed.

## Core Value

The post-news-release sweep methodology is the asset. Everything in this project exists to keep that research correct and easy to extend. When tradeoffs arise, protect the integrity of the methodology and the raw data over code elegance or speed.

For this milestone specifically: every script and test runs on polars instead of pandas, with the sweep methodology *logic* ported faithfully. Exact historical output reproduction is explicitly **not** a goal — the idea matters, not matching the old pandas numbers.

## Current State

**Shipped:** v1.0 Polars Migration (2026-06-07). pandas has been fully replaced by polars across all five scripts and the test suite, and dropped from the dependency manifest.

- All five scripts (`main.py`, `exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`) run on polars; the sweep methodology logic was ported intact.
- pytest suite ported to polars (13/13 green); zero `import pandas` repo-wide.
- Pinned, pandas-free `requirements.txt` (polars==1.40.1 / numpy / matplotlib / scikit-learn / pytest) — pyarrow also dropped via native polars parquet I/O.
- ~1,965 LOC Python across 5 scripts + 3 test modules.

**Next milestone:** not yet defined — run `/gsd-new-milestone`. Strongest candidates are the deferred **Future** items below (shared-utils extraction, CWD-independent paths, clean package structure, direct core-logic tests).

## Requirements

### Validated

<!-- Inferred from existing code (brownfield). These capabilities exist and must keep working after the polars port. -->

- ✓ Sweep analysis engine — detects high/low sweeps and reversal-vs-momentum resolution after US economic events, with session-context features; produces `sweep_analysis_results.parquet` — existing (`main.py`)
- ✓ Exploration analysis — win-rate, release-timing, range-quartile, and MAE breakdowns with charts — existing (`exploration.py`)
- ✓ Causal analysis — interpretable ML models (RandomForest / DecisionTree / Logistic) ranking predictive factors and per-event edge — existing (`causal_analysis.py`)
- ✓ Forward-returns analysis — multi-horizon (15/30/45/60/90m) return and MAE/MFE profiles by release-candle direction — existing (`forward_returns.py`)
- ✓ Injection analysis — per-event release-candle and 10-minute range histograms — existing (`injection.py`)
- ✓ pytest suite — partial coverage of data loading, forward-returns math, and exploration/causal utilities — existing

<!-- Shipped this milestone (v1.0 Polars Migration). -->

- ✓ All five scripts ported pandas → polars, sweep methodology logic intact (`main.py`, `exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`) — v1.0
- ✓ scikit-learn boundary in `causal_analysis.py` handled via a single explicit `polars → numpy` conversion at `.fit()`/`cross_val_score` — v1.0
- ✓ pytest suite ported to polars and passing — v1.0 (13/13 green, zero `import pandas` in tests)
- ✓ Dependency manifest rewritten: polars replaces pandas, pyarrow dropped (native polars parquet I/O), reproducible runtime pinned — v1.0

### Active

<!-- No milestone in progress. Run /gsd-new-milestone to define the next one. -->

_(None — v1.0 shipped. The next milestone is not yet scoped; see **Future** for the leading candidates.)_

### Future

<!-- Deferred from the original Clean Foundation milestone — revisit after the migration. -->

- Shared utilities extracted into one module (eliminate `ensure_utc` / `find_sorted_pos` / `qcut_with_fallback_labels` duplication)
- CWD-independent data and output paths across all scripts; CWD-independent test suite
- Clean package / project structure with a consistent entry-point pattern
- Direct test coverage for the currently-untested core logic (`analyze_event`, `injection.py`)
- Scoped warning handling replacing the global `warnings.filterwarnings("ignore")`
- Repo hygiene — stale root-level PNGs, chart-output tracking policy, lingering notebooks, README rewrite
- Triage of the three known validity bugs (hardcoded 16:59 ET prior-close, silent event-dropping, `loc`/`iloc` mix in `get_candles_until_eod`)

### Out of Scope

<!-- Deferred to future milestones, with reasons to prevent re-adding. -->

- New research hypotheses or new instruments — this codebase's research idea is preserved, not extended, this milestone
- Validation / backtest harness and statistical significance testing — future "new research" milestone
- Trading-system, signal generator, or dashboard productization — far future; foundation must come first
- Baseline output reproduction / oracle diffing — explicitly dropped; the *idea* matters, not reproducing exact historical numbers (reaffirmed for the polars migration: numeric drift from the engine swap is acceptable)
- Deleting or modifying the raw data (`nq_1m.parquet`, `economic_events.parquet`) — irreplaceable, gitignored, no fetcher exists
- Data-fetching / ingestion pipeline — candidate for a later reproducibility milestone
- Rewrite in another language — stay on Python 3.12

## Context

- **Origin:** Migrated off Jupyter notebooks; the Python scripts are now canonical.
- **Shape:** Five flat scripts at the project root forming a linear ETL — `main.py` produces `sweep_analysis_results.parquet`, consumed by `exploration.py` and `causal_analysis.py`; `forward_returns.py` and `injection.py` are independent pipelines that re-read raw data. All currently pandas-based.
- **Data:** NQ 1-minute OHLCV (2010–2026) and a US economic event calendar, both local Parquet, gitignored. No data-fetching code — the raw files are irreplaceable from this codebase alone. Polars reads Parquet natively.
- **Stack today:** Python 3.12 with pandas, numpy, matplotlib, scikit-learn, pyarrow; polars 1.40.1 is already installed but unused. Migration target: polars in, pandas out.
- **Latest findings (4,792 events):** opposite side swept 80.6%; momentum-box-first 52.2% vs reversal-first 45.7% — the central near-coin-flip the research probes.
- **Migration touch points:** all five scripts use pandas DataFrames pervasively; the test suite is pandas-based; `causal_analysis.py` feeds DataFrames into scikit-learn (needs numpy at that boundary); the `np.searchsorted` timestamp-lookup optimization in `forward_returns.py` was replaced in Phase 2 with a pure-polars exact-match lookup (`build_timestamp_index`); `injection.py` was upgraded to the same construct. `main.py` intentionally keeps its numpy-`searchsorted` pattern (D-03 — the lone numpy lookup holdout, by decision).
- **Reference:** Full codebase map at `.planning/codebase/` (mapped 2026-06-07).

## Constraints

- **Tech stack**: Python 3.12 + **polars**/numpy/matplotlib/scikit-learn. pandas is being removed this milestone. No rewrite in another language.
- **Data**: Raw Parquet inputs are irreplaceable and gitignored — must not be deleted or modified by the migration.
- **Methodology**: The sweep research *logic* must survive the migration intact — code structure and DataFrame engine are disposable, the methodology is not.
- **Output parity**: Not required. Favor a correct, idiomatic polars port over byte-for-byte parity with the old pandas numbers.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pivot the project to polars, dropping pandas | polars is the chosen DataFrame engine going forward | ✓ Shipped v1.0 — pandas fully removed |
| Migrate-first — port before adding the unit-test net | Speed; user accepted the methodology-integrity risk of porting untested core logic | ✓ Shipped v1.0 — port held; tests green post-migration |
| Phases 3 & 4 executed directly (no per-phase GSD plans) | Drop ceremony for mechanical test-port + pandas-removal work | ✓ Good — both verified complete |
| `main.py` keeps its numpy `searchsorted` lookup (D-03) | Lone numpy lookup holdout by decision; consumers use polars `build_timestamp_index` | ✓ Good |
| No baseline / output parity for the migration | The research idea matters, not reproducing exact pandas numbers | — Locked |
| ~~Refactor in place (cleanup-only Clean Foundation milestone)~~ | Superseded by the polars pivot | — Superseded 2026-06-07 |
| ~~Scope first milestone to cleanup only~~ | Superseded by the polars pivot; cleanup items moved to Future | — Superseded 2026-06-07 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-07 after v1.0 milestone — Polars Migration SHIPPED and archived. All five scripts + the test suite run on polars; pandas removed repo-wide; pinned pandas-free `requirements.txt`; sweep methodology intact. Roadmap and requirements archived to `.planning/milestones/v1.0-*`; tagged `v1.0`. Next: `/gsd-new-milestone`.*
