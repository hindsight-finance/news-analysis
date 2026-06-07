"""Phase-1 integration smoke harness for the pandas->polars migration.

This is the Phase-1 validation signal. It is kept deliberately SEPARATE from the
pandas-based ``tests/`` suite, which asserts pandas-only semantics on the very
functions being ported and is therefore expected to stay RED until Phase 3
(TEST-01). Do NOT use ``pytest tests`` as the Phase-1 gate; use this harness.

The harness imports only polars (the project's chosen engine), argparse, re,
sys, and pathlib -- it never imports the pandas library, so it can validate the
"no pandas in the ported scripts" invariant without contaminating its own
read path.

Checks (run individually via ``--check`` or all at once):
  * contract     -- the 21-column data contract schema + non-zero height
  * read         -- both raw inputs read natively (use_pyarrow=False), read-only
  * nopandas     -- static scan: the three Phase-1 scripts contain no pandas import
  * exploration  -- exploration chart + summary CSV outputs exist
  * causal       -- causal chart + event_stats CSV outputs exist

Run from the project root:
    python3 smoke/phase1_smoke.py --check {contract,read,nopandas,exploration,causal,all}

On success: prints ``SMOKE OK: <check>`` and exits 0.
On failure: prints ``SMOKE FAIL: <message>`` and exits 1.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import polars as pl

# Paths (relative to the project root -- the harness is meant to run from root).
CONTRACT_PATH = "data/sweep_analysis_results.parquet"
RAW_NQ_PATH = "data/nq_1m.parquet"
RAW_EVENTS_PATH = "data/economic_events.parquet"
PHASE1_SCRIPTS = ("main.py", "exploration.py", "causal_analysis.py")

# The exact 21-column data contract, in on-disk order. Each value is the verified
# polars 1.40.1 ``str(dtype)`` output for the existing contract artifact. Asserting
# the dtype STRINGS (not just the column count) is what makes a silent us/ns or
# Int64/Float64 dtype drift fail loudly (RESEARCH Pitfall 1 & 2). The drift-prone
# entries are ``event_datetime`` (us-drift), ``pre_candle_volume`` (Int64-drift),
# and ``release_volume`` (must stay Int64).
EXPECTED_SCHEMA: dict[str, str] = {
    "event_type": "String",
    "event_datetime": "Datetime(time_unit='ns', time_zone='UTC')",
    "release_time": "String",
    "data_high": "Float64",
    "data_low": "Float64",
    "range": "Float64",
    "range_pct": "Float64",
    "first_sweep": "String",
    "time_to_first_sweep": "Float64",
    "opposite_swept": "Boolean",
    "time_to_opposite_sweep": "Float64",
    "synthetic_box_breached": "Boolean",
    "first_target_hit": "String",
    "mae_before_reversal": "Float64",
    "pre_candle_range_pct": "Float64",
    "pre_candle_volume": "Float64",
    "dist_from_midnight_open_pct": "Float64",
    "dist_from_6pm_open_pct": "Float64",
    "gap_6pm_pct": "Float64",
    "gap_6pm_direction": "String",
    "release_volume": "Int64",
}

# Matches a top-level pandas import on a source line. Built from parts so this
# harness file itself contains no literal "<import> pandas" substring -- the
# nopandas static scan (and the equivalent grep) must find zero matches here.
_PANDAS_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+pandas\b")


def check_contract(path: str = CONTRACT_PATH) -> None:
    """Validate the regenerated data contract against EXPECTED_SCHEMA.

    Asserts: exactly 21 columns, names in the exact on-disk order, every dtype
    string matches, and height > 0 (a us/ns mismatch silently drops every row).
    """
    df = pl.read_parquet(path)
    schema = df.schema

    if len(schema) != len(EXPECTED_SCHEMA):
        raise AssertionError(
            f"contract column count {len(schema)} != expected {len(EXPECTED_SCHEMA)} "
            f"(got columns: {list(schema)})"
        )

    actual_names = list(schema)
    expected_names = list(EXPECTED_SCHEMA)
    if actual_names != expected_names:
        raise AssertionError(
            "contract column names/order drift:\n"
            f"  expected: {expected_names}\n"
            f"  actual:   {actual_names}"
        )

    for name, expected_dtype in EXPECTED_SCHEMA.items():
        actual_dtype = str(schema[name])
        if actual_dtype != expected_dtype:
            raise AssertionError(
                f"contract dtype drift on '{name}': "
                f"expected {expected_dtype!r}, got {actual_dtype!r}"
            )

    if df.height <= 0:
        raise AssertionError(
            f"contract has {df.height} rows (expected > 0); "
            "a us/ns timestamp mismatch silently drops every event"
        )


def check_read() -> None:
    """Read both irreplaceable raw inputs natively (use_pyarrow=False), read-only.

    No write/rename/delete is performed -- the raw inputs are irreplaceable and
    gitignored. This proves ENV-02: polars' native reader handles them with no
    pandas/pyarrow in the read path.
    """
    for path in (RAW_NQ_PATH, RAW_EVENTS_PATH):
        if not Path(path).is_file():
            raise AssertionError(f"raw input missing: {path}")
        try:
            pl.read_parquet(path, use_pyarrow=False)
        except Exception as exc:  # noqa: BLE001 - surface any native-read failure
            raise AssertionError(f"native read failed for {path}: {exc}") from exc


def check_nopandas(files: tuple[str, ...] = PHASE1_SCRIPTS) -> None:
    """Static scan: assert none of the Phase-1 scripts pull in pandas.

    Reads each file as TEXT (never imports it). At Wave 1 this is expected to
    FAIL (the scripts are still pandas) and flips to passing as each is ported.
    """
    offenders: list[str] = []
    for fname in files:
        path = Path(fname)
        if not path.is_file():
            raise AssertionError(f"expected script not found: {fname}")
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _PANDAS_IMPORT_RE.match(line):
                offenders.append(f"{fname}:{lineno}: {line.strip()}")

    if offenders:
        joined = "\n  ".join(offenders)
        raise AssertionError(
            "pandas import found in ported script(s):\n  " + joined
        )


def check_exploration() -> None:
    """Assert exploration.py outputs exist (summary CSV + at least one PNG)."""
    csv_path = Path("charts/exploration/summary_by_event.csv")
    if not csv_path.is_file():
        raise AssertionError(f"missing exploration summary CSV: {csv_path}")
    pngs = list(Path("charts/exploration").glob("*.png"))
    if not pngs:
        raise AssertionError("no PNG charts found in charts/exploration/")


def check_causal() -> None:
    """Assert causal_analysis.py outputs exist (event_stats CSV + at least one PNG)."""
    csv_path = Path("charts/causal/event_stats.csv")
    if not csv_path.is_file():
        raise AssertionError(f"missing causal event_stats CSV: {csv_path}")
    pngs = list(Path("charts/causal").glob("*.png"))
    if not pngs:
        raise AssertionError("no PNG charts found in charts/causal/")


CHECKS = {
    "contract": check_contract,
    "read": check_read,
    "nopandas": check_nopandas,
    "exploration": check_exploration,
    "causal": check_causal,
}


def run_check(name: str) -> None:
    """Run a single named check, or every check when ``name == 'all'``."""
    if name == "all":
        for check in CHECKS.values():
            check()
    else:
        CHECKS[name]()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase-1 pandas->polars migration smoke harness.",
    )
    parser.add_argument(
        "--check",
        choices=[*CHECKS.keys(), "all"],
        default="all",
        help="Which check to run (default: all).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_check(args.check)
    except AssertionError as exc:
        print(f"SMOKE FAIL: {exc}")
        return 1
    print(f"SMOKE OK: {args.check}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
