"""Validation: prove a table is trustworthy. Raises on problems, never changes data."""
import pandas as pd

OHLC = ["open", "high", "low", "close"]


def require_ohlc_columns(df: pd.DataFrame) -> None:
    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing columns: {missing}")
