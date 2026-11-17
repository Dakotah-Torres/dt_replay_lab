"""Timeline: every event, and the answer to "what is visible at bar N?"."""
from __future__ import annotations

from bisect import bisect_right

import pandas as pd

from dt_replay_lab.data import normalize_ohlc
from dt_replay_lab.engine.runner import Event, pre_run
from dt_replay_lab.engine.validator import collect_specs
from dt_replay_lab.indicators.indicator import Draw, Indicator, Mark, SeriesSpec, Value

RENAME = {"index": "time", "start_index": "start_time", "end_index": "end_time"}


def marker_dicts(marks, times) -> list[dict]:
    """Chart-ready marker dicts, ordered by bar."""
    return [dict(time=pd.Timestamp(times[m.index]), position=m.position, shape=m.shape,
                 color=m.color, text=m.text)
            for m in sorted(marks, key=lambda m: m.index)]


def resolve_draw(draw: Draw, times) -> tuple[str, dict]:
    """(chart method, kwargs) with bar indices turned into timestamps."""
    kwargs = {}

    for k, v in draw.args.items():
        if k in RENAME:
            kwargs[RENAME[k]] = None if v is None else pd.Timestamp(times[v])
        else:
            kwargs[k] = v

    return draw.kind, kwargs


class Recording:
    """Every output of every indicator, stamped with the bar it appeared on."""

    def __init__(self, df: pd.DataFrame, indicators: list[Indicator], events: list[Event],
                 specs: dict[str, SeriesSpec]) -> None:
        self.df = df
        self.n = len(df)
        self.indicators = indicators
        self.events = events
        self.specs = specs
        self.times = df["time"].to_numpy()

        self._val_ats: dict[str, list[int]] = {s: [] for s in specs}
        self._val_rows: dict[str, list[tuple[int, float]]] = {s: [] for s in specs}
        self._marks: list[Mark] = []
        self._mark_ats: list[int] = []
        self._draws: list[Draw] = []
        self._draw_ats: list[int] = []
        self._irregular_ats: list[int] = []                     # values about an earlier bar
        self.values_by_at: dict[int, list[tuple[str, float]]] = {}

        for e in events:
            o = e.out

            if isinstance(o, Value):
                idx = e.at if o.index is None else o.index
                self._val_ats[o.series].append(e.at)
                self._val_rows[o.series].append((idx, o.value))

                if idx == e.at:
                    self.values_by_at.setdefault(e.at, []).append((o.series, o.value))
                else:
                    self._irregular_ats.append(e.at)

            elif isinstance(o, Mark):
                self._marks.append(o)
                self._mark_ats.append(e.at)

            else:
                self._draws.append(o)
                self._draw_ats.append(e.at)


    @classmethod
    def record(cls, data: pd.DataFrame, indicators: list[Indicator]) -> "Recording":
        """Normalize the data, run every indicator over it, and index the results."""
        df = normalize_ohlc(data)

        return cls(df, indicators, pre_run(df, indicators), collect_specs(indicators))


    def lines_at(self, cursor: int) -> dict[str, pd.DataFrame]:
        """Every series up to cursor; a later value for the same bar wins."""
        out = {}

        for name, ats in self._val_ats.items():
            rows = dict(self._val_rows[name][:bisect_right(ats, cursor)])
            idxs = sorted(rows)
            out[name] = pd.DataFrame({"time": self.times[idxs], name: [rows[i] for i in idxs]})

        return out


    def markers_at(self, cursor: int) -> list[dict]:
        """Markers up to cursor; for a shared key only the highest rank shows."""
        best: dict = {}

        for k, m in enumerate(self._marks[:bisect_right(self._mark_ats, cursor)]):
            key = m.key if m.key is not None else ("_", k)

            if key not in best or m.rank >= best[key].rank:
                best[key] = m

        return marker_dicts(best.values(), self.times)


    def drawings_at(self, cursor: int) -> dict:
        """{key: (version, Draw)} up to cursor; the version changes when a key is replaced."""
        latest: dict = {}

        for k, d in enumerate(self._draws[:bisect_right(self._draw_ats, cursor)]):
            latest[d.key if d.key is not None else ("_", k)] = (k, d)

        return latest


    def has_marks(self, a: int, b: int) -> bool:
        """Any marker emitted in bars (a, b]?"""
        return bisect_right(self._mark_ats, b) > bisect_right(self._mark_ats, a)


    def has_draws(self, a: int, b: int) -> bool:
        """Any drawing emitted in bars (a, b]?"""
        return bisect_right(self._draw_ats, b) > bisect_right(self._draw_ats, a)


    def has_irregular_values(self, a: int, b: int) -> bool:
        """Any value about an earlier bar emitted in (a, b]? Those can't be streamed in."""
        return bisect_right(self._irregular_ats, b) > bisect_right(self._irregular_ats, a)


    def visualizer(self, cursor: int | None = None, **kwargs):
        """A static Visualizer showing the state at cursor (default: the end)."""
        from dt_replay_lab.viz.visualizer import Visualizer

        cursor = self.n - 1 if cursor is None else cursor
        viz = Visualizer(self.df.iloc[:cursor + 1], **kwargs)
        bar_of = {t: i for i, t in enumerate(viz.df["time"])}

        for name, frame in self.lines_at(cursor).items():
            spec = self.specs[name]
            series = pd.Series(frame[name].to_numpy(), index=frame["time"].map(bar_of).to_numpy())

            if spec.kind == "histogram":
                viz.add_histogram(series, name, color=spec.color, pane=spec.pane, height=spec.height)
            else:
                viz.add_line(series, name, color=spec.color, pane=spec.pane, width=spec.width,
                             style=spec.style, levels=spec.levels, height=spec.height)

        viz.add_markers(self.markers_at(cursor))

        for _, draw in self.drawings_at(cursor).values():
            viz.add_drawing(*resolve_draw(draw, self.times))

        return viz


    def summary(self) -> str:
        """'1000 bars, SMA 20: 981 outputs, ...'"""
        counts: dict[str, int] = {}

        for e in self.events:
            counts[e.source] = counts.get(e.source, 0) + 1

        return f"{self.n} bars, " + ", ".join(f"{k}: {v} outputs" for k, v in counts.items())
