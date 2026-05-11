from pathlib import Path

import pandas as pd

import main


def test_load_data_accepts_lowercase_utc_schema_and_adds_et(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    events = pd.DataFrame(
        {
            "datetime_utc": [pd.Timestamp("2010-06-07 12:30:00", tz="UTC")],
            "currency": ["USD"],
            "impact": ["High"],
            "title": ["US Test Event"],
            "id": [1],
            "leaked": [False],
        }
    )
    nq = pd.DataFrame(
        {
            "datetime_utc": [pd.Timestamp("2010-06-07 12:30:00", tz="UTC")],
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [10],
        }
    )
    events.to_parquet(data_dir / "economic_events.parquet")
    nq.to_parquet(data_dir / "nq_1m.parquet")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)

    loaded_events, loaded_nq = main.load_data()

    assert loaded_events.loc[0, "datetime_utc"] == pd.Timestamp("2010-06-07 12:30:00", tz="UTC")
    assert loaded_nq.loc[0, "DateTime_UTC"] == pd.Timestamp("2010-06-07 12:30:00", tz="UTC")
    assert loaded_nq.loc[0, "DateTime_ET"] == pd.Timestamp("2010-06-07 08:30:00")


def test_prepare_lookup_arrays_are_added_by_load_data(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame({"datetime_utc": [pd.Timestamp("2010-06-07 12:30:00", tz="UTC")], "title": ["US Test Event"]}).to_parquet(
        data_dir / "economic_events.parquet"
    )
    pd.DataFrame(
        {
            "datetime_utc": [pd.Timestamp("2010-06-07 12:30:00", tz="UTC")],
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [10],
        }
    ).to_parquet(data_dir / "nq_1m.parquet")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)

    _, loaded_nq = main.load_data()

    assert loaded_nq.attrs["utc_values"].tolist() == [pd.Timestamp("2010-06-07 12:30:00", tz="UTC").value]
    assert loaded_nq.attrs["et_values"].tolist() == [pd.Timestamp("2010-06-07 08:30:00").value]


def test_get_candles_until_eod_uses_lookup_without_timezone_compare_error():
    nq = pd.DataFrame(
        {
            "DateTime_UTC": pd.to_datetime(
                ["2010-06-07 12:30:00", "2010-06-07 12:31:00", "2010-06-07 20:00:00", "2010-06-07 20:01:00"], utc=True
            ),
            "DateTime_ET": pd.to_datetime(["2010-06-07 08:30:00", "2010-06-07 08:31:00", "2010-06-07 16:00:00", "2010-06-07 16:01:00"]),
            "Open": [1.0, 2.0, 3.0, 4.0],
            "High": [1.0, 2.0, 3.0, 4.0],
            "Low": [1.0, 2.0, 3.0, 4.0],
            "Close": [1.0, 2.0, 3.0, 4.0],
            "Volume": [1, 1, 1, 1],
        }
    )
    nq = main.add_lookup_tables(nq)

    result = main.get_candles_until_eod(nq, pd.Timestamp("2010-06-07 12:30:00", tz="UTC"))

    assert result["DateTime_ET"].tolist() == [pd.Timestamp("2010-06-07 08:31:00"), pd.Timestamp("2010-06-07 16:00:00")]
