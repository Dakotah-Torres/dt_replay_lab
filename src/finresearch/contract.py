"""Does this indicator follow the replay contract?  (see docs/indicator-contract.md)

    report = check_contract(df, MyIndicator(period=20))
    print(report)          # PASS / WARN / FAIL line per rule
    assert report.ok       # no FAIL lines

Rules checked, in order:
  1. structure      subclasses Indicator, has a name, implements on_bar (or compute),
                    series() returns unique, valid SeriesSpecs
  2. runs           no crash; every output is a valid Value / Mark / Draw
  3. deterministic  two runs on the same data give identical output (reset() works)
  4. no lookahead   output at bar k is the same whether or not bars after k exist
  5. sanity         emits something, uses every declared series, is fast enough
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from .checks import check_lookahead
from .data import normalize_ohlc
from .indicator import BatchIndicator, Indicator, SeriesSpec, Value
from .recording import Recording

SLOW_MS_PER_BAR = 2.0


@dataclass(frozen=True)
class Issue:
    level: Literal["error", "warning"]
    code: str
    message: str


@dataclass
class Report:
    indicator: str
    bars: int
    lines: list[tuple[str, str, str]] = field(default_factory=list)   # (PASS|WARN|FAIL, rule, detail)
    issues: list[Issue] = field(default_factory=list)

    def _add(self, status: str, rule: str, detail: str = "", code: str = "") -> None:
        self.lines.append((status, rule, detail))
        if status != "PASS":
            self.issues.append(Issue("error" if status == "FAIL" else "warning", code or rule, detail))

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        head = f"Contract check: {self.indicator} on {self.bars} bars"
        body = "\n".join(f"  {s}  {rule}" + (f" - {detail}" if detail else "")
                         for s, rule, detail in self.lines)
        verdict = "OK" if self.ok else "NOT OK: fix the FAIL lines above"
        return f"{head}\n{body}\n  => {verdict}"


def _structure(ind) -> list[tuple[str, str, str]]:
    """Returns [(FAIL|WARN, code, message)] for static problems."""
    out = []
    if not isinstance(ind, Indicator):
        return [("FAIL", "not_indicator",
                 f"{type(ind).__name__} must subclass finresearch.Indicator (or BatchIndicator)")]
    if isinstance(ind, BatchIndicator):
        if type(ind).compute is BatchIndicator.compute:
            out.append(("FAIL", "no_compute", "BatchIndicator must implement compute(self, df)"))
    elif type(ind).on_bar is Indicator.on_bar:
        out.append(("FAIL", "no_on_bar", "implement on_bar(self, bars)"))
    if not ind.name:
        out.append(("WARN", "no_name", f"set self.name in __init__ (legend label); using {type(ind).__name__!r}"))
    try:
        specs = ind.series()
    except Exception as e:
        return out + [("FAIL", "series_crash", f"series() raised {type(e).__name__}: {e}")]
    if not isinstance(specs, (list, tuple)) or not all(isinstance(s, SeriesSpec) for s in specs):
        return out + [("FAIL", "series_type", "series() must return a list of SeriesSpec")]
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        out.append(("FAIL", "series_dupe", f"series() has duplicate names: {names}"))
    for s in specs:
        if not s.name:
            out.append(("FAIL", "series_name", "every SeriesSpec needs a name"))
        if s.kind not in ("line", "histogram"):
            out.append(("FAIL", "series_kind", f"{s.name!r}: kind must be 'line' or 'histogram', got {s.kind!r}"))
        if not 0 < s.height <= 0.6:
            out.append(("FAIL", "series_height", f"{s.name!r}: height must be in (0, 0.6], got {s.height}"))
    return out


def _signature(rec: Recording):
    return [(e.at, repr(e.out)) for e in rec.events]


def check_contract(data, indicator: Indicator) -> Report:
    df = normalize_ohlc(data)
    report = Report(repr(indicator), len(df))

    # 1. structure
    problems = _structure(indicator)
    if problems:
        for status, code, msg in problems:
            report._add(status, "structure", msg, code)
    else:
        report._add("PASS", "structure", "subclasses Indicator, named, series() valid")
    if any(s == "FAIL" for s, _, _ in problems):
        return report

    # 2. runs without crashing, outputs valid
    try:
        t0 = time.perf_counter()
        rec = Recording.record(df, [indicator])
        ms = (time.perf_counter() - t0) * 1000 / max(len(df), 1)
    except Exception as e:
        hint = " (bars.* arrays are read-only: copy before modifying)" if "read-only" in str(e) else ""
        report._add("FAIL", "runs", f"{type(e).__name__}: {e}{hint}", "run_failed")
        return report
    report._add("PASS", "runs", f"{len(rec.events)} outputs, {ms:.3f} ms/bar")

    # 3. deterministic
    again = Recording.record(df, [indicator])
    if _signature(rec) != _signature(again):
        report._add("FAIL", "deterministic",
                    "two runs on the same data differ: reset() isn't restoring all state "
                    "(or something random/global is used)", "not_deterministic")
    else:
        report._add("PASS", "deterministic", "identical output on a rerun")

    # 4. lookahead
    problems = check_lookahead(df, indicator)
    if problems:
        for p in problems[:3]:
            report._add("FAIL", "no lookahead", p, "lookahead")
    else:
        report._add("PASS", "no lookahead", "output at bar k never depends on bars after k")

    # 5. sanity
    if not rec.events:
        report._add("WARN", "emits something", "indicator produced no outputs on this data", "silent")
    declared = set(rec.specs)
    used = {e.out.series for e in rec.events if isinstance(e.out, Value)}
    if declared - used:
        report._add("WARN", "uses its series", f"declared but never emitted: {sorted(declared - used)}",
                    "unused_series")
    if ms > SLOW_MS_PER_BAR:
        report._add("WARN", "fast enough", f"{ms:.1f} ms/bar; replay of 100k bars would take "
                    f"{ms * 100:.0f}s to precompute (consider a BatchIndicator)", "slow")
    return report
