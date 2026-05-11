"""
News Event Data High/Low Sweep Analysis

Research script to test the hypothesis: when a news release candle's data high 
or low is swept, does price tend to reverse and sweep the opposite side?

Lookback: Scans from release candle to end of trading day (4:00 PM ET).
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time

# Setup paths
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "sweep_analysis_results.parquet"

# Trading day end (ET)
TRADING_DAY_END = time(16, 0)


def load_data():
    """Load economic events and NQ 1m price data."""
    events = pd.read_parquet(DATA_DIR / "economic_events.parquet")
    nq = pd.read_parquet(DATA_DIR / "nq_1m.parquet")
    
    # Ensure DateTime columns are properly formatted
    nq['DateTime_UTC'] = pd.to_datetime(nq['DateTime_UTC']).dt.tz_localize('UTC')
    nq['DateTime_ET'] = pd.to_datetime(nq['DateTime_ET'])
    events['datetime_utc'] = pd.to_datetime(events['datetime_utc'])
    
    if events['datetime_utc'].dt.tz is None:
        events['datetime_utc'] = events['datetime_utc'].dt.tz_localize('UTC')
    
    # Sort NQ by time for efficient lookups
    nq = nq.sort_values('DateTime_UTC').reset_index(drop=True)
    
    return events, nq


def get_release_candle(nq: pd.DataFrame, event_time: pd.Timestamp) -> pd.Series | None:
    """Get the release candle for an event."""
    mask = nq['DateTime_UTC'] == event_time
    candle = nq[mask]
    return candle.iloc[0] if not candle.empty else None


def get_candles_until_eod(nq: pd.DataFrame, start_time: pd.Timestamp) -> pd.DataFrame:
    """Get all candles from start_time until end of trading day (4:00 PM ET)."""
    # Get the start candle to find the trading day
    start_mask = nq['DateTime_UTC'] == start_time
    if not start_mask.any():
        return pd.DataFrame()
    
    start_idx = nq[start_mask].index[0]
    start_et = nq.loc[start_idx, 'DateTime_ET']
    
    # Get end of day timestamp (4:00 PM ET same day, or handle overnight)
    end_of_day = start_et.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # If event is after 4 PM, use next day's 4 PM
    if start_et.time() >= TRADING_DAY_END:
        end_of_day = end_of_day + pd.Timedelta(days=1)
    
    # Filter candles: after start_time AND before end of day
    mask = (nq['DateTime_UTC'] > start_time) & (nq['DateTime_ET'] <= end_of_day)
    return nq[mask]


def get_candle_at_time(nq: pd.DataFrame, target_et: pd.Timestamp) -> pd.Series | None:
    """Get a specific candle by ET timestamp."""
    mask = nq['DateTime_ET'] == target_et
    candle = nq[mask]
    return candle.iloc[0] if not candle.empty else None


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
    
    # Initialize tracking variables
    first_sweep = None
    first_sweep_time = None
    first_sweep_idx = None
    opposite_swept = False
    opposite_sweep_time = None
    synthetic_box_breached = False
    mae_before_reversal = 0.0
    
    high_swept = False
    low_swept = False
    
    # Scan for sweeps
    for idx, candle in subsequent.iterrows():
        candle_high = candle['High']
        candle_low = candle['Low']
        candle_time = candle['DateTime_UTC']
        
        # Check for high sweep
        if not high_swept and candle_high > data_high:
            high_swept = True
            if first_sweep is None:
                first_sweep = 'high'
                first_sweep_time = candle_time
                first_sweep_idx = idx
        
        # Check for low sweep
        if not low_swept and candle_low < data_low:
            low_swept = True
            if first_sweep is None:
                first_sweep = 'low'
                first_sweep_time = candle_time
                first_sweep_idx = idx
        
        # If both swept, we have our answer
        if high_swept and low_swept:
            opposite_swept = True
            opposite_sweep_time = candle_time
            break
    
    # If no first sweep occurred, skip this event
    if first_sweep is None:
        return None
    
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
    post_sweep = subsequent.loc[first_sweep_idx:]
    first_target_hit = None  # 'box', 'opposite', or None
    box_hit_time = None
    opposite_hit_time = None
    mae_before_reversal = 0.0
    synthetic_box_breached = False
    
    for idx, candle in post_sweep.iterrows():
        candle_high = candle['High']
        candle_low = candle['Low']
        candle_time = candle['DateTime_UTC']
        
        if first_sweep == 'high':
            # Momentum target = synthetic box (above)
            # Reversal target = opposite (data_low)
            if candle_high > synthetic_box_level and box_hit_time is None:
                box_hit_time = candle_time
                synthetic_box_breached = True
                if first_target_hit is None:
                    first_target_hit = 'box'
            if candle_low < opposite_level and opposite_hit_time is None:
                opposite_hit_time = candle_time
                if first_target_hit is None:
                    first_target_hit = 'opposite'
            # Track MAE (max extension in momentum direction before hitting opposite)
            if opposite_hit_time is None:
                extension = (candle_high - data_high) / range_size if range_size > 0 else 0
                mae_before_reversal = max(mae_before_reversal, extension)
        else:  # first_sweep == 'low'
            # Momentum target = synthetic box (below)
            # Reversal target = opposite (data_high)
            if candle_low < synthetic_box_level and box_hit_time is None:
                box_hit_time = candle_time
                synthetic_box_breached = True
                if first_target_hit is None:
                    first_target_hit = 'box'
            if candle_high > opposite_level and opposite_hit_time is None:
                opposite_hit_time = candle_time
                if first_target_hit is None:
                    first_target_hit = 'opposite'
            # Track MAE (max extension in momentum direction before hitting opposite)
            if opposite_hit_time is None:
                extension = (data_low - candle_low) / range_size if range_size > 0 else 0
                mae_before_reversal = max(mae_before_reversal, extension)
        
        # If both targets hit, we can stop scanning
        if box_hit_time is not None and opposite_hit_time is not None:
            break
    
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
