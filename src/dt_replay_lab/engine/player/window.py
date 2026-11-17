"""Window: chart layout and play loop shared by both players."""
from __future__ import annotations

import asyncio
import time

from dt_replay_lab.indicators.indicator import SeriesSpec
from dt_replay_lab.viz.visualizer import PALETTE, THEME, apply_theme

SPEEDS = ("1/s", "2/s", "5/s", "10/s", "25/s", "60/s")


def parse_speed(label: str) -> float:
    """'10/s' -> 10.0"""
    return float(label.split("/")[0])


def build_window(specs: dict[str, SeriesSpec], has_volume: bool, title: str, width: int, height: int):
    """Main chart, a sub-pane per non-main pane, a line per series; returns (chart, lines)."""
    from lightweight_charts import Chart     # needs a GUI backend, so imported late

    panes: dict[str, float] = {}

    for spec in specs.values():
        if spec.pane != "main":
            panes.setdefault(spec.pane, spec.height)

    chart = Chart(width=width, height=height, title=title, inner_width=1,
                  inner_height=1.0 - sum(panes.values()))
    apply_theme(chart, right_offset=8)
    chart.legend(visible=True, ohlc=True, percent=True, lines=True, color=THEME["text"], font_family=THEME["font"])

    if has_volume:
        chart.volume_config(up_color=THEME["vol_up"], down_color=THEME["vol_down"])

    hosts = {"main": chart}

    for name, pane_height in panes.items():
        sub = chart.create_subchart(position="bottom", width=1, height=pane_height, sync=True)
        apply_theme(sub, right_offset=8)
        sub.legend(visible=True, ohlc=False, percent=False, lines=True, color=THEME["text"], font_family=THEME["font"])
        hosts[name] = sub

    lines = {}

    for i, spec in enumerate(specs.values()):
        host, color = hosts[spec.pane], spec.color or PALETTE[i % len(PALETTE)]

        if spec.kind == "histogram":
            lines[spec.name] = host.create_histogram(spec.name, color=color)
            continue

        line = host.create_line(spec.name, color=color, width=spec.width, style=spec.style,
                                price_line=False, price_label=False)

        for level in spec.levels:
            line.horizontal_line(level, color="#b0b5bf", width=1, style="dashed")

        lines[spec.name] = line

    return chart, lines


def run_window(chart, player) -> None:
    """Show the window and step the player at its speed while playing; blocks until closed."""

    async def loop():
        last, credit = time.monotonic(), 0.0

        while True:
            await asyncio.sleep(1 / 30)
            now = time.monotonic()
            dt, last = now - last, now

            if not player.playing:
                credit = 0.0
                continue

            credit += player.speed * dt
            k = int(credit)

            if k:
                credit -= k
                player.step(k)

            if player.at_end:
                player.pause()


    async def main():
        task = asyncio.create_task(loop())

        try:
            await chart.show_async()
        finally:
            task.cancel()


    asyncio.run(main())
