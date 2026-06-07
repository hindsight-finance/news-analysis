import polars as pl

from exploration import build_summary_table, compute_win_rates
from causal_analysis import build_features


def sample_results() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "event_type": ["A", "A", "B", "B"],
            "release_time": ["08:30", "08:30", "10:00", "10:00"],
            "first_target_hit": ["box", "opposite", "box", None],
            "first_sweep": ["high", "low", "high", "low"],
            "range_pct": [0.1, 0.2, 0.3, 0.4],
            "mae_before_reversal": [1.0, 0.5, 2.0, 3.0],
            "time_to_first_sweep": [1.0, 2.0, 3.0, 4.0],
            "release_volume": [100, 200, 300, 400],
            "pre_candle_range_pct": [0.01, None, 0.03, 0.04],
            "pre_candle_volume": [10, None, 30, 40],
            "dist_from_midnight_open_pct": [0.1, None, -0.2, 0.3],
            "dist_from_6pm_open_pct": [0.2, 0.1, None, -0.1],
            "gap_6pm_pct": [0.01, None, 0.03, 0.04],
            "gap_6pm_direction": ["up", "down", "flat", None],
        }
    )


def test_compute_win_rates_counts_resolved_outcomes_only():
    rates = compute_win_rates(sample_results(), ["event_type"])
    row_b = rates.filter(pl.col("event_type") == "B").row(0, named=True)
    assert row_b["total"] == 2
    assert row_b["resolved"] == 1
    assert row_b["momentum_rate"] == 100.0
    assert row_b["reversal_rate"] == 0.0


def test_build_summary_table_orders_by_edge():
    summary = build_summary_table(sample_results())
    assert summary.columns == [
        "event_type",
        "n",
        "momentum_rate",
        "reversal_rate",
        "edge",
        "median_mae",
        "avg_time_to_sweep",
        "avg_range_pct",
    ]
    assert summary.row(0, named=True)["event_type"] == "B"
    assert summary.row(0, named=True)["edge"] == 50.0


def test_build_features_encodes_missing_context_as_zero_or_minus_one():
    resolved = sample_results().filter(pl.col("first_target_hit").is_not_null()).with_columns(
        (pl.col("first_target_hit") == "box").cast(pl.Int64).alias("target")
    )
    features, target = build_features(resolved)
    assert features.height == 3
    assert target.to_list() == [1, 0, 1]
    assert features.row(1, named=True)["pre_candle_range_pct"] == 0
    assert features.row(1, named=True)["gap_6pm_pct"] == 0
    assert features.row(2, named=True)["gap_direction_encoded"] == -1
