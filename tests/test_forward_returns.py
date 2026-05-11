import pandas as pd

from forward_returns import build_forward_returns, candle_direction, direction_normalized_return


def test_candle_direction_labels_up_down_flat():
    assert candle_direction(100.0, 101.0) == "up"
    assert candle_direction(101.0, 100.0) == "down"
    assert candle_direction(100.0, 100.0) == "flat"


def test_direction_normalized_return_flips_down_candles_and_excludes_flat():
    assert direction_normalized_return(1.5, "up") == 1.5
    assert direction_normalized_return(1.5, "down") == -1.5
    assert pd.isna(direction_normalized_return(1.5, "flat"))


def test_build_forward_returns_computes_raw_and_normalized_returns():
    events = pd.DataFrame({"datetime_utc": [pd.Timestamp("2024-01-02 13:30:00", tz="UTC")], "title": ["US Test"]})
    nq = pd.DataFrame(
        {
            "datetime_utc": pd.to_datetime(
                ["2024-01-02 13:30:00", "2024-01-02 14:00:00", "2024-01-02 15:00:00"], utc=True
            ),
            "Open": [100.0, 101.0, 102.0],
            "High": [102.0, 103.0, 104.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [101.0, 103.02, 98.98],
            "Volume": [10, 11, 12],
        }
    )

    result = build_forward_returns(events, nq, horizons=(30, 90))

    assert result["horizon_minutes"].tolist() == [30, 90]
    assert result["news_candle_direction"].tolist() == ["up", "up"]
    assert result["raw_forward_return_pct"].round(2).tolist() == [2.0, -2.0]
    assert result["direction_normalized_return_pct"].round(2).tolist() == [2.0, -2.0]


def test_build_forward_returns_skips_missing_future_candle():
    events = pd.DataFrame({"datetime_utc": [pd.Timestamp("2024-01-02 13:30:00", tz="UTC")], "title": ["US Test"]})
    nq = pd.DataFrame(
        {
            "datetime_utc": pd.to_datetime(["2024-01-02 13:30:00", "2024-01-02 14:00:00"], utc=True),
            "Open": [101.0, 100.0],
            "High": [102.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.0, 99.0],
            "Volume": [10, 11],
        }
    )

    result = build_forward_returns(events, nq, horizons=(30, 90))

    assert result["horizon_minutes"].tolist() == [30]
    assert result["news_candle_direction"].tolist() == ["down"]
    assert result["raw_forward_return_pct"].round(2).tolist() == [-1.0]
    assert result["direction_normalized_return_pct"].round(2).tolist() == [1.0]
