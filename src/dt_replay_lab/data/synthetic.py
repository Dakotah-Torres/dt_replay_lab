"""Synthetic: realistic fake OHLCV bars for testing indicators."""
import numpy as np
import pandas as pd


def _session_times(n_bars: int, start: str = "2026-01-05", freq_min: int = 5) -> pd.DatetimeIndex:
    """Weekday 09:30-16:00 bar times, no overnight or weekend bars."""
    per_day = 390 // freq_min
    days = pd.bdate_range(start, periods=-(-n_bars // per_day))
    offsets = pd.to_timedelta(np.arange(per_day) * freq_min, unit="min") + pd.Timedelta("9h30min")
    times = (days.values[:, None] + offsets.values[None, :]).ravel()[:n_bars]

    return pd.DatetimeIndex(times)


def make_test_data(n_bars: int = 1000, seed: int = 42, start_price: float = 4500.0,
                   tick: float = 0.25) -> pd.DataFrame:
    """5-minute futures-style bars with swings at three scales, gaps and realistic volume."""
    rng = np.random.default_rng(seed)
    times = _session_times(n_bars)
    t = np.arange(n_bars)
    bar_of_day = np.asarray((times.hour * 60 + times.minute - 570) // 5)
    first_bar = bar_of_day == 0

    # U-shape: busy at the open and close, quiet at lunch
    x = (bar_of_day + 0.5) / 78
    u_shape = 1.0 + 1.4 * np.exp(-x / 0.07) + 0.8 * np.exp(-(1 - x) / 0.07)

    # volatility clustering
    log_vol = np.zeros(n_bars)

    for i in range(1, n_bars):
        log_vol[i] = 0.97 * log_vol[i - 1] + rng.normal(0, 0.12)

    sigma = start_price * 0.0003 * u_shape * np.exp(log_vol - log_vol.var() / 2)

    # major / intermediate / minor waves on a fat-tailed random walk
    ph = rng.uniform(0, 2 * np.pi, 3)
    trend = (start_price * 0.012 * np.sin(t / 90 + ph[0])
             + start_price * 0.004 * np.sin(t / 22 + ph[1])
             + start_price * 0.0012 * np.sin(t / 6 + ph[2]))
    ret = rng.standard_t(5, n_bars) * sigma / np.sqrt(5 / 3)
    close = start_price + trend + np.cumsum(ret)

    # overnight gap at the first bar of each day
    gap = np.where(first_bar, rng.normal(0, start_price * 0.0006, n_bars), 0.0)
    gap[0] = 0.0
    close = close + np.cumsum(gap)

    open_ = np.concatenate([[close[0]], close[:-1]]) + gap + rng.normal(0, sigma * 0.05)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, sigma * 0.45))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, sigma * 0.45))

    bar_range = high - low
    volume = rng.lognormal(0, 0.35, n_bars) * 900 * u_shape * (0.5 + bar_range / bar_range.mean())

    snap = lambda a: np.round(a / tick) * tick     # round to the tick size

    return pd.DataFrame({
        "time": times.astype("datetime64[ns]"),
        "open": snap(open_),
        "high": snap(high),
        "low": snap(low),
        "close": snap(close),
        "volume": volume.astype(int),
    })
