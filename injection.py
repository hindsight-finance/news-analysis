"""
News Event Injection Analysis
Generates histograms of price ranges for each news event:
1. Release candle range (1-minute)
2. 10-minute range following release (inclusive)
Ranges are normalized to percentages.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from datetime import timedelta
from pathlib import Path

# Setup paths
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "charts"
OUTPUT_DIR.mkdir(exist_ok=True)

def load_data():
    """Load economic events and NQ 1m price data (polars; mirrors main.py:load_data).

    The on-disk nq column is ``datetime_utc`` (us precision); rename to ``DateTime_UTC``,
    stamp/convert to UTC, then force ns precision so the pure-polars equality lookup
    matches the ns events key (D-05). Skipping the cast silently drops every event.
    """
    events = pl.read_parquet(DATA_DIR / "economic_events.parquet", use_pyarrow=False)
    nq = pl.read_parquet(DATA_DIR / "nq_1m.parquet", use_pyarrow=False)

    if "DateTime_UTC" not in nq.columns and "datetime_utc" in nq.columns:
        nq = nq.rename({"datetime_utc": "DateTime_UTC"})

    # Normalize DateTime_UTC to tz-aware UTC (naive -> stamp UTC; aware -> convert).
    if nq.schema["DateTime_UTC"].time_zone is None:
        nq = nq.with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC"))
    else:
        nq = nq.with_columns(pl.col("DateTime_UTC").dt.convert_time_zone("UTC"))

    # D-05: us -> ns so the equality/join lookup matches the ns event key.
    nq = nq.with_columns(pl.col("DateTime_UTC").dt.cast_time_unit("ns"))

    # Normalize events datetime_utc to tz-aware UTC, ns precision (D-05).
    if events.schema["datetime_utc"].time_zone is None:
        events = events.with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC"))
    else:
        events = events.with_columns(pl.col("datetime_utc").dt.convert_time_zone("UTC"))
    events = events.with_columns(pl.col("datetime_utc").dt.cast_time_unit("ns"))

    nq = nq.sort("DateTime_UTC")
    return events, nq


def calculate_percentage_range(high, low, reference_price):
    """Calculate price range as a percentage of the reference price."""
    return ((high - low) / reference_price) * 100


def build_release_index(events: pl.DataFrame, nq: pl.DataFrame) -> dict:
    """Pure-polars exact-match lookup: event timestamp -> nq row index (D-02/D-03/D-04).

    Inner-joins every event datetime against ``nq[[DateTime_UTC, idx]]`` in one pass
    (exact-match; misses drop, reproducing the old ``if candle.empty: return None``,
    D-04), then collapses the matches into a ``{timestamp: idx}`` dict. This is the same
    pure-polars construct ``forward_returns.py`` uses (D-03) — it replaces the old
    per-event full-frame boolean-mask scan (the documented D-02 anti-pattern) and uses
    no as-of/nearest-match join.
    """
    nq_keys = nq.with_row_index("idx").select(["DateTime_UTC", "idx"])
    wanted = events.select(
        pl.col("datetime_utc").dt.cast_time_unit("ns").alias("DateTime_UTC")
    ).unique()
    matched = wanted.join(nq_keys, on="DateTime_UTC", how="inner")
    return dict(
        zip(
            matched.get_column("DateTime_UTC").to_list(),
            matched.get_column("idx").to_list(),
        )
    )


def get_release_candle_data(nq: pl.DataFrame, ts_to_idx: dict, event_time) -> tuple[float, int] | None:
    """Get the percentage range and volume of the 1-minute release candle, or None.

    Resolves ``event_time`` to an nq row index via the pre-built exact-match lookup
    (D-02); a miss returns ``None`` exactly as the old ``if candle.empty`` guard (D-04).
    """
    idx = ts_to_idx.get(event_time)
    if idx is None:
        return None

    candle = nq.row(idx, named=True)
    pct_range = calculate_percentage_range(candle["High"], candle["Low"], candle["Open"])
    return pct_range, candle["Volume"]


def get_10min_range(nq: pl.DataFrame, event_time) -> float | None:
    """Percentage range of the inclusive 10-minute window [event_time, event_time+9min].

    D-06: a TIME-bounded ``is_between`` filter (robust to missing minutes/gaps), NOT a
    positional +9-row slice. Returns ``None`` when no candle falls in the window.
    """
    # Get candles from event_time to event_time + 9 minutes (inclusive both ends).
    end_time = event_time + timedelta(minutes=9)
    candles = nq.filter(
        pl.col("DateTime_UTC").is_between(event_time, end_time, closed="both")
    )

    if candles.is_empty():
        return None

    high = candles.get_column("High").max()
    low = candles.get_column("Low").min()
    reference_price = candles.row(0, named=True)["Open"]  # first candle by time (nq sorted)

    return calculate_percentage_range(high, low, reference_price)


def create_histograms(event_name: str, release_ranges: list, release_volumes: list, ten_min_ranges: list):
    """Create and save histograms for a single news event."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f'{event_name}', fontsize=14, fontweight='bold')
    
    # Release candle price range histogram
    ax1 = axes[0]
    if release_ranges:
        ax1.hist(release_ranges, bins=30, edgecolor='black', alpha=0.7, color='steelblue')
        ax1.axvline(np.median(release_ranges), color='red', linestyle='--', 
                    label=f'Median: {np.median(release_ranges):.3f}%')
        ax1.axvline(np.mean(release_ranges), color='orange', linestyle='--', 
                    label=f'Mean: {np.mean(release_ranges):.3f}%')
        ax1.legend()
    ax1.set_xlabel('Price Range (%)')
    ax1.set_ylabel('Frequency')
    ax1.set_title(f'Release Candle Range | n={len(release_ranges)}')
    ax1.grid(axis='y', alpha=0.3)
    
    # Release candle volume histogram
    ax2 = axes[1]
    if release_volumes:
        ax2.hist(release_volumes, bins=30, edgecolor='black', alpha=0.7, color='seagreen')
        ax2.axvline(np.median(release_volumes), color='red', linestyle='--', 
                    label=f'Median: {np.median(release_volumes):,.0f}')
        ax2.axvline(np.mean(release_volumes), color='orange', linestyle='--', 
                    label=f'Mean: {np.mean(release_volumes):,.0f}')
        ax2.legend()
    ax2.set_xlabel('Volume')
    ax2.set_ylabel('Frequency')
    ax2.set_title(f'Release Candle Volume | n={len(release_volumes)}')
    ax2.grid(axis='y', alpha=0.3)
    
    # 10-minute range histogram
    ax3 = axes[2]
    if ten_min_ranges:
        ax3.hist(ten_min_ranges, bins=30, edgecolor='black', alpha=0.7, color='darkorange')
        ax3.axvline(np.median(ten_min_ranges), color='red', linestyle='--', 
                    label=f'Median: {np.median(ten_min_ranges):.3f}%')
        ax3.axvline(np.mean(ten_min_ranges), color='purple', linestyle='--', 
                    label=f'Mean: {np.mean(ten_min_ranges):.3f}%')
        ax3.legend()
    ax3.set_xlabel('Price Range (%)')
    ax3.set_ylabel('Frequency')
    ax3.set_title(f'10-min Window Range | n={len(ten_min_ranges)}')
    ax3.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    # Sanitize filename
    safe_name = event_name.replace('/', '-').replace('\\', '-').replace(':', '-')
    filepath = OUTPUT_DIR / f"{safe_name}.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    
    return filepath


def main():
    print("Loading data...")
    events, nq = load_data()

    # Pure-polars exact-match release lookup, built once over all events (D-02/D-03).
    ts_to_idx = build_release_index(events, nq)

    # Get unique event titles
    unique_events = events.get_column("title").unique().to_list()
    print(f"Found {len(unique_events)} unique event types")

    # Process each event type
    for event_name in unique_events:
        print(f"\nProcessing: {event_name}")

        # Get all occurrences of this event
        event_occurrences = events.filter(pl.col("title") == event_name)

        release_ranges = []
        release_volumes = []
        ten_min_ranges = []

        for row in event_occurrences.iter_rows(named=True):
            event_time = row["datetime_utc"]

            # Get release candle data (range and volume)
            release_data = get_release_candle_data(nq, ts_to_idx, event_time)
            if release_data is not None:
                release_ranges.append(release_data[0])
                release_volumes.append(release_data[1])

            # Get 10-minute range
            ten_min_range = get_10min_range(nq, event_time)
            if ten_min_range is not None:
                ten_min_ranges.append(ten_min_range)

        # Create histograms if we have data
        if release_ranges or ten_min_ranges:
            filepath = create_histograms(event_name, release_ranges, release_volumes, ten_min_ranges)
            print(f"  Saved: {filepath}")
            print(f"  Release candle samples: {len(release_ranges)}")
            print(f"  10-min window samples: {len(ten_min_ranges)}")
        else:
            print(f"  No matching price data found for this event")

    print(f"\n✓ All charts saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
