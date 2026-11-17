"""``finresearch new my_idea``: write a ready-to-run indicator file."""
from __future__ import annotations

import re
import sys
from pathlib import Path

TEMPLATE = '''"""{title}: <one line - what should this indicator show you?>.

Run it:   uv run python {filename}
Contract: docs/indicator-contract.md
"""
from finresearch import Indicator, Mark, SeriesSpec, Value, engine, hline, make_test_data
# also available: trend, box, vline, vspan (drawings), BatchIndicator (vectorised)


class {cls}(Indicator):
    # 1. PARAMETERS ----------------------------------------------------------
    # Everything you want to tune is an __init__ argument with a default.
    # Store it on self, and set self.name (shown in the legend, keep it unique).
    def __init__(self, period: int = 20):
        self.period = period
        self.name = f"{title} {{period}}"
        self.reset()

    # 2. STATE ---------------------------------------------------------------
    # reset() runs before every replay. Put ALL running state here (counters,
    # last swing, lists...). If it isn't reset, reruns differ and check fails.
    def reset(self):
        self._last_high = None

    # 3. SERIES --------------------------------------------------------------
    # Lines/histograms you emit Value(...) onto. pane="main" overlays price;
    # any other name (e.g. "osc") makes its own pane under the chart.
    def series(self):
        return [SeriesSpec(self.name, pane="main", color=None, levels=())]

    # 4. LOGIC ---------------------------------------------------------------
    # Called once per bar, oldest first. `bars` only contains the past:
    #   bars.i            index of the current bar
    #   bars.close[-1]    current close      bars.high[-n:]   last n highs
    #   bars.open / .high / .low / .close / .volume / .time   (read-only arrays)
    # Yield zero or more outputs:
    #   Value(series_name, number)              a point on a line
    #   Mark(bar_index, "above"|"below", text, shape, color, key=..., rank=...)
    #   hline(price, key=...) / trend(...) / box(...) / vline(...) / vspan(...)
    # A Mark/drawing may point at an EARLIER bar (e.g. a swing confirmed later),
    # never a later one. Skip bars with nothing to say; never emit NaN.
    def on_bar(self, bars):
        if len(bars) < self.period:
            return
        yield Value(self.name, float(bars.close[-self.period:].mean()))


if __name__ == "__main__":
    df = make_test_data()                 # or engine.run("data/my.csv", ...)
    engine.check(df, {cls}())             # contract report: PASS / WARN / FAIL
    engine.run(df, {cls}())               # replay window
'''


def _names(raw: str) -> tuple[str, str, str]:
    words = [w for w in re.split(r"[^0-9a-zA-Z]+", raw) if w]
    if not words:
        raise SystemExit("usage: finresearch new <name>   e.g. finresearch new breakout")
    snake = "_".join(w.lower() for w in words)
    cls = "".join(w[:1].upper() + w[1:] for w in words)
    if cls[0].isdigit():
        raise SystemExit("name must not start with a digit")
    return snake, cls, " ".join(w.capitalize() for w in words)


def new_indicator(name: str, directory: str | Path = ".") -> Path:
    snake, cls, title = _names(name)
    path = Path(directory) / f"{snake}.py"
    if path.exists():
        raise SystemExit(f"{path} already exists; not overwriting")
    path.write_text(TEMPLATE.format(cls=cls, title=title, filename=path.name))
    return path


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        raise SystemExit("usage: finresearch new <name> [directory]")
    path = new_indicator(argv[0], argv[1] if len(argv) > 1 else ".")
    print(f"created {path}\nnext:  uv run python {path}")
