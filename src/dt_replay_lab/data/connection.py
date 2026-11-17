"""Connection: get a raw table from a source. No cleaning, no checks."""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def read_csv(path: str | Path) -> pd.DataFrame:
    """Raw csv contents, exactly as pandas reads them."""
    return pd.read_csv(path)
