"""
Forward return analysis around news events.

Calculates 30m/90m forward returns from release candle close and contextualizes
results by release-candle direction.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

DEFAULT_EVENTS = Path(__file__).parent / "data" / "economic_events.parquet"
DEFAULT_NQ = Path(__file__).parent / "data" / "nq_1m.parquet"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "charts" / "forward_returns"
DEFAULT_HORIZONS = (15, 30, 45, 60, 90)


def normalize_nq(nq: pl.DataFrame) -> pl.DataFrame:
    """Normalize the raw NQ frame to a sorted ns/UTC DateTime_UTC (mirrors main.py:load_data).

    The on-disk column is ``datetime_utc`` (us precision); rename to ``DateTime_UTC``,
    stamp/convert to UTC, then force ns precision so equality/join keys match the ns
    events datetime (D-05). Skipping the cast silently drops every event.
    """
    if "DateTime_UTC" not in nq.columns and "datetime_utc" in nq.columns:
        nq = nq.rename({"datetime_utc": "DateTime_UTC"})

    if nq.schema["DateTime_UTC"].time_zone is None:
        nq = nq.with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC"))
    else:
        nq = nq.with_columns(pl.col("DateTime_UTC").dt.convert_time_zone("UTC"))

    # D-05: us -> ns so the pure-polars equality lookup matches the ns event key.
    nq = nq.with_columns(pl.col("DateTime_UTC").dt.cast_time_unit("ns"))
    return nq.sort("DateTime_UTC")


def normalize_events(events: pl.DataFrame) -> pl.DataFrame:
    """Normalize the raw events frame to a ns/UTC datetime_utc key (D-05)."""
    if events.schema["datetime_utc"].time_zone is None:
        events = events.with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC"))
    else:
        events = events.with_columns(pl.col("datetime_utc").dt.convert_time_zone("UTC"))

    # D-05: keep the event key at ns/UTC to match the (ns-cast) nq column.
    events = events.with_columns(pl.col("datetime_utc").dt.cast_time_unit("ns"))
    return events


def candle_direction(open_price: float, close_price: float) -> str:
    if close_price > open_price:
        return "up"
    if close_price < open_price:
        return "down"
    return "flat"


def direction_normalized_return(raw_return_pct: float, direction: str) -> float:
    if direction == "up":
        return raw_return_pct
    if direction == "down":
        return -raw_return_pct
    return np.nan


def direction_normalized_profile(
    release_close: float,
    window_high: float,
    window_low: float,
    direction: str,
) -> tuple[float, float]:
    """Return continuation-context MFE and MAE percentages."""
    if direction == "up":
        return (
            ((window_high - release_close) / release_close) * 100,
            ((window_low - release_close) / release_close) * 100,
        )
    if direction == "down":
        return (
            ((release_close - window_low) / release_close) * 100,
            ((release_close - window_high) / release_close) * 100,
        )
    return (np.nan, np.nan)


def build_timestamp_index(
    events: pl.DataFrame,
    nq: pl.DataFrame,
    horizons: tuple[int, ...],
) -> dict:
    """Pure-polars exact-match lookup: timestamp -> nq row index (D-01/D-03/D-04).

    Builds every wanted timestamp (each event datetime plus each horizon offset),
    inner-joins them against ``nq[[DateTime_UTC, idx]]`` (exact-match; misses drop,
    reproducing the old sorted-position lookup returning None -> ``continue``), and
    collapses the matches into a ``{timestamp: idx}`` dict. No numpy searchsorted, no
    as-of/nearest-match join, no per-event full-frame scan: the join resolves all
    lookups in one pass.
    """
    nq_keys = nq.with_row_index("idx").select(["DateTime_UTC", "idx"])

    wanted_parts = [
        events.select(pl.col("datetime_utc").dt.cast_time_unit("ns").alias("DateTime_UTC"))
    ]
    for horizon in horizons:
        wanted_parts.append(
            events.select(
                (pl.col("datetime_utc") + pl.duration(minutes=int(horizon)))
                .dt.cast_time_unit("ns")
                .alias("DateTime_UTC")
            )
        )

    wanted = pl.concat(wanted_parts).unique()
    matched = wanted.join(nq_keys, on="DateTime_UTC", how="inner")
    return dict(
        zip(
            matched.get_column("DateTime_UTC").to_list(),
            matched.get_column("idx").to_list(),
        )
    )


def build_forward_returns(
    events: pl.DataFrame,
    nq: pl.DataFrame,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pl.DataFrame:
    events = normalize_events(events)
    nq = normalize_nq(nq)

    ts_to_idx = build_timestamp_index(events, nq, horizons)

    rows: list[dict] = []
    for event in events.iter_rows(named=True):
        event_time = event["datetime_utc"]
        release_idx = ts_to_idx.get(event_time)
        if release_idx is None:
            continue

        release = nq.row(release_idx, named=True)
        release_open = float(release["Open"])
        release_high = float(release["High"])
        release_low = float(release["Low"])
        release_close = float(release["Close"])
        direction = candle_direction(release_open, release_close)

        for horizon in horizons:
            future_time = event_time + timedelta(minutes=int(horizon))
            future_idx = ts_to_idx.get(future_time)
            if future_idx is None:
                continue
            future = nq.row(future_idx, named=True)
            future_close = float(future["Close"])
            raw_return = ((future_close - release_close) / release_close) * 100

            # Positional window [release_idx+1, future_idx] inclusive (D-07):
            # length = future_idx - release_idx covers idx+1 .. future_idx.
            window = nq.slice(release_idx + 1, future_idx - release_idx)
            if window.is_empty():
                continue
            window_high = float(window.get_column("High").max())
            window_low = float(window.get_column("Low").min())
            raw_mfe = ((window_high - release_close) / release_close) * 100
            raw_mae = ((window_low - release_close) / release_close) * 100
            normalized_mfe, normalized_mae = direction_normalized_profile(
                release_close,
                window_high,
                window_low,
                direction,
            )
            rows.append(
                {
                    "event_type": event["title"],
                    "event_datetime": event_time,
                    "horizon_minutes": int(horizon),
                    "news_candle_direction": direction,
                    "release_open": release_open,
                    "release_high": release_high,
                    "release_low": release_low,
                    "release_close": release_close,
                    "future_close": future_close,
                    "raw_forward_return_pct": raw_return,
                    "direction_normalized_return_pct": direction_normalized_return(raw_return, direction),
                    "window_high": window_high,
                    "window_low": window_low,
                    "raw_mfe_pct": raw_mfe,
                    "raw_mae_pct": raw_mae,
                    "direction_normalized_mfe_pct": normalized_mfe,
                    "direction_normalized_mae_pct": normalized_mae,
                }
            )

    return pl.DataFrame(rows)


def summarize_returns(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    raw_summary = (
        df.group_by(["horizon_minutes", "news_candle_direction"])
        .agg(
            pl.len().alias("count"),
            pl.col("raw_forward_return_pct").mean().alias("mean_return_pct"),
            pl.col("raw_forward_return_pct").median().alias("median_return_pct"),
            ((pl.col("raw_forward_return_pct") > 0).mean() * 100).alias("win_rate"),
            pl.col("raw_forward_return_pct").quantile(0.25).alias("p25"),
            pl.col("raw_forward_return_pct").quantile(0.75).alias("p75"),
        )
        .sort(["horizon_minutes", "news_candle_direction"])
    )

    # D-09: flat-direction rows carry float np.nan (not polars null) -> is_not_nan.
    normalized = df.filter(pl.col("direction_normalized_return_pct").is_not_nan())
    normalized_summary = (
        normalized.group_by("horizon_minutes")
        .agg(
            pl.len().alias("count"),
            pl.col("direction_normalized_return_pct").mean().alias("mean_return_pct"),
            pl.col("direction_normalized_return_pct").median().alias("median_return_pct"),
            ((pl.col("direction_normalized_return_pct") > 0).mean() * 100).alias("continuation_rate"),
            pl.col("direction_normalized_return_pct").quantile(0.25).alias("p25"),
            pl.col("direction_normalized_return_pct").quantile(0.75).alias("p75"),
        )
        .sort("horizon_minutes")
    )
    return raw_summary, normalized_summary


def summarize_path_profiles(df: pl.DataFrame) -> pl.DataFrame:
    # D-09: exclude flat-direction NaN rows via is_not_nan (is_not_null would not drop NaN).
    normalized = df.filter(pl.col("direction_normalized_mfe_pct").is_not_nan())
    return (
        normalized.group_by("horizon_minutes")
        .agg(
            pl.len().alias("count"),
            pl.col("direction_normalized_mfe_pct").mean().alias("mean_mfe_pct"),
            pl.col("direction_normalized_mfe_pct").median().alias("median_mfe_pct"),
            pl.col("direction_normalized_mae_pct").mean().alias("mean_mae_pct"),
            pl.col("direction_normalized_mae_pct").median().alias("median_mae_pct"),
        )
        .sort("horizon_minutes")
    )


def plot_raw_by_direction(df: pl.DataFrame, horizon: int, output_path: Path) -> None:
    horizon_df = df.filter(pl.col("horizon_minutes") == horizon)
    present = set(horizon_df.get_column("news_candle_direction").to_list())
    directions = [d for d in ["up", "down", "flat"] if d in present]
    data = [
        horizon_df.filter(pl.col("news_candle_direction") == d).get_column("raw_forward_return_pct").to_numpy()
        for d in directions
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(data, labels=directions, showfliers=False)
    rng = np.random.default_rng(42)
    for idx, values in enumerate(data, start=1):
        jitter = rng.normal(0, 0.035, size=len(values))
        ax.scatter(np.full(len(values), idx) + jitter, values, alpha=0.25, s=10)
    ax.axhline(0, color="black", linewidth=1, alpha=0.7)
    ax.set_title(f"{horizon}m Raw Forward Returns by News Candle Direction (n={horizon_df.height})")
    ax.set_xlabel("Release candle direction")
    ax.set_ylabel("Forward return from release close (%)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_direction_normalized(df: pl.DataFrame, horizon: int, output_path: Path) -> None:
    values = (
        df.filter(
            (pl.col("horizon_minutes") == horizon)
            & pl.col("direction_normalized_return_pct").is_not_nan()
        )
        .get_column("direction_normalized_return_pct")
        .to_numpy()
    )
    median = float(np.median(values)) if len(values) else float("nan")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(values, bins=50, edgecolor="black", alpha=0.75, color="#4c78a8")
    ax.axvline(0, color="black", linewidth=1.2, alpha=0.8)
    ax.axvline(median, color="red", linestyle="--", label=f"Median: {median:.3f}%")
    ax.set_title(f"{horizon}m Direction-Normalized Forward Returns (n={len(values)})")
    ax.set_xlabel("Return normalized to release candle direction (%)\npositive = continuation, negative = fade")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_mae_mfe_by_direction(df: pl.DataFrame, horizon: int, output_path: Path) -> None:
    horizon_df = df.filter(pl.col("horizon_minutes") == horizon)
    present = set(horizon_df.get_column("news_candle_direction").to_list())
    directions = [d for d in ["up", "down", "flat"] if d in present]
    positions: list[float] = []
    data: list[np.ndarray] = []
    labels: list[str] = []
    for idx, direction in enumerate(directions, start=1):
        subset = horizon_df.filter(pl.col("news_candle_direction") == direction)
        positions.extend([idx - 0.18, idx + 0.18])
        data.extend([
            subset.get_column("raw_mae_pct").to_numpy(),
            subset.get_column("raw_mfe_pct").to_numpy(),
        ])
        labels.extend([f"{direction}\nMAE", f"{direction}\nMFE"])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(data, positions=positions, widths=0.28, showfliers=False)
    ax.axhline(0, color="black", linewidth=1, alpha=0.7)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_title(f"{horizon}m Raw MAE/MFE by News Candle Direction (n={horizon_df.height})")
    ax.set_ylabel("Excursion from release close (%)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_normalized_mae_mfe_scatter(df: pl.DataFrame, horizon: int, output_path: Path) -> None:
    horizon_df = df.filter(
        (pl.col("horizon_minutes") == horizon)
        & pl.col("direction_normalized_mfe_pct").is_not_nan()
        & pl.col("direction_normalized_mae_pct").is_not_nan()
    )
    colors = {"up": "#e74c3c", "down": "#2ecc71", "flat": "#7f8c8d"}

    fig, ax = plt.subplots(figsize=(7, 6))
    # polars group_by is unordered; iterate an explicit ordered direction list instead.
    for direction in ["up", "down", "flat"]:
        subset = horizon_df.filter(pl.col("news_candle_direction") == direction)
        if subset.is_empty():
            continue
        ax.scatter(
            subset.get_column("direction_normalized_mae_pct").to_numpy(),
            subset.get_column("direction_normalized_mfe_pct").to_numpy(),
            s=12,
            alpha=0.35,
            label=direction,
            color=colors.get(direction, "#4c78a8"),
        )
    ax.axhline(0, color="black", linewidth=1, alpha=0.7)
    ax.axvline(0, color="black", linewidth=1, alpha=0.7)
    ax.set_title(f"{horizon}m Direction-Normalized MAE/MFE Profile (n={horizon_df.height})")
    ax.set_xlabel("Normalized MAE (%)\nnegative = adverse excursion")
    ax.set_ylabel("Normalized MFE (%)\npositive = favorable continuation excursion")
    ax.legend(title="Candle direction")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def write_outputs(df: pl.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df.write_csv(output_dir / "forward_returns_by_event.csv")
    for horizon in sorted(df.get_column("horizon_minutes").unique().to_list()):
        plot_raw_by_direction(df, int(horizon), output_dir / f"forward_returns_{int(horizon)}m_raw_by_direction.png")
        plot_direction_normalized(df, int(horizon), output_dir / f"forward_returns_{int(horizon)}m_direction_normalized.png")
        plot_mae_mfe_by_direction(df, int(horizon), output_dir / f"forward_returns_{int(horizon)}m_mae_mfe_by_direction.png")
        plot_normalized_mae_mfe_scatter(
            df,
            int(horizon),
            output_dir / f"forward_returns_{int(horizon)}m_normalized_mae_mfe_scatter.png",
        )


def run(
    input_events: Path = DEFAULT_EVENTS,
    input_nq: Path = DEFAULT_NQ,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> None:
    events = pl.read_parquet(input_events, use_pyarrow=False)
    nq = pl.read_parquet(input_nq, use_pyarrow=False)
    df = build_forward_returns(events, nq, horizons=horizons)
    if df.is_empty():
        raise ValueError("No forward return rows produced; check event/NQ timestamp alignment")
    write_outputs(df, output_dir)
    raw_summary, normalized_summary = summarize_returns(df)
    path_summary = summarize_path_profiles(df)
    print(f"Built {df.height} event/horizon forward-return rows")
    print(f"Wrote outputs to {output_dir}")
    with pl.Config(tbl_rows=-1):
        print("\nRaw returns by horizon and release candle direction:")
        print(raw_summary.with_columns(pl.col(pl.Float64).round(4)))
        print("\nDirection-normalized returns by horizon:")
        print(normalized_summary.with_columns(pl.col(pl.Float64).round(4)))
        print("\nDirection-normalized MAE/MFE path profiles by horizon:")
        print(path_summary.with_columns(pl.col(pl.Float64).round(4)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--nq", type=Path, default=DEFAULT_NQ)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--horizons", type=int, nargs="+", default=list(DEFAULT_HORIZONS))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.events, args.nq, args.output_dir, tuple(args.horizons))
