# Testing Patterns

**Analysis Date:** 2026-06-07

## Test Framework

**Runner:**
- pytest (inferred from `.pytest_cache/`, `monkeypatch` and `tmp_path` built-in fixtures, and cached node IDs in `.pytest_cache/v/cache/nodeids`)
- Python 3.12 (from `__pycache__/test_*.cpython-312-pytest-9.0.2.pyc`)
- pytest version: 9.0.2
- Config: No `pytest.ini`, `pyproject.toml`, or `setup.cfg` found — pytest runs with defaults

**Assertion Library:**
- Plain `assert` statements. No third-party assertion library.

**Run Commands:**
```bash
pytest                   # Run all tests
pytest tests/            # Run tests directory explicitly
pytest -v                # Verbose output with test names
# No coverage command configured
```

## Test File Organization

**Location:**
- Separate `tests/` directory at the project root — not co-located with source files

**Naming:**
- Files: `test_<subject>.py` — grouped by the module or concern being tested
  - `tests/test_forward_returns.py` — tests for `forward_returns.py`
  - `tests/test_analysis_scripts.py` — tests for `exploration.py` and `causal_analysis.py`
  - `tests/test_main_data_loading.py` — tests for data-loading functions in `main.py`
- Test functions: `test_<function_name>_<behavior_description>` — extremely descriptive, behavior-focused names that read as sentences:
  - `test_candle_direction_labels_up_down_flat`
  - `test_build_forward_returns_computes_raw_and_normalized_returns`
  - `test_load_data_accepts_lowercase_utc_schema_and_adds_et`
  - `test_qcut_with_fallback_labels_handles_duplicate_bin_edges`

**Structure:**
```
tests/
├── test_analysis_scripts.py   # exploration.py + causal_analysis.py
├── test_forward_returns.py    # forward_returns.py
└── test_main_data_loading.py  # main.py (data loading functions only)
```

No `conftest.py` exists. No shared fixtures.

## Test Structure

**Suite Organization:**
```python
# No class grouping — all tests are module-level functions
def test_<name>():
    # arrange inline
    # act
    result = function_under_test(...)
    # assert
    assert result["column"].tolist() == [...]
```

**Patterns:**
- Arrange-Act-Assert within each test function body
- No shared setup/teardown — each test is fully self-contained
- Helper functions at module level to build shared test data (not fixtures):
  ```python
  def sample_results() -> pd.DataFrame:
      return pd.DataFrame({
          "event_type": ["A", "A", "B", "B"],
          ...
      })
  ```
  Used in `tests/test_analysis_scripts.py` — called directly inside each test, not injected

## Mocking

**Framework:** pytest built-in `monkeypatch` only. No `unittest.mock`, no `pytest-mock`.

**Patterns:**
```python
# Patching module-level Path constants to redirect file I/O
def test_load_data_accepts_lowercase_utc_schema_and_adds_et(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # write test parquet files to tmp_path
    events.to_parquet(data_dir / "economic_events.parquet")
    nq.to_parquet(data_dir / "nq_1m.parquet")
    # redirect DATA_DIR constant in the main module
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    loaded_events, loaded_nq = main.load_data()
    ...
```
See `tests/test_main_data_loading.py` lines 8–39.

**What to Mock:**
- Module-level `Path` constants that point to real data files (e.g., `main.DATA_DIR`)
- Use `monkeypatch.setattr(module, "CONSTANT_NAME", tmp_path / "data")` to redirect I/O

**What NOT to Mock:**
- DataFrame operations, numpy operations, computation logic — always tested with real in-memory data
- No mocking of pandas, numpy, matplotlib, or sklearn functions

## Fixtures and Factories

**Test Data:**
```python
# Pattern 1: inline minimal DataFrame in each test
nq = pd.DataFrame({
    "datetime_utc": pd.to_datetime(
        ["2024-01-02 13:30:00", "2024-01-02 14:00:00", "2024-01-02 15:00:00"], utc=True
    ),
    "Open": [100.0, 101.0, 102.0],
    "High": [102.0, 103.0, 104.0],
    "Low": [99.0, 100.0, 101.0],
    "Close": [101.0, 103.02, 98.98],
    "Volume": [10, 11, 12],
})

# Pattern 2: module-level factory function returning shared DataFrame
def sample_results() -> pd.DataFrame:
    return pd.DataFrame({...})

def test_compute_win_rates_counts_resolved_outcomes_only():
    rates = compute_win_rates(sample_results(), ["event_type"])
    ...
```

**Location:**
- All test data defined inline or in helper functions within the test file itself
- No `fixtures/` directory, no fixture files, no external test data files

**Filesystem Fixtures:**
- `tmp_path` (pytest built-in) used in `tests/test_main_data_loading.py` and `tests/test_forward_returns.py` to create isolated temporary directories for parquet files and chart output

## Coverage

**Requirements:** None enforced — no coverage tool configured, no minimum threshold set

**View Coverage:**
```bash
# Not configured. Run manually if needed:
pytest --cov=. --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- All tests are unit tests. Functions tested in isolation with constructed in-memory data.
- Pure computation functions tested with minimal DataFrames (2–4 rows) that exercise specific branches

**Integration Tests:**
- `test_write_outputs_creates_csv_and_expected_charts` in `tests/test_forward_returns.py` tests the full `write_outputs()` pipeline — DataFrame in, files on disk out — using `tmp_path`. This is the closest to integration.
- `test_load_data_accepts_lowercase_utc_schema_and_adds_et` in `tests/test_main_data_loading.py` writes real parquet files to `tmp_path` and calls `main.load_data()` end-to-end

**E2E Tests:** Not present

## Common Patterns

**Numeric Assertion Pattern:**
```python
# Round then compare as list — avoids float precision issues
assert result["raw_forward_return_pct"].round(2).tolist() == [2.0, -2.0]
assert result["raw_mfe_pct"].round(2).tolist() == [1.98, 2.97]
```
Used consistently in `tests/test_forward_returns.py`.

**NaN Assertion Pattern:**
```python
import pandas as pd
assert pd.isna(direction_normalized_return(1.5, "flat"))
```

**File Output Assertion Pattern:**
```python
# Assert exact set of output filenames — no extra or missing files
expected = {
    "forward_returns_by_event.csv",
    "forward_returns_30m_raw_by_direction.png",
    ...
}
assert expected == {p.name for p in tmp_path.iterdir()}
```
Used in `tests/test_forward_returns.py` `test_write_outputs_creates_csv_and_expected_charts`.

**DataFrame Cell Assertion Pattern:**
```python
# Access by label index after filtering
row_b = rates[rates["event_type"] == "B"].iloc[0]
assert row_b["momentum_rate"] == 100.0
# Or by positional index
assert summary.iloc[0]["event_type"] == "B"
# Or by column label on resolved index
assert features.loc[1, "pre_candle_range_pct"] == 0
```

**Mid-File Import Pattern:**
Secondary symbols are imported mid-file in some tests (non-standard placement):
```python
# tests/test_forward_returns.py line 69
from forward_returns import write_outputs

def test_write_outputs_creates_csv_and_expected_charts(tmp_path):
    ...
```
This pattern groups imports with the tests that use them rather than consolidating at the top of the file.

**Constants Test Pattern:**
```python
# Regression-guard for configuration constants
def test_default_horizons_include_intermediate_timeframes():
    from forward_returns import DEFAULT_HORIZONS
    assert DEFAULT_HORIZONS == (15, 30, 45, 60, 90)
```
Used in `tests/test_forward_returns.py` to lock down `DEFAULT_HORIZONS`.

---

*Testing analysis: 2026-06-07*
