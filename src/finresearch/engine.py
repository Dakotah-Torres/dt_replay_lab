"""The entry point:  engine.run(data, SwingIndicator(n=5), SMA(20))

    from finresearch import engine
    engine.run(df, SMA(20), SwingIndicator(n=5))        # open the replay window
    rec = engine.record(df, SMA(20))                    # no GUI, just the data
    engine.check(df, SwingIndicator(n=5))               # does it follow the contract?
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .contract import Report, check_contract
from .data import load_ohlc, normalize_ohlc
from .indicator import Indicator
from .player import Player
from .recording import Recording


def _load(data) -> pd.DataFrame:
    if isinstance(data, (str, Path)):
        return load_ohlc(data)
    return normalize_ohlc(data)


def _instances(indicators) -> list[Indicator]:
    return [i() if isinstance(i, type) else i for i in indicators]


def record(data, *indicators: Indicator) -> Recording:
    """Run indicators over ``data`` and return the Recording (no window)."""
    return Recording.record(_load(data), _instances(indicators))


def run(data, *indicators: Indicator, start: int | None = None, speed: str = "10/s",
        title: str = "finresearch replay", width: int = 1500, height: int = 900) -> Player:
    """Run indicators over ``data`` and open the replay window (blocks until closed).

    ``data`` is a DataFrame (time/open/high/low/close[/volume], or a
    DatetimeIndex) or a path to a csv. ``start`` is how many bars are visible
    when the window opens.
    """
    rec = record(data, *indicators)
    print(rec.summary())
    return Player(rec, title=title, start=start, speed=speed, width=width, height=height).run()


def check(data, indicator: Indicator) -> Report:
    """Check an indicator against the contract; prints the report and returns it."""
    report = check_contract(_load(data), indicator)
    print(report)
    return report
