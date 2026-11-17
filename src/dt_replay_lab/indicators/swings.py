"""Batch swing hierarchy (minor -> intermediate -> major): the reference for SwingIndicator."""
from dataclasses import dataclass
from typing import Literal

import pandas as pd

Kind = Literal["high", "low"]

MINOR, INTERMEDIATE, MAJOR = 1, 2, 3


@dataclass(frozen=True)
class Swing:
    """A swing high or low, with the bar it was confirmed on."""

    index: int
    time: pd.Timestamp
    price: float
    kind: Kind
    confirmed_at: int
    level: int = MINOR


def detect_minor_swings(df: pd.DataFrame, n: int = 5) -> list[Swing]:
    """Bars whose high (low) strictly beats the n bars on each side; confirmed n bars later."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    times = df["time"]
    swings: list[Swing] = []

    for c in range(n, len(df) - n):
        window_h = highs[c - n:c + n + 1]
        window_l = lows[c - n:c + n + 1]

        if highs[c] == window_h.max() and (window_h == highs[c]).sum() == 1:
            swings.append(Swing(c, times.iat[c], float(highs[c]), "high", c + n))

        if lows[c] == window_l.min() and (window_l == lows[c]).sum() == 1:
            swings.append(Swing(c, times.iat[c], float(lows[c]), "low", c + n))

    return swings


def promote(swings: list[Swing]) -> list[Swing]:
    """Swings that beat the previous and next swing of the same kind, one level up."""
    promoted: list[Swing] = []

    for kind in ("high", "low"):
        same = sorted((s for s in swings if s.kind == kind), key=lambda s: s.index)

        for prev, cur, nxt in zip(same, same[1:], same[2:]):
            if kind == "high":
                beats = cur.price > prev.price and cur.price > nxt.price
            else:
                beats = cur.price < prev.price and cur.price < nxt.price

            if beats:
                promoted.append(Swing(cur.index, cur.time, cur.price, kind,
                                      confirmed_at=nxt.confirmed_at, level=cur.level + 1))

    return sorted(promoted, key=lambda s: (s.index, s.kind))


def build_hierarchy(df: pd.DataFrame, n: int = 5, levels: int = 3) -> dict[int, list[Swing]]:
    """{level: swings} for levels 1..levels."""
    out = {MINOR: detect_minor_swings(df, n)}

    for level in range(MINOR + 1, levels + 1):
        out[level] = promote(out[level - 1])

    return out


def swings_to_frame(swings: list[Swing]) -> pd.DataFrame:
    """Swings as a DataFrame for inspection."""
    return pd.DataFrame([s.__dict__ for s in swings])
