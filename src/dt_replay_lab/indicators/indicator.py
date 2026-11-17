"""The indicator contract: what an indicator sees, and what it may emit.

A *streaming* indicator is fed one bar at a time via ``on_bar``. It only
ever sees bars up to and including the current one, so it cannot peek at the
future. Whatever it yields is stamped with the bar it was emitted on, and the
replay shows it from that bar onward. A swing high found at bar 40 but only
confirmed at bar 45 appears at bar 45 -- exactly as it would live.

A *batch* indicator (``BatchIndicator``) computes everything in one
vectorised pass and must say on which bar each output became knowable.
``dt_replay_lab.check_lookahead`` verifies it didn't cheat.

Outputs
-------
``Value``  a point on a declared line/histogram series
``Mark``   a marker on a candle (may refer to an earlier bar than it is
           emitted on, e.g. a swing confirmed ``n`` bars later)
``Draw``   a drawing: hline, vline, trend, box, vspan
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, Iterable, Literal

import numpy as np

Position = Literal["above", "below"]


@dataclass(frozen=True)
class Bars:
    """Read-only view of every bar up to and including the current one."""
    i: int                     # index of the current (latest) bar
    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return self.i + 1


@dataclass(frozen=True)
class SeriesSpec:
    """Declares a line/histogram an indicator draws values onto."""
    name: str                          # unique across all indicators in a run
    pane: str = "main"                 # "main" overlays price, else a sub-pane name
    color: str | None = None
    width: int = 2
    style: str = "solid"
    kind: Literal["line", "histogram"] = "line"
    levels: tuple[float, ...] = ()     # horizontal guides (e.g. RSI 30/70)
    height: float = 0.2                # sub-pane height as a fraction of the window


@dataclass(frozen=True)
class Value:
    series: str
    value: float
    index: int | None = None           # bar the value belongs to; default = emit bar


@dataclass(frozen=True)
class Mark:
    index: int                         # candle the marker sits on (<= emit bar)
    position: Position
    text: str = ""
    shape: str = "circle"
    color: str = "#888780"
    key: Hashable | None = None        # same key => higher rank replaces lower
    rank: int = 0


@dataclass(frozen=True)
class Draw:
    kind: str                          # name of the chart method that draws it
    args: dict = field(default_factory=dict)
    key: Hashable | None = None        # same key => replaces the earlier drawing

    def indices(self) -> list[int]:
        return [v for k, v in self.args.items()
                if (k == "index" or k.endswith("_index")) and v is not None]


Output = Value | Mark | Draw

MARK_SHAPES = ("circle", "square", "arrow_up", "arrow_down")
MARK_POSITIONS = ("above", "below")

# Draw.kind -> (required args, optional args). Bar positions are `*index` args.
DRAW_ARGS: dict[str, tuple[frozenset, frozenset]] = {
    "horizontal_line": (frozenset({"price"}), frozenset({"color", "width", "style", "text"})),
    "vertical_line": (frozenset({"index"}), frozenset({"color", "width", "style", "text"})),
    "trend_line": (frozenset({"start_index", "start_value", "end_index", "end_value"}),
                   frozenset({"line_color", "width", "style"})),
    "box": (frozenset({"start_index", "start_value", "end_index", "end_value"}),
            frozenset({"color", "fill_color", "width", "style"})),
    "vertical_span": (frozenset({"start_index"}), frozenset({"end_index", "color"})),
}


def hline(price: float, *, key=None, color="#7a92ca", width=1, style="dashed", text="") -> Draw:
    return Draw("horizontal_line", dict(price=price, color=color, width=width, style=style, text=text), key)


def vline(index: int, *, key=None, color="#7a92ca", width=1, style="dashed", text="") -> Draw:
    return Draw("vertical_line", dict(index=index, color=color, width=width, style=style, text=text), key)


def trend(i0: int, p0: float, i1: int, p1: float, *, key=None,
          color="#2962ff", width=2, style="solid") -> Draw:
    return Draw("trend_line", dict(start_index=i0, start_value=p0, end_index=i1, end_value=p1,
                                   line_color=color, width=width, style=style), key)


def box(i0: int, p0: float, i1: int, p1: float, *, key=None, color="#2962ff",
        fill="rgba(41, 98, 255, 0.10)", width=1, style="solid") -> Draw:
    return Draw("box", dict(start_index=i0, start_value=p0, end_index=i1, end_value=p1,
                            color=color, fill_color=fill, width=width, style=style), key)


def vspan(i0: int, i1: int | None = None, *, key=None, color="rgba(255, 193, 7, 0.15)") -> Draw:
    return Draw("vertical_span", dict(start_index=i0, end_index=i1, color=color), key)


class Indicator:
    """Streaming indicator. Subclass it and implement ``on_bar``."""

    name: str = ""

    def __repr__(self) -> str:
        import inspect
        try:
            params = [p for p in inspect.signature(type(self).__init__).parameters if p != "self"]
        except (TypeError, ValueError):
            params = []
        args = ", ".join(f"{p}={getattr(self, p)!r}" for p in params if hasattr(self, p))
        return f"{type(self).__name__}({args})"

    def series(self) -> list[SeriesSpec]:
        """Lines/histograms this indicator writes ``Value`` outputs to."""
        return []

    def reset(self) -> None:
        """Clear all state. Called before every run, so reruns are identical."""

    def on_bar(self, bars: Bars) -> Iterable[Output] | None:
        """Called once per bar, oldest first. Yield/return outputs, or None."""
        raise NotImplementedError


class BatchIndicator(Indicator):
    """Vectorised indicator. Compute over the whole frame in one go.

    ``compute`` yields ``(emitted_at, output)`` pairs, where ``emitted_at`` is
    the first bar on which that output could have been known. Use
    ``dt_replay_lab.check_lookahead`` to confirm that claim.
    """

    def compute(self, df) -> Iterable[tuple[int, Output]]:
        raise NotImplementedError

    def on_bar(self, bars: Bars):  # pragma: no cover - never called for batch
        raise TypeError("BatchIndicator is computed via compute(), not on_bar()")
