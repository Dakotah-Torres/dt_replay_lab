"""Lookahead / repaint checking for indicators."""
from __future__ import annotations

import numpy as np

from .indicator import Indicator
from .recording import Recording


def check_lookahead(data, indicator: Indicator, cuts: int = 8, seed: int = 0) -> list[str]:
    """Return a list of problems (empty = clean).

    For several cut points k, the indicator is run on only bars 0..k and its
    output is compared with what the full-data run had emitted by bar k. If
    the two differ, the indicator used information from after bar k (or
    repainted something it had already shown).
    """
    full = Recording.record(data, [indicator])
    n = full.n
    rng = np.random.default_rng(seed)
    ks = sorted(set(rng.integers(min(30, n - 1), n - 1, cuts).tolist()))

    def key(e):
        return (e.at, repr(e.out))

    problems = []
    for k in ks:
        part = Recording.record(full.df.iloc[:k + 1], [indicator])
        expected = sorted((e for e in full.events if e.at <= k), key=key)
        got = sorted(part.events, key=key)
        if [key(e) for e in expected] != [key(e) for e in got]:
            only_full = {key(e) for e in expected} - {key(e) for e in got}
            only_cut = {key(e) for e in got} - {key(e) for e in expected}
            problems.append(f"cut at bar {k}: {len(only_full)} outputs only in the full run, "
                            f"{len(only_cut)} only in the truncated run "
                            f"(e.g. {next(iter(only_full or only_cut))})")
    return problems
