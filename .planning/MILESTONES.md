# Milestones

## v1.0 Polars Migration (Shipped: 2026-06-07)

**Phases completed:** 2 phases, 6 plans, 11 tasks

**Key accomplishments:**

- Pandas-free polars-migration smoke harness (`smoke/phase1_smoke.py`) that independently encodes the 21-column CONTRACT_SCHEMA, validates the live data contract + native raw reads today, and exposes the per-check CLI gate every downstream Phase-1 port task depends on.
- Ported `main.py` (the sweep engine) from pandas to polars by swapping only the I/O boundary — native parquet reads, explicitly-threaded ns-int64 lookups (no `.attrs`), dict-row candle access, and a pinned 21-column `CONTRACT_SCHEMA` write — while preserving the numpy sweep-methodology kernel verbatim; the regenerated contract is 4792 rows with zero pandas in `main.py`.
- Ported `exploration.py` (consumer #1) from pandas to polars by swapping the engine at read/aggregate/extract/write while keeping matplotlib — `group_by/agg` + `pl.when/then` win-rate math, `qcut(allow_duplicates=True)` quartile bins, every plotted series fed via `.to_numpy()`/`.to_list()` at the chart boundary, and `write_csv` — consuming the pinned 21-col contract and regenerating all four chart PNGs plus `summary_by_event.csv` with zero pandas imports.
- Ported `causal_analysis.py` (the second contract consumer) from pandas to polars by keeping all data handling in polars and crossing to numpy exactly once at the scikit-learn boundary (`features.to_numpy()` / `y.to_numpy()` at `.fit()`/`cross_val_score`/`StandardScaler`/`LabelEncoder`), with retained `feature_names` driving importance/coefficient/decision-tree labels; the script trains RF / DecisionTree / LogisticRegression and regenerates `event_stats.csv` plus all causal charts with zero pandas imports.
- forward_returns.py runs entirely on polars: a pandas-free, searchsorted-free pipeline that resolves candle lookups with a with_row_index + inner-join exact-match, preserves the positional MFE/MAE window, and computes summaries via group_by/agg — producing forward_returns_by_event.csv (23,935 rows) plus 20 per-horizon charts.
- injection.py runs entirely on polars: a pandas-free, headless-safe pipeline whose release-candle lookup is a pure-polars exact-match (with_row_index + inner-join) replacing the linear boolean-mask scan, with a time-bounded is_between 10-minute window — regenerating per-event range/volume histograms for 67 event types.

---

## v1.1 Core Validation & Hardening (Shipped: 2026-06-07)

**Phases completed:** 1 phase (Phase 5, direct execution), 9 requirements, ~8 atomic fix commits

**Tests:** 13 → 29 passing (16 new); suite green. `main.py` smoke-run preserved the core methodology numbers (80.6% opposite swept, 52.2% momentum-first, 45.7% reversal-first).

**Key accomplishments:**

- Locked the sweep-methodology core under direct tests for the first time: `analyze_event` high/low sweep identification + reversal-vs-momentum-box resolution on controlled fixtures (TEST-01), `main.py` session-context / gap features (TEST-02), and `injection.py`'s lookup/range functions — `build_release_index`, `get_release_candle_data`, `get_10min_range`, `calculate_percentage_range` (TEST-03) — testing the asset itself, not just the loaders around it.
- Fixed the hardcoded `16:59` ET prior-close magic minute (`main.py`) by resolving the prior-session close via `get_last_candle_before`, so short/holiday sessions no longer silently miss (VALID-01).
- Made analysis runs honest about coverage: `analyze_event` takes an optional `drops` Counter and `main()` prints a dropped-event summary line instead of silently skipping events via `return None` / `continue` (VALID-02).
- Confirmed and closed the legacy `loc`/`iloc` bug as already eliminated by the v1.0 polars migration — `grep` for `.loc[`/`.iloc[` is empty repo-wide, `get_candles_until_eod` is pure-polars positional slicing, and a regression test guards it (VALID-03, no code change needed).
- Cleared hygiene/quality debt: removed the 4 stale root-level PNGs and gitignored `/*.png` as chart-output policy (HYG-01); narrowed the global `warnings.filterwarnings("ignore")` in `causal_analysis.py` to ConvergenceWarning / UndefinedMetricWarning around the emitting call (QUAL-01); refreshed `README.md` for the polars era (HYG-02).
- Delivered the whole milestone as direct GSD fixes (no per-phase discuss/plan/execute), mirroring the v1.0 precedent for mechanical phases — without touching the methodology logic.

---
