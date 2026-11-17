"""dt_replay_lab: indicator replay engine, swing research and light-theme charting."""
from dt_replay_lab import engine
from dt_replay_lab.data import DATA_DIR, load_ohlc, make_test_data, normalize_ohlc
from dt_replay_lab.engine.checks import check_lookahead
from dt_replay_lab.engine.contract import Issue, Report, check_contract
from dt_replay_lab.engine.feed import Feed
from dt_replay_lab.engine.player import LivePlayer, Player
from dt_replay_lab.engine.runner import RunType, live_run, pre_run
from dt_replay_lab.engine.validator import IndicatorError, LookaheadError
from dt_replay_lab.indicators import RSI, SMA, SwingIndicator
from dt_replay_lab.indicators.indicator import (
    Bars, BatchIndicator, Draw, Indicator, Mark, SeriesSpec, Value, box, hline, trend, vline, vspan,
)
from dt_replay_lab.indicators.swings import (
    INTERMEDIATE, MAJOR, MINOR, Swing, build_hierarchy, detect_minor_swings, promote, swings_to_frame,
)
from dt_replay_lab.viz import Recording, Visualizer

__all__ = [
    "engine", "RunType", "Feed", "live_run", "pre_run", "Player", "LivePlayer", "Recording",
    "check_contract", "check_lookahead", "Report", "Issue", "IndicatorError", "LookaheadError",
    "Indicator", "BatchIndicator", "Bars", "SeriesSpec", "Value", "Mark", "Draw",
    "hline", "vline", "trend", "box", "vspan",
    "SMA", "RSI", "SwingIndicator",
    "DATA_DIR", "load_ohlc", "make_test_data", "normalize_ohlc",
    "Swing", "MINOR", "INTERMEDIATE", "MAJOR", "detect_minor_swings", "promote", "build_hierarchy",
    "swings_to_frame",
    "Visualizer",
    "main",
]


def main() -> None:
    """`dt-replay-lab` runs the demo; `dt-replay-lab new <name>` scaffolds an indicator."""
    import sys

    if sys.argv[1:2] == ["new"]:
        from dt_replay_lab.cli import main as new_main
        return new_main(sys.argv[2:])

    engine.run(make_test_data(), SwingIndicator(n=2), title="Swing replay")
