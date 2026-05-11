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
    assert result["raw_mfe_pct"].round(2).tolist() == [1.98, 2.97]
    assert result["raw_mae_pct"].round(2).tolist() == [-0.99, -0.99]
    assert result["direction_normalized_mfe_pct"].round(2).tolist() == [1.98, 2.97]
    assert result["direction_normalized_mae_pct"].round(2).tolist() == [-0.99, -0.99]


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
    assert result["raw_mfe_pct"].round(2).tolist() == [1.0]
    assert result["raw_mae_pct"].round(2).tolist() == [-1.0]
    assert result["direction_normalized_mfe_pct"].round(2).tolist() == [1.0]
    assert result["direction_normalized_mae_pct"].round(2).tolist() == [-1.0]

from forward_returns import write_outputs


def test_write_outputs_creates_csv_and_expected_charts(tmp_path):
    df = pd.DataFrame(
        {
            "event_type": ["US Test", "US Test", "US Test", "US Test"],
            "event_datetime": pd.to_datetime(
                ["2024-01-02 13:30:00", "2024-01-03 13:30:00", "2024-01-02 13:30:00", "2024-01-03 13:30:00"], utc=True
            ),
            "horizon_minutes": [30, 30, 90, 90],
            "news_candle_direction": ["up", "down", "up", "down"],
            "raw_forward_return_pct": [1.0, -0.5, 2.0, -1.0],
            "direction_normalized_return_pct": [1.0, 0.5, 2.0, 1.0],
            "release_open": [100.0, 100.0, 100.0, 100.0],
            "release_close": [101.0, 99.0, 101.0, 99.0],
            "future_close": [102.01, 98.505, 103.02, 98.01],
            "window_high": [103.0, 101.0, 104.0, 102.0],
            "window_low": [100.0, 98.0, 99.0, 97.0],
            "raw_mfe_pct": [1.98, 2.02, 2.97, 3.03],
            "raw_mae_pct": [-0.99, -1.01, -1.98, -2.02],
            "direction_normalized_mfe_pct": [1.98, 1.01, 2.97, 2.02],
            "direction_normalized_mae_pct": [-0.99, -2.02, -1.98, -3.03],
        }
    )

    write_outputs(df, tmp_path)

    expected = {
        "forward_returns_by_event.csv",
        "forward_returns_30m_raw_by_direction.png",
        "forward_returns_90m_raw_by_direction.png",
        "forward_returns_30m_direction_normalized.png",
        "forward_returns_90m_direction_normalized.png",
        "forward_returns_30m_mae_mfe_by_direction.png",
        "forward_returns_90m_mae_mfe_by_direction.png",
        "forward_returns_30m_normalized_mae_mfe_scatter.png",
        "forward_returns_90m_normalized_mae_mfe_scatter.png",
    }
    assert expected == {p.name for p in tmp_path.iterdir()}


def test_default_horizons_include_intermediate_timeframes():
    from forward_returns import DEFAULT_HORIZONS

    assert DEFAULT_HORIZONS == (15, 30, 45, 60, 90)
