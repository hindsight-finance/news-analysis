"""
News Event Sweep Analysis - Exploration

Script version of exploration.ipynb. Reads sweep analysis results, prints summary
statistics, and writes exploration charts to an output directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl


DEFAULT_INPUT = Path(__file__).parent / "data" / "sweep_analysis_results.parquet"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "charts" / "exploration"


def compute_win_rates(df: pl.DataFrame, group_cols: list[str], min_count: int = 0) -> pl.DataFrame:
    """Compute momentum/reversal rates for grouped sweep outcomes.

    Returns a polars DataFrame with the group columns plus:
    ``total``, ``momentum_wins``, ``reversal_wins``, ``resolved``,
    ``momentum_rate``, ``reversal_rate`` (rates are null when ``resolved == 0``).
    polars ``group_by`` keeps null groups by default, matching the old
    pandas ``dropna=False``.
    """
    return (
        df.group_by(group_cols)
        .agg(
            pl.len().alias("total"),
            (pl.col("first_target_hit") == "box").sum().alias("momentum_wins"),
            (pl.col("first_target_hit") == "opposite").sum().alias("reversal_wins"),
        )
        .with_columns(
            (pl.col("momentum_wins") + pl.col("reversal_wins")).alias("resolved")
        )
        .filter(pl.col("total") >= min_count)
        .with_columns(
            pl.when(pl.col("resolved") > 0)
            .then(pl.col("momentum_wins") / pl.col("resolved") * 100)
            .otherwise(None)
            .alias("momentum_rate"),
            pl.when(pl.col("resolved") > 0)
            .then(pl.col("reversal_wins") / pl.col("resolved") * 100)
            .otherwise(None)
            .alias("reversal_rate"),
        )
    )


def build_summary_table(df: pl.DataFrame) -> pl.DataFrame:
    """Build the all-event summary table from the notebook.

    Returns a polars DataFrame sorted by ``edge`` descending with the original 8
    output columns: ``event_type``, ``n``, ``momentum_rate``, ``reversal_rate``,
    ``edge``, ``median_mae``, ``avg_time_to_sweep``, ``avg_range_pct``.
    """
    return (
        df.group_by("event_type")
        .agg(
            pl.len().alias("n"),
            (pl.col("first_target_hit") == "box").sum().alias("momentum"),
            (pl.col("first_target_hit") == "opposite").sum().alias("reversal"),
            pl.col("mae_before_reversal").mean().alias("avg_mae"),
            pl.col("mae_before_reversal").median().alias("median_mae"),
            pl.col("time_to_first_sweep").mean().alias("avg_time_to_sweep"),
            pl.col("range_pct").mean().alias("avg_range_pct"),
        )
        .with_columns(
            (pl.col("momentum") + pl.col("reversal")).alias("resolved")
        )
        .with_columns(
            (pl.col("momentum") / pl.col("resolved") * 100).round(1).alias("momentum_rate"),
            (pl.col("reversal") / pl.col("resolved") * 100).round(1).alias("reversal_rate"),
        )
        .with_columns(
            ((pl.col("momentum_rate") - 50).abs()).round(1).alias("edge")
        )
        .sort("edge", descending=True)
        .select(
            [
                "event_type",
                "n",
                "momentum_rate",
                "reversal_rate",
                "edge",
                "median_mae",
                "avg_time_to_sweep",
                "avg_range_pct",
            ]
        )
    )


def plot_event_win_rates(by_event: pl.DataFrame, output_path: Path) -> None:
    by_event = by_event.sort("reversal_rate", nulls_last=True)
    fig, ax = plt.subplots(figsize=(12, 10))
    y_pos = range(len(by_event))
    ax.barh(y_pos, by_event.get_column("momentum_rate").to_numpy(), label="Momentum (box first)", color="#e74c3c", alpha=0.8)
    ax.barh(y_pos, -by_event.get_column("reversal_rate").to_numpy(), label="Reversal (opposite first)", color="#2ecc71", alpha=0.8)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels([f"{e} (n={int(t)})" for e, t in zip(by_event.get_column("event_type").to_list(), by_event.get_column("resolved").to_list())])
    ax.axvline(0, color="black", linewidth=0.5)
    ax.axvline(50, color="gray", linestyle="--", alpha=0.5)
    ax.axvline(-50, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Win Rate (%)")
    ax.set_title("Momentum vs Reversal Win Rate by Event Type")
    ax.legend(loc="lower right")
    ax.set_xlim(-100, 100)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_release_time_rates(by_time: pl.DataFrame, output_path: Path) -> None:
    by_time = by_time.sort("release_time")
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(by_time))
    width = 0.35
    ax.bar([i - width / 2 for i in x], by_time.get_column("momentum_rate").to_numpy(), width, label="Momentum", color="#e74c3c")
    ax.bar([i + width / 2 for i in x], by_time.get_column("reversal_rate").to_numpy(), width, label="Reversal", color="#2ecc71")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{t}\n(n={int(n)})" for t, n in zip(by_time.get_column("release_time").to_list(), by_time.get_column("resolved").to_list())])
    ax.axhline(50, color="gray", linestyle="--", alpha=0.5, label="50% baseline")
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Momentum vs Reversal by Release Time")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_range_quartile_rates(df: pl.DataFrame, output_path: Path) -> pl.DataFrame:
    working = df.with_columns(
        df.get_column("range_pct").qcut(
            4, labels=["Q1 (smallest)", "Q2", "Q3", "Q4 (largest)"], allow_duplicates=True
        ).alias("range_quartile")
    )
    by_range = compute_win_rates(working, ["range_quartile"])
    avg_range = working.group_by("range_quartile").agg(
        pl.col("range_pct").mean().alias("avg_range")
    )
    by_range = by_range.join(avg_range, on="range_quartile", how="left")
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(by_range))
    width = 0.35
    ax.bar([i - width / 2 for i in x], by_range.get_column("momentum_rate").to_numpy(), width, label="Momentum", color="#e74c3c")
    ax.bar([i + width / 2 for i in x], by_range.get_column("reversal_rate").to_numpy(), width, label="Reversal", color="#2ecc71")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{q}\n(avg {r:.2f}%)" for q, r in zip(by_range.get_column("range_quartile").to_list(), by_range.get_column("avg_range").to_list())])
    ax.axhline(50, color="gray", linestyle="--", alpha=0.5)
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate by News Impact Size (Range Quartile)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return by_range


def plot_mae_distribution(df: pl.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    ax1, ax2 = axes
    mae = df.get_column("mae_before_reversal")
    ax1.hist(mae.clip(upper_bound=10).to_numpy(), bins=50, edgecolor="black", alpha=0.7)
    ax1.axvline(mae.median(), color="red", linestyle="--", label=f"Median: {mae.median():.2f}R")
    ax1.axvline(1, color="orange", linestyle="--", label="1R (synthetic box)")
    ax1.set_xlabel("MAE (in range units)")
    ax1.set_ylabel("Frequency")
    ax1.set_title("MAE Distribution (clipped at 10R)")
    ax1.legend()

    reversal_mae = df.filter(pl.col("first_target_hit") == "opposite").get_column("mae_before_reversal")
    momentum_mae = df.filter(pl.col("first_target_hit") == "box").get_column("mae_before_reversal")
    ax2.hist(reversal_mae.clip(upper_bound=5).to_numpy(), bins=30, alpha=0.6, label=f"Reversal wins (med: {reversal_mae.median():.2f}R)", color="#2ecc71")
    ax2.hist(momentum_mae.clip(upper_bound=5).to_numpy(), bins=30, alpha=0.6, label=f"Momentum wins (med: {momentum_mae.median():.2f}R)", color="#e74c3c")
    ax2.set_xlabel("MAE (in range units)")
    ax2.set_ylabel("Frequency")
    ax2.set_title("MAE by Outcome (clipped at 5R)")
    ax2.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR, event: str = "US Non-Farm Employment Change") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pl.read_parquet(input_path)
    print(f"Loaded {len(df)} events from {input_path}")

    by_event = compute_win_rates(df, ["event_type"])
    plot_event_win_rates(by_event, output_dir / "momentum_vs_reversal_by_event.png")

    vc = df.get_column("release_time").value_counts()  # cols: ["release_time", "count"]
    common_times = vc.filter(pl.col("count") >= 10).get_column("release_time").to_list()
    by_time = compute_win_rates(df.filter(pl.col("release_time").is_in(common_times)), ["release_time"])
    plot_release_time_rates(by_time, output_dir / "momentum_vs_reversal_by_release_time.png")

    by_range = plot_range_quartile_rates(df, output_dir / "win_rate_by_range_quartile.png")
    print("\nRange quartiles:")
    print(by_range.select(["range_quartile", "avg_range", "resolved", "momentum_rate", "reversal_rate"]))

    by_sweep = compute_win_rates(df, ["first_sweep"])
    print("\nFirst sweep direction:")
    print(by_sweep.select(["first_sweep", "resolved", "momentum_rate", "reversal_rate"]))

    plot_mae_distribution(df, output_dir / "mae_distribution.png")

    working = df.with_columns(
        df.get_column("time_to_first_sweep").qcut(
            4, labels=["Q1 (fastest)", "Q2", "Q3", "Q4 (slowest)"], allow_duplicates=True
        ).alias("time_quartile")
    )
    by_timing = compute_win_rates(working, ["time_quartile"])
    avg_time = working.group_by("time_quartile").agg(
        pl.col("time_to_first_sweep").mean().alias("avg_time")
    )
    by_timing = by_timing.join(avg_time, on="time_quartile", how="left")
    print("\nTiming quartiles:")
    print(by_timing.select(["time_quartile", "avg_time", "resolved", "momentum_rate", "reversal_rate"]))

    event_df = df.filter(pl.col("event_type") == event)
    if event_df.height > 0:
        resolved = event_df.filter(pl.col("first_target_hit").is_not_null())
        momentum = int((resolved.get_column("first_target_hit") == "box").sum())
        reversal = int((resolved.get_column("first_target_hit") == "opposite").sum())
        print(f"\n=== {event} ===")
        print(f"Total samples: {event_df.height}")
        if resolved.height > 0:
            print(f"Momentum wins: {momentum} ({momentum / resolved.height * 100:.1f}%)")
            print(f"Reversal wins: {reversal} ({reversal / resolved.height * 100:.1f}%)")
        print(f"Median MAE: {event_df.get_column('mae_before_reversal').median():.2f}R")
        print(f"Avg time to first sweep: {event_df.get_column('time_to_first_sweep').mean():.1f} min")
        print(event_df.get_column("first_sweep").value_counts())

    summary = build_summary_table(df)
    summary_path = output_dir / "summary_by_event.csv"
    summary.write_csv(summary_path)
    print("\nSummary table:")
    print(summary)
    print(f"\nWrote charts and summary to {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--event", default="US Non-Farm Employment Change")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.output_dir, args.event)
