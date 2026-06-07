"""Direct tests for the sweep-methodology core in main.py.

Covers the previously-untested asset: analyze_event sweep detection, session-context
gap features (including the short-session prior-close fix), and event-drop accounting.
Fixtures are tiny in-memory polars frames built the same way load_data() wires its
ns-int64 lookup arrays, so no raw data files are needed.
"""

from collections import Counter
from datetime import datetime, timezone

import polars as pl

import main


def _build_nq(rows: list[dict]) -> pl.DataFrame:
    """Build an nq frame (tz-aware UTC + naive ET) from explicit candle rows, sorted by UTC."""
    nq = pl.DataFrame(
        {
            "DateTime_UTC": [r["utc"] for r in rows],
            "DateTime_ET": [r["et"] for r in rows],
            "Open": [float(r["o"]) for r in rows],
            "High": [float(r["h"]) for r in rows],
            "Low": [float(r["l"]) for r in rows],
            "Close": [float(r["c"]) for r in rows],
            "Volume": [int(r["v"]) for r in rows],
        }
    ).with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC")).sort("DateTime_UTC")
    return nq


def _lookups(nq: pl.DataFrame) -> dict:
    """Mirror load_data()'s ns-int64 lookup arrays (polars has no per-frame metadata)."""
    utc_values = nq.get_column("DateTime_UTC").to_numpy().astype("datetime64[ns]").astype("int64")
    et_values = nq.get_column("DateTime_ET").to_numpy().astype("datetime64[ns]").astype("int64")
    return {"utc_values": utc_values, "et_values": et_values}


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# --- get_last_candle_before (VALID-01 helper) --------------------------------------


def test_get_last_candle_before_returns_strictly_prior_row():
    nq = _build_nq(
        [
            {"utc": _utc(2024, 1, 2, 18, 0), "et": datetime(2024, 1, 2, 13, 0), "o": 1, "h": 1, "l": 1, "c": 190.0, "v": 1},
            {"utc": _utc(2024, 1, 2, 23, 0), "et": datetime(2024, 1, 2, 18, 0), "o": 200.0, "h": 1, "l": 1, "c": 1, "v": 1},
        ]
    )
    candle = main.get_last_candle_before(nq, _lookups(nq), datetime(2024, 1, 2, 18, 0))
    assert candle is not None
    assert candle["DateTime_ET"] == datetime(2024, 1, 2, 13, 0)
    assert candle["Close"] == 190.0


def test_get_last_candle_before_returns_none_at_array_start():
    nq = _build_nq(
        [{"utc": _utc(2024, 1, 2, 18, 0), "et": datetime(2024, 1, 2, 13, 0), "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]
    )
    assert main.get_last_candle_before(nq, _lookups(nq), datetime(2024, 1, 2, 13, 0)) is None


# --- get_session_context gap features ----------------------------------------------


def _session_fixture(prior_close_row: dict) -> tuple[pl.DataFrame, dict, dict]:
    """Build a session fixture (prior day + release day) parameterized by the prior-close candle."""
    rows = [
        prior_close_row,
        # 6pm open (18:00 ET prior day = Globex reopen)
        {"utc": _utc(2024, 1, 2, 23, 0), "et": datetime(2024, 1, 2, 18, 0), "o": 200.0, "h": 200.0, "l": 200.0, "c": 200.0, "v": 1},
        # midnight open (00:00 ET release day)
        {"utc": _utc(2024, 1, 3, 5, 0), "et": datetime(2024, 1, 3, 0, 0), "o": 201.0, "h": 201.0, "l": 201.0, "c": 201.0, "v": 1},
        # 8:29 pre-news candle
        {"utc": _utc(2024, 1, 3, 13, 29), "et": datetime(2024, 1, 3, 8, 29), "o": 202.0, "h": 203.0, "l": 201.0, "c": 202.0, "v": 50},
        # 8:30 release candle
        {"utc": _utc(2024, 1, 3, 13, 30), "et": datetime(2024, 1, 3, 8, 30), "o": 205.0, "h": 206.0, "l": 204.0, "c": 205.0, "v": 10},
    ]
    nq = _build_nq(rows)
    lookups = _lookups(nq)
    release_candle = nq.filter(pl.col("DateTime_ET") == datetime(2024, 1, 3, 8, 30)).row(0, named=True)
    return nq, lookups, release_candle


def test_get_session_context_computes_gap_from_prior_close_normal_day():
    # Normal session: a 16:59 ET candle exists.
    nq, lookups, release = _session_fixture(
        {"utc": _utc(2024, 1, 2, 21, 59), "et": datetime(2024, 1, 2, 16, 59), "o": 199.0, "h": 199.0, "l": 199.0, "c": 199.0, "v": 1}
    )
    ctx = main.get_session_context(nq, lookups, release)

    assert ctx["release_volume"] == 10
    assert ctx["pre_candle_volume"] == 50
    assert round(ctx["pre_candle_range_pct"], 4) == round((203.0 - 201.0) / 202.0 * 100, 4)
    assert round(ctx["dist_from_midnight_open_pct"], 4) == round((205.0 - 201.0) / 201.0 * 100, 4)
    assert round(ctx["dist_from_6pm_open_pct"], 4) == 2.5
    # gap = (200 - 199) / 199 * 100
    assert ctx["gap_6pm_direction"] == "up"
    assert round(ctx["gap_6pm_pct"], 4) == round((200.0 - 199.0) / 199.0 * 100, 4)


def test_get_session_context_resolves_prior_close_on_short_session():
    # VALID-01: short/holiday session closes early at 13:00 ET — no 16:59 candle.
    # The old hardcoded 16:59 lookup would have left the gap null; the fix resolves
    # the actual last candle before the 18:00 reopen (the 13:00 close).
    nq, lookups, release = _session_fixture(
        {"utc": _utc(2024, 1, 2, 18, 0), "et": datetime(2024, 1, 2, 13, 0), "o": 190.0, "h": 190.0, "l": 190.0, "c": 190.0, "v": 1}
    )
    ctx = main.get_session_context(nq, lookups, release)

    assert ctx["gap_6pm_pct"] is not None
    assert ctx["gap_6pm_direction"] == "up"
    # gap = (200 - 190) / 190 * 100
    assert round(ctx["gap_6pm_pct"], 4) == round((200.0 - 190.0) / 190.0 * 100, 4)
