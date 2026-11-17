"""Contract check: structure, runs, deterministic, no lookahead, sanity (docs/indicator-contract.md)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from dt_replay_lab.data import normalize_ohlc
from dt_replay_lab.engine.checks import check_lookahead
from dt_replay_lab.indicators.indicator import BatchIndicator, Indicator, SeriesSpec, Value
from dt_replay_lab.viz.recording import Recording

SLOW_MS_PER_BAR = 2.0


@dataclass(frozen=True)
class Issue:
    level: Literal["error", "warning"]
    code: str
    message: str


@dataclass
class Report:
    """PASS / WARN / FAIL per rule; truthy when nothing failed."""

    indicator: str
    bars: int
    lines: list[tuple[str, str, str]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


    def add(self, status: str, rule: str, detail: str = "", code: str = "") -> None:
        self.lines.append((status, rule, detail))

        if status != "PASS":
            self.issues.append(Issue("error" if status == "FAIL" else "warning", code or rule, detail))


    @property
    def ok(self) -> bool:
        return all(i.level != "error" for i in self.issues)


    def __bool__(self) -> bool:
        return self.ok


    def __str__(self) -> str:
        rows = [f"  {s}  {rule}" + (f" - {detail}" if detail else "") for s, rule, detail in self.lines]
        verdict = "OK" if self.ok else "NOT OK: fix the FAIL lines above"

        return "\n".join([f"Contract check: {self.indicator} on {self.bars} bars", *rows, f"  => {verdict}"])


def _structure(ind) -> list[tuple[str, str, str]]:
    """Static problems as (FAIL|WARN, code, message)."""
    if not isinstance(ind, Indicator):
        return [("FAIL", "not_indicator", f"{type(ind).__name__} must subclass Indicator (or BatchIndicator)")]

    out = []

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


def check_contract(data, indicator: Indicator) -> Report:
    """Run every contract rule against an indicator on this data."""
    df = normalize_ohlc(data)
    report = Report(repr(indicator), len(df))

    # 1. structure
    problems = _structure(indicator)

    for status, code, msg in problems:
        report.add(status, "structure", msg, code)

    if not problems:
        report.add("PASS", "structure", "subclasses Indicator, named, series() valid")

    if any(status == "FAIL" for status, _, _ in problems):
        return report

    # 2. runs
    try:
        t0 = time.perf_counter()
        rec = Recording.record(df, [indicator])
        ms = (time.perf_counter() - t0) * 1000 / max(len(df), 1)
    except Exception as e:
        hint = " (bars.* arrays are read-only: copy before modifying)" if "read-only" in str(e) else ""
        report.add("FAIL", "runs", f"{type(e).__name__}: {e}{hint}", "run_failed")
        return report

    report.add("PASS", "runs", f"{len(rec.events)} outputs, {ms:.3f} ms/bar")

    # 3. deterministic
    signature = lambda r: [(e.at, repr(e.out)) for e in r.events]

    if signature(rec) != signature(Recording.record(df, [indicator])):
        report.add("FAIL", "deterministic", "two runs on the same data differ: reset() isn't restoring "
                   "all state (or something random/global is used)", "not_deterministic")
    else:
        report.add("PASS", "deterministic", "identical output on a rerun")

    # 4. no lookahead
    problems = check_lookahead(df, indicator)

    for p in problems[:3]:
        report.add("FAIL", "no lookahead", p, "lookahead")

    if not problems:
        report.add("PASS", "no lookahead", "output at bar k never depends on bars after k")

    # 5. sanity
    unused = set(rec.specs) - {e.out.series for e in rec.events if isinstance(e.out, Value)}

    if not rec.events:
        report.add("WARN", "emits something", "indicator produced no outputs on this data", "silent")

    if unused:
        report.add("WARN", "uses its series", f"declared but never emitted: {sorted(unused)}", "unused_series")

    if ms > SLOW_MS_PER_BAR:
        report.add("WARN", "fast enough", f"{ms:.1f} ms/bar; 100k bars would take {ms * 100:.0f}s "
                   "to precompute (consider a BatchIndicator)", "slow")

    return report
