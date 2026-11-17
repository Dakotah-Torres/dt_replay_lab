"""Validation: prove a table is trustworthy; raises on problems, never changes data."""
import pandas as pd

OHLC = ["open", "high", "low", "close"]


def require_ohlc_columns(df: pd.DataFrame) -> None:
    """Raise if any of open/high/low/close is missing."""
    missing = [c for c in OHLC if c not in df.columns]

    if missing:
        raise ValueError(f"DataFrame is missing columns: {missing}")
