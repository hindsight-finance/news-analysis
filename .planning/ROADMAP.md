# Roadmap: News Analysis

## Milestones

- ✅ **v1.0 Polars Migration** — Phases 1-4 (shipped 2026-06-07) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Core Validation & Hardening** — Phase 5 (shipped 2026-06-07) — [archive](milestones/v1.1-ROADMAP.md)

_No milestone currently in progress. Run `/gsd-new-milestone` to start the next cycle._

## Phases

<details>
<summary>✅ v1.0 Polars Migration (Phases 1-4) — SHIPPED 2026-06-07</summary>

Swapped the DataFrame engine from pandas to polars across the whole codebase, migrate-first, and dropped pandas. Full phase details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

- [x] Phase 1: Primary Pipeline on Polars (4/4 plans) — completed 2026-06-07
- [x] Phase 2: Independent Pipelines on Polars (2/2 plans) — completed 2026-06-07
- [x] Phase 3: Test Suite on Polars (direct) — completed 2026-06-07
- [x] Phase 4: Pandas Removal & Manifest Finalization (direct) — completed 2026-06-07

</details>

<details>
<summary>✅ v1.1 Core Validation & Hardening (Phase 5) — SHIPPED 2026-06-07</summary>

Locked the sweep kernel (`analyze_event`) under direct tests, fixed the two real validity bugs, and cleared hygiene/quality debt — direct-execution, without changing the methodology logic. Full phase details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

- [x] Phase 5: Core Validation & Hardening (direct) — completed 2026-06-07 (9/9 requirements, 29/29 tests green)

</details>

## Progress

| Phase                                      | Milestone | Plans Complete | Status   | Completed  |
| ------------------------------------------ | --------- | -------------- | -------- | ---------- |
| 1. Primary Pipeline on Polars              | v1.0      | 4/4            | Complete | 2026-06-07 |
| 2. Independent Pipelines on Polars         | v1.0      | 2/2            | Complete | 2026-06-07 |
| 3. Test Suite on Polars                    | v1.0      | direct         | Complete | 2026-06-07 |
| 4. Pandas Removal & Manifest Finalization  | v1.0      | direct         | Complete | 2026-06-07 |
| 5. Core Validation & Hardening             | v1.1      | direct         | Complete | 2026-06-07 |
