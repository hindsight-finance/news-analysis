---
phase: 1
slug: primary-pipeline-on-polars
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-07
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

**Critical caveat (from RESEARCH.md):** the existing pytest suite is **pandas-based** and asserts
pandas-only semantics (`.loc`, `.attrs`, `pd.Timestamp.value`) on the very functions being ported.
It **will go red under the Phase-1 port by design** — porting it is TEST-01 (Phase 3). Therefore the
Phase-1 validation signal is **integration smoke** (run the 3 scripts against real `data/`, assert the
data contract + chart/CSV outputs), **not** the unit suite. Do **not** gate Phase 1 on `tests/`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 present, but Phase-1 signal is **integration smoke** (shell one-liners), not the pandas unit suite |
| **Config file** | none (`pytest.ini`/`pyproject.toml`/`setup.cfg` absent) — run from project root |
| **Quick run command** | per-script smoke (see Per-Task map) — e.g. `python3 main.py` + 21-col contract assert |
| **Full suite command** | `python3 main.py && python3 exploration.py && python3 causal_analysis.py` + no-pandas grep |
| **Estimated runtime** | ~minutes (full `nq_1m.parquet` load dominates; smoke is I/O-bound) |

---

## Sampling Rate

- **After every task commit:** Run the relevant per-script smoke one-liner for the file touched.
- **After every plan wave:** Run the full pipeline + `! grep -nE "import pandas" main.py exploration.py causal_analysis.py`.
- **Before `/gsd-verify-work`:** Full pipeline runs end-to-end on polars; contract schema asserts pass; zero `import pandas` in the three files.
- **Max feedback latency:** one full-pipeline run.

---

## Per-Task Verification Map

> Requirement-level map (task IDs assigned by the planner). Each ported script's smoke check is the
> automated signal. The pandas unit suite is **expected red** until Phase 3 — excluded from the gate.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| ENV-02 | polars reads raw inputs natively, no pandas in read path | smoke | `python3 -c "import polars as pl; pl.read_parquet('data/nq_1m.parquet', use_pyarrow=False); pl.read_parquet('data/economic_events.parquet', use_pyarrow=False); print('native read OK')"` | ✅ one-liner | ⬜ pending |
| MIGRATE-01 | `main.py` on polars writes the 21-col contract, methodology intact | integration smoke + schema assert | `python3 main.py` then assert `pl.read_parquet('data/sweep_analysis_results.parquet')` schema == pinned `CONTRACT_SCHEMA` (21 cols; `event_datetime`=Datetime(ns, UTC); `release_volume`=Int64), height > 0 | ❌ W0 (smoke harness) | ⬜ pending |
| MIGRATE-02 | `exploration.py` on polars writes charts + summary CSV | integration smoke | `python3 exploration.py && test -f charts/exploration/summary_by_event.csv && ls charts/exploration/*.png` | ❌ W0 | ⬜ pending |
| MIGRATE-03 | `causal_analysis.py` on polars, models trained via explicit polars→numpy, writes CSV + charts | integration smoke | `python3 causal_analysis.py && test -f charts/causal/event_stats.csv && ls charts/causal/*.png` | ❌ W0 | ⬜ pending |
| (all) | no pandas import in the three ported scripts | static check | `! grep -nE "^[[:space:]]*(import pandas|from pandas)" main.py exploration.py causal_analysis.py` | ✅ grep | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] A minimal **integration smoke harness** (shell script or a tiny `pytest` kept separate from the pandas `tests/`) that runs the three scripts against real `data/` and asserts: contract schema == 21-col `CONTRACT_SCHEMA`, non-zero row count, expected chart/CSV files exist. This is the Phase-1 signal because the existing unit suite is pandas-bound and Phase-3-owned.
- [ ] No framework install needed (pytest 9.0.2 present); no `conftest.py` exists and none is required for smoke.
- [ ] Do **not** port `tests/` here — TEST-01 = Phase 3.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sweep methodology ported faithfully (no output-parity diff by milestone decision) | MIGRATE-01 | Per REQUIREMENTS.md the port is trusted, not diffed against historical pandas numbers; numeric drift from the engine swap is acceptable | Spot-inspect a handful of rows of `sweep_analysis_results.parquet` for sane sweep direction / first-target / MAE values; confirm the numpy methodology kernel (main.py sweep block) is preserved verbatim |

*Chart visuals are not pixel-diffed — existence + non-empty is the automated bar.*

---

## Validation Sign-Off

- [ ] All requirements have a smoke/static automated command or a Wave 0 harness dependency
- [ ] Sampling continuity: every ported script has a per-commit smoke check
- [ ] Wave 0 covers the integration smoke harness gap
- [ ] No watch-mode flags
- [ ] Phase-1 gate excludes the pandas unit suite (expected red until Phase 3)
- [ ] `nyquist_compliant: true` set in frontmatter once the planner maps task IDs to these checks

**Approval:** pending
