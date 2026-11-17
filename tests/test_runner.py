import unittest

import numpy as np
import pandas as pd

from dt_replay_lab import (
    Feed, RSI, SMA, BatchIndicator, Indicator, IndicatorError, LivePlayer, Mark, Recording, RunType,
    SeriesSpec, SwingIndicator, Value, hline, live_run, make_test_data, normalize_ohlc, pre_run,
)
from dt_replay_lab.viz.recording import marker_dicts

DF = normalize_ohlc(make_test_data(400))


def streaming():
    return [SMA(20), RSI(14), SwingIndicator(n=5)]


class Counting(Indicator):
    name = "count"

    def reset(self):
        self.calls = 0

    def on_bar(self, bars):
        self.calls += 1


class Batch(BatchIndicator):
    name = "batch"

    def series(self):
        return [SeriesSpec("batch")]

    def compute(self, df):
        return [(i, Value("batch", v)) for i, v in enumerate(df["close"].rolling(5).mean())
                if not np.isnan(v)]


class TestRunType(unittest.TestCase):
    def test_choices(self):
        self.assertEqual({r.value for r in RunType}, {"prerun", "liverun"})
        self.assertIs(RunType("liverun"), RunType.LIVERUN)


class TestLiveRun(unittest.TestCase):
    def test_bars_arrive_in_order_and_events_belong_to_their_bar(self):
        seen = []
        for i, events in live_run(Feed(DF), streaming()):
            seen.append(i)
            self.assertTrue(all(e.at == i for e in events))
        self.assertEqual(seen, list(range(len(DF))))

    def test_is_lazy(self):
        ind = Counting()
        stream = live_run(Feed(DF), [ind])
        for _ in range(7):
            next(stream)
        self.assertEqual(ind.calls, 7)          # nothing computed ahead of what was pulled

    def test_rejects_batch_indicators(self):
        with self.assertRaises(TypeError):
            live_run(Feed(DF), [SMA(5), Batch()])

    def test_pre_run_is_live_run_drained(self):
        live = [e for _, events in live_run(Feed(DF), streaming()) for e in events]
        self.assertEqual(pre_run(DF, streaming()), live)

    def test_pre_run_still_supports_batch(self):
        events = pre_run(DF, [Batch(), SMA(10)])
        self.assertEqual([e.at for e in events], sorted(e.at for e in events))
        self.assertIn("batch", {e.source for e in events})


class TestLivePlayerState(unittest.TestCase):
    """What the live window holds at bar k must equal what the replay shows at bar k."""

    def test_live_state_matches_recording_at_every_checkpoint(self):
        rec = Recording.record(DF, streaming())
        live = LivePlayer(DF, streaming())          # no window is opened
        for k in range(len(DF)):
            i, events = live._pull()
            live._absorb(i, events)
            if k in (25, 100, 237, len(DF) - 1):
                self.assertEqual(marker_dicts(live._marks.values(), live._times), rec.markers_at(k))
                for name, frame in rec.lines_at(k).items():
                    pd.testing.assert_frame_equal(live._frame(name), frame)
        self.assertIsNone(live._pull())
        self.assertTrue(live.finished)

    def test_drawings_replace_by_key(self):
        class Level(Indicator):
            name = "lvl"
            def on_bar(self, bars):
                if bars.i in (3, 8):
                    yield hline(float(bars.close[-1]), key="level")
        live = LivePlayer(DF, [Level()])
        for _ in range(10):
            live._absorb(*live._pull())
        self.assertEqual(list(live._pending_draws), ["level"])     # the newer drawing replaced the older


class TestSeams(unittest.TestCase):
    def test_any_feed_can_be_injected(self):
        class Countdown:                       # anything with __len__, next() and data_kind
            data_kind = None

            def __init__(self):
                self.left = 3

            def __len__(self):
                return 3

            def next(self):
                if self.left == 0:
                    return None

                self.left -= 1
                return self.left

        class Echo(Indicator):
            name = "echo"

            def series(self):
                return [SeriesSpec("echo")]

            def on_bar(self, view):
                yield Value("echo", float(view))

        got = [[e.out.value for e in events] for _, events in live_run(Countdown(), [Echo()])]
        self.assertEqual(got, [[2.0], [1.0], [0.0]])

    def test_data_kind_must_match_the_feed(self):
        class WantsTicks(Indicator):
            name, data_kind = "ticks", "tick"

            def on_bar(self, view):
                return None

        with self.assertRaises(IndicatorError):
            live_run(Feed(DF), [WantsTicks()])

    def test_declared_outputs_are_enforced(self):
        class ValuesOnly(Indicator):
            name, outputs = "values only", ("value",)

            def on_bar(self, bars):
                yield Mark(bars.i, "above")

        with self.assertRaises(IndicatorError):
            pre_run(DF, [ValuesOnly()])


if __name__ == "__main__":
    unittest.main()
