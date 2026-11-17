"""Replay window: play / pause / step / rewind over a Recording.

Forward steps stream new candles in with ``update()``. Anything that can't
be streamed (rewind, jump, values about earlier bars) re-sends the visible
slice with ``set()``. Both paths end in the same state, so rewinding to bar N
always looks exactly like having played up to bar N.

Keys: Space play/pause, Right/Left step 1, Shift+Right/Left step 10.
"""
from __future__ import annotations

import asyncio
import time

import pandas as pd

from dt_replay_lab.viz.recording import Recording
from dt_replay_lab.viz.visualizer import PALETTE, THEME, apply_theme

SPEEDS = ("1/s", "2/s", "5/s", "10/s", "25/s", "60/s")


class Player:
    def __init__(self, recording: Recording, title: str = "dt_replay_lab replay",
                 start: int | None = None, speed: str = "10/s",
                 width: int = 1500, height: int = 900) -> None:
        self.rec = recording
        self.title, self.width, self.height = title, width, height
        n = recording.n
        self.floor = min(19, n - 1)                     # chart needs a few bars to size itself
        self.cursor = self._clamp((start if start is not None else min(100, n)) - 1)
        self.speed = float(speed.split("/")[0])
        self._speed_label = speed
        self.playing = False

        self.chart = None
        self._lines: dict = {}
        self._shown = -1                                # last bar currently on screen
        self._marker_sig = None
        self._drawn: dict = {}                          # key -> (version, drawing object)

    # ── public controls (also bound to buttons / keys) ────────
    def seek(self, bar: int) -> None:
        self._render(self._clamp(bar))

    def step(self, k: int = 1) -> None:
        self.seek(self.cursor + k)

    def play(self) -> None:
        if self.cursor >= self.rec.n - 1:
            self.seek(self.floor)
        self.playing = True
        self._sync_button()

    def pause(self) -> None:
        self.playing = False
        self._sync_button()

    def toggle(self) -> None:
        self.pause() if self.playing else self.play()

    def set_speed(self, label: str) -> None:
        self.speed = float(label.split("/")[0])

    def _clamp(self, bar: int) -> int:
        return max(self.floor, min(self.rec.n - 1, bar))

    # ── window ────────────────────────────────────────────────
    def build(self):
        from lightweight_charts import Chart  # needs a GUI backend, so imported late

        rec = self.rec
        panes: dict[str, float] = {}
        for spec in rec.specs.values():
            if spec.pane != "main":
                panes.setdefault(spec.pane, spec.height)

        chart = Chart(width=self.width, height=self.height, title=self.title,
                      inner_width=1, inner_height=1.0 - sum(panes.values()))
        apply_theme(chart, right_offset=8)
        chart.legend(visible=True, ohlc=True, percent=True, lines=True,
                     color=THEME["text"], font_family=THEME["font"])
        if "volume" in rec.df:
            chart.volume_config(up_color=THEME["vol_up"], down_color=THEME["vol_down"])

        hosts = {"main": chart}
        for name, height in panes.items():
            sub = chart.create_subchart(position="bottom", width=1, height=height, sync=True)
            apply_theme(sub, right_offset=8)
            sub.legend(visible=True, ohlc=False, percent=False, lines=True,
                       color=THEME["text"], font_family=THEME["font"])
            hosts[name] = sub

        for i, spec in enumerate(rec.specs.values()):
            host, color = hosts[spec.pane], spec.color or PALETTE[i % len(PALETTE)]
            if spec.kind == "histogram":
                obj = host.create_histogram(spec.name, color=color)
            else:
                obj = host.create_line(spec.name, color=color, width=spec.width, style=spec.style,
                                       price_line=False, price_label=False)
                for level in spec.levels:
                    obj.horizontal_line(level, color="#b0b5bf", width=1, style="dashed")
            self._lines[spec.name] = obj

        self._add_controls(chart)
        self.chart = chart
        self._render(self.cursor, full=True)
        chart.fit()
        return chart

    def _add_controls(self, chart) -> None:
        tb = chart.topbar
        for name, label, k in (("start", "|<", None), ("b10", "-10", -10), ("b1", "-1", -1)):
            tb.button(name, label, func=(lambda c: self.pause() or self.seek(0)) if k is None
                      else (lambda c, k=k: self.step(k)))
        tb.button("play", "Play", func=lambda c: self.toggle())
        for name, label, k in (("f1", "+1", 1), ("f10", "+10", 10)):
            tb.button(name, label, func=lambda c, k=k: self.step(k))
        tb.button("end", ">|", func=lambda c: self.pause() or self.seek(self.rec.n - 1))
        tb.switcher("speed", SPEEDS, self._speed_label,
                    func=lambda c: self.set_speed(tb["speed"].value))
        tb.textbox("pos", "", align="right")

        chart.hotkey(None, " ", lambda *a: self.toggle())
        chart.hotkey(None, "ArrowRight", lambda *a: self.step(1))
        chart.hotkey(None, "ArrowLeft", lambda *a: self.step(-1))
        chart.hotkey("shift", "ArrowRight", lambda *a: self.step(10))
        chart.hotkey("shift", "ArrowLeft", lambda *a: self.step(-10))

    def _sync_button(self) -> None:
        if self.chart is not None:
            self.chart.topbar["play"].set("Pause" if self.playing else "Play")

    # ── rendering ─────────────────────────────────────────────
    def _render(self, target: int, full: bool = False) -> None:
        rec, chart = self.rec, self.chart
        prev = self._shown
        stream = (not full and 0 < target - prev <= 500
                  and not rec.has_irregular_values(prev, target))

        if stream:
            for j in range(prev + 1, target + 1):
                chart.update(self._bar(j))
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
        t = self._time(target)
        if chart is not None:
            chart.topbar["pos"].set(f"bar {target + 1}/{rec.n}   {t:%Y-%m-%d %H:%M}")

    def _time(self, i: int) -> pd.Timestamp:
        return pd.Timestamp(self.rec.df["time"].iat[i])

    def _bar(self, i: int) -> pd.Series:
        return self.rec.df.iloc[i]

    def _sync_markers(self, target: int) -> None:
        marks = self.rec.markers_at(target)
        sig = [(m["time"], m["position"], m["shape"], m["color"], m["text"]) for m in marks]
        if sig == self._marker_sig:
            return
        self._marker_sig = sig
        self.chart.clear_markers()
        if marks:
            self.chart.marker_list(marks)

    def _sync_drawings(self, target: int) -> None:
        want = self.rec.drawings_at(target)
        for key in [k for k, (ver, _) in self._drawn.items() if k not in want or want[k][0] != ver]:
            self._drawn.pop(key)[1].delete()
        for key, (ver, draw) in want.items():
            if key not in self._drawn:
                method, kwargs = self.rec.resolve(draw)
                self._drawn[key] = (ver, getattr(self.chart, method)(**kwargs))

    # ── run loop ──────────────────────────────────────────────
    async def _loop(self) -> None:
        last, credit = time.monotonic(), 0.0
        while True:
            await asyncio.sleep(1 / 30)
            now = time.monotonic()
            dt, last = now - last, now
            if not self.playing:
                credit = 0.0
                continue
            credit += self.speed * dt
            k = int(credit)
            if k:
                credit -= k
                self.step(k)
            if self.cursor >= self.rec.n - 1:
                self.pause()

    def run(self) -> "Player":
        """Open the window and block until it is closed."""
        chart = self.chart or self.build()

        async def main():
            task = asyncio.create_task(self._loop())
            try:
                await chart.show_async()
            finally:
                task.cancel()

        asyncio.run(main())
        return self
