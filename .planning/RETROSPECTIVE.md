# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Polars Migration

**Shipped:** 2026-06-07
**Phases:** 4 | **Plans:** 6 | **Sessions:** 1 (2026-06-07)

### What Was Built
- All five analysis scripts (`main.py`, `exploration.py`, `causal_analysis.py`, `forward_returns.py`, `injection.py`) ported pandas → polars, sweep methodology logic preserved intact.
- A pinned 21-column `CONTRACT_SCHEMA` for `sweep_analysis_results.parquet` that kept the producer→consumer data contract stable across the engine swap.
- A pure-polars exact-match timestamp lookup (`build_timestamp_index`: `with_row_index` + inner-join) replacing `np.searchsorted` in `forward_returns.py` and the linear boolean-mask scan in `injection.py`.
- A single explicit `polars → numpy` boundary at the scikit-learn interface in `causal_analysis.py`.
- pytest suite ported to polars (13/13 green, zero `import pandas` in tests); pandas removed repo-wide; pinned, pandas-free, pyarrow-free `requirements.txt`.

### What Worked
- **Migrate-first paid off.** Porting the DataFrame layer before adding a unit-test net was fast, and the suite came back green after the port — the accepted methodology-integrity risk did not bite.
- **Contract-first sequencing.** Porting `main.py` together with its two consumers behind a pinned `CONTRACT_SCHEMA` meant the intermediate parquet contract never broke mid-migration.
- **Smoke harness as Phase-1 gate.** `smoke/phase1_smoke.py` gave a real validation signal while the pandas unit suite was expectedly red, de-risking the early ports.
- **Dropping ceremony where it added nothing.** Phases 3 (test port) and 4 (pandas removal) were mechanical and ran directly without per-phase GSD plans.

### What Was Inefficient
- STATE.md decision log accumulated several `[Phase ?]` entries with unresolved phase tags — minor metadata drift during fast execution.
- The milestone-complete SDK undercounted progress (50%) because Phases 3 & 4 had no on-disk summaries (done directly) — required a manual STATE.md correction.

### Patterns Established
- **Engine swap at the I/O boundary only:** keep numpy methodology kernels verbatim, port load/lookup/extract/write around them.
- **Pinned output schema** (`CONTRACT_SCHEMA`) to stop dict-inference dtype drift when writing parquet from polars.
- **`build_timestamp_index`** as the shared pure-polars exact-match lookup construct, reused across raw-data pipelines.
- **One explicit `.to_numpy()` boundary** at the scikit-learn `.fit()`/`cross_val_score` interface; capture `feature_names` before crossing it.

### Key Lessons
1. A trusted port (no output-parity diffing) is viable when the methodology logic is isolated and a fast test net follows — but only because the kernel was ported verbatim, not rewritten.
2. Directly-executed phases (no plans/summaries) confuse summary-count-based progress tooling; expect to hand-correct STATE.md frontmatter at milestone close.
3. Carrying the duplicated-utils debt forward (rather than fixing inline) kept the migration focused — STRUCT-01 is the natural first item for the next milestone.

### Cost Observations
- Model mix: predominantly opus (quality model profile).
- Sessions: 1 working day (2026-06-07); 52 total commits in repo history.
- Notable: full migration of 5 scripts + test suite completed in a single session via wave-based phase execution.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 1 | 4 | First GSD milestone; migrate-first with a smoke-harness gate; later phases run directly to drop ceremony |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 13 passing | partial (data loading, forward-returns math, exploration/causal utils) | dropped pandas + pyarrow; net dependency reduction |

### Top Lessons (Verified Across Milestones)

1. _(pending a second milestone to cross-validate)_
