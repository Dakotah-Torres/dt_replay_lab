"""Live window: indicators compute each bar as it arrives; no rewind."""
from __future__ import annotations

import pandas as pd

from dt_replay_lab.engine.feed import Feed
from dt_replay_lab.engine.player.window import SPEEDS, build_window, parse_speed, run_window
from dt_replay_lab.engine.runner import Event, live_run
from dt_replay_lab.engine.validator import collect_specs
from dt_replay_lab.indicators.indicator import Indicator, Mark, Value
from dt_replay_lab.viz.recording import marker_dicts, resolve_draw


class LivePlayer:
    """Pulls bars from live_run while playing; keys: Space, Right, Shift+Right."""

    def __init__(self, df: pd.DataFrame, indicators: list[Indicator], title: str = "dt_replay_lab live",
                 start: int | None = None, speed: str = "10/s", width: int = 1500, height: int = 900) -> None:
        self.df = df
        self.n = len(df)
        self.specs = collect_specs(indicators)
        self._stream = live_run(Feed(df), indicators)
        self.title, self.width, self.height = title, width, height
        self.history = min(max(start if start is not None else 100, 20), self.n)   # bars shown at open
        self.speed = parse_speed(speed)
        self._speed_label = speed
        self.playing = False
        self.cursor = -1
        self.finished = False

        self._times = df["time"].to_numpy()
        self._rows: dict[str, dict[int, float]] = {name: {} for name in self.specs}
        self._marks: dict = {}                    # key -> best Mark so far
        self._pending_draws: dict = {}            # key -> newest Draw not yet on screen
        self._drawn: dict = {}                    # key -> drawing object
        self._seq = 0                             # unique keys for unkeyed outputs

        self.chart = None
        self._lines: dict = {}


    def step(self, k: int = 1) -> None:
        """Receive the next k bars and draw them."""
        marks_changed = False

        for _ in range(k):
            got = self._pull()

            if got is None:
                break

            i, events = got
            self.chart.update(self.df.iloc[i])
            regular, redraw, changed = self._absorb(i, events)
            marks_changed |= changed

            for name, value in regular:
                if name not in redraw:
                    self._lines[name].update(pd.Series({"time": self._time(i), name: value}))

            for name in redraw:
                self._lines[name].set(self._frame(name))

            self._apply_draws()

        if marks_changed:
            self._draw_markers()

        self._show_position()


    def play(self) -> None:
        if not self.finished:
            self.playing = True
            self._sync_button()


    def pause(self) -> None:
        self.playing = False
        self._sync_button()


    def toggle(self) -> None:
        self.pause() if self.playing else self.play()


    def set_speed(self, label: str) -> None:
        self.speed = parse_speed(label)


    @property
    def at_end(self) -> bool:
        return self.finished


    def _pull(self) -> tuple[int, list[Event]] | None:
        """Next (bar, events) from the stream, or None when it is exhausted."""
        try:
            self.cursor, events = next(self._stream)
        except StopIteration:
            self.finished = True
            return None

        return self.cursor, events


    def _key(self, key):
        """The output's key, or a fresh unique one."""
        self._seq += 1

        return key if key is not None else ("_", self._seq)


    def _absorb(self, i: int, events: list[Event]):
        """Fold one bar's events into state; returns (values, series to redraw, markers changed)."""
        regular, redraw, marks_changed = [], set(), False

        for e in events:
            o = e.out

            if isinstance(o, Value):
                idx = i if o.index is None else o.index
                self._rows[o.series][idx] = o.value

                if idx == i:
                    regular.append((o.series, o.value))
                else:
                    redraw.add(o.series)     # a value about an earlier bar

            elif isinstance(o, Mark):
                key = self._key(o.key)
                best = self._marks.get(key)

                if best is None or o.rank >= best.rank:
                    self._marks[key] = o
                    marks_changed = True

            else:
                self._pending_draws[self._key(o.key)] = o

        return regular, redraw, marks_changed


    def _apply_draws(self) -> None:
        """Put pending drawings on screen, replacing any with the same key."""
        for key, draw in self._pending_draws.items():
            if key in self._drawn:
                self._drawn.pop(key).delete()

            method, kwargs = resolve_draw(draw, self._times)
            self._drawn[key] = getattr(self.chart, method)(**kwargs)

        self._pending_draws.clear()


    def _draw_markers(self) -> None:
        self.chart.clear_markers()

        if self._marks:
            self.chart.marker_list(marker_dicts(self._marks.values(), self._times))


    def _frame(self, name: str) -> pd.DataFrame:
        rows = self._rows[name]
        idxs = sorted(rows)

        return pd.DataFrame({"time": self._times[idxs], name: [rows[i] for i in idxs]})


    def _time(self, i: int) -> pd.Timestamp:
        return pd.Timestamp(self._times[i])


    def _show_position(self) -> None:
        label = "END" if self.finished else "LIVE"
        self.chart.topbar["pos"].set(f"{label}  bar {self.cursor + 1}/{self.n}   "
                                     f"{self._time(max(self.cursor, 0)):%Y-%m-%d %H:%M}")


    def _sync_button(self) -> None:
        if self.chart is not None:
            self.chart.topbar["play"].set("Pause" if self.playing else "Play")


    def build(self):
        """Create the window and join the stream with some history already on screen."""
        self.chart, self._lines = build_window(self.specs, "volume" in self.df, self.title, self.width, self.height)
        self._add_controls(self.chart)

        for _ in range(self.history):
            got = self._pull()

            if got is None:
                break

            self._absorb(*got)

        self.chart.set(self.df.iloc[:self.cursor + 1])

        for name in self.specs:
            self._lines[name].set(self._frame(name))

        self._draw_markers()
        self._apply_draws()
        self._show_position()
        self.chart.fit()

        return self.chart


    def _add_controls(self, chart) -> None:
        tb = chart.topbar
        tb.button("play", "Play", func=lambda c: self.toggle())
        tb.button("f1", "+1", func=lambda c: self.step(1))
        tb.button("f10", "+10", func=lambda c: self.step(10))
        tb.switcher("speed", SPEEDS, self._speed_label, func=lambda c: self.set_speed(tb["speed"].value))
        tb.textbox("pos", "", align="right")

        chart.hotkey(None, " ", lambda *a: self.toggle())
        chart.hotkey(None, "ArrowRight", lambda *a: self.step(1))
        chart.hotkey("shift", "ArrowRight", lambda *a: self.step(10))


    def run(self) -> "LivePlayer":
        """Open the window; blocks until it is closed."""
        run_window(self.chart or self.build(), self)

        return self
