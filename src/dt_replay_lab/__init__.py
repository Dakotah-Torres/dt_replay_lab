"""dt_replay_lab: indicator replay engine, swing hierarchy research, light-theme charting."""
from . import engine
from .data import DATA_DIR, load_ohlc, make_test_data, normalize_ohlc
from .engine.checks import check_lookahead
from .engine.contract import Issue, Report, check_contract
from .engine.player import Player
from .indicators import RSI, SMA, SwingIndicator
from .indicators.indicator import (
    Bars, BatchIndicator, Draw, Indicator, Mark, SeriesSpec, Value,
    box, hline, trend, vline, vspan,
)
from .indicators.swings import (
    INTERMEDIATE, MAJOR, MINOR, Swing, build_hierarchy, detect_minor_swings, promote,
    swings_to_frame,
)
from .viz import IndicatorError, LookaheadError, Recording, Visualizer

__all__ = [
    "engine", "check_lookahead", "check_contract", "Report", "Issue", "IndicatorError", "Recording", "Player", "LookaheadError",
    "Indicator", "BatchIndicator", "Bars", "SeriesSpec", "Value", "Mark", "Draw",
    "hline", "vline", "trend", "box", "vspan",
    "SMA", "RSI", "SwingIndicator",
    "DATA_DIR", "load_ohlc", "make_test_data", "normalize_ohlc",
    "Swing", "MINOR", "INTERMEDIATE", "MAJOR",
    "detect_minor_swings", "promote", "build_hierarchy", "swings_to_frame",
    "Visualizer",
    "main",
]


def main() -> None:
    """Entry point (`dt-replay-lab` / `python -m dt_replay_lab`): replay demo.

    `dt-replay-lab new <name>` writes a ready-to-edit indicator file instead.
    """
    import sys
    if sys.argv[1:2] == ["new"]:
        from .cli import main as new_main
        return new_main(sys.argv[2:])
    engine.run(make_test_data(), SwingIndicator(n=2), title="Swing replay")
