# Requirements: News Analysis — Clean Foundation

**Defined:** 2026-06-07
**Core Value:** The post-news-release sweep methodology is the asset; everything serves keeping that research correct, reproducible, and easy to extend.

## v1 Requirements

Requirements for the **Clean Foundation** milestone. Cleanup, hardening, and restructuring only — no new research. Each maps to a roadmap phase.

### Structure

- [ ] **STRUCT-01**: Shared utility functions (`ensure_utc`, `find_sorted_pos`, timestamp helpers, `qcut_with_fallback_labels`) live in one importable module, with all cross-script duplication removed
- [ ] **STRUCT-02**: Every script resolves its data and output paths independent of the current working directory (runnable from anywhere)
- [ ] **STRUCT-03**: Analysis code is organized into a clean, importable package layout with a consistent entry-point pattern across scripts

### Reproducibility

- [ ] **REPRO-01**: A version-pinned dependency manifest rebuilds the full runtime + test environment from a single install command

### Quality

- [ ] **QUAL-01**: The global `warnings.filterwarnings("ignore")` is replaced with scoped, category-specific warning handling

### Testing

- [ ] **TEST-01**: `analyze_event` sweep-detection logic has direct unit tests covering sweep direction, first-target classification, MAE, and session-context features
- [ ] **TEST-02**: `injection.py` has unit tests covering its range calculation and output generation
- [ ] **TEST-03**: The test suite runs reliably from any directory via committed pytest path configuration (`conftest.py` / `pyproject` pythonpath)

### Hygiene

- [ ] **HYG-01**: Stale root-level chart PNGs are removed and a clear chart-output tracking policy is in place (gitignored or curated)
- [ ] **HYG-02**: Any lingering Jupyter notebooks are removed from the repo (scripts are canonical)
- [ ] **HYG-03**: The README is rewritten to reflect the cleaned structure, setup, and usage

### Validity

- [ ] **VALID-01**: The three known validity bugs (hardcoded 16:59 ET prior-close, silent event-dropping, `loc`/`iloc` mix in `get_candles_until_eod`) are documented at their code sites so none is silently inherited
- [ ] **VALID-02**: Silent event-dropping is made observable — the count of skipped events is reported at runtime

> **Note on validity bugs:** Behavior-changing numeric fixes for VALID-01's bugs are decided per phase during `/gsd-discuss-phase`. This milestone guarantees the bugs are *surfaced and triaged*, not silently carried; whether each numeric fix lands now or is deferred to a research milestone is a phase-level decision.

## v2 Requirements

Acknowledged but deferred — not in this milestone's roadmap.

### Reproducibility

- **REPRO-02**: Data-fetching / ingestion pipeline so the raw Parquet inputs are reproducible (currently irreplaceable, no fetcher)

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
|---------|--------|
| New research hypotheses or instruments | Cleanup-only milestone; research is a future milestone |
| Validation / backtest harness, statistical significance testing | Future "new research" milestone |
| Trading system, signal generator, or dashboard | Productization; foundation must come first |
| Baseline output reproduction / oracle diffing | Dropped by decision — the idea matters, not reproducing exact historical numbers |
| Deleting or modifying raw data (`nq_1m.parquet`, `economic_events.parquet`) | Irreplaceable, gitignored, no fetcher exists |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STRUCT-01 | Phase 2 | Pending |
| STRUCT-02 | Phase 2 | Pending |
| STRUCT-03 | Phase 2 | Pending |
| REPRO-01 | Phase 1 | Pending |
| QUAL-01 | Phase 4 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 1 | Pending |
| HYG-01 | Phase 5 | Pending |
| HYG-02 | Phase 5 | Pending |
| HYG-03 | Phase 5 | Pending |
| VALID-01 | Phase 4 | Pending |
| VALID-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13 ✓
- Unmapped: 0

---
*Requirements defined: 2026-06-07*
*Last updated: 2026-06-07 after roadmap creation (phase mappings populated)*
