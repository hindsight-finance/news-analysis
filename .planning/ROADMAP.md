# Roadmap: News Analysis — Clean Foundation

## Overview

This milestone rebuilds the codebase around the existing post-news-release sweep methodology without touching the research idea or the irreplaceable raw data. It starts by establishing a reproducible environment and a directory-independent test suite (the safety net), then performs the structural refactor (shared utilities, CWD-independent paths, clean package layout) against that net. With the structure stable, it adds direct tests for the previously-untested core logic, surfaces hidden problems (scoped warnings, documented validity bugs, observable event-dropping), and finishes by cleaning the repository and rewriting the documentation. The result is a clean, hardened, well-tested base that future research can safely grow on.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Reproducible Foundation** - Pinned dependency manifest and a directory-independent test suite as the refactor safety net
- [ ] **Phase 2: Structural Refactor** - Shared utilities, CWD-independent paths, and a clean importable package layout
- [ ] **Phase 3: Core Logic Test Coverage** - Direct unit tests for `analyze_event` and `injection.py`
- [ ] **Phase 4: Observability & Validity Triage** - Scoped warnings, documented validity bugs, and observable event-dropping
- [ ] **Phase 5: Repo Hygiene & Documentation** - Remove stale artifacts, set chart-output policy, and rewrite the README

## Phase Details

### Phase 1: Reproducible Foundation
**Goal**: A single command rebuilds the runtime + test environment, and the existing test suite runs reliably from any directory — establishing the safety net all later refactoring depends on.
**Depends on**: Nothing (first phase)
**Requirements**: REPRO-01, TEST-03
**Success Criteria** (what must be TRUE):
  1. A single install command rebuilds the full runtime + test environment from a version-pinned manifest
  2. `pytest` passes when invoked from a subdirectory, not only from the project root
  3. Committed pytest path configuration (`conftest.py` / `pyproject` pythonpath) makes test imports CWD-independent
**Plans**: TBD

### Phase 2: Structural Refactor
**Goal**: Consolidate the flat scripts into a clean importable package with shared utilities and CWD-independent paths, with the sweep methodology verified intact.
**Depends on**: Phase 1
**Requirements**: STRUCT-01, STRUCT-02, STRUCT-03
**Success Criteria** (what must be TRUE):
  1. `ensure_utc`, `find_sorted_pos`, timestamp helpers, and `qcut_with_fallback_labels` live in one importable module, with no duplicated copies remaining across any script
  2. Every script resolves its data and output paths independent of the current working directory (runnable from anywhere)
  3. Analysis code is organized into a clean importable package with a consistent entry-point pattern across scripts
  4. The existing test suite still passes after the restructure (sweep methodology unchanged)
**Plans**: TBD

### Phase 3: Core Logic Test Coverage
**Goal**: Put direct unit tests around the previously-untested core research logic so future changes have a verification signal.
**Depends on**: Phase 2
**Requirements**: TEST-01, TEST-02
**Success Criteria** (what must be TRUE):
  1. `analyze_event` has direct unit tests covering sweep direction, first-target classification, MAE, and session-context features
  2. `injection.py` has unit tests covering its range calculation and output generation
  3. The full suite (new + existing tests) passes from any directory
**Plans**: TBD

### Phase 4: Observability & Validity Triage
**Goal**: Stop hiding problems — scope warning handling, document the known validity bugs at their code sites, and surface silent event-dropping at runtime.
**Depends on**: Phase 3
**Requirements**: QUAL-01, VALID-01, VALID-02
**Success Criteria** (what must be TRUE):
  1. The global `warnings.filterwarnings("ignore")` is replaced with scoped, category-specific handling, so unrelated warnings surface again
  2. All three known validity bugs (hardcoded 16:59 ET prior-close, silent event-dropping, `loc`/`iloc` mix in `get_candles_until_eod`) are documented at their code sites with a fix-or-defer decision recorded, so none is silently inherited
  3. The count of skipped/dropped events is reported at runtime, making silent event-dropping observable
**Plans**: TBD

> Note: Per milestone scoping, behavior-changing numeric fixes for the VALID-01 bugs are decided during `/gsd-discuss-phase`, not mandated by this roadmap. This phase guarantees the bugs are surfaced and triaged.

### Phase 5: Repo Hygiene & Documentation
**Goal**: Leave a clean repository with documentation that accurately reflects the rebuilt structure, setup, and usage.
**Depends on**: Phase 4
**Requirements**: HYG-01, HYG-02, HYG-03
**Success Criteria** (what must be TRUE):
  1. Stale root-level chart PNGs are removed and a clear chart-output tracking policy is in place (gitignored or curated)
  2. No Jupyter notebooks remain in the repository (scripts are canonical)
  3. The README accurately reflects the cleaned structure, setup, and usage
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Reproducible Foundation | 0/TBD | Not started | - |
| 2. Structural Refactor | 0/TBD | Not started | - |
| 3. Core Logic Test Coverage | 0/TBD | Not started | - |
| 4. Observability & Validity Triage | 0/TBD | Not started | - |
| 5. Repo Hygiene & Documentation | 0/TBD | Not started | - |
