"""Entry points: engine.run (window), engine.record (no window), engine.check (contract)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from dt_replay_lab.data import load_ohlc, normalize_ohlc
from dt_replay_lab.engine.contract import Report, check_contract
from dt_replay_lab.engine.player import LivePlayer, Player
from dt_replay_lab.engine.runner import RunType
from dt_replay_lab.indicators.indicator import Indicator
from dt_replay_lab.viz.recording import Recording


def _load(data) -> pd.DataFrame:
    """A csv path or a DataFrame, normalized."""
    return load_ohlc(data) if isinstance(data, (str, Path)) else normalize_ohlc(data)


def _instances(indicators) -> list[Indicator]:
    """Allow passing a class instead of an instance."""
    return [i() if isinstance(i, type) else i for i in indicators]


def record(data, *indicators: Indicator) -> Recording:
    """Run indicators over data and return the Recording."""
    return Recording.record(_load(data), _instances(indicators))


def run(data, *indicators: Indicator, run_type: RunType = RunType.PRERUN,
        start: int | None = None, speed: str = "10/s", title: str | None = None,
        width: int = 1500, height: int = 900) -> Player | LivePlayer:
    """Open a replay (PRERUN) or live (LIVERUN) window; blocks until it is closed."""
    window = dict(start=start, speed=speed, width=width, height=height)

    if RunType(run_type) is RunType.LIVERUN:
        df = _load(data)
        print(f"{len(df)} bars, live")

        return LivePlayer(df, _instances(indicators), title=title or "dt_replay_lab live", **window).run()

    rec = record(data, *indicators)
    print(rec.summary())

    return Player(rec, title=title or "dt_replay_lab replay", **window).run()


def check(data, indicator: Indicator) -> Report:
    """Check an indicator against the contract; prints and returns the report."""
    report = check_contract(_load(data), indicator)
    print(report)

    return report
