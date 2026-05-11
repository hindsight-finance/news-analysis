# Forward Returns Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build forward-return calculations and charts for 30-minute and 90-minute horizons, contextualized by release-candle direction.

**Architecture:** Add standalone `forward_returns.py` with pure calculation functions plus CLI plotting. Tests exercise calculation behavior with small pandas DataFrames. README documents the new script and outputs.

**Tech Stack:** Python 3.12, pandas, numpy, matplotlib, pytest, Parquet inputs in ignored `data/`.

---

## File Structure

- Create `forward_returns.py`: load data, compute event/horizon return rows, print summaries, save CSV/charts.
- Create `tests/test_forward_returns.py`: unit tests for candle direction, raw returns, normalized returns, missing horizon skip.
- Modify `README.md`: document script and generated outputs.

### Task 1: Forward Return Calculation Core

**Files:**
- Create: `forward_returns.py`
- Create: `tests/test_forward_returns.py`

- [ ] **Step 1: Write failing tests**

```python
import pandas as pd

from forward_returns import build_forward_returns, candle_direction, direction_normalized_return


def test_candle_direction_labels_up_down_flat():
    assert candle_direction(100.0, 101.0) == "up"
    assert candle_direction(101.0, 100.0) == "down"
    assert candle_direction(100.0, 100.0) == "flat"


def test_direction_normalized_return_flips_down_candles_and_excludes_flat():
    assert direction_normalized_return(1.5, "up") == 1.5
    assert direction_normalized_return(1.5, "down") == -1.5
    assert pd.isna(direction_normalized_return(1.5, "flat"))


def test_build_forward_returns_computes_raw_and_normalized_returns():
    events = pd.DataFrame({"datetime_utc": [pd.Timestamp("2024-01-02 13:30:00", tz="UTC")], "title": ["US Test"]})
    nq = pd.DataFrame(
        {
            "datetime_utc": pd.to_datetime(
                ["2024-01-02 13:30:00", "2024-01-02 14:00:00", "2024-01-02 15:00:00"], utc=True
            ),
            "Open": [100.0, 101.0, 102.0],
            "High": [102.0, 103.0, 104.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [101.0, 103.02, 98.98],
            "Volume": [10, 11, 12],
        }
    )

    result = build_forward_returns(events, nq, horizons=(30, 90))

    assert result["horizon_minutes"].tolist() == [30, 90]
    assert result["news_candle_direction"].tolist() == ["up", "up"]
    assert result["raw_forward_return_pct"].round(2).tolist() == [2.0, -2.0]
    assert result["direction_normalized_return_pct"].round(2).tolist() == [2.0, -2.0]


def test_build_forward_returns_skips_missing_future_candle():
    events = pd.DataFrame({"datetime_utc": [pd.Timestamp("2024-01-02 13:30:00", tz="UTC")], "title": ["US Test"]})
    nq = pd.DataFrame(
        {
            "datetime_utc": pd.to_datetime(["2024-01-02 13:30:00", "2024-01-02 14:00:00"], utc=True),
            "Open": [101.0, 100.0],
            "High": [102.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.0, 99.0],
            "Volume": [10, 11],
        }
    )

    result = build_forward_returns(events, nq, horizons=(30, 90))

    assert result["horizon_minutes"].tolist() == [30]
    assert result["news_candle_direction"].tolist() == ["down"]
    assert result["raw_forward_return_pct"].round(2).tolist() == [-1.0]
    assert result["direction_normalized_return_pct"].round(2).tolist() == [1.0]
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python3 -m pytest tests/test_forward_returns.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'forward_returns'`.

- [ ] **Step 3: Implement calculation functions in `forward_returns.py`**

Implement:

- `ensure_utc(series: pd.Series) -> pd.Series`
- `normalize_nq_columns(nq: pd.DataFrame) -> pd.DataFrame`
- `candle_direction(open_price: float, close_price: float) -> str`
- `direction_normalized_return(raw_return_pct: float, direction: str) -> float`
- `build_forward_returns(events: pd.DataFrame, nq: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame`

Use exact timestamp lookup via nanosecond arrays; output one row per event/horizon with release OHLC and returns.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python3 -m pytest tests/test_forward_returns.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forward_returns.py tests/test_forward_returns.py
git commit -m "feat: calculate news forward returns"
```

### Task 2: Charts, CLI, README

**Files:**
- Modify: `forward_returns.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI/chart test**

Add test to `tests/test_forward_returns.py`:

```python
from pathlib import Path

from forward_returns import write_outputs


def test_write_outputs_creates_csv_and_expected_charts(tmp_path):
    df = pd.DataFrame(
        {
            "event_type": ["US Test", "US Test", "US Test", "US Test"],
            "event_datetime": pd.to_datetime(
                ["2024-01-02 13:30:00", "2024-01-03 13:30:00", "2024-01-02 13:30:00", "2024-01-03 13:30:00"], utc=True
            ),
            "horizon_minutes": [30, 30, 90, 90],
            "news_candle_direction": ["up", "down", "up", "down"],
            "raw_forward_return_pct": [1.0, -0.5, 2.0, -1.0],
            "direction_normalized_return_pct": [1.0, 0.5, 2.0, 1.0],
            "release_open": [100.0, 100.0, 100.0, 100.0],
            "release_close": [101.0, 99.0, 101.0, 99.0],
            "future_close": [102.01, 98.505, 103.02, 98.01],
        }
    )

    write_outputs(df, tmp_path)

    expected = {
        "forward_returns_by_event.csv",
        "forward_returns_30m_raw_by_direction.png",
        "forward_returns_90m_raw_by_direction.png",
        "forward_returns_30m_direction_normalized.png",
        "forward_returns_90m_direction_normalized.png",
    }
    assert expected == {p.name for p in tmp_path.iterdir()}
```

- [ ] **Step 2: Run chart test to verify RED**

Run: `python3 -m pytest tests/test_forward_returns.py::test_write_outputs_creates_csv_and_expected_charts -q`

Expected: FAIL with `ImportError` for `write_outputs` or missing files.

- [ ] **Step 3: Implement chart and CLI functions**

Implement:

- `summarize_returns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`
- `plot_raw_by_direction(df: pd.DataFrame, horizon: int, output_path: Path) -> None`
- `plot_direction_normalized(df: pd.DataFrame, horizon: int, output_path: Path) -> None`
- `write_outputs(df: pd.DataFrame, output_dir: Path) -> None`
- `run(input_events: Path, input_nq: Path, output_dir: Path, horizons: tuple[int, ...]) -> None`
- CLI args for `--events`, `--nq`, `--output-dir`, `--horizons`

- [ ] **Step 4: Run full tests**

Run: `python3 -m pytest tests -q`

Expected: PASS.

- [ ] **Step 5: Run script on local data**

Run: `python3 -u forward_returns.py`

Expected: creates all files under `charts/forward_returns/` and prints summaries.

- [ ] **Step 6: Update README**

Add `forward_returns.py` to Scripts and add new outputs under `charts/forward_returns/`.

- [ ] **Step 7: Commit**

```bash
git add forward_returns.py tests/test_forward_returns.py README.md charts/forward_returns docs/superpowers/plans/2026-05-11-forward-returns.md
git commit -m "feat: chart forward returns by news candle direction"
```

## Self-Review

- Spec coverage: calculation, charts, CSV, summaries, missing data behavior, tests, README are covered.
- Placeholder scan: no placeholders remain.
- Type consistency: function names match between tests and implementation tasks.
