# Forward Returns Charts Design

## Goal

Add a script that calculates and plots 30-minute and 90-minute forward returns around each economic news event, contextualized by the direction of the release candle.

## Inputs

- `data/economic_events.parquet`
  - event timestamps in `datetime_utc`
  - event labels in `title`
- `data/nq_1m.parquet`
  - 1-minute NQ OHLCV bars
  - UTC timestamps in `datetime_utc` or `DateTime_UTC`

The `data/` directory remains local and ignored by git.

## Script

Create `forward_returns.py`.

The script will:

1. Load event and NQ data.
2. Normalize NQ timestamp column to `DateTime_UTC`.
3. Sort NQ by UTC timestamp and use integer nanosecond arrays for fast exact lookups.
4. For each event with an exact release candle match:
   - derive `news_candle_direction`:
     - `up` when `Close > Open`
     - `down` when `Close < Open`
     - `flat` when `Close == Open`
   - compute raw forward return from release candle close to future close at 30 and 90 minutes:
     - `(future_close - release_close) / release_close * 100`
   - compute direction-normalized return:
     - `up`: raw return
     - `down`: `-raw_return`
     - `flat`: null / excluded from normalized charts
5. Save an event-level CSV and charts.

## Outputs

Directory: `charts/forward_returns/`

- `forward_returns_by_event.csv`
  - one row per event/horizon where release and future candles exist
  - columns: event type, event timestamp, horizon, release OHLC, news candle direction, raw forward return percent, direction-normalized return percent
- `forward_returns_30m_raw_by_direction.png`
- `forward_returns_90m_raw_by_direction.png`
- `forward_returns_30m_direction_normalized.png`
- `forward_returns_90m_direction_normalized.png`

## Chart Design

Raw by-direction charts:

- one chart per horizon
- boxplot plus jittered points grouped by `news_candle_direction`
- y-axis: raw forward return percent
- horizontal zero line
- title includes horizon and sample count

Direction-normalized charts:

- one histogram per horizon
- positive values mean continuation in release candle direction
- negative values mean fade against release candle direction
- vertical zero line
- title includes horizon and sample count

## Console Summary

Print summary by horizon and candle direction:

- count
- mean raw return percent
- median raw return percent
- win rate where raw return percent is positive
- 25th percentile
- 75th percentile

Print summary by horizon for direction-normalized returns:

- count
- mean normalized return percent
- median normalized return percent
- continuation rate where normalized return percent is positive
- 25th percentile
- 75th percentile

## Error Handling

- If an event has no exact release candle, skip it.
- If a horizon candle is missing, skip that event/horizon row.
- If no rows are produced, raise a clear error.
- Flat candles remain in raw charts but are excluded from normalized charts.

## Tests

Add tests covering:

- release candle direction labeling
- raw forward return calculation
- direction-normalized return sign flip for down candles
- missing future candle skip behavior

## Scope

This feature adds forward-return research outputs only. It does not change sweep-analysis logic in `main.py`.
