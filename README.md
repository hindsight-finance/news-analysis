# News Analysis

Python research scripts for studying NQ 1-minute price behavior around US economic news releases.

The core hypothesis: after a news-release candle's high or low is swept, does price reverse to sweep the opposite side, or continue to a synthetic momentum box?

## Data

Tracked Parquet inputs live in `data/`:

- `economic_events.parquet` — US economic event calendar, `2010-01-01` to `2026-03-31`
- `nq_1m.parquet` — NQ 1-minute OHLCV data, `2010-06-06` to `2026-03-15`
- `sweep_analysis_results.parquet` — generated event-level sweep analysis, currently `2010-06-09` to `2026-03-13`

## Scripts

- `main.py` — builds `data/sweep_analysis_results.parquet` from raw event and NQ data
- `exploration.py` — creates exploratory charts and `charts/exploration/summary_by_event.csv`
- `causal_analysis.py` — trains simple interpretable models and creates causal-factor charts/CSVs
- `injection.py` — creates per-event release-candle and 10-minute range histograms

## Outputs

Main generated outputs:

- `data/sweep_analysis_results.parquet`
- `charts/exploration/`
  - `momentum_vs_reversal_by_event.png`
  - `momentum_vs_reversal_by_release_time.png`
  - `win_rate_by_range_quartile.png`
  - `mae_distribution.png`
  - `summary_by_event.csv`
- `charts/causal/`
  - `feature_importance.png`
  - `decision_tree.png`
  - `logistic_coefficients.png`
  - `event_edge.png`
  - `event_stats.csv`

Latest full run summary:

- Events loaded: `5067`
- Events analyzed: `4792`
- Opposite side swept: `3860 / 4792` (`80.6%`)
- Momentum box first: `2500 / 4792` (`52.2%`)
- Reversal opposite first: `2189 / 4792` (`45.7%`)
- Neither target hit by EOD: `103 / 4792` (`2.1%`)
- Resolved trades: momentum `53.3%`, reversal `46.7%`

## Usage

Use Python 3.12+ with pandas, numpy, matplotlib, scikit-learn, pyarrow, polars, and pytest installed.

Run the full analysis:

```bash
python3 main.py
python3 exploration.py
python3 causal_analysis.py
```

Run tests:

```bash
python3 -m pytest tests -q
```

## Notes

This repo was migrated away from Jupyter notebooks. The Python scripts are now canonical; old notebooks were removed after equivalent scripts were added.
