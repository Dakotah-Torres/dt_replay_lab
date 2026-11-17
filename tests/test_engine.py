import unittest

import numpy as np
import pandas as pd

from finresearch import (
    SMA, RSI, BatchIndicator, LookaheadError, Mark, Recording, SeriesSpec, SwingIndicator, Value,
    Indicator, IndicatorError, Draw, build_hierarchy, check_contract, check_lookahead, hline,
    make_test_data, normalize_ohlc,
)
from finresearch.cli.scaffold import new_indicator

DF = normalize_ohlc(make_test_data(600))


class CheatingSMA(BatchIndicator):
    """Centered average: uses future bars but claims to know them immediately."""
    name = "cheat"

    def series(self):
        return [SeriesSpec("cheat")]

    def compute(self, df):
        c = df["close"].rolling(11, center=True).mean()
        return [(i, Value("cheat", v)) for i, v in enumerate(c) if not np.isnan(v)]


class HonestSMA(BatchIndicator):
    name = "honest"

    def series(self):
        return [SeriesSpec("honest")]

    def compute(self, df):
        c = df["close"].rolling(11).mean()
        return [(i, Value("honest", v)) for i, v in enumerate(c) if not np.isnan(v)]


class TestSwings(unittest.TestCase):
    def test_streaming_matches_batch(self):
        rec = Recording.record(DF, [SwingIndicator(n=5)])
        batch = build_hierarchy(DF, n=5)
        for level, swings in batch.items():
            got = {(e.out.index, e.out.position, e.at) for e in rec.events
                   if isinstance(e.out, Mark) and e.out.rank == level}
            want = {(s.index, "above" if s.kind == "high" else "below", s.confirmed_at) for s in swings}
            self.assertEqual(got, want, f"level {level}")

    def test_rerun_is_identical(self):
        ind = SwingIndicator(n=5)
        a = Recording.record(DF, [ind]).events
        b = Recording.record(DF, [ind]).events
        self.assertEqual(a, b)


class TestReplayState(unittest.TestCase):
    def test_state_at_cursor_equals_truncated_run(self):
        """Rewinding to bar k must look exactly like having only ever seen bars 0..k."""
        inds = lambda: [SMA(20), RSI(14), SwingIndicator(n=5)]
        full = Recording.record(DF, inds())
        for k in (40, 123, 300, 599):
            part = Recording.record(DF.iloc[:k + 1], inds())
            self.assertEqual(full.markers_at(k), part.markers_at(k))
            for name, frame in part.lines_at(k).items():
                pd.testing.assert_frame_equal(full.lines_at(k)[name], frame)

    def test_promotion_replaces_marker(self):
        rec = Recording.record(DF, [SwingIndicator(n=5)])
        promoted = next(e.out for e in rec.events if isinstance(e.out, Mark) and e.out.rank == 2)
        at = min(e.at for e in rec.events if isinstance(e.out, Mark) and e.out.rank == 2
                 and e.out.index == promoted.index)
        text = lambda cur: [m["text"] for m in rec.markers_at(cur)
                            if m["time"] == pd.Timestamp(DF["time"].iat[promoted.index])]
        self.assertIn(text(at - 1)[0], ("STH", "STL"))
        self.assertIn(text(at)[0], ("ITH", "ITL"))

    def test_draw_key_replaces(self):
        class D(BatchIndicator):
            def compute(self, df):
                return [(10, hline(100, key="lvl")), (20, hline(101, key="lvl"))]
        rec = Recording.record(DF, [D()])
        self.assertEqual(rec.drawings_at(15)["lvl"][1].args["price"], 100)
        self.assertEqual(rec.drawings_at(25)["lvl"][1].args["price"], 101)
        self.assertEqual(len(rec.drawings_at(25)), 1)


class TestLookahead(unittest.TestCase):
    def test_future_reference_rejected(self):
        class Bad(BatchIndicator):
            def compute(self, df):
                return [(10, Mark(11, "above"))]
        with self.assertRaises(LookaheadError):
            Recording.record(DF, [Bad()])

    def test_checker_catches_cheater(self):
        self.assertTrue(check_lookahead(DF, CheatingSMA()))

    def test_checker_passes_honest_and_streaming(self):
        self.assertEqual(check_lookahead(DF, HonestSMA()), [])
        self.assertEqual(check_lookahead(DF, SwingIndicator(n=5)), [])
        self.assertEqual(check_lookahead(DF, RSI(14)), [])



def codes(report):
    return {i.code for i in report.issues}


class TestContract(unittest.TestCase):
    def test_shipped_indicators_pass(self):
        for ind in (SMA(20), RSI(14), SwingIndicator(n=5), HonestSMA()):
            self.assertTrue(check_contract(DF, ind).ok, repr(ind))

    def test_missing_on_bar(self):
        class NoLogic(Indicator):
            name = "x"
        self.assertIn("no_on_bar", codes(check_contract(DF, NoLogic())))

    def test_undeclared_series(self):
        class Bad(Indicator):
            name = "bad"
            def on_bar(self, bars):
                yield Value("oops", 1.0)
        r = check_contract(DF, Bad())
        self.assertIn("run_failed", codes(r))
        self.assertIn("did not declare", str(r))

    def test_crash_names_the_bar(self):
        class Crash(Indicator):
            name = "crash"
            def on_bar(self, bars):
                if bars.i == 7:
                    raise ZeroDivisionError("boom")
        with self.assertRaisesRegex(IndicatorError, "bar 7"):
            Recording.record(DF, [Crash()])

    def test_nan_rejected(self):
        class Nan(Indicator):
            name = "nan"
            def series(self):
                return [SeriesSpec("nan")]
            def on_bar(self, bars):
                yield Value("nan", float("nan"))
        self.assertIn("run_failed", codes(check_contract(DF, Nan())))

    def test_bad_mark_and_draw(self):
        class BadMark(Indicator):
            name = "m"
            def on_bar(self, bars):
                yield Mark(bars.i, "above", shape="star")
        class BadDraw(Indicator):
            name = "d"
            def on_bar(self, bars):
                yield Draw("horizontal_line", {})
        self.assertIn("run_failed", codes(check_contract(DF, BadMark())))
        self.assertIn("run_failed", codes(check_contract(DF, BadDraw())))

    def test_forgot_reset_is_nondeterministic(self):
        class Leaky(Indicator):
            name = "leaky"
            def __init__(self):
                self.count = 0                  # never reset
            def series(self):
                return [SeriesSpec("leaky")]
            def on_bar(self, bars):
                self.count += 1
                yield Value("leaky", float(self.count))
        self.assertIn("not_deterministic", codes(check_contract(DF, Leaky())))

    def test_cheater_fails_lookahead(self):
        self.assertIn("lookahead", codes(check_contract(DF, CheatingSMA())))

    def test_readonly_bars(self):
        class Writer(Indicator):
            name = "w"
            def on_bar(self, bars):
                bars.close[-1] = 0.0
        r = check_contract(DF, Writer())
        self.assertIn("read-only", str(r))

    def test_duplicate_series_names(self):
        with self.assertRaises(ValueError):
            Recording.record(DF, [SMA(20), SMA(20)])


class TestScaffold(unittest.TestCase):
    def test_generated_file_is_valid_and_passes(self):
        import importlib.util, pathlib, tempfile
        with tempfile.TemporaryDirectory() as d:
            path = new_indicator("my cool idea", d)
            self.assertEqual(path.name, "my_cool_idea.py")
            spec = importlib.util.spec_from_file_location("gen", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertTrue(check_contract(DF, mod.MyCoolIdea()).ok)
            with self.assertRaises(SystemExit):          # never overwrites
                new_indicator("my cool idea", d)


if __name__ == "__main__":
    unittest.main()
