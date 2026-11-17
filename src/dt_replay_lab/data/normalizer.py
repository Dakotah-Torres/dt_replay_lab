"""Normalizer: reshape a raw table into the standard form the engine expects."""
import pandas as pd

from dt_replay_lab.data.validation import require_ohlc_columns


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

    # kept here so behaviour matches the old data.py; pipeline order is still to decide
    require_ohlc_columns(df)

    # lightweight-charts converts with `astype("int64") // 10**9`, which assumes
    # nanoseconds. pandas 3 defaults to microseconds, which collapses bars onto
    # duplicate timestamps and makes the chart throw "Value is null".
    df["time"] = pd.to_datetime(df["time"]).astype("datetime64[ns]")
    return df.sort_values("time").reset_index(drop=True)
