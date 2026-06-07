# News Analysis

## What This Is

A Python research codebase that studies NQ (Nasdaq-100 futures) 1-minute price behavior around US economic news releases. The central research idea: after a news-release candle's high or low is swept, does price *reverse* to sweep the opposite side, or *continue* into a momentum box?

The current milestone — **Clean Foundation** — does not add research. It refactors, hardens, and restructures the existing scripts into a clean, tested, reproducible base that future research can safely build on. The research *idea* is preserved; the code around it is rebuilt for maintainability.

## Core Value

The post-news-release sweep methodology is the asset. Everything in this project exists to keep that research correct, reproducible, and easy to extend. When tradeoffs arise, protect the integrity of the methodology and the raw data over code elegance or speed.

For this milestone specifically: a clean, hardened, well-tested foundation that leaves the research idea intact and runnable while making the codebase a place new research can grow.

## Requirements

### Validated

<!-- Inferred from existing code (brownfield). These already work and must keep working. -->

- ✓ Sweep analysis engine — detects high/low sweeps and reversal-vs-momentum resolution after US economic events, with session-context features; produces `sweep_analysis_results.parquet` — existing (`main.py`)
- ✓ Exploration analysis — win-rate, release-timing, range-quartile, and MAE breakdowns with charts — existing (`exploration.py`)
- ✓ Causal analysis — interpretable ML models (RandomForest / DecisionTree / Logistic) ranking predictive factors and per-event edge — existing (`causal_analysis.py`)
- ✓ Forward-returns analysis — multi-horizon (15/30/45/60/90m) return and MAE/MFE profiles by release-candle direction — existing (`forward_returns.py`)
- ✓ Injection analysis — per-event release-candle and 10-minute range histograms — existing (`injection.py`)
- ✓ pytest suite — partial coverage of data loading, forward-returns math, and exploration/causal utilities — existing

### Active

<!-- This milestone: Clean Foundation (cleanup only). -->

- [ ] Shared utilities extracted into one module (eliminate `ensure_utc` / `find_sorted_pos` / `qcut_with_fallback_labels` duplication)
- [ ] CWD-independent data and output paths across all scripts
- [ ] Scoped warning handling replacing the global `warnings.filterwarnings("ignore")`
- [ ] Dependency manifest pinning the tested package set (reproducible environment)
- [ ] Clean package / project structure
- [ ] Repo hygiene — remove stale root-level PNGs, decide chart-output tracking, remove any lingering notebooks, rewrite the README
- [ ] Real test coverage for the currently-untested core logic (`analyze_event`, `injection.py`)
- [ ] Three known validity bugs acknowledged and triaged — each one's fix-or-defer decision is made during its phase discussion

### Out of Scope

<!-- Deferred to future milestones, with reasons to prevent re-adding. -->

- New research hypotheses or new instruments — this milestone is cleanup only; research is a future milestone
- Validation / backtest harness and statistical significance testing — future "new research" milestone
- Trading-system, signal generator, or dashboard productization — far future; foundation must come first
- Baseline output reproduction / oracle diffing — explicitly dropped; the *idea* matters, not reproducing exact historical numbers
- Deleting or modifying the raw data (`nq_1m.parquet`, `economic_events.parquet`) — irreplaceable, gitignored, no fetcher exists
- Data-fetching / ingestion pipeline — not part of cleanup; candidate for a later reproducibility milestone

## Context

- **Origin:** Migrated off Jupyter notebooks; the Python scripts are now canonical.
- **Shape:** Five flat scripts at the project root forming a linear ETL — `main.py` produces `sweep_analysis_results.parquet`, consumed by `exploration.py` and `causal_analysis.py`; `forward_returns.py` and `injection.py` are independent pipelines that re-read raw data.
- **Data:** NQ 1-minute OHLCV (2010–2026) and a US economic event calendar, both local Parquet, gitignored. No data-fetching code and no provenance recorded in the repo — the raw files are irreplaceable from this codebase alone.
- **Stack today:** Python 3.12 with pandas, numpy, matplotlib, scikit-learn, pyarrow; no `requirements.txt` / `pyproject.toml` / lockfile.
- **Latest findings (4,792 events):** opposite side swept 80.6%; momentum-box-first 52.2% vs reversal-first 45.7% — the central near-coin-flip the research probes.
- **Known fragility:** `analyze_event` (the core logic) and `injection.py` have zero direct tests; three validity bugs can bias findings (hardcoded 16:59 ET prior-close → zero-imputed gap features, silent event-dropping on candle-lookup misses, `loc`/`iloc` mix in `get_candles_until_eod`).
- **Reference:** Full codebase map at `.planning/codebase/` (mapped 2026-06-07).

## Constraints

- **Tech stack**: Stay on Python 3.12 + pandas/numpy/matplotlib/scikit-learn — no rewrite in another language.
- **Data**: Raw Parquet inputs are irreplaceable and gitignored — must not be deleted or modified by cleanup.
- **Methodology**: The sweep research idea must survive the refactor intact — code structure is disposable, the methodology is not.
- **Output parity**: No baseline diffing required — preserve the idea, not exact historical numbers; favor a clean result over byte-for-byte output parity.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Refactor in place rather than rewrite from scratch | Preserve the methodology and 16 years of findings at lowest risk | — Pending |
| Scope this milestone to cleanup only | Keep it tight; defer all new research to later milestones | — Pending |
| Drop baseline / oracle output comparison | User cares about the research idea, not reproducing exact numbers | — Pending |
| Decide each validity-bug fix per phase | Number-changing fixes deserve focused, individual attention in phase discussion | — Pending |

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
*Last updated: 2026-06-07 after initialization*
