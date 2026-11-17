# dt-replay-lab

Research sandbox for splitting price action into **minor / intermediate / major** swings, with a light-theme chart visualizer.

```
src/dt_replay_lab/
  __init__.py       public API + main()
  cli/              `dt-replay-lab new`: scaffold.py
  data/             data.py: load_ohlc, normalize_ohlc, make_test_data
  indicators/       indicator.py (the contract), swing.py (streaming), swings.py (batch),
                    moving_average.py (SMA, RSI)
  engine/           engine.py (run / record / check), contract.py, checks.py
    player/         player.py: the replay window
  viz/              recording.py (what's visible at bar N), visualizer.py (theme + static chart)
data/               sample csv files (outside the package)
tests/  docs/
```

Run the demo: `uv run dt-replay-lab` (or `uv run python -m dt_replay_lab`).

## Replay engine

```python
from dt_replay_lab import engine, SMA, RSI, SwingIndicator, make_test_data

engine.run(make_test_data(), SMA(20), RSI(14), SwingIndicator(n=5))
```

Two run types:

```python
from dt_replay_lab import RunType
engine.run(df, SMA(20))                              # RunType.PRERUN (default): compute all, then replay with rewind
engine.run(df, SMA(20), run_type=RunType.LIVERUN)    # compute each bar as it arrives, like a live feed; no rewind
```

PRERUN opens a window that plays candles in one at a time. Buttons: `|<  -10  -1  Play  +1  +10  >|` and a speed switcher.
Keys: **Space** play/pause, **←/→** step 1, **Shift+←/→** step 10.

How it stays honest: the indicator is fed one bar at a time and only sees bars up to the current one (`Bars` is a read-only prefix view). Everything it emits is stamped with the bar it was emitted on, and the replay shows it from that bar onward, so a swing confirmed 5 bars late appears 5 bars late. Rewinding just moves the cursor, so bar N always looks the same however you got there.

### Writing an indicator

Start with `uv run dt-replay-lab new my_idea`, which writes a ready-to-edit file. The full rules are in [docs/indicator-contract.md](docs/indicator-contract.md). Short version:

```python
from dt_replay_lab import engine, Indicator, Mark, SMA, hline

class Breakout(Indicator):
    def __init__(self, n=20):
        self.n, self.name = n, f"Breakout {n}"

    def reset(self):                      # called before every run
        self.level = None

    def on_bar(self, bars):               # bars.close[-1] is the current bar
        if len(bars) > self.n and bars.close[-1] > bars.high[-self.n - 1:-1].max():
            yield Mark(bars.i, "below", "BO", "arrow_up", "#00a67e")
            yield hline(float(bars.close[-1]), key="last-bo")   # same key replaces the old line

engine.run("data/my.csv", Breakout(20), SMA(50))
```

- `Value(series, v)` needs a `SeriesSpec` declared in `series()`. `pane="rsi"` puts it in its own sub-pane.
- `Mark(index, ...)` may point at an earlier bar than the current one (a confirmed swing), never a later one (raises `LookaheadError`).
- Drawings: `hline`, `vline`, `trend`, `box`, `vspan`. Reuse a `key` to replace one.
- Vectorised indicators: subclass `BatchIndicator` and yield `(emitted_at, output)` from `compute(df)`.
- `engine.check(df, indicator)` checks the whole contract (structure, crashes, determinism, lookahead) and prints PASS/WARN/FAIL per rule.
- `engine.record(df, ...)` gives the `Recording` with no window; `rec.visualizer(cursor)` gives a static chart at any bar.

Use it from another project: `uv add --editable /path/to/dt-replay-lab` (or `pip install -e`).

## Swings

```python
from dt_replay_lab import load_ohlc, build_hierarchy

df = load_ohlc("data/swing_test.csv")        # needs time/open/high/low/close
levels = build_hierarchy(df, n=5)            # {1: minor, 2: intermediate, 3: major}
```

- Minor: bar whose high (low) is strictly beyond the `n` bars either side. Confirmed at `index + n`.
- `promote()`: a swing is promoted when it is beyond the previous and next swing of the same kind and level. `confirmed_at` is the next swing's confirmation bar, so there is no lookahead.

## Visualizer

```python
from dt_replay_lab import Visualizer

viz = Visualizer(df, title="ES 5m")
viz.add_line(df.close.rolling(20).mean(), "SMA 20")                 # overlay
viz.add_line(rsi, "RSI 14", pane="rsi", levels=[30, 70])            # sub-pane
viz.add_histogram(macd_hist, "MACD hist", pane="macd")
viz.add_swings(levels[1] + levels[2] + levels[3])
viz.hline(101.5).trend_line(t0, p0, t1, p1).box(t0, hi, t1, lo).vspan(t0, t1)
viz.show()
```

Series can be the same length as `df` or indexed like it. Nothing is drawn until `show()`/`build()`, so calls can come in any order.
