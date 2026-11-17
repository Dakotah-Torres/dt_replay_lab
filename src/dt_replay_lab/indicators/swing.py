"""Minor / intermediate / major swings as a streaming indicator.

Same rules as ``dt_replay_lab.swings`` (strict ties, promote when beyond the
previous and next same-kind swing), but computed bar by bar. A swing is
emitted on the bar that confirms it, so on screen it appears ``n`` bars after
the candle it marks -- and is re-marked at a higher level when a later swing
promotes it.
"""
from __future__ import annotations

from .indicator import Bars, Indicator, Mark
from dt_replay_lab.viz.visualizer import SWING_STYLE


class SwingIndicator(Indicator):
    def __init__(self, n: int = 5, levels: int = 3) -> None:
        self.n, self.levels = n, levels
        self.name = f"Swings n={n}"
        self.reset()

    def reset(self) -> None:
        # per level and kind: [(bar index, price), ...] in confirmation order
        self._seen = {lv: {"high": [], "low": []} for lv in range(1, self.levels + 1)}

    def on_bar(self, bars: Bars):
        n, i = self.n, bars.i
        if i < 2 * n:
            return
        c = i - n                                   # the bar that can be judged now
        hi, lo = bars.high[c - n:i + 1], bars.low[c - n:i + 1]
        if hi[n] == hi.max() and (hi == hi[n]).sum() == 1:
            yield from self._found(1, "high", c, float(hi[n]))
        if lo[n] == lo.min() and (lo == lo[n]).sum() == 1:
            yield from self._found(1, "low", c, float(lo[n]))

    def _found(self, level: int, kind: str, index: int, price: float):
        shape, color, hi_text, lo_text = SWING_STYLE[min(level, max(SWING_STYLE))]
        is_high = kind == "high"
        if not is_high and shape == "arrow_down":
            shape = "arrow_up"
        yield Mark(index, "above" if is_high else "below", hi_text if is_high else lo_text,
                   shape, color, key=(index, kind), rank=level)

        seen = self._seen[level][kind]
        seen.append((index, price))
        if level < self.levels and len(seen) >= 3:
            (_, p_prev), (i_cur, p_cur), (_, p_next) = seen[-3:]
            beats = (p_cur > p_prev and p_cur > p_next) if is_high else (p_cur < p_prev and p_cur < p_next)
            if beats:
                yield from self._found(level + 1, kind, i_cur, p_cur)
