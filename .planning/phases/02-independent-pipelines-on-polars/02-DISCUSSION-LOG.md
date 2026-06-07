# Phase 2: Independent Pipelines on Polars - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-07
**Phase:** 2-Independent Pipelines on Polars
**Areas discussed:** Lookup mechanism, injection.py speed, injection.py conventions, Summary aggregations, Cross-script consistency

---

## Lookup mechanism (forward_returns.py)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror main.py | Keep numpy searchsorted fed from polars columns + threaded `lookups` dict (Phase-1 pattern). Pandas-free, proven, lowest risk. | |
| Pure-polars lookup | Replace searchsorted entirely with join_asof / with_row_index + filter. No numpy in lookup path. Bigger rewrite. | ✓ |
| You decide | Defer to research/planning. | |

**User's choice:** Pure-polars lookup
**Notes:** User preferred a true pure-polars lookup over reusing main.py's numpy pattern. Methodology landmine captured in CONTEXT.md: must preserve EXACT-match semantics (not join_asof/nearest) and precision/tz match on equality (µs→ns landmine in equality-join form).

---

## injection.py speed

| Option | Description | Selected |
|--------|-------------|----------|
| Faithful port | Translate linear boolean-mask scans to polars .filter(), preserve exact behavior. Migrate-first aligned, stays O(n)/event. | |
| Upgrade to fast lookup | Give injection.py the same fast indexed lookup as the other scripts. Fixes the documented anti-pattern. | ✓ |
| You decide | Defer to planning. | |

**User's choice:** Upgrade to fast lookup
**Notes:** Combined with the lookup-mechanism choice → injection.py gets the same pure-polars fast lookup as forward_returns.py. 10-min range must stay time-bounded (not positional +9 slice) to preserve gap behavior.

---

## injection.py conventions

| Option | Description | Selected |
|--------|-------------|----------|
| Add Agg only | Add matplotlib.use("Agg") before pyplot import; leave entry-point/structure alone. | ✓ |
| DataFrame-port only | Touch nothing but pandas→polars. Leaves injection headless-unsafe. | |
| Full alignment | Agg + run()/argparse + double quotes + future annotations. Overlaps deferred STRUCT-03. | |

**User's choice:** Add Agg only (Recommended)
**Notes:** run()/argparse restructure deferred to STRUCT-03 (Future milestone).

---

## Summary aggregations (forward_returns.py)

| Option | Description | Selected |
|--------|-------------|----------|
| Follow exploration.py | Reuse Phase-1 polars group_by/agg pattern: win_rate as (pl.col>0).mean()*100, quantiles via pl.col().quantile(). | ✓ |
| Discuss edge cases | Dig into NaN/flat-direction filtering, dropna semantics, quantile interpolation differences. | |
| You decide | Mechanical port following the established pattern. | |

**User's choice:** Follow exploration.py (Recommended)
**Notes:** Preserve the .notna() exclusion of flat-direction rows from normalized/path summaries.

---

## Cross-script consistency (clarifying follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Pure-polars for both | Both Phase-2 scripts use the same pure-polars lookup; main.py keeps its numpy pattern (re-port is out of scope). | ✓ |
| injection.py mirrors main.py | forward_returns goes pure-polars but injection reuses main.py's numpy pattern (two different mechanisms). | |
| Also re-port main.py | Convert main.py too for full convergence — flagged as Phase-1 rework / scope creep. | |

**User's choice:** Pure-polars for both (Recommended)
**Notes:** Accepted divergence: main.py is the lone numpy-searchsorted holdout. Re-porting main.py captured as a deferred idea.

## Claude's Discretion

- Exact pure-polars lookup construction (with_row_index + filter vs inner-join of a lookup-timestamps frame vs hybrid; whether to vectorize the per-event/horizon loop) — left to research/planning, constrained only by the D-04…D-07 methodology-integrity rules.

## Deferred Ideas

- Re-port main.py's lookup to pure-polars for full codebase uniformity — declined as Phase-1 rework.
- injection.py run()/argparse entry point + full convention alignment — STRUCT-03, deferred to post-migration.
- VALID-02 (report count of silently-skipped events) — remains deferred; keep silent skip behavior in both ports.
