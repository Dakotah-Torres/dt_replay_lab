# finresearch

Research sandbox for splitting price action into **minor / intermediate / major** swings, with a light-theme chart visualizer.

```
src/finresearch/
  data.py        load_ohlc(), normalize_ohlc(), make_test_data()
  swings.py      Swing, detect_minor_swings(), promote(), build_hierarchy()
  visualizer.py  Visualizer (candles, indicators, markers, drawings)
data/            sample csv files
```

Run the demo: `uv run finresearch` (or `uv run python -m finresearch`).

## Swings

```python
from finresearch import load_ohlc, build_hierarchy

df = load_ohlc("data/swing_test.csv")        # needs time/open/high/low/close
levels = build_hierarchy(df, n=5)            # {1: minor, 2: intermediate, 3: major}
```

- Minor: bar whose high (low) is strictly beyond the `n` bars either side. Confirmed at `index + n`.
- `promote()`: a swing is promoted when it is beyond the previous and next swing of the same kind and level. `confirmed_at` is the next swing's confirmation bar, so there is no lookahead.

## Visualizer

```python
from finresearch import Visualizer

viz = Visualizer(df, title="ES 5m")
viz.add_line(df.close.rolling(20).mean(), "SMA 20")                 # overlay
viz.add_line(rsi, "RSI 14", pane="rsi", levels=[30, 70])            # sub-pane
viz.add_histogram(macd_hist, "MACD hist", pane="macd")
viz.add_swings(levels[1] + levels[2] + levels[3])
viz.hline(101.5).trend_line(t0, p0, t1, p1).box(t0, hi, t1, lo).vspan(t0, t1)
viz.show()
```

Series can be the same length as `df` or indexed like it. Nothing is drawn until `show()`/`build()`, so calls can come in any order.
