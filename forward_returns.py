"""
Forward return analysis around news events.

Calculates 30m/90m forward returns from release candle close and contextualizes
results by release-candle direction.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DEFAULT_EVENTS = Path("data/economic_events.parquet")
DEFAULT_NQ = Path("data/nq_1m.parquet")
DEFAULT_OUTPUT_DIR = Path("charts/forward_returns")
DEFAULT_HORIZONS = (30, 90)


def ensure_utc(series: pd.Series) -> pd.Series:
    converted = pd.to_datetime(series)
    if converted.dt.tz is None:
        return converted.dt.tz_localize("UTC")
    return converted.dt.tz_convert("UTC")


def normalize_nq_columns(nq: pd.DataFrame) -> pd.DataFrame:
    normalized = nq.copy()
    if "DateTime_UTC" not in normalized.columns and "datetime_utc" in normalized.columns:
        normalized = normalized.rename(columns={"datetime_utc": "DateTime_UTC"})
    normalized["DateTime_UTC"] = ensure_utc(normalized["DateTime_UTC"])
    return normalized.sort_values("DateTime_UTC").reset_index(drop=True)


def timestamp_ns_utc(timestamp: pd.Timestamp) -> int:
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.value


def find_sorted_pos(values: np.ndarray, value: int) -> int | None:
    pos = int(np.searchsorted(values, value, side="left"))
    if pos < len(values) and values[pos] == value:
        return pos
    return None


def candle_direction(open_price: float, close_price: float) -> str:
    if close_price > open_price:
        return "up"
    if close_price < open_price:
        return "down"
    return "flat"


def direction_normalized_return(raw_return_pct: float, direction: str) -> float:
    if direction == "up":
        return raw_return_pct
    if direction == "down":
        return -raw_return_pct
    return np.nan


def build_forward_returns(
    events: pd.DataFrame,
    nq: pd.DataFrame,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    events = events.copy()
    events["datetime_utc"] = ensure_utc(events["datetime_utc"])
    nq = normalize_nq_columns(nq)
    utc_values = nq["DateTime_UTC"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")

    rows: list[dict] = []
    for _, event in events.iterrows():
        event_time = event["datetime_utc"]
        release_pos = find_sorted_pos(utc_values, timestamp_ns_utc(event_time))
        if release_pos is None:
            continue

        release = nq.iloc[release_pos]
        release_close = float(release["Close"])
        direction = candle_direction(float(release["Open"]), release_close)

        for horizon in horizons:
            future_time = event_time + pd.Timedelta(minutes=int(horizon))
            future_pos = find_sorted_pos(utc_values, timestamp_ns_utc(future_time))
            if future_pos is None:
                continue
            future = nq.iloc[future_pos]
            future_close = float(future["Close"])
            raw_return = ((future_close - release_close) / release_close) * 100
            rows.append(
                {
                    "event_type": event["title"],
                    "event_datetime": event_time,
                    "horizon_minutes": int(horizon),
                    "news_candle_direction": direction,
                    "release_open": float(release["Open"]),
                    "release_high": float(release["High"]),
                    "release_low": float(release["Low"]),
                    "release_close": release_close,
                    "future_close": future_close,
                    "raw_forward_return_pct": raw_return,
                    "direction_normalized_return_pct": direction_normalized_return(raw_return, direction),
                }
            )

    return pd.DataFrame(rows)
