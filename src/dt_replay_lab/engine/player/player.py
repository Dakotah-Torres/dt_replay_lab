"""Replay window: play, pause, step and rewind over a Recording."""
from __future__ import annotations

import pandas as pd

from dt_replay_lab.engine.player.window import SPEEDS, build_window, parse_speed, run_window
from dt_replay_lab.viz.recording import Recording, resolve_draw


class Player:
    """Moves a cursor through a Recording; keys: Space, Left/Right, Shift+Left/Right."""

    def __init__(self, recording: Recording, title: str = "dt_replay_lab replay",
                 start: int | None = None, speed: str = "10/s", width: int = 1500, height: int = 900) -> None:
        self.rec = recording
        self.title, self.width, self.height = title, width, height
        self.floor = min(19, recording.n - 1)         # the chart needs a few bars to size itself
        self.cursor = self._clamp((start if start is not None else min(100, recording.n)) - 1)
        self.speed = parse_speed(speed)
        self._speed_label = speed
        self.playing = False

        self.chart = None
        self._lines: dict = {}
        self._shown = -1                              # last bar on screen
        self._marker_sig = None
        self._drawn: dict = {}                        # key -> (version, drawing object)


    def seek(self, bar: int) -> None:
        self._render(self._clamp(bar))


    def step(self, k: int = 1) -> None:
        self.seek(self.cursor + k)


    def play(self) -> None:
        if self.at_end:
            self.seek(self.floor)

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
        return self.cursor >= self.rec.n - 1


    def _clamp(self, bar: int) -> int:
        return max(self.floor, min(self.rec.n - 1, bar))


    def build(self):
        """Create the window and draw the starting state."""
        self.chart, self._lines = build_window(self.rec.specs, "volume" in self.rec.df,
                                               self.title, self.width, self.height)
        self._add_controls(self.chart)
        self._render(self.cursor, full=True)
        self.chart.fit()

        return self.chart


    def _add_controls(self, chart) -> None:
        tb = chart.topbar
        tb.button("start", "|<", func=lambda c: self.pause() or self.seek(0))
        tb.button("b10", "-10", func=lambda c: self.step(-10))
        tb.button("b1", "-1", func=lambda c: self.step(-1))
        tb.button("play", "Play", func=lambda c: self.toggle())
        tb.button("f1", "+1", func=lambda c: self.step(1))
        tb.button("f10", "+10", func=lambda c: self.step(10))
        tb.button("end", ">|", func=lambda c: self.pause() or self.seek(self.rec.n - 1))
        tb.switcher("speed", SPEEDS, self._speed_label, func=lambda c: self.set_speed(tb["speed"].value))
        tb.textbox("pos", "", align="right")

        chart.hotkey(None, " ", lambda *a: self.toggle())
        chart.hotkey(None, "ArrowRight", lambda *a: self.step(1))
        chart.hotkey(None, "ArrowLeft", lambda *a: self.step(-1))
        chart.hotkey("shift", "ArrowRight", lambda *a: self.step(10))
        chart.hotkey("shift", "ArrowLeft", lambda *a: self.step(-10))


    def _sync_button(self) -> None:
        if self.chart is not None:
            self.chart.topbar["play"].set("Pause" if self.playing else "Play")


    def _render(self, target: int, full: bool = False) -> None:
        """Stream forward when possible, otherwise redraw everything up to target."""
        rec, chart, prev = self.rec, self.chart, self._shown
        stream = not full and 0 < target - prev <= 500 and not rec.has_irregular_values(prev, target)

        if stream:
            for j in range(prev + 1, target + 1):
                chart.update(rec.df.iloc[j])

                for name, value in rec.values_by_at.get(j, ()):
                    self._lines[name].update(pd.Series({"time": self._time(j), name: value}))

        elif target != prev or full:
            chart.set(rec.df.iloc[:target + 1])

            for name, frame in rec.lines_at(target).items():
                self._lines[name].set(frame)

        if not stream or rec.has_marks(prev, target):
            self._sync_markers(target)

        if not stream or rec.has_draws(prev, target):
            self._sync_drawings(target)

        self._shown = self.cursor = target
        chart.topbar["pos"].set(f"bar {target + 1}/{rec.n}   {self._time(target):%Y-%m-%d %H:%M}")


    def _time(self, i: int) -> pd.Timestamp:
        return pd.Timestamp(self.rec.df["time"].iat[i])


    def _sync_markers(self, target: int) -> None:
        """Redraw markers only when they changed."""
        marks = self.rec.markers_at(target)
        sig = [tuple(m.values()) for m in marks]

        if sig == self._marker_sig:
            return

        self._marker_sig = sig
        self.chart.clear_markers()

        if marks:
            self.chart.marker_list(marks)


    def _sync_drawings(self, target: int) -> None:
        """Delete drawings that are gone or replaced, create the new ones."""
        want = self.rec.drawings_at(target)

        for key in [k for k, (ver, _) in self._drawn.items() if want.get(k, (None,))[0] != ver]:
            self._drawn.pop(key)[1].delete()

        for key, (ver, draw) in want.items():
            if key not in self._drawn:
                method, kwargs = resolve_draw(draw, self.rec.times)
                self._drawn[key] = (ver, getattr(self.chart, method)(**kwargs))


    def run(self) -> "Player":
        """Open the window; blocks until it is closed."""
        run_window(self.chart or self.build(), self)

        return self
