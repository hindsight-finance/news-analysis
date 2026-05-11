"""
News Event Injection Analysis
Generates histograms of price ranges for each news event:
1. Release candle range (1-minute)
2. 10-minute range following release (inclusive)
Ranges are normalized to percentages.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Setup paths
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "charts"
OUTPUT_DIR.mkdir(exist_ok=True)

def load_data():
    """Load economic events and NQ 1m price data."""
    events = pd.read_parquet(DATA_DIR / "economic_events.parquet")
    nq = pd.read_parquet(DATA_DIR / "nq_1m.parquet")
    
    # Ensure DateTime_UTC is datetime with timezone
    nq['DateTime_UTC'] = pd.to_datetime(nq['DateTime_UTC']).dt.tz_localize('UTC')
    events['datetime_utc'] = pd.to_datetime(events['datetime_utc'])
    
    # Ensure events datetime is UTC-aware
    if events['datetime_utc'].dt.tz is None:
        events['datetime_utc'] = events['datetime_utc'].dt.tz_localize('UTC')
    
    return events, nq


def calculate_percentage_range(high, low, reference_price):
    """Calculate price range as a percentage of the reference price."""
    return ((high - low) / reference_price) * 100


def get_release_candle_data(nq: pd.DataFrame, event_time: pd.Timestamp) -> tuple[float, int] | None:
    """Get the percentage range and volume of the 1-minute candle at event release time."""
    # Find the exact minute matching the event time
    mask = nq['DateTime_UTC'] == event_time
    candle = nq[mask]
    
    if candle.empty:
        return None
    
    candle = candle.iloc[0]
    pct_range = calculate_percentage_range(candle['High'], candle['Low'], candle['Open'])
    return pct_range, candle['Volume']


def get_10min_range(nq: pd.DataFrame, event_time: pd.Timestamp) -> float | None:
    """Get the percentage range of the 10-minute window following event release (inclusive)."""
    # Get candles from event_time to event_time + 9 minutes (10 candles total)
    end_time = event_time + pd.Timedelta(minutes=9)
    mask = (nq['DateTime_UTC'] >= event_time) & (nq['DateTime_UTC'] <= end_time)
    candles = nq[mask]
    
    if candles.empty:
        return None
    
    high = candles['High'].max()
    low = candles['Low'].min()
    reference_price = candles.iloc[0]['Open']  # Use first candle's open as reference
    
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
    
    # Get unique event titles
    unique_events = events['title'].unique()
    print(f"Found {len(unique_events)} unique event types")
    
    # Process each event type
    for event_name in unique_events:
        print(f"\nProcessing: {event_name}")
        
        # Get all occurrences of this event
        event_occurrences = events[events['title'] == event_name]
        
        release_ranges = []
        release_volumes = []
        ten_min_ranges = []
        
        for _, row in event_occurrences.iterrows():
            event_time = row['datetime_utc']
            
            # Get release candle data (range and volume)
            release_data = get_release_candle_data(nq, event_time)
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
