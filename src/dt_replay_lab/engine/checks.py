"""Lookahead check: does output at bar k change when bars after k are removed?"""
from __future__ import annotations

from collections import Counter

import numpy as np

from dt_replay_lab.indicators.indicator import Indicator
from dt_replay_lab.viz.recording import Recording


def check_lookahead(data, indicator: Indicator, cuts: int = 8, seed: int = 0) -> list[str]:
    """Problems found at random cut points; an empty list means clean."""
    full = Recording.record(data, [indicator])
    rng = np.random.default_rng(seed)
    ks = sorted(set(rng.integers(min(30, full.n - 1), full.n - 1, cuts).tolist()))
    key = lambda e: (e.at, repr(e.out))
    problems = []

    for k in ks:
        part = Recording.record(full.df.iloc[:k + 1], [indicator])
        expected = Counter(key(e) for e in full.events if e.at <= k)
        got = Counter(key(e) for e in part.events)

        if expected != got:
            only_full, only_cut = expected - got, got - expected
            problems.append(f"cut at bar {k}: {len(only_full)} outputs only in the full run, "
                            f"{len(only_cut)} only in the truncated run "
                            f"(e.g. {next(iter(only_full or only_cut))})")

    return problems
