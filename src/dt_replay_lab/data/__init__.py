"""Data layer: connection -> normalizer -> validation."""
from pathlib import Path

import pandas as pd

from dt_replay_lab.data.connection import DATA_DIR, make_test_data, read_csv
from dt_replay_lab.data.normalizer import normalize_ohlc
from dt_replay_lab.data.validation import OHLC, require_ohlc_columns


def load_ohlc(path: str | Path) -> pd.DataFrame:
    """Load an OHLC(V) csv into the normalized shape."""
    return normalize_ohlc(read_csv(path))


__all__ = [
    "DATA_DIR", "OHLC", "load_ohlc", "make_test_data", "normalize_ohlc", "read_csv",
    "require_ohlc_columns",
]
