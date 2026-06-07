"""
News Event Data High/Low Sweep Analysis

Research script to test the hypothesis: when a news release candle's data high 
or low is swept, does price tend to reverse and sweep the opposite side?

Lookback: Scans from release candle to end of trading day (4:00 PM ET).
"""

from __future__ import annotations

import polars as pl
import numpy as np
from pathlib import Path
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# Setup paths
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "sweep_analysis_results.parquet"

# Trading day end (ET)
TRADING_DAY_END = time(16, 0)


def timestamp_ns_utc(dt: datetime) -> int:
    """Convert a python datetime to integer UTC nanoseconds (no float rounding).

    A naive datetime is treated as UTC. Inputs here are minute-aligned, so the
    microsecond term is exact and the whole-second value is exactly
    representable as a double.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp()) * 1_000_000_000 + dt.microsecond * 1000


def find_sorted_pos(values: np.ndarray, value: int) -> int | None:
    """Return exact row position in a sorted int64 timestamp array."""
    pos = int(np.searchsorted(values, value, side='left'))
    if pos < len(values) and values[pos] == value:
        return pos
    return None


def load_data():
    """Load economic events and NQ 1m price data (polars; native parquet reader).

    Returns a 3-tuple ``(events, nq, lookups)`` where ``lookups`` holds the two
    ns-int64 timestamp arrays, threaded explicitly because polars frames have no
    per-frame metadata cache.
    """
    # ENV-02: native polars read path, no pandas/pyarrow.
    events = pl.read_parquet(DATA_DIR / "economic_events.parquet", use_pyarrow=False)
    nq = pl.read_parquet(DATA_DIR / "nq_1m.parquet", use_pyarrow=False)

    if "DateTime_UTC" not in nq.columns and "datetime_utc" in nq.columns:
        nq = nq.rename({"datetime_utc": "DateTime_UTC"})

    # Normalize DateTime_UTC to tz-aware UTC (naive -> stamp UTC; aware -> convert).
    if nq.schema["DateTime_UTC"].time_zone is None:
        nq = nq.with_columns(pl.col("DateTime_UTC").dt.replace_time_zone("UTC"))
    else:
        nq = nq.with_columns(pl.col("DateTime_UTC").dt.convert_time_zone("UTC"))

    # Derive naive ET from UTC (session wall-clock used for lookups + context).
    if "DateTime_ET" not in nq.columns:
        nq = nq.with_columns(
            pl.col("DateTime_UTC")
            .dt.convert_time_zone("America/New_York")
            .dt.replace_time_zone(None)
            .alias("DateTime_ET")
        )

    # Normalize events datetime_utc to tz-aware UTC.
    if events.schema["datetime_utc"].time_zone is None:
        events = events.with_columns(pl.col("datetime_utc").dt.replace_time_zone("UTC"))
    else:
        events = events.with_columns(pl.col("datetime_utc").dt.convert_time_zone("UTC"))

    # Sort NQ by time for efficient lookups.
    nq = nq.sort("DateTime_UTC")

    # Build ns-int64 lookup arrays (threaded via the lookups dict). The
    # .astype("datetime64[ns]") FORCES microseconds->nanoseconds; without it every
    # event lookup is 1000x off and silently dropped (RESEARCH Pitfall 1).
    utc_values = nq.get_column("DateTime_UTC").to_numpy().astype("datetime64[ns]").astype("int64")
    et_values = nq.get_column("DateTime_ET").to_numpy().astype("datetime64[ns]").astype("int64")
    lookups = {"utc_values": utc_values, "et_values": et_values}

    return events, nq, lookups


def get_release_candle(nq: pl.DataFrame, lookups: dict, event_time: datetime) -> dict | None:
    """Get the release candle for an event (dict row), or None if not found."""
    pos = find_sorted_pos(lookups["utc_values"], timestamp_ns_utc(event_time))
    return nq.row(pos, named=True) if pos is not None else None


def get_candles_until_eod(nq: pl.DataFrame, lookups: dict, start_time: datetime) -> pl.DataFrame:
    """Get all candles from start_time until end of trading day (4:00 PM ET)."""
    utc_values = lookups["utc_values"]
    start_idx = find_sorted_pos(utc_values, timestamp_ns_utc(start_time))
    if start_idx is None:
        return pl.DataFrame()

    start_et = nq.row(start_idx, named=True)["DateTime_ET"]  # naive python datetime (ET)

    # End of trading day = 16:00 ET same day; if at/after 16:00, roll to next day's 16:00.
    end_of_day = start_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if start_et.time() >= TRADING_DAY_END:
        end_of_day = end_of_day + timedelta(days=1)

    # Localize the ET wall-clock anchor -> UTC (DST-safe: 16:00 never falls in the 02:00 gap).
    end_utc = end_of_day.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    end_pos = int(np.searchsorted(utc_values, timestamp_ns_utc(end_utc), side="right"))

    length = end_pos - (start_idx + 1)
    if length <= 0:
        return pl.DataFrame()
    return nq.slice(start_idx + 1, length)


def get_candle_at_time(nq: pl.DataFrame, lookups: dict, target_et: datetime) -> dict | None:
    """Get a specific candle by naive-ET timestamp (dict row), or None if not found."""
    target_ns = int(np.datetime64(target_et, "ns").astype("int64"))
    pos = find_sorted_pos(lookups["et_values"], target_ns)
    return nq.row(pos, named=True) if pos is not None else None


def get_session_context(nq: pd.DataFrame, release_candle: pd.Series) -> dict:
    """
    Extract session context features:
    - 8:29 candle (pre-news)
    - Midnight open (00:00 ET)
    - 6pm open (18:00 ET prior day)
    - 6pm gap (open vs prior close)
    """
    release_et = release_candle['DateTime_ET']
    release_date = release_et.date()
    release_price = release_candle['Open']
    
    context = {
        'pre_candle_range_pct': None,
        'pre_candle_volume': None,
        'dist_from_midnight_open_pct': None,
        'dist_from_6pm_open_pct': None,
        'gap_6pm_pct': None,
        'gap_6pm_direction': None,
        'release_volume': release_candle['Volume'],
    }
    
    # 8:29 candle (1 minute before 8:30 news)
    pre_news_time = release_et.replace(hour=8, minute=29, second=0, microsecond=0)
    pre_candle = get_candle_at_time(nq, pre_news_time)
    if pre_candle is not None:
        pre_range = pre_candle['High'] - pre_candle['Low']
        context['pre_candle_range_pct'] = (pre_range / pre_candle['Open']) * 100
        context['pre_candle_volume'] = pre_candle['Volume']
    
    # Midnight open (00:00 ET same day)
    midnight_time = pd.Timestamp(release_date) + pd.Timedelta(hours=0)
    midnight_candle = get_candle_at_time(nq, midnight_time)
    if midnight_candle is not None:
        midnight_open = midnight_candle['Open']
        context['dist_from_midnight_open_pct'] = ((release_price - midnight_open) / midnight_open) * 100
    
    # 6pm open (18:00 ET prior day = start of Globex session)
    prior_day = release_date - pd.Timedelta(days=1)
    six_pm_time = pd.Timestamp(prior_day) + pd.Timedelta(hours=18)
    six_pm_candle = get_candle_at_time(nq, six_pm_time)
    if six_pm_candle is not None:
        six_pm_open = six_pm_candle['Open']
        context['dist_from_6pm_open_pct'] = ((release_price - six_pm_open) / six_pm_open) * 100
        
        # 6pm gap: compare 6pm open to prior session close (find 4:59 PM or last candle before 5 PM)
        prior_close_time = pd.Timestamp(prior_day) + pd.Timedelta(hours=16, minutes=59)
        prior_close_candle = get_candle_at_time(nq, prior_close_time)
        if prior_close_candle is not None:
            prior_close = prior_close_candle['Close']
            gap_pct = ((six_pm_open - prior_close) / prior_close) * 100
            context['gap_6pm_pct'] = abs(gap_pct)
            context['gap_6pm_direction'] = 'up' if gap_pct > 0 else ('down' if gap_pct < 0 else 'flat')
    
    return context


def analyze_event(nq: pd.DataFrame, event_time: pd.Timestamp, event_type: str) -> dict | None:
    """Analyze a single news event for sweep behavior."""
    
    # Get release candle
    release_candle = get_release_candle(nq, event_time)
    if release_candle is None:
        return None
    
    data_high = release_candle['High']
    data_low = release_candle['Low']
    range_size = data_high - data_low
    range_pct = (range_size / release_candle['Open']) * 100
    
    # Get subsequent candles until end of day
    subsequent = get_candles_until_eod(nq, event_time)
    if subsequent.empty:
        return None
    
    highs = subsequent['High'].to_numpy()
    lows = subsequent['Low'].to_numpy()
    times = subsequent['DateTime_UTC'].to_numpy()

    high_hits = highs > data_high
    low_hits = lows < data_low
    high_swept = bool(high_hits.any())
    low_swept = bool(low_hits.any())
    high_pos = int(np.argmax(high_hits)) if high_swept else None
    low_pos = int(np.argmax(low_hits)) if low_swept else None

    if not high_swept and not low_swept:
        return None

    if high_swept and (not low_swept or high_pos <= low_pos):
        first_sweep = 'high'
        first_sweep_pos = high_pos
    else:
        first_sweep = 'low'
        first_sweep_pos = low_pos

    first_sweep_time = pd.Timestamp(times[first_sweep_pos])
    opposite_swept = high_swept and low_swept
    opposite_sweep_time = pd.Timestamp(times[max(high_pos, low_pos)]) if opposite_swept else None

    # Calculate time metrics
    time_to_first_sweep = (first_sweep_time - event_time).total_seconds() / 60  # minutes

    time_to_opposite_sweep = None
    if opposite_swept and opposite_sweep_time is not None:
        time_to_opposite_sweep = (opposite_sweep_time - first_sweep_time).total_seconds() / 60

    # Determine synthetic box level
    if first_sweep == 'high':
        synthetic_box_level = data_high + range_size
        opposite_level = data_low
    else:  # first_sweep == 'low'
        synthetic_box_level = data_low - range_size
        opposite_level = data_high

    # Scan post-sweep candles to determine which target is hit FIRST
    post_highs = highs[first_sweep_pos:]
    post_lows = lows[first_sweep_pos:]
    post_times = times[first_sweep_pos:]
    first_target_hit = None  # 'box', 'opposite', or None
    box_hit_time = None
    opposite_hit_time = None
    mae_before_reversal = 0.0
    synthetic_box_breached = False

    if first_sweep == 'high':
        box_hits = post_highs > synthetic_box_level
        opposite_hits = post_lows < opposite_level
    else:
        box_hits = post_lows < synthetic_box_level
        opposite_hits = post_highs > opposite_level

    box_hit_pos = int(np.argmax(box_hits)) if box_hits.any() else None
    opposite_hit_pos = int(np.argmax(opposite_hits)) if opposite_hits.any() else None

    if box_hit_pos is not None:
        box_hit_time = pd.Timestamp(post_times[box_hit_pos])
        synthetic_box_breached = True
    if opposite_hit_pos is not None:
        opposite_hit_time = pd.Timestamp(post_times[opposite_hit_pos])

    if box_hit_pos is not None and (opposite_hit_pos is None or box_hit_pos <= opposite_hit_pos):
        first_target_hit = 'box'
    elif opposite_hit_pos is not None:
        first_target_hit = 'opposite'

    if range_size > 0:
        mae_limit = opposite_hit_pos if opposite_hit_pos is not None else len(post_highs)
        if mae_limit > 0 and first_sweep == 'high':
            mae_before_reversal = max(0.0, float(np.max((post_highs[:mae_limit] - data_high) / range_size)))
        elif mae_limit > 0:
            mae_before_reversal = max(0.0, float(np.max((data_low - post_lows[:mae_limit]) / range_size)))

    # Extract release time of day
    release_time_str = release_candle['DateTime_ET'].strftime('%H:%M')
    
    # Get session context features
    session_context = get_session_context(nq, release_candle)
    
    result = {
        'event_type': event_type,
        'event_datetime': event_time,
        'release_time': release_time_str,
        'data_high': data_high,
        'data_low': data_low,
        'range': range_size,
        'range_pct': range_pct,
        'first_sweep': first_sweep,
        'time_to_first_sweep': time_to_first_sweep,
        'opposite_swept': opposite_swept,
        'time_to_opposite_sweep': time_to_opposite_sweep,
        'synthetic_box_breached': synthetic_box_breached,
        'first_target_hit': first_target_hit,  # 'box', 'opposite', or None
        'mae_before_reversal': mae_before_reversal,
    }
    
    # Add session context features
    result.update(session_context)
    
    return result


def main():
    print("Loading data...")
    events, nq = load_data()
    
    print(f"Analyzing {len(events)} news events...")
    
    results = []
    for _, event in events.iterrows():
        result = analyze_event(nq, event['datetime_utc'], event['title'])
        if result is not None:
            results.append(result)
    
    print(f"Successfully analyzed {len(results)} events")
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Save results
    df.to_parquet(OUTPUT_FILE, index=False)
    print(f"\nResults saved to: {OUTPUT_FILE}")
    
    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)
    
    print(f"\nTotal events analyzed: {len(df)}")
    print(f"First sweep HIGH: {(df['first_sweep'] == 'high').sum()} ({(df['first_sweep'] == 'high').mean()*100:.1f}%)")
    print(f"First sweep LOW: {(df['first_sweep'] == 'low').sum()} ({(df['first_sweep'] == 'low').mean()*100:.1f}%)")
    
    print(f"\n--- Reversal Success Rate ---")
    print(f"Opposite side swept: {df['opposite_swept'].sum()} / {len(df)} ({df['opposite_swept'].mean()*100:.1f}%)")
    
    print(f"\n--- First Target Hit (Momentum vs Reversal) ---")
    momentum_wins = (df['first_target_hit'] == 'box').sum()
    reversal_wins = (df['first_target_hit'] == 'opposite').sum()
    neither = df['first_target_hit'].isna().sum()
    total_resolved = momentum_wins + reversal_wins
    print(f"Momentum play (box first): {momentum_wins} / {len(df)} ({momentum_wins/len(df)*100:.1f}%)")
    print(f"Reversal play (opposite first): {reversal_wins} / {len(df)} ({reversal_wins/len(df)*100:.1f}%)")
    print(f"Neither hit by EOD: {neither} / {len(df)} ({neither/len(df)*100:.1f}%)")
    if total_resolved > 0:
        print(f"Of resolved trades: Momentum {momentum_wins/total_resolved*100:.1f}% vs Reversal {reversal_wins/total_resolved*100:.1f}%")
    
    print(f"\n--- Synthetic Box Breach ---")
    print(f"Breached (at any point): {df['synthetic_box_breached'].sum()} / {len(df)} ({df['synthetic_box_breached'].mean()*100:.1f}%)")
    
    print(f"\n--- Timing (minutes) ---")
    print(f"Avg time to first sweep: {df['time_to_first_sweep'].mean():.1f}")
    successful = df[df['opposite_swept']]
    if len(successful) > 0:
        print(f"Avg time to opposite sweep (when successful): {successful['time_to_opposite_sweep'].mean():.1f}")
    
    print(f"\n--- MAE (in range units) ---")
    print(f"Avg MAE before reversal: {df['mae_before_reversal'].mean():.2f}")
    print(f"Median MAE before reversal: {df['mae_before_reversal'].median():.2f}")
    
    # Breakdown by event type
    print(f"\n--- By Event Type ---")
    by_event = df.groupby('event_type').agg({
        'opposite_swept': ['sum', 'count', 'mean'],
        'time_to_first_sweep': 'mean',
        'mae_before_reversal': 'mean'
    }).round(2)
    by_event.columns = ['opposite_swept', 'total', 'reversal_rate', 'avg_time_to_1st_sweep', 'avg_mae']
    by_event = by_event.sort_values('reversal_rate', ascending=False)
    print(by_event.to_string())
    
    # Breakdown by release time
    print(f"\n--- By Release Time ---")
    by_time = df.groupby('release_time').agg({
        'opposite_swept': ['sum', 'count', 'mean'],
    }).round(2)
    by_time.columns = ['opposite_swept', 'total', 'reversal_rate']
    by_time = by_time.sort_values('reversal_rate', ascending=False)
    print(by_time.to_string())


if __name__ == "__main__":
    main()
