from datetime import datetime, timezone

import numpy as np
import polars as pl

import main


def test_load_data_accepts_lowercase_utc_schema_and_adds_et(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events = pl.DataFrame(
        {
            "datetime_utc": [datetime(2010, 6, 7, 12, 30)],
            "currency": ["USD"],
            "impact": ["High"],
            "title": ["US Test Event"],
            "id": [1],
            "leaked": [False],
        }
    ).with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC"))
    nq = pl.DataFrame(
        {
            "datetime_utc": [datetime(2010, 6, 7, 12, 30)],
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [10],
        }
    ).with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC"))
    events.write_parquet(data_dir / "economic_events.parquet")
    nq.write_parquet(data_dir / "nq_1m.parquet")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)

    loaded_events, loaded_nq, _ = main.load_data()

    assert loaded_events.row(0, named=True)["datetime_utc"] == datetime(2010, 6, 7, 12, 30, tzinfo=timezone.utc)
    assert loaded_nq.row(0, named=True)["DateTime_UTC"] == datetime(2010, 6, 7, 12, 30, tzinfo=timezone.utc)
    assert loaded_nq.row(0, named=True)["DateTime_ET"] == datetime(2010, 6, 7, 8, 30)


def test_load_data_builds_ns_lookup_arrays(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pl.DataFrame(
        {"datetime_utc": [datetime(2010, 6, 7, 12, 30)], "title": ["US Test Event"]}
    ).with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC")).write_parquet(
        data_dir / "economic_events.parquet"
    )
    pl.DataFrame(
        {
            "datetime_utc": [datetime(2010, 6, 7, 12, 30)],
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [10],
        }
    ).with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC")).write_parquet(
        data_dir / "nq_1m.parquet"
    )
    monkeypatch.setattr(main, "DATA_DIR", data_dir)

    _, _, lookups = main.load_data()

    # ns-int64 arrays, one row each; UTC 12:30 is 4h ahead of naive-ET 08:30.
    assert len(lookups["utc_values"]) == 1
    assert len(lookups["et_values"]) == 1
    assert lookups["utc_values"][0] - lookups["et_values"][0] == 4 * 3600 * 10**9


def test_get_candles_until_eod_uses_lookup_without_timezone_compare_error():
    nq = pl.DataFrame(
        {
            "DateTime_UTC": [
                datetime(2010, 6, 7, 12, 30),
                datetime(2010, 6, 7, 12, 31),
                datetime(2010, 6, 7, 20, 0),
                datetime(2010, 6, 7, 20, 1),
            ],
            "DateTime_ET": [
                datetime(2010, 6, 7, 8, 30),
                datetime(2010, 6, 7, 8, 31),
                datetime(2010, 6, 7, 16, 0),
                datetime(2010, 6, 7, 16, 1),
            ],
            "Open": [1.0, 2.0, 3.0, 4.0],
            "High": [1.0, 2.0, 3.0, 4.0],
            "Low": [1.0, 2.0, 3.0, 4.0],
            "Close": [1.0, 2.0, 3.0, 4.0],
            "Volume": [1, 1, 1, 1],
        }
    ).with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC")).sort("DateTime_UTC")

    # Mirror load_data()'s ns-int64 lookup arrays (no per-frame metadata in polars).
    utc_values = nq.get_column("DateTime_UTC").to_numpy().astype("datetime64[ns]").astype("int64")
    et_values = nq.get_column("DateTime_ET").to_numpy().astype("datetime64[ns]").astype("int64")
    lookups = {"utc_values": utc_values, "et_values": et_values}

    result = main.get_candles_until_eod(nq, lookups, datetime(2010, 6, 7, 12, 30, tzinfo=timezone.utc))

    assert result.get_column("DateTime_ET").to_list() == [
        datetime(2010, 6, 7, 8, 31),
        datetime(2010, 6, 7, 16, 0),
    ]
