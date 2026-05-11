# Forward MAE/MFE Profiles Design

## Goal

Extend `forward_returns.py` so each event/horizon row includes path-dependent MAE/MFE over the 30-minute and 90-minute windows, contextualized by release-candle direction.

## Definitions

All values use percent of release candle close.

Raw long-side path fields:

- `raw_mfe_pct`: `(max_high_in_window - release_close) / release_close * 100`
- `raw_mae_pct`: `(min_low_in_window - release_close) / release_close * 100`

Direction-normalized continuation fields:

- For `up` release candle:
  - `direction_normalized_mfe_pct = raw_mfe_pct`
  - `direction_normalized_mae_pct = raw_mae_pct`
- For `down` release candle:
  - `direction_normalized_mfe_pct = (release_close - min_low_in_window) / release_close * 100`
  - `direction_normalized_mae_pct = (release_close - max_high_in_window) / release_close * 100`
- For `flat` release candle:
  - normalized MAE/MFE fields are null.

The forward window starts at the first candle after the release candle and includes the horizon candle.

## Outputs

Update `charts/forward_returns/forward_returns_by_event.csv` with new columns:

- `window_high`
- `window_low`
- `raw_mfe_pct`
- `raw_mae_pct`
- `direction_normalized_mfe_pct`
- `direction_normalized_mae_pct`

Add charts:

- `forward_returns_30m_mae_mfe_by_direction.png`
- `forward_returns_90m_mae_mfe_by_direction.png`
- `forward_returns_30m_normalized_mae_mfe_scatter.png`
- `forward_returns_90m_normalized_mae_mfe_scatter.png`

## Chart Design

By-direction MAE/MFE charts:

- one chart per horizon
- grouped boxplots by release candle direction
- compare raw MAE and raw MFE distributions
- zero horizontal line

Normalized scatter charts:

- one chart per horizon
- x-axis: normalized MAE (negative = adverse excursion)
- y-axis: normalized MFE (positive = favorable continuation excursion)
- points colored by release candle direction
- zero reference lines

## Console Summary

Extend summary output with normalized path profile by horizon:

- count
- median normalized MFE
- median normalized MAE
- mean normalized MFE
- mean normalized MAE

## Tests

Add tests for:

- MAE/MFE calculation on up candle continuation context.
- MAE/MFE sign flip on down candle continuation context.
- generated output file names include new profile charts.

## Scope

Only extend `forward_returns.py`. Do not modify sweep analysis logic in `main.py`.
