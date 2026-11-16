"""Light-themed chart builder on top of lightweight-charts.

Queue things up, then call ``show()``::

    viz = Visualizer(df, title="ES 5m")
    viz.add_line(df.close.rolling(20).mean(), "SMA 20", color="#2962ff")
    viz.add_line(rsi, "RSI 14", pane="sub", levels=[30, 70])
    viz.add_swings(minor + intermediate + major)
    viz.hline(101.5).trend_line(t0, p0, t1, p1).box(t0, hi, t1, lo)
    viz.show()

Everything is stored as plain data until ``show()`` / ``build()``, so the
calls can be made in any order and the same Visualizer can be rebuilt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from .data import normalize_ohlc

THEME = {
    "bg": "#ffffff",
    "text": "#2b2f36",
    "grid": "rgba(0, 0, 0, 0.06)",
    "border": "#e1e4ea",
    "up": "#26a69a",
    "down": "#ef5350",
    "vol_up": "rgba(38, 166, 154, 0.35)",
    "vol_down": "rgba(239, 83, 80, 0.35)",
    "crosshair": "#9aa0ab",
    "crosshair_label": "#2b2f36",
    "font": "Inter, -apple-system, Segoe UI, sans-serif",
}

PALETTE = ["#2962ff", "#ff6d00", "#8e24aa", "#00897b", "#c62828", "#6d4c41"]

# swing level -> (shape, color, high label, low label)
SWING_STYLE = {
    1: ("circle", "#9e9e9e", "STH", "STL"),
    2: ("square", "#7e57c2", "ITH", "ITL"),
    3: ("arrow_down", "#00a67e", "LTH", "LTL"),
}


@dataclass
class _Pane:
    height: float
    lines: list[dict] = field(default_factory=list)
    hists: list[dict] = field(default_factory=list)


class Visualizer:
    """Collects candles, indicators, markers and drawings, then renders them."""

    def __init__(
        self,
        df: pd.DataFrame,
        title: str = "finresearch",
        width: int = 1400,
        height: int = 850,
        volume: bool = True,
    ) -> None:
        self.df = normalize_ohlc(df)
        self.title = title
        self.width, self.height = width, height
        self.volume = volume and "volume" in self.df.columns

        self._main_lines: list[dict] = []
        self._sub_panes: dict[str, _Pane] = {}
        self._markers: list[dict] = []
        self._drawings: list[tuple[str, dict]] = []
        self._color_i = 0
        self.chart = None

    # ── indicators ────────────────────────────────────────────
    def add_line(
        self,
        series: pd.Series | Sequence[float],
        name: str,
        color: str | None = None,
        pane: str = "main",
        width: int = 2,
        style: str = "solid",
        levels: Iterable[float] = (),
        height: float = 0.2,
    ) -> "Visualizer":
        """Add an indicator line.

        ``series`` is aligned to the candles by position when it has the same
        length as ``df`` or by index otherwise (so rolling results can be
        passed straight in). ``pane="main"`` overlays the price chart; any
        other string creates/uses a sub-pane of that name below it, with
        optional horizontal ``levels`` (e.g. RSI 30/70).
        """
        spec = dict(name=name, data=self._to_frame(series, name), color=color or self._next_color(),
                    width=width, style=style, levels=list(levels))
        if pane == "main":
            self._main_lines.append(spec)
        else:
            self._sub(pane, height).lines.append(spec)
        return self

    def add_histogram(
        self,
        series: pd.Series | Sequence[float],
        name: str,
        color: str | None = None,
        pane: str = "hist",
        height: float = 0.15,
    ) -> "Visualizer":
        """Add a histogram (e.g. MACD hist, volume-like data) in a sub-pane."""
        spec = dict(name=name, data=self._to_frame(series, name), color=color or self._next_color())
        self._sub(pane, height).hists.append(spec)
        return self

    # ── markers ───────────────────────────────────────────────
    def add_markers(self, markers: Iterable[dict]) -> "Visualizer":
        """Raw markers: dicts with time, position, shape, color, text."""
        self._markers.extend(markers)
        return self

    def add_swings(self, swings: Iterable[Any], style: dict | None = None) -> "Visualizer":
        """Mark swings (anything with .index .time .kind .level).

        Only the highest level per (bar, kind) is drawn so markers don't stack.
        """
        style = style or SWING_STYLE
        best: dict[tuple, Any] = {}
        for s in swings:
            key = (s.index, s.kind)
            if key not in best or s.level > best[key].level:
                best[key] = s

        for s in sorted(best.values(), key=lambda s: s.index):
            shape, color, hi, lo = style[min(s.level, max(style))]
            is_high = s.kind == "high"
            if not is_high and shape == "arrow_down":
                shape = "arrow_up"
            self._markers.append({
                "time": s.time,
                "position": "above" if is_high else "below",
                "shape": shape,
                "color": color,
                "text": hi if is_high else lo,
            })
        return self

    # ── drawings ──────────────────────────────────────────────
    def hline(self, price: float, color: str = "#7a92ca", width: int = 1,
              style: str = "dashed", text: str = "") -> "Visualizer":
        self._drawings.append(("horizontal_line", dict(price=price, color=color, width=width,
                                                       style=style, text=text)))
        return self

    def vline(self, time, color: str = "#7a92ca", width: int = 1,
              style: str = "dashed", text: str = "") -> "Visualizer":
        self._drawings.append(("vertical_line", dict(time=pd.Timestamp(time), color=color,
                                                     width=width, style=style, text=text)))
        return self

    def trend_line(self, start_time, start_price: float, end_time, end_price: float,
                   color: str = "#2962ff", width: int = 2, style: str = "solid") -> "Visualizer":
        self._drawings.append(("trend_line", dict(
            start_time=pd.Timestamp(start_time), start_value=start_price,
            end_time=pd.Timestamp(end_time), end_value=end_price,
            line_color=color, width=width, style=style)))
        return self

    def box(self, start_time, start_price: float, end_time, end_price: float,
            color: str = "#2962ff", fill: str = "rgba(41, 98, 255, 0.10)",
            width: int = 1, style: str = "solid") -> "Visualizer":
        self._drawings.append(("box", dict(
            start_time=pd.Timestamp(start_time), start_value=start_price,
            end_time=pd.Timestamp(end_time), end_value=end_price,
            color=color, fill_color=fill, width=width, style=style)))
        return self

    def vspan(self, start_time, end_time=None,
              color: str = "rgba(255, 193, 7, 0.15)") -> "Visualizer":
        end = None if end_time is None else pd.Timestamp(end_time)
        self._drawings.append(("vertical_span", dict(start_time=pd.Timestamp(start_time),
                                                     end_time=end, color=color)))
        return self

    # ── render ────────────────────────────────────────────────
    def build(self):
        """Create the chart window objects (does not block)."""
        from lightweight_charts import Chart  # imported late: needs a GUI backend

        sub_total = sum(p.height for p in self._sub_panes.values())
        main_h = 1.0 - sub_total

        chart = Chart(width=self.width, height=self.height, title=self.title,
                      inner_width=1, inner_height=main_h)
        self._style(chart)
        chart.legend(visible=True, ohlc=True, percent=True, lines=True,
                     color=THEME["text"], font_family=THEME["font"])

        if self.volume:
            chart.volume_config(up_color=THEME["vol_up"], down_color=THEME["vol_down"])
        chart.set(self.df)

        for spec in self._main_lines:
            self._draw_line(chart, spec)
        if self._markers:
            chart.marker_list(sorted(self._markers, key=lambda m: m["time"]))
        for method, kwargs in self._drawings:
            getattr(chart, method)(**kwargs)

        for pane in self._sub_panes.values():
            sub = chart.create_subchart(position="bottom", width=1, height=pane.height,
                                        sync=True)
            self._style(sub)
            sub.legend(visible=True, ohlc=False, percent=False, lines=True,
                       color=THEME["text"], font_family=THEME["font"])
            for spec in pane.lines:
                self._draw_line(sub, spec)
            for spec in pane.hists:
                hist = sub.create_histogram(spec["name"], color=spec["color"])
                hist.set(spec["data"])

        chart.fit()
        self.chart = chart
        return chart

    def show(self, block: bool = True) -> None:
        chart = self.chart or self.build()
        chart.show(block=block)

    def screenshot(self, path: str | Path) -> Path:
        """Save a PNG of the main chart. The window must be shown first."""
        chart = self.chart or self.build()
        chart.show(block=False)
        path = Path(path)
        path.write_bytes(chart.screenshot())
        return path

    # ── internals ─────────────────────────────────────────────
    def _next_color(self) -> str:
        color = PALETTE[self._color_i % len(PALETTE)]
        self._color_i += 1
        return color

    def _sub(self, name: str, height: float) -> _Pane:
        if name not in self._sub_panes:
            self._sub_panes[name] = _Pane(height=height)
        return self._sub_panes[name]

    def _to_frame(self, series, name: str) -> pd.DataFrame:
        if not isinstance(series, pd.Series):
            series = pd.Series(list(series))
        if len(series) == len(self.df):
            values = series.to_numpy()
        else:
            values = series.reindex(self.df.index).to_numpy()
        return pd.DataFrame({"time": self.df["time"], name: values}).dropna()

    @staticmethod
    def _draw_line(chart, spec: dict) -> None:
        line = chart.create_line(spec["name"], color=spec["color"], width=spec["width"],
                                 style=spec["style"], price_line=False, price_label=False)
        line.set(spec["data"])
        for level in spec["levels"]:
            line.horizontal_line(level, color="#b0b5bf", width=1, style="dashed")

    @staticmethod
    def _style(chart) -> None:
        t = THEME
        chart.layout(background_color=t["bg"], text_color=t["text"], font_family=t["font"])
        chart.grid(color=t["grid"])
        chart.candle_style(up_color=t["up"], down_color=t["down"])
        chart.price_scale(border_visible=True, border_color=t["border"], text_color=t["text"])
        chart.time_scale(border_visible=True, border_color=t["border"])
        chart.crosshair(vert_color=t["crosshair"], horz_color=t["crosshair"],
                        vert_label_background_color=t["crosshair_label"],
                        horz_label_background_color=t["crosshair_label"])
