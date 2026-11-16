"""Data helpers: load OHLC frames and generate synthetic test data."""
from pathlib import Path

import numpy as np
import pandas as pd

OHLC = ["open", "high", "low", "close"]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with lowercase columns and a ``time`` column.

    Accepts a frame that already has a ``time``/``date``/``datetime`` column
    or one indexed by a DatetimeIndex. The index is reset to 0..n-1 so that
    bar numbers line up with ``Swing.index``.
    """
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]

    if "time" not in df.columns:
        for alt in ("datetime", "date", "timestamp"):
            if alt in df.columns:
                df = df.rename(columns={alt: "time"})
                break
        else:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.rename_axis("time").reset_index()
            else:
                raise ValueError("DataFrame needs a 'time' column or a DatetimeIndex")

    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing columns: {missing}")

    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def load_ohlc(path: str | Path) -> pd.DataFrame:
    """Load an OHLC(V) csv into the normalized shape."""
    return normalize_ohlc(pd.read_csv(path))


def make_test_data(n_bars: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Layered sine waves so swings exist at three scales, plus noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_bars)

    close = (
        100
        + 8.0 * np.sin(t / 90)    # major
        + 3.0 * np.sin(t / 22)    # intermediate
        + 1.0 * np.sin(t / 6)     # minor
        + np.cumsum(rng.normal(0, 0.15, n_bars))
    )
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0, 0.25, n_bars))

    return pd.DataFrame({
        "time":   pd.date_range("2026-01-05 09:30", periods=n_bars, freq="5min"),
        "open":   open_,
        "high":   np.maximum(open_, close) + wick,
        "low":    np.minimum(open_, close) - wick,
        "close":  close,
        "volume": rng.integers(100, 1000, n_bars),
    })
