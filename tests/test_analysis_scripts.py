from pathlib import Path
import pandas as pd

from exploration import build_summary_table, compute_win_rates
from causal_analysis import build_features


def sample_results() -> pd.DataFrame:
    return pd.DataFrame(
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
    row_b = rates[rates["event_type"] == "B"].iloc[0]
    assert row_b["total"] == 2
    assert row_b["resolved"] == 1
    assert row_b["momentum_rate"] == 100.0
    assert row_b["reversal_rate"] == 0.0


def test_build_summary_table_orders_by_edge():
    summary = build_summary_table(sample_results())
    assert list(summary.columns) == [
        "event_type",
        "n",
        "momentum_rate",
        "reversal_rate",
        "edge",
        "median_mae",
        "avg_time_to_sweep",
        "avg_range_pct",
    ]
    assert summary.iloc[0]["event_type"] == "B"
    assert summary.iloc[0]["edge"] == 50.0


def test_build_features_encodes_missing_context_as_zero_or_minus_one():
    df = sample_results()
    resolved = df[df["first_target_hit"].notna()].copy()
    resolved["target"] = (resolved["first_target_hit"] == "box").astype(int)
    features, target = build_features(resolved)
    assert len(features) == 3
    assert target.tolist() == [1, 0, 1]
    assert features.loc[1, "pre_candle_range_pct"] == 0
    assert features.loc[1, "gap_6pm_pct"] == 0
    assert features.loc[2, "gap_direction_encoded"] == -1

from exploration import qcut_with_fallback_labels


def test_qcut_with_fallback_labels_handles_duplicate_bin_edges():
    result = qcut_with_fallback_labels(pd.Series([1, 1, 1, 2, 3]), 4, ["Q1", "Q2", "Q3", "Q4"])
    assert len(result) == 5
    assert result.isna().sum() == 0
