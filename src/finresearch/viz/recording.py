"""Run indicators over data once, then answer "what is visible at bar N?".

Nothing here touches a GUI, so it is fully testable. The Player only moves a
cursor and asks the Recording for the state at that cursor.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

import numpy as np
import pandas as pd

from finresearch.data import normalize_ohlc
from finresearch.indicators.indicator import (
    DRAW_ARGS, MARK_POSITIONS, MARK_SHAPES, BatchIndicator, Bars, Draw, Indicator, Mark, Output,
    SeriesSpec, Value,
)


class LookaheadError(ValueError):
    """An indicator emitted something about a bar it had not seen yet."""


class IndicatorError(RuntimeError):
    """An indicator crashed or broke the output rules; the message says where."""


@dataclass(frozen=True)
class Event:
    at: int          # bar on which the output became knowable
    out: Output
    source: str      # indicator name


class _Feed:
    """Hands out read-only prefix views of the price arrays."""

    def __init__(self, df: pd.DataFrame) -> None:
        def frozen(a):
            a = np.array(a, copy=True)
            a.flags.writeable = False
            return a

        self._a = [frozen(df["time"].to_numpy())] + [
            frozen(df[c].to_numpy()) for c in ("open", "high", "low", "close")]
        self._a.append(frozen(df["volume"].to_numpy() if "volume" in df else np.zeros(len(df))))

    def at(self, i: int) -> Bars:
        t, o, h, l, c, v = (a[:i + 1] for a in self._a)
        return Bars(i, t, o, h, l, c, v)


def _outputs(result):
    if result is None:
        return ()
    if isinstance(result, (Value, Mark, Draw)):
        return (result,)
    return result


class Recording:
    """Every output of every indicator, stamped with the bar it appeared on."""

    def __init__(self, df: pd.DataFrame, indicators: list[Indicator], events: list[Event],
                 specs: dict[str, SeriesSpec]) -> None:
        self.df = df
        self.n = len(df)
        self.indicators = indicators
        self.events = events
        self.specs = specs
        self._times = df["time"].to_numpy()

        self._val_ats: dict[str, list[int]] = {s: [] for s in specs}
        self._val_rows: dict[str, list[tuple[int, float]]] = {s: [] for s in specs}
        self._marks: list[tuple[int, Mark]] = []
        self._draws: list[tuple[int, Draw]] = []
        self._mark_ats: list[int] = []
        self._draw_ats: list[int] = []
        self.values_by_at: dict[int, list[tuple[str, float]]] = {}
        irregular: list[int] = []

        for e in events:
            o = e.out
            if isinstance(o, Value):
                idx = e.at if o.index is None else o.index
                self._val_ats[o.series].append(e.at)
                self._val_rows[o.series].append((idx, o.value))
                if idx == e.at:
                    self.values_by_at.setdefault(e.at, []).append((o.series, o.value))
                else:
                    irregular.append(e.at)
            elif isinstance(o, Mark):
                self._marks.append((e.at, o))
                self._mark_ats.append(e.at)
            else:
                self._draws.append((e.at, o))
                self._draw_ats.append(e.at)
        self._irregular_ats = sorted(irregular)

    # ── construction ──────────────────────────────────────────
    @classmethod
    def record(cls, data: pd.DataFrame, indicators: list[Indicator]) -> "Recording":
        df = normalize_ohlc(data)
        n = len(df)

        specs: dict[str, SeriesSpec] = {}
        for ind in indicators:
            for s in ind.series():
                if s.name in specs:
                    raise ValueError(f"duplicate series name {s.name!r}; series names must be unique")
                specs[s.name] = s

        events: list[Event] = []
        feed = _Feed(df)
        for ind in indicators:
            ind.reset()
            src = ind.name or type(ind).__name__
            if isinstance(ind, BatchIndicator):
                try:
                    pairs = list(ind.compute(df.copy()))
                except Exception as e:
                    raise IndicatorError(f"{src}.compute() crashed: {type(e).__name__}: {e}") from e
            else:
                pairs = []
                for i in range(n):
                    try:
                        pairs.extend((i, o) for o in _outputs(ind.on_bar(feed.at(i))))
                    except Exception as e:
                        raise IndicatorError(
                            f"{src} crashed on bar {i} ({df['time'].iat[i]}): "
                            f"{type(e).__name__}: {e}") from e
            for at, out in pairs:
                cls._validate(at, out, specs, n, src)
                events.append(Event(at, out, src))

        events.sort(key=lambda e: e.at)       # stable: emission order kept within a bar
        return cls(df, indicators, events, specs)

    @staticmethod
    def _validate(at: int, out: Output, specs: dict, n: int, src: str) -> None:
        if not 0 <= at < n:
            raise ValueError(f"{src}: emitted at bar {at}, outside 0..{n - 1}")
        if isinstance(out, Value):
            if out.series not in specs:
                raise IndicatorError(
                    f"{src}: Value for series {out.series!r}, which series() did not declare "
                    f"(declared: {sorted(specs) or 'none'})")
            if not np.isfinite(out.value):
                raise IndicatorError(f"{src}: Value for {out.series!r} at bar {at} is {out.value}; "
                                     "skip the bar instead of emitting NaN/inf")
            idxs = [at if out.index is None else out.index]
        elif isinstance(out, Mark):
            if out.position not in MARK_POSITIONS:
                raise IndicatorError(f"{src}: Mark position {out.position!r}; use one of {MARK_POSITIONS}")
            if out.shape not in MARK_SHAPES:
                raise IndicatorError(f"{src}: Mark shape {out.shape!r}; use one of {MARK_SHAPES}")
            idxs = [out.index]
        elif isinstance(out, Draw):
            if out.kind not in DRAW_ARGS:
                raise IndicatorError(f"{src}: unknown Draw kind {out.kind!r}; use one of {sorted(DRAW_ARGS)} "
                                     "(or the helpers hline/vline/trend/box/vspan)")
            required, optional = DRAW_ARGS[out.kind]
            missing, extra = required - out.args.keys(), out.args.keys() - required - optional
            if missing or extra:
                raise IndicatorError(f"{src}: Draw {out.kind!r} missing {sorted(missing)}, "
                                     f"unexpected {sorted(extra)}")
            idxs = out.indices()
        else:
            raise IndicatorError(f"{src}: emitted {out!r}; outputs must be Value, Mark or Draw")
        for idx in idxs:
            if idx > at:
                raise LookaheadError(f"{src}: output at bar {at} refers to future bar {idx}")
            if idx < 0:
                raise ValueError(f"{src}: negative bar index {idx}")

    # ── state at a cursor (last visible bar) ──────────────────
    def lines_at(self, cursor: int) -> dict[str, pd.DataFrame]:
        out = {}
        for name, ats in self._val_ats.items():
            rows = dict(self._val_rows[name][:bisect_right(ats, cursor)])   # last write wins
            idxs = sorted(rows)
            out[name] = pd.DataFrame({"time": self._times[idxs], name: [rows[i] for i in idxs]})
        return out

    def markers_at(self, cursor: int) -> list[dict]:
        best: dict = {}
        for k, (_, m) in enumerate(self._marks[:bisect_right(self._mark_ats, cursor)]):
            key = m.key if m.key is not None else ("_", k)
            if key not in best or m.rank >= best[key].rank:
                best[key] = m
        return [dict(time=pd.Timestamp(self._times[m.index]), position=m.position, shape=m.shape,
                     color=m.color, text=m.text)
                for m in sorted(best.values(), key=lambda m: m.index)]

    def drawings_at(self, cursor: int) -> dict:
        """``{key: (version, Draw)}``; ``version`` changes when a key is replaced."""
        latest: dict = {}
        for k, (_, d) in enumerate(self._draws[:bisect_right(self._draw_ats, cursor)]):
            latest[d.key if d.key is not None else ("_", k)] = (k, d)
        return latest

    def resolve(self, draw: Draw) -> tuple[str, dict]:
        """Turn bar indices into timestamps: ``(chart method, kwargs)``."""
        rename = {"index": "time", "start_index": "start_time", "end_index": "end_time"}
        kwargs = {}
        for k, v in draw.args.items():
            if k in rename:
                kwargs[rename[k]] = None if v is None else pd.Timestamp(self._times[v])
            else:
                kwargs[k] = v
        return draw.kind, kwargs

    # ── cheap "did anything change between bars a and b?" ─────
    def has_marks(self, a: int, b: int) -> bool:
        return bisect_right(self._mark_ats, b) > bisect_right(self._mark_ats, a)

    def has_draws(self, a: int, b: int) -> bool:
        return bisect_right(self._draw_ats, b) > bisect_right(self._draw_ats, a)

    def has_irregular_values(self, a: int, b: int) -> bool:
        """Values emitted in (a, b] about an earlier bar can't be streamed in."""
        return bisect_right(self._irregular_ats, b) > bisect_right(self._irregular_ats, a)

    # ── bridge to the static Visualizer ───────────────────────
    def visualizer(self, cursor: int | None = None, **kwargs):
        """A static ``Visualizer`` showing the state at ``cursor`` (default: end)."""
        from finresearch.viz.visualizer import Visualizer
        cursor = self.n - 1 if cursor is None else cursor
        viz = Visualizer(self.df.iloc[:cursor + 1], **kwargs)
        for name, frame in self.lines_at(cursor).items():
            spec = self.specs[name]
            idx = frame["time"].map({t: i for i, t in enumerate(viz.df["time"])})
            series = pd.Series(frame[name].to_numpy(), index=idx.to_numpy())
            if spec.kind == "histogram":
                viz.add_histogram(series, name, color=spec.color, pane=spec.pane, height=spec.height)
            else:
                viz.add_line(series, name, color=spec.color, pane=spec.pane, width=spec.width,
                             style=spec.style, levels=spec.levels, height=spec.height)
        viz.add_markers(self.markers_at(cursor))
        for _, draw in self.drawings_at(cursor).values():
            viz._drawings.append(self.resolve(draw))
        return viz

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for e in self.events:
            counts[e.source] = counts.get(e.source, 0) + 1
        return f"{self.n} bars, " + ", ".join(f"{k}: {v} outputs" for k, v in counts.items())
