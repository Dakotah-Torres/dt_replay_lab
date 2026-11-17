"""finresearch: indicator replay engine, swing hierarchy research, light-theme charting."""
from . import engine
from .checks import check_lookahead
from .contract import Issue, Report, check_contract
from .data import DATA_DIR, load_ohlc, make_test_data, normalize_ohlc
from .indicator import (
    Bars, BatchIndicator, Draw, Indicator, Mark, SeriesSpec, Value,
    box, hline, trend, vline, vspan,
)
from .indicators import RSI, SMA, SwingIndicator
from .player import Player
from .recording import IndicatorError, LookaheadError, Recording
from .swings import (
    INTERMEDIATE, MAJOR, MINOR, Swing, build_hierarchy, detect_minor_swings, promote,
    swings_to_frame,
)
from .visualizer import Visualizer

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
    """Entry point (`finresearch` / `python -m finresearch`): replay demo.

    `finresearch new <name>` writes a ready-to-edit indicator file instead.
    """
    import sys
    if sys.argv[1:2] == ["new"]:
        from .scaffold import main as new_main
        return new_main(sys.argv[2:])
    engine.run(make_test_data(), SwingIndicator(n=2), title="Swing replay")
