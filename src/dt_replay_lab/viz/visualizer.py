"""Light theme and a static chart: queue lines, markers and drawings, then show()."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import pandas as pd

from dt_replay_lab.data import normalize_ohlc
from dt_replay_lab.indicators.swing import SWING_STYLE

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


def apply_theme(chart, right_offset: int = 0) -> None:
    """Apply the light theme to a chart or sub-chart."""
    t = THEME
    chart.layout(background_color=t["bg"], text_color=t["text"], font_family=t["font"])
    chart.grid(color=t["grid"])
    chart.candle_style(up_color=t["up"], down_color=t["down"])
    chart.price_scale(border_visible=True, border_color=t["border"], text_color=t["text"])
    chart.time_scale(right_offset=right_offset, border_visible=True, border_color=t["border"])
    chart.crosshair(vert_color=t["crosshair"], horz_color=t["crosshair"],
                    vert_label_background_color=t["crosshair_label"],
                    horz_label_background_color=t["crosshair_label"])


@dataclass
class _Pane:
    height: float
    lines: list[dict] = field(default_factory=list)
    hists: list[dict] = field(default_factory=list)


class Visualizer:
    """Collects candles, lines, markers and drawings; nothing is drawn until build()."""

    def __init__(self, df: pd.DataFrame, title: str = "dt_replay_lab", width: int = 1400,
                 height: int = 850, volume: bool = True) -> None:
        self.df = normalize_ohlc(df)
        self.title, self.width, self.height = title, width, height
        self.volume = volume and "volume" in self.df.columns

        self._main_lines: list[dict] = []
        self._sub_panes: dict[str, _Pane] = {}
        self._markers: list[dict] = []
        self._drawings: list[tuple[str, dict]] = []
        self._color_i = 0
        self.chart = None


    def add_line(self, series: pd.Series | Sequence[float], name: str, color: str | None = None,
                 pane: str = "main", width: int = 2, style: str = "solid",
                 levels: Iterable[float] = (), height: float = 0.2) -> "Visualizer":
        """A line on price (pane="main") or in a named sub-pane, aligned by position or index."""
        spec = dict(name=name, data=self._to_frame(series, name), color=color or self._next_color(),
                    width=width, style=style, levels=list(levels))

        if pane == "main":
            self._main_lines.append(spec)
        else:
            self._sub(pane, height).lines.append(spec)

        return self


    def add_histogram(self, series: pd.Series | Sequence[float], name: str, color: str | None = None,
                      pane: str = "hist", height: float = 0.15) -> "Visualizer":
        """A histogram in a sub-pane."""
        spec = dict(name=name, data=self._to_frame(series, name), color=color or self._next_color())
        self._sub(pane, height).hists.append(spec)

        return self


    def add_markers(self, markers: Iterable[dict]) -> "Visualizer":
        """Raw marker dicts: time, position, shape, color, text."""
        self._markers.extend(markers)

        return self


    def add_swings(self, swings: Iterable[Any], style: dict | None = None) -> "Visualizer":
        """Mark batch swings; only the highest level per (bar, kind) is drawn."""
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

            self._markers.append(dict(time=s.time, position="above" if is_high else "below",
                                      shape=shape, color=color, text=hi if is_high else lo))

        return self


    def add_drawing(self, method: str, kwargs: dict) -> "Visualizer":
        """Any chart drawing method with its arguments."""
        self._drawings.append((method, kwargs))

        return self


    def hline(self, price: float, color: str = "#7a92ca", width: int = 1, style: str = "dashed",
              text: str = "") -> "Visualizer":
        return self.add_drawing("horizontal_line", dict(price=price, color=color, width=width,
                                                        style=style, text=text))


    def vline(self, time, color: str = "#7a92ca", width: int = 1, style: str = "dashed",
              text: str = "") -> "Visualizer":
        return self.add_drawing("vertical_line", dict(time=pd.Timestamp(time), color=color, width=width,
                                                      style=style, text=text))


    def trend_line(self, start_time, start_price: float, end_time, end_price: float,
                   color: str = "#2962ff", width: int = 2, style: str = "solid") -> "Visualizer":
        return self.add_drawing("trend_line", dict(start_time=pd.Timestamp(start_time), start_value=start_price,
                                                   end_time=pd.Timestamp(end_time), end_value=end_price,
                                                   line_color=color, width=width, style=style))


    def box(self, start_time, start_price: float, end_time, end_price: float, color: str = "#2962ff",
            fill: str = "rgba(41, 98, 255, 0.10)", width: int = 1, style: str = "solid") -> "Visualizer":
        return self.add_drawing("box", dict(start_time=pd.Timestamp(start_time), start_value=start_price,
                                            end_time=pd.Timestamp(end_time), end_value=end_price,
                                            color=color, fill_color=fill, width=width, style=style))


    def vspan(self, start_time, end_time=None, color: str = "rgba(255, 193, 7, 0.15)") -> "Visualizer":
        end = None if end_time is None else pd.Timestamp(end_time)

        return self.add_drawing("vertical_span", dict(start_time=pd.Timestamp(start_time), end_time=end,
                                                      color=color))


    def build(self):
        """Create the chart objects without blocking."""
        from lightweight_charts import Chart     # needs a GUI backend, so imported late

        chart = Chart(width=self.width, height=self.height, title=self.title, inner_width=1,
                      inner_height=1.0 - sum(p.height for p in self._sub_panes.values()))
        apply_theme(chart)
        chart.legend(visible=True, ohlc=True, percent=True, lines=True, color=THEME["text"], font_family=THEME["font"])

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
            sub = chart.create_subchart(position="bottom", width=1, height=pane.height, sync=True)
            apply_theme(sub)
            sub.legend(visible=True, ohlc=False, percent=False, lines=True, color=THEME["text"], font_family=THEME["font"])

            for spec in pane.lines:
                self._draw_line(sub, spec)

            for spec in pane.hists:
                sub.create_histogram(spec["name"], color=spec["color"]).set(spec["data"])

        chart.fit()
        self.chart = chart

        return chart


    def show(self, block: bool = True) -> None:
        (self.chart or self.build()).show(block=block)


    def _next_color(self) -> str:
        self._color_i += 1

        return PALETTE[(self._color_i - 1) % len(PALETTE)]


    def _sub(self, name: str, height: float) -> _Pane:
        return self._sub_panes.setdefault(name, _Pane(height=height))


    def _to_frame(self, series, name: str) -> pd.DataFrame:
        """Align a series to the candles: by position if lengths match, otherwise by index."""
        series = series if isinstance(series, pd.Series) else pd.Series(list(series))
        values = series.to_numpy() if len(series) == len(self.df) else series.reindex(self.df.index).to_numpy()

        return pd.DataFrame({"time": self.df["time"], name: values}).dropna()


    @staticmethod
    def _draw_line(chart, spec: dict) -> None:
        line = chart.create_line(spec["name"], color=spec["color"], width=spec["width"],
                                 style=spec["style"], price_line=False, price_label=False)
        line.set(spec["data"])

        for level in spec["levels"]:
            line.horizontal_line(level, color="#b0b5bf", width=1, style="dashed")
