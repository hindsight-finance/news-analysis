# Roadmap: News Analysis

## Milestones

- ✅ **v1.0 Polars Migration** — Phases 1-4 (shipped 2026-06-07) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Core Validation & Hardening** — Phase 5 (complete 2026-06-07) — direct-execution

## Phases

<details>
<summary>✅ v1.0 Polars Migration (Phases 1-4) — SHIPPED 2026-06-07</summary>

Swapped the DataFrame engine from pandas to polars across the whole codebase, migrate-first, and dropped pandas. Full phase details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

- [x] Phase 1: Primary Pipeline on Polars (4/4 plans) — completed 2026-06-07
- [x] Phase 2: Independent Pipelines on Polars (2/2 plans) — completed 2026-06-07
- [x] Phase 3: Test Suite on Polars (direct) — completed 2026-06-07
- [x] Phase 4: Pandas Removal & Manifest Finalization (direct) — completed 2026-06-07

</details>

### v1.1 Core Validation & Hardening (Phase 5)

- [x] **Phase 5: Core Validation & Hardening** — direct-execution: locked the sweep kernel (`analyze_event`) under direct tests, fixed the two real validity bugs, and cleared hygiene debt without changing the methodology logic. (9/9 requirements, 29/29 tests green, 2026-06-07.)

## Phase Details

### Phase 5: Core Validation & Hardening
**Goal**: The sweep-methodology core is provably correct under direct tests, the two real validity bugs are fixed, and hygiene/quality debt is cleared — all without altering the methodology logic itself.
**Depends on**: Phase 4 (v1.0 Polars Migration complete)
**Requirements**: TEST-01, TEST-02, TEST-03, VALID-01, VALID-02, VALID-03, HYG-01, HYG-02, QUAL-01
**Execution**: Direct — each requirement runs as a single direct GSD fix (atomic commit). No per-phase discuss/plan/execute ceremony (mirrors v1.0 Phases 3 & 4). Emergent issues found while doing the work are in scope to fix on the spot.
**Success Criteria** (what must be TRUE):
  1. `analyze_event` sweep detection (high/low sweep identification + reversal-vs-momentum-box resolution), `main.py` session-context/gap features, and `injection.py` lookup/range functions are all covered by passing direct tests on controlled fixtures — not just the loaders around them. *(TEST-01, TEST-02, TEST-03)*
  2. The prior-session close is resolved correctly without the hardcoded `16:59` ET magic minute, so short/holiday sessions no longer silently miss. *(VALID-01)*
  3. Events skipped for a missing release or required future candle are counted and reported in a run summary line instead of being silently dropped, and the legacy `loc`/`iloc` closure is recorded (no `.loc`/`.iloc` remain repo-wide; existing regression test stays green). *(VALID-02, VALID-03)*
  4. No stale root-level PNGs remain — charts live under `charts/` with generated outputs gitignored — and `README.md` accurately reflects the polars era (no stale pandas/pyarrow references, correct run instructions and script inventory). *(HYG-01, HYG-02)*
  5. The global `warnings.filterwarnings("ignore")` in `causal_analysis.py` is replaced by narrowly-scoped suppression (only the specific sklearn warning, only around the emitting call), and the full pytest suite is green. *(QUAL-01)*
**Plans**: Direct (no per-phase plans)

## Progress

| Phase                                      | Milestone | Plans Complete | Status   | Completed  |
| ------------------------------------------ | --------- | -------------- | -------- | ---------- |
| 1. Primary Pipeline on Polars              | v1.0      | 4/4            | Complete | 2026-06-07 |
| 2. Independent Pipelines on Polars         | v1.0      | 2/2            | Complete | 2026-06-07 |
| 3. Test Suite on Polars                    | v1.0      | direct         | Complete | 2026-06-07 |
| 4. Pandas Removal & Manifest Finalization  | v1.0      | direct         | Complete | 2026-06-07 |
| 5. Core Validation & Hardening             | v1.1      | direct         | Complete | 2026-06-07 |
