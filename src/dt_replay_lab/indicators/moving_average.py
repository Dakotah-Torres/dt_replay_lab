"""Small streaming indicators: templates for writing your own."""
from __future__ import annotations

from dt_replay_lab.indicators.indicator import Bars, Indicator, SeriesSpec, Value


class SMA(Indicator):
    """Simple moving average, overlaid on price."""

    def __init__(self, period: int = 20, source: str = "close", color: str | None = None) -> None:
        self.period, self.source, self.color = period, source, color
        self.name = f"SMA {period}"


    def series(self):
        return [SeriesSpec(self.name, color=self.color)]


    def on_bar(self, bars: Bars):
        if len(bars) >= self.period:
            yield Value(self.name, float(getattr(bars, self.source)[-self.period:].mean()))


class RSI(Indicator):
    """Wilder's RSI in its own pane with 30/70 guides."""

    def __init__(self, period: int = 14, color: str | None = None) -> None:
        self.period, self.color = period, color
        self.name = f"RSI {period}"
        self.reset()


    def reset(self) -> None:
        self._avg_gain = self._avg_loss = None     # None until warmed up
        self._gain_sum = self._loss_sum = 0.0      # running sums during warm-up


    def series(self):
        return [SeriesSpec(self.name, pane="rsi", color=self.color, levels=(30, 70))]


    def on_bar(self, bars: Bars):
        if bars.i == 0:
            return

        change = float(bars.close[-1] - bars.close[-2])
        gain, loss = max(change, 0.0), max(-change, 0.0)
        p = self.period

        if self._avg_gain is None:
            self._gain_sum += gain
            self._loss_sum += loss

            if bars.i < p:
                return

            self._avg_gain, self._avg_loss = self._gain_sum / p, self._loss_sum / p

        else:
            self._avg_gain = (self._avg_gain * (p - 1) + gain) / p
            self._avg_loss = (self._avg_loss * (p - 1) + loss) / p

        rs = self._avg_gain / self._avg_loss if self._avg_loss else float("inf")

        yield Value(self.name, 100.0 - 100.0 / (1.0 + rs))
