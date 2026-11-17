"""Normalizer: reshape a raw table into the standard form the engine expects."""
import pandas as pd

from dt_replay_lab.data.validation import require_ohlc_columns

TIME_NAMES = ("time", "datetime", "date", "timestamp")


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, a 'time' column in nanoseconds, sorted, rows numbered 0..n-1."""
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]

    time_col = next((c for c in TIME_NAMES if c in df.columns), None)

    if time_col:
        df = df.rename(columns={time_col: "time"})
    elif isinstance(df.index, pd.DatetimeIndex):
        df = df.rename_axis("time").reset_index()
    else:
        raise ValueError("DataFrame needs a 'time' column or a DatetimeIndex")

    require_ohlc_columns(df)

    # nanoseconds: the chart library assumes ns, pandas 3 defaults to us
    df["time"] = pd.to_datetime(df["time"]).astype("datetime64[ns]")

    return df.sort_values("time").reset_index(drop=True)
