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

DEFAULT_EVENTS = Path("data/economic_events.parquet")
DEFAULT_NQ = Path("data/nq_1m.parquet")
DEFAULT_OUTPUT_DIR = Path("charts/forward_returns")
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


def summarize_returns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_summary = (
        df.groupby(["horizon_minutes", "news_candle_direction"], dropna=False, observed=False)
        .agg(
            count=("raw_forward_return_pct", "size"),
            mean_return_pct=("raw_forward_return_pct", "mean"),
            median_return_pct=("raw_forward_return_pct", "median"),
            win_rate=("raw_forward_return_pct", lambda x: (x > 0).mean() * 100),
            p25=("raw_forward_return_pct", lambda x: x.quantile(0.25)),
            p75=("raw_forward_return_pct", lambda x: x.quantile(0.75)),
        )
        .reset_index()
    )

    normalized = df[df["direction_normalized_return_pct"].notna()].copy()
    normalized_summary = (
        normalized.groupby("horizon_minutes", dropna=False, observed=False)
        .agg(
            count=("direction_normalized_return_pct", "size"),
            mean_return_pct=("direction_normalized_return_pct", "mean"),
            median_return_pct=("direction_normalized_return_pct", "median"),
            continuation_rate=("direction_normalized_return_pct", lambda x: (x > 0).mean() * 100),
            p25=("direction_normalized_return_pct", lambda x: x.quantile(0.25)),
            p75=("direction_normalized_return_pct", lambda x: x.quantile(0.75)),
        )
        .reset_index()
    )
    return raw_summary, normalized_summary


def summarize_path_profiles(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df[df["direction_normalized_mfe_pct"].notna()].copy()
    return (
        normalized.groupby("horizon_minutes", dropna=False, observed=False)
        .agg(
            count=("direction_normalized_mfe_pct", "size"),
            mean_mfe_pct=("direction_normalized_mfe_pct", "mean"),
            median_mfe_pct=("direction_normalized_mfe_pct", "median"),
            mean_mae_pct=("direction_normalized_mae_pct", "mean"),
            median_mae_pct=("direction_normalized_mae_pct", "median"),
        )
        .reset_index()
    )


def plot_raw_by_direction(df: pd.DataFrame, horizon: int, output_path: Path) -> None:
    horizon_df = df[df["horizon_minutes"] == horizon].copy()
    directions = [d for d in ["up", "down", "flat"] if d in set(horizon_df["news_candle_direction"])]
    data = [horizon_df.loc[horizon_df["news_candle_direction"] == d, "raw_forward_return_pct"] for d in directions]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(data, labels=directions, showfliers=False)
    rng = np.random.default_rng(42)
    for idx, values in enumerate(data, start=1):
        jitter = rng.normal(0, 0.035, size=len(values))
        ax.scatter(np.full(len(values), idx) + jitter, values, alpha=0.25, s=10)
    ax.axhline(0, color="black", linewidth=1, alpha=0.7)
    ax.set_title(f"{horizon}m Raw Forward Returns by News Candle Direction (n={len(horizon_df)})")
    ax.set_xlabel("Release candle direction")
    ax.set_ylabel("Forward return from release close (%)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_direction_normalized(df: pd.DataFrame, horizon: int, output_path: Path) -> None:
    values = df.loc[
        (df["horizon_minutes"] == horizon) & df["direction_normalized_return_pct"].notna(),
        "direction_normalized_return_pct",
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(values, bins=50, edgecolor="black", alpha=0.75, color="#4c78a8")
    ax.axvline(0, color="black", linewidth=1.2, alpha=0.8)
    ax.axvline(values.median(), color="red", linestyle="--", label=f"Median: {values.median():.3f}%")
    ax.set_title(f"{horizon}m Direction-Normalized Forward Returns (n={len(values)})")
    ax.set_xlabel("Return normalized to release candle direction (%)\npositive = continuation, negative = fade")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_mae_mfe_by_direction(df: pd.DataFrame, horizon: int, output_path: Path) -> None:
    horizon_df = df[df["horizon_minutes"] == horizon].copy()
    directions = [d for d in ["up", "down", "flat"] if d in set(horizon_df["news_candle_direction"])]
    positions: list[float] = []
    data: list[pd.Series] = []
    labels: list[str] = []
    for idx, direction in enumerate(directions, start=1):
        subset = horizon_df[horizon_df["news_candle_direction"] == direction]
        positions.extend([idx - 0.18, idx + 0.18])
        data.extend([subset["raw_mae_pct"], subset["raw_mfe_pct"]])
        labels.extend([f"{direction}\nMAE", f"{direction}\nMFE"])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(data, positions=positions, widths=0.28, showfliers=False)
    ax.axhline(0, color="black", linewidth=1, alpha=0.7)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_title(f"{horizon}m Raw MAE/MFE by News Candle Direction (n={len(horizon_df)})")
    ax.set_ylabel("Excursion from release close (%)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_normalized_mae_mfe_scatter(df: pd.DataFrame, horizon: int, output_path: Path) -> None:
    horizon_df = df[
        (df["horizon_minutes"] == horizon)
        & df["direction_normalized_mfe_pct"].notna()
        & df["direction_normalized_mae_pct"].notna()
    ].copy()
    colors = {"up": "#e74c3c", "down": "#2ecc71", "flat": "#7f8c8d"}

    fig, ax = plt.subplots(figsize=(7, 6))
    for direction, subset in horizon_df.groupby("news_candle_direction", observed=False):
        ax.scatter(
            subset["direction_normalized_mae_pct"],
            subset["direction_normalized_mfe_pct"],
            s=12,
            alpha=0.35,
            label=direction,
            color=colors.get(direction, "#4c78a8"),
        )
    ax.axhline(0, color="black", linewidth=1, alpha=0.7)
    ax.axvline(0, color="black", linewidth=1, alpha=0.7)
    ax.set_title(f"{horizon}m Direction-Normalized MAE/MFE Profile (n={len(horizon_df)})")
    ax.set_xlabel("Normalized MAE (%)\nnegative = adverse excursion")
    ax.set_ylabel("Normalized MFE (%)\npositive = favorable continuation excursion")
    ax.legend(title="Candle direction")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def write_outputs(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "forward_returns_by_event.csv", index=False)
    for horizon in sorted(df["horizon_minutes"].unique()):
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
    events = pd.read_parquet(input_events)
    nq = pd.read_parquet(input_nq)
    df = build_forward_returns(events, nq, horizons=horizons)
    if df.empty:
        raise ValueError("No forward return rows produced; check event/NQ timestamp alignment")
    write_outputs(df, output_dir)
    raw_summary, normalized_summary = summarize_returns(df)
    path_summary = summarize_path_profiles(df)
    print(f"Built {len(df)} event/horizon forward-return rows")
    print(f"Wrote outputs to {output_dir}")
    print("\nRaw returns by horizon and release candle direction:")
    print(raw_summary.round(4).to_string(index=False))
    print("\nDirection-normalized returns by horizon:")
    print(normalized_summary.round(4).to_string(index=False))
    print("\nDirection-normalized MAE/MFE path profiles by horizon:")
    print(path_summary.round(4).to_string(index=False))


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
