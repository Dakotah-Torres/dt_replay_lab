"""The indicator contract: what an indicator receives and what it may emit."""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Hashable, Iterable, Literal

import numpy as np

Position = Literal["above", "below"]


@dataclass(frozen=True)
class Bars:
    """Read-only view of every bar up to and including the current one."""

    i: int
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
    """A line or histogram an indicator draws values onto."""

    name: str
    pane: str = "main"                  # "main" overlays price, anything else is a sub-pane
    color: str | None = None
    width: int = 2
    style: str = "solid"
    kind: Literal["line", "histogram"] = "line"
    levels: tuple[float, ...] = ()      # horizontal guide lines
    height: float = 0.2                 # sub-pane height as a fraction of the window


@dataclass(frozen=True)
class Value:
    """A point on a declared series; index defaults to the bar it was emitted on."""

    series: str
    value: float
    index: int | None = None


@dataclass(frozen=True)
class Mark:
    """A marker on a candle; the same key keeps only the highest rank."""

    index: int
    position: Position
    text: str = ""
    shape: str = "circle"
    color: str = "#888780"
    key: Hashable | None = None
    rank: int = 0


@dataclass(frozen=True)
class Draw:
    """A drawing; kind is the chart method name, the same key replaces the old one."""

    kind: str
    args: dict = field(default_factory=dict)
    key: Hashable | None = None


    def indices(self) -> list[int]:
        return [v for k, v in self.args.items() if k.endswith("index") and v is not None]


Output = Value | Mark | Draw

MARK_SHAPES = ("circle", "square", "arrow_up", "arrow_down")
MARK_POSITIONS = ("above", "below")

# Draw kind -> (required args, optional args)
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
    """Streaming indicator: subclass it and implement on_bar."""

    name: str = ""
    data_kind = None        # hook: the data type this indicator consumes (your DataKind enum)
    outputs: tuple = ()     # hook: the output types it may emit (your drawing enum); empty = any


    def __repr__(self) -> str:
        params = [p for p in inspect.signature(type(self).__init__).parameters if p != "self"]
        args = ", ".join(f"{p}={getattr(self, p)!r}" for p in params if hasattr(self, p))
        return f"{type(self).__name__}({args})"


    def series(self) -> list[SeriesSpec]:
        """Lines and histograms this indicator writes Values to."""
        return []


    def reset(self) -> None:
        """Clear all state; called before every run."""


    def on_bar(self, bars: Bars) -> Iterable[Output] | None:
        """Called once per bar, oldest first; yield outputs."""
        raise NotImplementedError


class BatchIndicator(Indicator):
    """Vectorised indicator: compute yields (bar it became knowable, output) pairs."""

    def compute(self, df) -> Iterable[tuple[int, Output]]:
        raise NotImplementedError
