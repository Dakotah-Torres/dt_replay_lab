"""Atr: <one line - what should this indicator show you?>.

Run it:   uv run python atr.py
Contract: docs/indicator-contract.md
"""
from dt_replay_lab import Indicator, Mark, SeriesSpec, Value, engine, hline, make_test_data
# also available: trend, box, vline, vspan (drawings), BatchIndicator (vectorised)
import numpy as np

class Atr(Indicator):

    _atr: float | None
    _tr_sum: float
    # 1. PARAMETERS ----------------------------------------------------------
    # Everything you want to tune is an __init__ argument with a default.
    # Store it on self, and set self.name (shown in the legend, keep it unique).
    def __init__(self, period: int = 20):
        self.period = period
        self.name = f"Atr {period}"
        self.reset()

    # 2. STATE ---------------------------------------------------------------
    # reset() runs before every replay. Put ALL running state here (counters,
    # last swing, lists...). If it isn't reset, reruns differ and check fails.
    def reset(self):
        self._atr = None
        self._tr_sum = 0.0

    # 3. SERIES --------------------------------------------------------------
    
    def series(self):
        return [SeriesSpec(self.name, pane="atr", color=None, levels=())]

    # 4. LOGIC ---------------------------------------------------------------
   
    def on_bar(self, bars):
        tr = self.true_range(bars)

        if len(bars) < self.period:
            self._tr_sum += self.true_range(bars)
            
            
        yield Value(self.name, tr)

    def true_range(self, bars) -> float:
        cur_high = bars.high[-1]
        cur_low = bars.low[-1]
        if bars.i > 0: 
            return cur_high-cur_low

        prev_close = bars.close[-2]
       
        
        TR = max(cur_high-cur_low, abs(cur_high-prev_close), abs(cur_low-prev_close) )

        return TR 

if __name__ == "__main__":
    df = make_test_data()                 # or engine.run("data/my.csv", ...)
    engine.check(df, Atr())             # contract report: PASS / WARN / FAIL
    engine.run(df, Atr())               # replay window
