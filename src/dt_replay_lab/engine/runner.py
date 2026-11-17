"""Runner: drive a feed through indicators; live_run is the loop, pre_run drains it."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator

import pandas as pd

from dt_replay_lab.engine.feed import Feed
from dt_replay_lab.engine.validator import (
    IndicatorError, as_outputs, check_data_kind, collect_specs, source, validate_output,
)
from dt_replay_lab.indicators.indicator import BatchIndicator, Indicator, Output, SeriesSpec


class RunType(Enum):
    PRERUN = "prerun"       # compute everything first, then replay with rewind
    LIVERUN = "liverun"     # compute each bar as it arrives, no rewind


@dataclass(frozen=True)
class Event:
    """One output, stamped with the bar it became known on."""

    at: int
    out: Output
    source: str


def _steps(feed, indicators: list[Indicator], specs: dict[str, SeriesSpec]) -> Iterator:
    """The one loop: advance the feed, hand each indicator the view, collect what it emits."""
    n = len(feed)

    for ind in indicators:
        ind.reset()

    i = -1

    while (view := feed.next()) is not None:
        i += 1
        events = []

        for ind in indicators:
            src = source(ind)

            try:
                outs = list(as_outputs(ind.on_bar(view)))
            except Exception as e:
                raise IndicatorError(f"{src} crashed on bar {i}: {type(e).__name__}: {e}") from e

            for out in outs:
                validate_output(i, out, specs, n, src, ind.outputs)
                events.append((ind, Event(i, out, src)))

        yield i, events


def live_run(feed, indicators: list[Indicator]) -> Iterator[tuple[int, list[Event]]]:
    """Yield (bar, events) one step at a time; the caller decides the pace."""
    batch = [source(i) for i in indicators if isinstance(i, BatchIndicator)]

    if batch:
        raise TypeError(f"live_run can't run batch indicators {batch}; use RunType.PRERUN")

    check_data_kind(feed, indicators)
    steps = _steps(feed, indicators, collect_specs(indicators))

    return ((i, [e for _, e in events]) for i, events in steps)


def pre_run(df: pd.DataFrame, indicators: list[Indicator], feed=None) -> list[Event]:
    """Every event from every indicator, sorted by bar; supports batch indicators."""
    feed = Feed(df) if feed is None else feed
    specs, n = collect_specs(indicators), len(df)
    position = {id(ind): p for p, ind in enumerate(indicators)}
    keyed = []      # (bar, indicator position, event)

    streaming = [ind for ind in indicators if not isinstance(ind, BatchIndicator)]

    if streaming:
        check_data_kind(feed, streaming)

        for _, events in _steps(feed, streaming, specs):
            keyed += [(e.at, position[id(ind)], e) for ind, e in events]

    for ind in indicators:
        if not isinstance(ind, BatchIndicator):
            continue

        src = source(ind)
        ind.reset()

        try:
            pairs = list(ind.compute(df.copy()))
        except Exception as e:
            raise IndicatorError(f"{src}.compute() crashed: {type(e).__name__}: {e}") from e

        for at, out in pairs:
            validate_output(at, out, specs, n, src, ind.outputs)
            keyed.append((at, position[id(ind)], Event(at, out, src)))

    keyed.sort(key=lambda k: k[:2])     # stable: emission order kept within a bar
    return [e for _, _, e in keyed]
