"""finresearch: swing hierarchy research + light-theme charting."""
from .data import DATA_DIR, load_ohlc, make_test_data, normalize_ohlc
from .swings import (
    INTERMEDIATE, MAJOR, MINOR, Swing, build_hierarchy, detect_minor_swings, promote,
    swings_to_frame,
)
from .visualizer import Visualizer

__all__ = [
    "DATA_DIR", "load_ohlc", "make_test_data", "normalize_ohlc",
    "Swing", "MINOR", "INTERMEDIATE", "MAJOR",
    "detect_minor_swings", "promote", "build_hierarchy", "swings_to_frame",
    "Visualizer",
    "main",
]


def main() -> None:
    """Entry point (`finresearch` / `python -m finresearch`): swing demo chart."""
    df = load_ohlc(DATA_DIR / "swing_test.csv")
    hierarchy = build_hierarchy(df, n=5)
    print("  ".join(f"level {k}: {len(v)}" for k, v in hierarchy.items()))

    viz = Visualizer(df, title="Swing Lab")
    viz.add_swings([s for level in hierarchy.values() for s in level])
    viz.show()
