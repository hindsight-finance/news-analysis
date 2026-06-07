# Requirements: News Analysis — v1.0 Polars Migration

**Defined:** 2026-06-07
**Core Value:** The post-news-release sweep methodology is the asset; everything serves keeping that research correct and easy to extend.

## v1 Requirements

Requirements for the **Polars Migration** milestone. Replace pandas with polars as the DataFrame engine across all scripts and the test suite, and drop pandas. Sequencing is **migrate-first** (port before adding a unit-test net). No output-parity diffing — the port is trusted, not verified against historical pandas numbers.

### Migration

- [ ] **MIGRATE-01**: `main.py` sweep engine runs on polars — data loading and all DataFrame operations use polars; `sweep_analysis_results.parquet` is still produced and the sweep methodology logic is preserved
- [ ] **MIGRATE-02**: `exploration.py` runs on polars — win-rate, release-timing, range-quartile, and MAE computations and their chart inputs use polars
- [ ] **MIGRATE-03**: `causal_analysis.py` runs on polars for data handling, with an explicit `polars → numpy` conversion at the scikit-learn boundary so models receive numpy arrays
- [ ] **MIGRATE-04**: `forward_returns.py` runs on polars, including a polars replacement for the `np.searchsorted` timestamp-lookup optimization
- [ ] **MIGRATE-05**: `injection.py` runs on polars — range calculation and histogram inputs use polars
- [ ] **MIGRATE-06**: No `import pandas` remains anywhere in the scripts or tests (pandas fully removed from source)

### Environment

- [ ] **ENV-01**: A version-pinned dependency manifest rebuilds the full polars-based runtime + test environment from a single install command, with pandas absent from the manifest
- [ ] **ENV-02**: polars reads the raw Parquet inputs (`nq_1m.parquet`, `economic_events.parquet`) directly; the parquet backend dependency is resolved and pinned

### Testing

- [ ] **TEST-01**: The existing pytest suite is ported to polars (fixtures and assertions use polars) and passes

## Future Requirements

Acknowledged but deferred — not in this milestone's roadmap. Carried over from the original Clean Foundation scope, to revisit after the migration.

### Structure

- **STRUCT-01**: Shared utilities (`ensure_utc`, `find_sorted_pos`, timestamp helpers, `qcut_with_fallback_labels`) extracted into one importable module, with cross-script duplication removed
- **STRUCT-02**: Every script resolves its data and output paths independent of the current working directory
- **STRUCT-03**: Analysis code organized into a clean importable package with a consistent entry-point pattern

### Testing

- **TEST-FUT-01**: Direct unit tests for the previously-untested core logic (`analyze_event`, `injection.py`)
- **TEST-FUT-02**: Test suite runs reliably from any directory via committed pytest path configuration

### Quality / Validity

- **QUAL-01**: Global `warnings.filterwarnings("ignore")` replaced with scoped, category-specific handling
- **VALID-01**: The three known validity bugs (hardcoded 16:59 ET prior-close, silent event-dropping, `loc`/`iloc` mix in `get_candles_until_eod`) documented at their code sites
- **VALID-02**: Silent event-dropping made observable — count of skipped events reported at runtime

### Hygiene

- **HYG-01/02/03**: Stale root-level PNG cleanup + chart-output policy, remove lingering notebooks, rewrite README

### Reproducibility

- **REPRO-02**: Data-fetching / ingestion pipeline so the raw Parquet inputs are reproducible (currently irreplaceable, no fetcher)

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Output / baseline parity diffing for the migration | Dropped by decision — the idea matters, not reproducing exact pandas numbers; numeric drift from the engine swap is acceptable |
| New research hypotheses or instruments | Research idea is preserved, not extended, this milestone |
| Validation / backtest harness, statistical significance testing | Future "new research" milestone |
| Trading system, signal generator, or dashboard | Productization; foundation must come first |
| Deleting or modifying raw data (`nq_1m.parquet`, `economic_events.parquet`) | Irreplaceable, gitignored, no fetcher exists |
| Rewrite in another language | Stay on Python 3.12 |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MIGRATE-01 | TBD | Pending |
| MIGRATE-02 | TBD | Pending |
| MIGRATE-03 | TBD | Pending |
| MIGRATE-04 | TBD | Pending |
| MIGRATE-05 | TBD | Pending |
| MIGRATE-06 | TBD | Pending |
| ENV-01 | TBD | Pending |
| ENV-02 | TBD | Pending |
| TEST-01 | TBD | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 9

---
*Requirements defined: 2026-06-07 for v1.0 Polars Migration*
