# Roadmap: News Analysis — v1.0 Polars Migration

## Overview

This milestone swaps the DataFrame engine from pandas to polars across the whole codebase, migrate-first. It starts with the primary sweep pipeline — `main.py` and the two scripts that consume its `sweep_analysis_results.parquet` (`exploration.py`, `causal_analysis.py`) — porting them together so the intermediate parquet data contract never breaks mid-migration, and resolving polars' direct raw-parquet reads in the process. It then ports the two independent raw-data pipelines (`forward_returns.py`, `injection.py`), including a polars replacement for the `np.searchsorted` timestamp-lookup optimization. With every script on polars, the pytest suite is ported to assert against the ported code. Finally, pandas is removed entirely from source and the manifest, and a single-command, version-pinned polars runtime is locked in. There is no output-parity or baseline-diffing step — the port is trusted, not verified against historical pandas numbers; only the methodology logic must survive intact.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Primary Pipeline on Polars** - Port `main.py` and its two consumers, keeping the intermediate parquet contract intact and enabling direct polars parquet reads (completed 2026-06-07)
- [ ] **Phase 2: Independent Pipelines on Polars** - Port `forward_returns.py` and `injection.py`, including a polars timestamp-lookup replacement
- [ ] **Phase 3: Test Suite on Polars** - Port the pytest suite (fixtures and assertions) to polars and get it green against the ported scripts
- [ ] **Phase 4: Pandas Removal & Manifest Finalization** - Remove all remaining pandas imports and pin a reproducible, pandas-free polars runtime

## Phase Details

### Phase 1: Primary Pipeline on Polars

**Goal**: The sweep-analysis pipeline (`main.py` → `exploration.py` + `causal_analysis.py`) runs end-to-end on polars, with the intermediate `sweep_analysis_results.parquet` data contract intact and the sweep methodology logic ported faithfully.
**Depends on**: Nothing (first phase)
**Requirements**: MIGRATE-01, MIGRATE-02, MIGRATE-03, ENV-02
**Success Criteria** (what must be TRUE):

  1. Running `python3 main.py` on polars produces `data/sweep_analysis_results.parquet` with the sweep methodology logic (sweep direction, first-target classification, MAE, session context) ported intact
  2. polars reads `nq_1m.parquet` and `economic_events.parquet` directly with no pandas in the read path, and the parquet backend dependency required for those reads is identified and pinned
  3. `exploration.py` runs on polars, consuming the polars-produced sweep results and writing its win-rate, release-timing, range-quartile, and MAE chart outputs
  4. `causal_analysis.py` runs on polars for data handling and trains its scikit-learn models via an explicit `polars → numpy` conversion at the model boundary**Plans**: 4 plans (3 waves)

**Wave 1**

- [x] 01-01-PLAN.md — Wave 1: Phase-1 integration smoke harness (21-col contract + native-read + no-pandas checks), separate from the pandas `tests/` suite

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Wave 2: Port `main.py` sweep engine to polars (MIGRATE-01, ENV-02) — native reads, threaded lookups (no `.attrs`), us↔ns reconcile, pinned 21-col CONTRACT_SCHEMA, methodology kernel verbatim

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Wave 3: Port `exploration.py` to polars (MIGRATE-02) — win-rate/timing/quartile/MAE aggregations + charts + summary CSV
- [x] 01-04-PLAN.md — Wave 3: Port `causal_analysis.py` to polars (MIGRATE-03) — explicit `polars → numpy` model boundary + event_stats CSV + charts

### Phase 2: Independent Pipelines on Polars

**Goal**: The two independent raw-data pipelines (`forward_returns.py`, `injection.py`) run on polars, with the pandas/numpy timestamp-lookup optimization replaced by a polars equivalent.
**Depends on**: Nothing (independent of Phase 1; sequenced after it)
**Requirements**: MIGRATE-04, MIGRATE-05
**Success Criteria** (what must be TRUE):

  1. Running `python3 forward_returns.py` on polars produces its multi-horizon return and MAE/MFE charts and `forward_returns_by_event.csv`
  2. The `np.searchsorted` timestamp-lookup optimization in `forward_returns.py` is replaced with a polars equivalent, so candle lookups no longer depend on pandas
  3. Running `python3 injection.py` on polars produces its per-event release-candle and 10-minute range histograms, with range calculation and histogram inputs computed in polars

**Plans**: TBD

### Phase 3: Test Suite on Polars

**Goal**: The existing pytest suite is ported to polars and passes against the ported scripts, restoring the verification signal under the new engine.
**Depends on**: Phases 1 and 2 (tests assert against the ported scripts)
**Requirements**: TEST-01
**Success Criteria** (what must be TRUE):

  1. All three test modules (`test_main_data_loading.py`, `test_forward_returns.py`, `test_analysis_scripts.py`) build fixtures and make assertions using polars
  2. No test fixture constructs data with pandas (`pd.DataFrame` / `pd.to_datetime` removed from the test suite)
  3. `pytest` runs green against the polars-ported scripts

**Plans**: TBD

### Phase 4: Pandas Removal & Manifest Finalization

**Goal**: pandas is fully removed from source and the dependency manifest, and a single install command rebuilds a version-pinned, pandas-free polars runtime + test environment.
**Depends on**: Phases 1, 2, and 3 (pandas can only be removed once every script and test is ported)
**Requirements**: MIGRATE-06, ENV-01
**Success Criteria** (what must be TRUE):

  1. A repo-wide search for `import pandas` (including `import pandas as pd`) across all scripts and tests returns zero matches
  2. A version-pinned dependency manifest rebuilds the full polars-based runtime + test environment from a single install command, with pandas absent from the manifest
  3. A clean install from the manifest yields an environment that runs the full `pytest` suite green

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Primary Pipeline on Polars | 4/4 | Complete   | 2026-06-07 |
| 2. Independent Pipelines on Polars | 0/TBD | Not started | - |
| 3. Test Suite on Polars | 0/TBD | Not started | - |
| 4. Pandas Removal & Manifest Finalization | 0/TBD | Not started | - |
