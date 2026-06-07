# News Analysis

## What This Is

A Python research codebase that studies NQ (Nasdaq-100 futures) 1-minute price behavior around US economic news releases. The central research idea: after a news-release candle's high or low is swept, does price *reverse* to sweep the opposite side, or *continue* into a momentum box?

As of **v1.0 (Polars Migration, shipped 2026-06-07)** the codebase runs on **polars** — pandas was dropped entirely across all five scripts and the test suite. As of **v1.1 (Core Validation & Hardening, shipped 2026-06-07)** the sweep-methodology core is under direct test, the known validity bugs are fixed, and hygiene/quality debt is cleared. The research *idea* and methodology were preserved throughout; only the surrounding code changed.

## Core Value

The post-news-release sweep methodology is the asset. Everything in this project exists to keep that research correct and easy to extend. When tradeoffs arise, protect the integrity of the methodology and the raw data over code elegance or speed.

## Current State

**Shipped:** v1.1 Core Validation & Hardening (2026-06-07). The sweep-methodology core (`analyze_event`) is now provably correct under direct tests, the two real validity bugs are fixed, and hygiene/quality debt is cleared — without altering the methodology logic.

- Direct tests on the core asset: `analyze_event` high/low sweep + reversal-vs-momentum resolution, `main.py` session-context/gap features, and `injection.py` lookup/range functions. Suite grew 13 → 29 (16 new tests, 29/29 green).
- Prior-session close resolved without the hardcoded `16:59` ET magic minute (`get_last_candle_before`) — short/holiday sessions no longer silently miss (VALID-01).
- Dropped events (missing release / required future candle) are counted and reported in a run summary line instead of being silently skipped (VALID-02); the legacy `loc`/`iloc` mix is confirmed already eliminated by the migration (VALID-03).
- Hygiene/quality: stale root PNGs removed + root chart outputs gitignored (HYG-01), README refreshed for the polars era (HYG-02), the global sklearn `filterwarnings("ignore")` narrowed to the specific warnings around the emitting call (QUAL-01).
- `main.py` smoke-run preserved the core methodology numbers (80.6% opposite swept; 52.2% momentum-first vs 45.7% reversal-first).

<details>
<summary>Previously shipped: v1.0 Polars Migration (2026-06-07)</summary>

- All five scripts (`main.py`, `exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`) ported pandas → polars; sweep methodology logic intact.
- pytest suite ported to polars; zero `import pandas` repo-wide.
- Pinned, pandas-free `requirements.txt` (polars==1.40.1 / numpy / matplotlib / scikit-learn / pytest); pyarrow dropped via native polars parquet I/O.
- ~1,965 LOC Python across 5 scripts + 3 test modules.

</details>

**Next:** No milestone currently scoped. Run `/gsd-new-milestone` to plan the next cycle — the natural first candidate is the deferred structure work (shared-utils extraction, CWD-independent paths, package layout).

## Requirements

### Validated

<!-- Inferred from existing code (brownfield). These capabilities exist and must keep working. -->

- ✓ Sweep analysis engine — detects high/low sweeps and reversal-vs-momentum resolution after US economic events, with session-context features; produces `sweep_analysis_results.parquet` (`main.py`)
- ✓ Exploration analysis — win-rate, release-timing, range-quartile, and MAE breakdowns with charts (`exploration.py`)
- ✓ Causal analysis — interpretable ML models (RandomForest / DecisionTree / Logistic) ranking predictive factors and per-event edge (`causal_analysis.py`)
- ✓ Forward-returns analysis — multi-horizon (15/30/45/60/90m) return and MAE/MFE profiles by release-candle direction (`forward_returns.py`)
- ✓ Injection analysis — per-event release-candle and 10-minute range histograms (`injection.py`)

<!-- Shipped v1.0 Polars Migration. -->

- ✓ All five scripts ported pandas → polars, sweep methodology logic intact — v1.0
- ✓ scikit-learn boundary handled via a single explicit `polars → numpy` conversion at `.fit()`/`cross_val_score` — v1.0
- ✓ pytest suite ported to polars and passing — v1.0
- ✓ Dependency manifest rewritten: polars replaces pandas, pyarrow dropped (native polars parquet I/O), reproducible runtime pinned — v1.0

<!-- Shipped v1.1 Core Validation & Hardening. -->

- ✓ Direct tests for `analyze_event` sweep detection — high/low sweep + reversal-vs-momentum — v1.1 (TEST-01)
- ✓ Direct tests for `main.py` session-context / gap features — v1.1 (TEST-02)
- ✓ Direct tests for `injection.py` lookup + range functions — v1.1 (TEST-03)
- ✓ Hardcoded 16:59 ET prior-close fixed (`get_last_candle_before`) — v1.1 (VALID-01)
- ✓ Silent event-dropping replaced by a reported dropped-event count — v1.1 (VALID-02)
- ✓ `loc`/`iloc` mix confirmed resolved by the migration; closed out — v1.1 (VALID-03)
- ✓ Stale root PNGs removed + chart-tracking policy set — v1.1 (HYG-01)
- ✓ README accuracy pass for the polars era — v1.1 (HYG-02)
- ✓ Global `filterwarnings("ignore")` in `causal_analysis.py` narrowed to the specific sklearn warnings — v1.1 (QUAL-01)

### Active

<!-- No milestone currently scoped. Run /gsd-new-milestone to define the next cycle. -->

(None — next milestone not yet scoped. The Future items below are the leading candidates.)

### Future

<!-- Deferred — natural candidates for the next milestone. -->

- **Structure** — extract shared utilities into one module (kill the `ensure_utc` / `find_sorted_pos` / `qcut_with_fallback_labels` triplication, STRUCT-01); CWD-independent data/output paths across all scripts + CWD-independent test suite (STRUCT-02); clean package/project structure with a consistent entry-point pattern (STRUCT-03)
- **Research** — validation / backtest harness and statistical-significance testing for the sweep methodology (RSRCH-01); new research hypotheses or additional instruments (RSRCH-02)
- **Reproducibility** — data-fetching / ingestion pipeline (candidate for a later reproducibility milestone)

### Out of Scope

<!-- Deferred to future milestones, with reasons to prevent re-adding. -->

- Extending the research (new hypotheses, new instruments) *before* the foundation work lands — hardening/structure comes first; research extension is tracked under Future, not started ad hoc
- Trading-system, signal generator, or dashboard productization — far future; foundation must come first
- Baseline output reproduction / oracle diffing — explicitly dropped; the *idea* matters, not reproducing exact historical numbers (numeric drift from the engine swap is acceptable)
- Deleting or modifying the raw data (`nq_1m.parquet`, `economic_events.parquet`) — irreplaceable, gitignored, no fetcher exists
- Rewrite in another language — stay on Python 3.12 + polars

## Context

- **Origin:** Migrated off Jupyter notebooks; the Python scripts are now canonical.
- **Shape:** Five flat scripts at the project root forming a linear ETL — `main.py` produces `sweep_analysis_results.parquet`, consumed by `exploration.py` and `causal_analysis.py`; `forward_returns.py` and `injection.py` are independent pipelines that re-read raw data. All run on polars.
- **Data:** NQ 1-minute OHLCV (2010–2026) and a US economic event calendar, both local Parquet, gitignored. No data-fetching code — the raw files are irreplaceable from this codebase alone. Polars reads Parquet natively.
- **Stack:** Python 3.12 with polars 1.40.1, numpy, matplotlib, scikit-learn — pinned in `requirements.txt`. pandas and pyarrow fully removed (v1.0).
- **Tests:** pytest, 29/29 green — data loading, forward-returns math, exploration/causal utils, plus v1.1's direct coverage of `analyze_event`, session-context/gap features, and `injection.py` lookup/range functions.
- **Latest findings (4,792 events):** opposite side swept 80.6%; momentum-box-first 52.2% vs reversal-first 45.7% — the central near-coin-flip the research probes.
- **Lookup decisions:** `build_timestamp_index` (pure-polars `with_row_index` + inner-join exact-match) is the shared lookup reused by `forward_returns.py` and `injection.py`; `main.py` intentionally keeps its numpy-`searchsorted` pattern (D-03 — the lone numpy lookup holdout, by decision).
- **Carried tech debt:** shared utilities (`ensure_utc`, `find_sorted_pos`, `qcut_with_fallback_labels`) remain triplicated inline per script (STRUCT-01, deferred).
- **Reference:** Full codebase map at `.planning/codebase/` (mapped 2026-06-07).

## Constraints

- **Tech stack**: Python 3.12 + polars/numpy/matplotlib/scikit-learn. pandas removed (v1.0). No rewrite in another language.
- **Data**: Raw Parquet inputs are irreplaceable and gitignored — must not be deleted or modified.
- **Methodology**: The sweep research *logic* must survive any refactor intact — code structure and DataFrame engine are disposable, the methodology is not.
- **Output parity**: Not required. Favor correct, idiomatic code over byte-for-byte parity with the old numbers.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pivot the project to polars, dropping pandas | polars is the chosen DataFrame engine going forward | ✓ Shipped v1.0 — pandas fully removed |
| Migrate-first — port before adding the unit-test net | Speed; user accepted the methodology-integrity risk of porting untested core logic | ✓ Shipped v1.0 — port held; tests green post-migration |
| Phases 3 & 4 (v1.0) executed directly (no per-phase GSD plans) | Drop ceremony for mechanical test-port + pandas-removal work | ✓ Good — both verified complete |
| `main.py` keeps its numpy `searchsorted` lookup (D-03) | Lone numpy lookup holdout by decision; consumers use polars `build_timestamp_index` | ✓ Good |
| No baseline / output parity | The research idea matters, not reproducing exact pandas numbers | — Locked |
| Scope v1.1 to core-test coverage + validity fixes + hygiene (no new research) | Harden the foundation before extending the research; the sweep kernel was ported untested in v1.0 | ✓ Shipped v1.1 — the sweep kernel is now directly tested |
| Execute v1.1 as direct GSD fixes (no per-phase discuss/plan/execute) | Small, mechanical, well-understood tasks; matches the v1.0 precedent of running mechanical phases directly | ✓ Good — atomic fix commits, suite green, methodology numbers unchanged |
| `loc`/`iloc` validity bug treated as resolved by the polars migration | `get_candles_until_eod` was rewritten in polars; no `.loc`/`.iloc` remain repo-wide | ✓ Good — closed as VALID-03 |
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
*Last updated: 2026-06-07 — v1.1 Core Validation & Hardening SHIPPED. The sweep core is now under direct test (16 new tests, 29/29 green), the two real validity bugs are fixed (VALID-01 prior-close, VALID-02 dropped-event reporting), the `loc`/`iloc` bug is confirmed closed (VALID-03), and hygiene/quality debt is cleared (HYG-01/02, QUAL-01). Methodology numbers preserved (80.6% / 52.2% / 45.7%). Next: `/gsd-new-milestone`.*
