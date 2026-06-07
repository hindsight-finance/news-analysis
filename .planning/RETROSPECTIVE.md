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

## Milestone: v1.1 — Core Validation & Hardening

**Shipped:** 2026-06-07
**Phases:** 1 (Phase 5, direct) | **Plans:** 0 on disk (direct fixes) | **Sessions:** 1 (2026-06-07)

### What Was Built
- Direct tests for the sweep-methodology core that v1.0 had ported untested: `analyze_event` high/low sweep + reversal-vs-momentum resolution (TEST-01), `main.py` session-context/gap features (TEST-02), and `injection.py` lookup/range functions (TEST-03). Suite grew 13 → 29 (16 new), all green.
- Two real validity fixes: prior-session close resolved without the hardcoded `16:59` ET magic minute via `get_last_candle_before` (VALID-01); dropped events (missing release/future candle) now counted via an optional `drops` Counter and reported in a `main()` summary line instead of being silently skipped (VALID-02).
- `loc`/`iloc` bug confirmed already eliminated by the v1.0 migration and closed with no code change (VALID-03).
- Hygiene/quality: 4 stale root PNGs removed + `/*.png` gitignored (HYG-01); `causal_analysis.py`'s global `filterwarnings("ignore")` narrowed to the specific sklearn warnings around the emitting call (QUAL-01); README refreshed for the polars era (HYG-02).

### What Worked
- **Harden-after-migrate sequencing.** Adding the direct test net immediately after the trusted v1.0 port closed the one real risk that port took on (untested kernel) — and the new tests passed against the ported code, retroactively validating the migrate-first bet.
- **Direct execution again fit the work.** Nine small, well-understood fixes ran as atomic commits with no per-phase ceremony — the same pattern that worked for v1.0 Phases 3 & 4.
- **Smoke-run as the methodology guardrail.** Re-running `main.py` and checking the core numbers (80.6% / 52.2% / 45.7%) confirmed the hardening did not disturb the methodology.
- **Triage-and-close as a first-class outcome.** VALID-03 was resolved by *verifying* the migration had already fixed it and recording the closure — cheaper and more honest than a speculative re-fix.

### What Was Inefficient
- Same direct-execution tooling gap as v1.0: with no on-disk plans/summaries, `roadmap.analyze` reports the phase at 0% / progress 0% even though `disk_status` is `complete` — readiness has to be judged from requirements + tests, not the progress number.
- The milestone-archive CLI (`milestone.complete`) adds little value for direct-execution milestones (no SUMMARY.md files to harvest), so archives were authored by hand for full control.

### Patterns Established
- **Optional `drops` Counter threaded into a kernel function** as the idiom for surfacing silently-skipped records without changing the happy path.
- **`get_last_candle_before`** as the way to resolve a prior-session boundary, replacing wall-clock magic minutes that break on short/holiday sessions.
- **Scoped warning suppression** (specific warning category, wrapped around the emitting call) instead of a module-level global filter.
- **Confirm-and-close** for bugs a prior milestone already eliminated: prove it with a grep + a guarding test, record the closure, ship no code.

### Key Lessons
1. Migrate-first only pays off if the test net actually follows — v1.1 is where that debt was honoured, and it came back green, closing the loop the v1.0 retrospective opened.
2. For lean hardening milestones, hand-authored archives beat the SDK archiver: the CLI assumes SUMMARY.md files that direct execution never produces.
3. A validity item can legitimately resolve to "already fixed, here's the proof" — budget triage outcomes, not just code outcomes.

### Cost Observations
- Model mix: predominantly opus (quality model profile).
- Sessions: 1 (2026-06-07); ~8 atomic fix commits.
- Notable: full milestone (9 requirements, 16 new tests) completed in a single short session via direct fixes.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 1 | 4 | First GSD milestone; migrate-first with a smoke-harness gate; later phases run directly to drop ceremony |
| v1.1 | 1 | 1 | Harden-after-migrate; whole milestone run as direct fixes; hand-authored archives over the SDK archiver |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 13 passing | partial (data loading, forward-returns math, exploration/causal utils) | dropped pandas + pyarrow; net dependency reduction |
| v1.1 | 29 passing (+16) | core now direct-tested (`analyze_event`, session-context/gap, `injection.py` lookup/range) | none — hardening milestone |

### Top Lessons (Verified Across Milestones)

1. **Direct execution fits mechanical phases — but breaks progress tooling.** Both milestones ran their mechanical phases directly; both saw `roadmap.analyze` undercount progress (no on-disk plans/summaries). Judge readiness by requirements + green tests, not the progress percentage.
2. **Migrate-first is only safe when the test net follows.** v1.0 took the untested-port risk; v1.1 paid it down and the suite came back green — the bet only closes when hardening actually happens.
3. **The quality model profile (opus) cleared both milestones in single sessions.** Small, well-scoped, single-session milestones are the emerging cadence for this project.
