"""Feed: the engine-owned stream that hands indicators the past, one step at a time."""
import numpy as np
import pandas as pd

from dt_replay_lab.indicators.indicator import Bars

COLUMNS = ("time", "open", "high", "low", "close", "volume")


class Feed:
    """Any object with __len__, next() and data_kind can replace this (your cursor goes here)."""

    data_kind = None        # hook: which data type this stream carries (your DataKind enum)


    def __init__(self, df: pd.DataFrame) -> None:
        self._arrays = []

        for col in COLUMNS:
            values = df[col].to_numpy() if col in df else np.zeros(len(df))
            array = np.array(values, copy=True)
            array.flags.writeable = False
            self._arrays.append(array)

        self._i = -1


    def __len__(self) -> int:
        return len(self._arrays[0])


    def next(self) -> Bars | None:
        """Move forward one bar and return everything seen so far; None at the end."""
        self._i += 1

        if self._i >= len(self):
            return None

        return Bars(self._i, *(a[:self._i + 1] for a in self._arrays))
