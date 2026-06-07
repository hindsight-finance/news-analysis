# Technology Stack

**Analysis Date:** 2026-06-07

## Languages

**Primary:**
- Python 3.12 - All analysis scripts and tests

## Runtime

**Environment:**
- CPython 3.12.3

**Package Manager:**
- pip (system-level; no lockfile, no `requirements.txt`, no `pyproject.toml`)
- Lockfile: missing — dependencies documented only in `README.md` prose

## Frameworks

**Core:**
- pandas 2.1.4 - Tabular data manipulation, parquet I/O, timezone-aware datetime handling
- numpy 1.26.4 - Array operations, sorted binary search (`np.searchsorted`), random number generation
- matplotlib 3.6.3 - All chart rendering; non-interactive `Agg` backend used in all analysis scripts

**Machine Learning:**
- scikit-learn 1.8.0 - `RandomForestClassifier`, `DecisionTreeClassifier`, `LogisticRegression`, `StandardScaler`, `LabelEncoder`, `cross_val_score` (used in `causal_analysis.py`)

**Testing:**
- pytest 9.0.2 - Test runner; no config file (`pytest.ini` / `pyproject.toml` / `setup.cfg` absent); tests run with `python3 -m pytest tests -q`

**Build/Dev:**
- None detected — no build tooling, no virtual environment manager config (no `Pipfile`, `poetry.lock`, `.python-version`, or `venv`)

## Key Dependencies

**Critical:**
- `pandas` 2.1.4 - Core data structure for all event and OHLCV data; parquet read/write via `read_parquet` / `to_parquet`; timezone conversion throughout
- `pyarrow` 23.0.1 - Parquet serialization backend for pandas; required for reading `data/economic_events.parquet`, `data/nq_1m.parquet`, and `data/sweep_analysis_results.parquet`
- `numpy` 1.26.4 - Fast sorted timestamp lookups (`np.searchsorted`) used as a performance optimization in `main.py` and `forward_returns.py`
- `scikit-learn` 1.8.0 - All ML models in `causal_analysis.py`; `n_jobs=-1` used in RandomForest (parallelism)
- `matplotlib` 3.6.3 - Every PNG chart output; `matplotlib.use("Agg")` called at module level in `causal_analysis.py`, `exploration.py`, and `forward_returns.py`

**Infrastructure:**
- `polars` 1.40.1 - Listed as a project dependency in `README.md`; not imported in any current script (available but unused)
- `zoneinfo` - Python 3.9+ stdlib; used in `main.py` for `America/New_York` timezone handling

## Configuration

**Environment:**
- No environment variables used; no `.env` file
- All paths are relative `Path(__file__).parent / "data"` or hardcoded `Path("data/...")` defaults, making scripts CWD-sensitive when called with argparse defaults
- Data directory `data/` is gitignored

**Build:**
- No build configuration files detected

## Platform Requirements

**Development:**
- Python 3.12+ (uses `int | None` union syntax in function signatures, `from __future__ import annotations` in newer scripts)
- All listed packages installed system-wide or in active environment
- No OS-specific code; `zoneinfo` stdlib handles timezone data

**Production:**
- Not applicable — pure research/analysis scripts; no server, no deployment target
- Outputs are local files: `.parquet` in `data/`, `.png` and `.csv` in `charts/`

---

*Stack analysis: 2026-06-07*
