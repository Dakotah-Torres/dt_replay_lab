"""Validator: check every output, and every declaration, before it is accepted."""
import numpy as np

from dt_replay_lab.indicators.indicator import (
    DRAW_ARGS, MARK_POSITIONS, MARK_SHAPES, Draw, Indicator, Mark, Output, SeriesSpec, Value,
)


class LookaheadError(ValueError):
    """An indicator emitted something about a bar it had not seen yet."""


class IndicatorError(RuntimeError):
    """An indicator crashed or broke the output rules."""


def source(ind: Indicator) -> str:
    """The name used for an indicator in errors and summaries."""
    return ind.name or type(ind).__name__


def collect_specs(indicators: list[Indicator]) -> dict[str, SeriesSpec]:
    """All declared series by name; names must be unique."""
    specs: dict[str, SeriesSpec] = {}

    for ind in indicators:
        for s in ind.series():
            if s.name in specs:
                raise ValueError(f"duplicate series name {s.name!r}; series names must be unique")

            specs[s.name] = s

    return specs


def check_data_kind(feed, indicators: list[Indicator]) -> None:
    """Hook: an indicator that declares a data_kind must match the feed's."""
    for ind in indicators:
        if ind.data_kind is not None and ind.data_kind != getattr(feed, "data_kind", None):
            raise IndicatorError(f"{source(ind)} consumes {ind.data_kind}, "
                                 f"but the feed carries {getattr(feed, 'data_kind', None)}")


def output_kind(out: Output) -> str:
    """Hook: the output type checked against Indicator.outputs (swap for your enum)."""
    return out.kind if isinstance(out, Draw) else type(out).__name__.lower()


def as_outputs(result):
    """on_bar may return None, one output, or an iterable of outputs."""
    if result is None:
        return ()

    if isinstance(result, (Value, Mark, Draw)):
        return (result,)

    return result


def validate_output(at: int, out: Output, specs: dict, n: int, src: str, allowed: tuple = ()) -> None:
    """Raise if an output is malformed, undeclared, or refers to a future bar."""
    if not 0 <= at < n:
        raise ValueError(f"{src}: emitted at bar {at}, outside 0..{n - 1}")

    if allowed and output_kind(out) not in allowed:
        raise IndicatorError(f"{src}: emitted {output_kind(out)!r}, but only declared {allowed}")

    if isinstance(out, Value):
        if out.series not in specs:
            raise IndicatorError(f"{src}: Value for series {out.series!r}, which series() did not "
                                 f"declare (declared: {sorted(specs) or 'none'})")

        if not np.isfinite(out.value):
            raise IndicatorError(f"{src}: Value for {out.series!r} at bar {at} is {out.value}; "
                                 "skip the bar instead of emitting NaN/inf")

        idxs = [at if out.index is None else out.index]

    elif isinstance(out, Mark):
        if out.position not in MARK_POSITIONS:
            raise IndicatorError(f"{src}: Mark position {out.position!r}; use one of {MARK_POSITIONS}")

        if out.shape not in MARK_SHAPES:
            raise IndicatorError(f"{src}: Mark shape {out.shape!r}; use one of {MARK_SHAPES}")

        idxs = [out.index]

    elif isinstance(out, Draw):
        if out.kind not in DRAW_ARGS:
            raise IndicatorError(f"{src}: unknown Draw kind {out.kind!r}; use one of {sorted(DRAW_ARGS)}")

        required, optional = DRAW_ARGS[out.kind]
        missing, extra = required - out.args.keys(), out.args.keys() - required - optional

        if missing or extra:
            raise IndicatorError(f"{src}: Draw {out.kind!r} missing {sorted(missing)}, "
                                 f"unexpected {sorted(extra)}")

        idxs = out.indices()

    else:
        raise IndicatorError(f"{src}: emitted {out!r}; outputs must be Value, Mark or Draw")

    for idx in idxs:
        if idx > at:
            raise LookaheadError(f"{src}: output at bar {at} refers to future bar {idx}")

        if idx < 0:
            raise ValueError(f"{src}: negative bar index {idx}")
