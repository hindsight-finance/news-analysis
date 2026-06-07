"""Direct tests for injection.py's previously-untested lookup and range functions.

Frames mirror injection.load_data()'s contract: DateTime_UTC is tz-aware UTC at ns
precision so the pure-polars exact-match join/lookup keys line up (D-05).
"""

from datetime import datetime, timezone

import polars as pl

import injection


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def _nq(rows: list[dict]) -> pl.DataFrame:
    return (
        pl.DataFrame(
            {
                "DateTime_UTC": [r["utc"] for r in rows],
                "Open": [float(r["o"]) for r in rows],
                "High": [float(r["h"]) for r in rows],
                "Low": [float(r["l"]) for r in rows],
                "Close": [float(r.get("c", r["o"])) for r in rows],
                "Volume": [int(r["v"]) for r in rows],
            }
        )
        .with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC").dt.cast_time_unit("ns"))
        .sort("DateTime_UTC")
    )


def _events(times: list[datetime]) -> pl.DataFrame:
    return pl.DataFrame({"datetime_utc": times, "title": ["US Test"] * len(times)}).with_columns(
        pl.col("datetime_utc").dt.replace_time_zone("UTC").dt.cast_time_unit("ns")
    )


def test_calculate_percentage_range():
    assert injection.calculate_percentage_range(110, 90, 100) == 20.0


def test_build_release_index_maps_event_times_to_row_indices():
    nq = _nq(
        [
            {"utc": _utc(2024, 1, 2, 13, 30), "o": 100, "h": 102, "l": 99, "v": 10},
            {"utc": _utc(2024, 1, 2, 13, 31), "o": 100, "h": 101, "l": 99, "v": 11},
            {"utc": _utc(2024, 1, 2, 13, 35), "o": 100, "h": 103, "l": 98, "v": 12},
        ]
    )
    events = _events([_utc(2024, 1, 2, 13, 30), _utc(2024, 1, 2, 13, 35)])

    ts_to_idx = injection.build_release_index(events, nq)

    assert ts_to_idx[_utc(2024, 1, 2, 13, 30)] == 0
    assert ts_to_idx[_utc(2024, 1, 2, 13, 35)] == 2
    assert _utc(2024, 1, 2, 13, 31) not in ts_to_idx  # not an event time


def test_get_release_candle_data_returns_range_and_volume():
    nq = _nq([{"utc": _utc(2024, 1, 2, 13, 30), "o": 100, "h": 102, "l": 99, "v": 10}])
    ts_to_idx = injection.build_release_index(_events([_utc(2024, 1, 2, 13, 30)]), nq)

    result = injection.get_release_candle_data(nq, ts_to_idx, _utc(2024, 1, 2, 13, 30))

    assert result is not None
    pct_range, volume = result
    assert round(pct_range, 4) == 3.0  # (102 - 99) / 100 * 100
    assert volume == 10


def test_get_release_candle_data_returns_none_on_miss():
    nq = _nq([{"utc": _utc(2024, 1, 2, 13, 30), "o": 100, "h": 102, "l": 99, "v": 10}])
    ts_to_idx = injection.build_release_index(_events([_utc(2024, 1, 2, 13, 30)]), nq)

    assert injection.get_release_candle_data(nq, ts_to_idx, _utc(2024, 1, 2, 14, 0)) is None


def test_get_10min_range_uses_inclusive_time_window():
    # 10 one-minute candles; window max High = 105, min Low = 98, reference Open = 100.
    rows = []
    for minute in range(10):
        high = 105 if minute == 5 else 101
        low = 98 if minute == 5 else 99.5
        rows.append({"utc": _utc(2024, 1, 2, 13, 30 + minute), "o": 100, "h": high, "l": low, "v": 1})
    nq = _nq(rows)

    result = injection.get_10min_range(nq, _utc(2024, 1, 2, 13, 30))

    assert round(result, 4) == 7.0  # (105 - 98) / 100 * 100


def test_get_10min_range_returns_none_when_no_candles_in_window():
    nq = _nq([{"utc": _utc(2024, 1, 2, 13, 30), "o": 100, "h": 101, "l": 99, "v": 1}])
    assert injection.get_10min_range(nq, _utc(2024, 1, 3, 13, 30)) is None
