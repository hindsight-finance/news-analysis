# Forward MAE/MFE Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add path-dependent MAE/MFE metrics and charts to the forward returns analysis.

**Architecture:** Extend the existing standalone `forward_returns.py` calculation loop to derive window highs/lows and normalized continuation MAE/MFE. Add chart functions for raw by-direction profiles and normalized MAE/MFE scatter. Update tests and README.

**Tech Stack:** Python 3.12, pandas, numpy, matplotlib, pytest.

---

## File Structure

- Modify `forward_returns.py`: add MAE/MFE columns, summaries, charts.
- Modify `tests/test_forward_returns.py`: add TDD tests for MAE/MFE and output chart names.
- Modify `README.md`: document new outputs.

### Task 1: Calculation Columns

**Files:**
- Modify: `forward_returns.py`
- Modify: `tests/test_forward_returns.py`

- [ ] **Step 1: Write failing MAE/MFE calculation assertions**

Add assertions to existing forward-return tests checking `raw_mfe_pct`, `raw_mae_pct`, `direction_normalized_mfe_pct`, and `direction_normalized_mae_pct`.

- [ ] **Step 2: Run focused test**

Run: `python3 -m pytest tests/test_forward_returns.py::test_build_forward_returns_computes_raw_and_normalized_returns -q`

Expected: FAIL with missing MAE/MFE columns.

- [ ] **Step 3: Implement MAE/MFE columns**

In `build_forward_returns`, slice `nq.iloc[release_pos + 1:future_pos + 1]`, calculate `window_high`, `window_low`, raw long-side MFE/MAE, and direction-normalized continuation MFE/MAE.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_forward_returns.py -q`

Expected: PASS.

### Task 2: Charts and Summaries

**Files:**
- Modify: `forward_returns.py`
- Modify: `tests/test_forward_returns.py`
- Modify: `README.md`

- [ ] **Step 1: Update output test expected files**

Add expected file names:

- `forward_returns_30m_mae_mfe_by_direction.png`
- `forward_returns_90m_mae_mfe_by_direction.png`
- `forward_returns_30m_normalized_mae_mfe_scatter.png`
- `forward_returns_90m_normalized_mae_mfe_scatter.png`

Run: `python3 -m pytest tests/test_forward_returns.py::test_write_outputs_creates_csv_and_expected_charts -q`

Expected: FAIL because new charts are not written.

- [ ] **Step 2: Implement chart functions**

Add:

- `plot_mae_mfe_by_direction(df, horizon, output_path)`
- `plot_normalized_mae_mfe_scatter(df, horizon, output_path)`

Call both from `write_outputs`.

- [ ] **Step 3: Extend summaries**

Add `summarize_path_profiles(df)` and print output from `run`.

- [ ] **Step 4: Update README**

Add new chart outputs under `charts/forward_returns/`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python3 -m pytest tests -q
python3 -u forward_returns.py
```

Commit:

```bash
git add forward_returns.py tests/test_forward_returns.py README.md charts/forward_returns docs/superpowers/specs/2026-05-11-forward-mae-mfe-profiles-design.md docs/superpowers/plans/2026-05-11-forward-mae-mfe-profiles.md
git commit -m "feat: add forward mae mfe profiles"
```

## Self-Review

- Spec coverage: calculation, charts, CSV columns, summaries, tests, README covered.
- Placeholder scan: no placeholders remain.
- Type consistency: column and function names match spec and tasks.
