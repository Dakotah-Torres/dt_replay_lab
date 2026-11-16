"""Swing hierarchy: minor -> intermediate -> major.

Every level uses the same shape (``Swing``) in and out, so ``promote`` can be
applied repeatedly. ``confirmed_at`` is the bar on which a swing became
knowable, which keeps any backtest free of lookahead.
"""
from dataclasses import dataclass
from typing import Literal

import pandas as pd

Kind = Literal["high", "low"]

MINOR, INTERMEDIATE, MAJOR = 1, 2, 3
LEVEL_NAMES = {MINOR: "minor", INTERMEDIATE: "intermediate", MAJOR: "major"}


@dataclass(frozen=True)
class Swing:
    index: int               # bar index of the swing candle
    time: pd.Timestamp       # where the marker goes
    price: float             # the high (or low)
    kind: Kind               # "high" or "low"
    confirmed_at: int        # bar index when you KNEW it (anti-lookahead)
    level: int = MINOR


def detect_minor_swings(df: pd.DataFrame, n: int = 5) -> list[Swing]:
    """Minor swings: a bar whose high (low) beats the n bars on each side.

    Ties are NOT swings (strict comparison). A candidate at bar c is only
    confirmed at bar c + n, which is recorded in ``confirmed_at``.
    Returns swings sorted by (index, kind).
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    times = df["time"]

    swings: list[Swing] = []
    for c in range(n, len(df) - n):
        window_h = highs[c - n:c + n + 1]
        window_l = lows[c - n:c + n + 1]

        # strictly greater than every other bar in the window
        if highs[c] == window_h.max() and (window_h == highs[c]).sum() == 1:
            swings.append(Swing(c, times.iat[c], float(highs[c]), "high", c + n))

        if lows[c] == window_l.min() and (window_l == lows[c]).sum() == 1:
            swings.append(Swing(c, times.iat[c], float(lows[c]), "low", c + n))

    return swings


def promote(swings: list[Swing]) -> list[Swing]:
    """Next level up from one level of swings.

    A high is promoted when it is higher than the previous AND next high of
    the same level (lows mirrored). It only becomes known when that next
    same-kind swing is confirmed, so ``confirmed_at`` is taken from it.
    """
    promoted: list[Swing] = []
    for kind in ("high", "low"):
        same = sorted((s for s in swings if s.kind == kind), key=lambda s: s.index)
        for prev, cur, nxt in zip(same, same[1:], same[2:]):
            if kind == "high":
                ok = cur.price > prev.price and cur.price > nxt.price
            else:
                ok = cur.price < prev.price and cur.price < nxt.price
            if ok:
                promoted.append(Swing(
                    cur.index, cur.time, cur.price, kind,
                    confirmed_at=nxt.confirmed_at, level=cur.level + 1,
                ))
    return sorted(promoted, key=lambda s: (s.index, s.kind))


def build_hierarchy(df: pd.DataFrame, n: int = 5, levels: int = 3) -> dict[int, list[Swing]]:
    """Return ``{level: swings}`` for level 1..levels."""
    out = {MINOR: detect_minor_swings(df, n)}
    for level in range(MINOR + 1, levels + 1):
        out[level] = promote(out[level - 1])
    return out


def swings_to_frame(swings: list[Swing]) -> pd.DataFrame:
    """Swings as a DataFrame, handy for inspection in a notebook."""
    return pd.DataFrame([s.__dict__ for s in swings])
