# Indicator contract

To start research: `uv run finresearch new my_idea` writes `my_idea.py` with every part below already in place. Fill in the logic, then `uv run python my_idea.py` checks it and opens the replay.

## What you write

```python
class MyIdea(Indicator):
    def __init__(self, period=20):     # 1. parameters, and self.name
    def reset(self):                   # 2. all running state, back to start
    def series(self):                  # 3. lines/histograms you will draw on
    def on_bar(self, bars):            # 4. the logic, once per bar
```

| Part | Required | Rule |
|---|---|---|
| `self.name` | yes | Legend label. Set it in `__init__`, include the params, keep it unique. |
| `reset()` | if you keep state | Restore **all** state. Runs before every replay. Anything not reset makes reruns differ. |
| `series()` | if you emit `Value` | Return `SeriesSpec`s. Names must be unique across all indicators in a run. |
| `on_bar(bars)` | yes | Called once per bar, oldest first. `yield` outputs, or return nothing. |

Vectorised alternative: subclass `BatchIndicator` and implement `compute(df)` yielding `(emitted_at, output)`, where `emitted_at` is the first bar on which that output could have been known.

## What `on_bar` receives

`bars` is a **read-only view of the past**: bars up to and including the current one.

| | |
|---|---|
| `bars.i` | index of the current bar |
| `bars.open/high/low/close/volume/time` | numpy arrays; `[-1]` is the current bar |
| `len(bars)` | number of bars seen so far |

You cannot see the future, and writing into the arrays raises an error.

## What you can emit

| Output | Meaning | Rules |
|---|---|---|
| `Value(series, number)` | a point on a declared line/histogram, on the current bar | series must be declared; number must be finite (skip the bar instead of NaN) |
| `Mark(index, position, text, shape, color, key, rank)` | marker on a candle | `position` is `"above"`/`"below"`; `shape` is `circle`, `square`, `arrow_up`, `arrow_down`; same `key` keeps only the highest `rank` |
| `hline(price)` `vline(i)` `trend(i0,p0,i1,p1)` `box(i0,p0,i1,p1)` `vspan(i0,i1)` | drawings | same `key` replaces the earlier drawing |

`Mark`/drawing bar indices may be **earlier** than the current bar (a swing confirmed 5 bars later marks the candle 5 bars back) but never later: that raises `LookaheadError`.

Everything you emit is shown from the bar it was emitted on, so the replay shows exactly what you would have known live.

## Checking it

```python
engine.check(df, MyIdea())
```

```
Contract check: MyIdea(period=20) on 1000 bars
  PASS  structure - subclasses Indicator, named, series() valid
  PASS  runs - 981 outputs, 0.012 ms/bar
  PASS  deterministic - identical output on a rerun
  PASS  no lookahead - output at bar k never depends on bars after k
  => OK
```

| Rule | FAIL means |
|---|---|
| structure | missing `on_bar`/`compute`, bad or duplicate `SeriesSpec`, not an `Indicator` |
| runs | crashed (message says which bar) or emitted an invalid output |
| deterministic | two runs differ: `reset()` misses some state, or you use randomness/globals |
| no lookahead | output at bar k changes when bars after k are removed |

Warnings (don't fail): emits nothing, declares a series it never uses, slower than 2 ms/bar.

## Running it

```python
engine.run(df_or_csv_path, MyIdea(period=20), SMA(50))   # replay window
rec = engine.record(df, MyIdea())                        # no window
rec.visualizer(cursor=400).show()                        # static chart at bar 400
```
