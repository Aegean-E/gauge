"""Text renderers: sparklines, signed bar charts and a statistics table."""

from typing import List, Sequence

from gauge.series import Summary

UNICODE_LEVELS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
ASCII_LEVELS = "_.-=+*#@"
UNICODE_BLOCK = "\u2588"
UNICODE_AXIS = "\u2502"
ASCII_BLOCK = "#"
ASCII_AXIS = "|"


def format_number(value: float) -> str:
    """A compact human label for one value, with negative zero folded to zero."""
    if value == 0:
        return "0"
    return f"{value:.6g}"


def resample(values: Sequence[float], width: int) -> List[float]:
    """
    `values` unchanged when it already fits, else `width` bucket averages.

    Buckets are split by proportional index, so a long series keeps its shape without random
    sampling; no value is invented or dropped (ADR-003).
    """
    if width < 1:
        raise ValueError("width must be at least 1.")
    if len(values) <= width:
        return list(values)
    count = len(values)
    sampled = []
    for index in range(width):
        start = index * count // width
        end = max(start + 1, (index + 1) * count // width)
        bucket = values[start:end]
        sampled.append(sum(bucket) / len(bucket))
    return sampled


def _level(value: float, low: float, high: float, levels: int) -> int:
    """The half-up level of `value` between `low` and `high`; a flat series sits in the middle."""
    if high == low:
        return levels // 2
    scaled = (value - low) / (high - low) * (levels - 1)
    return min(levels - 1, max(0, int(scaled + 0.5)))


def sparkline(values: Sequence[float], width: int, ascii_only: bool = False) -> str:
    """One character per value, resampled to `width`; eight levels from lowest to highest."""
    if not values:
        raise ValueError("sparkline needs at least one value.")
    levels = ASCII_LEVELS if ascii_only else UNICODE_LEVELS
    sampled = resample(values, width)
    low = min(sampled)
    high = max(sampled)
    return "".join(levels[_level(value, low, high, len(levels))] for value in sampled)


def _position(value: float, low: float, high: float, width: int) -> int:
    """The half-up column of `value` in a chart of `width` cells."""
    if high == low:
        return width // 2
    scaled = (value - low) / (high - low) * (width - 1)
    return min(width - 1, max(0, int(scaled + 0.5)))


def _bar_row(value: float, low: float, high: float, width: int, zero: int,
             block: str, axis: str) -> str:
    """One bar row with the zero axis kept visible; a tiny non-zero value keeps one block."""
    cells = [" "] * width
    if value > 0:
        start = zero
        end = min(width - 1, max(zero + 1, _position(value, low, high, width)))
        for index in range(start, end + 1):
            cells[index] = block
    elif value < 0:
        end = zero
        start = max(0, min(zero - 1, _position(value, low, high, width)))
        for index in range(start, end + 1):
            cells[index] = block
    cells[zero] = axis
    return "".join(cells).rstrip()


def bar_chart(values: Sequence[float], width: int, ascii_only: bool = False) -> str:
    """One labelled row per value, bars growing from a shared zero axis."""
    if not values:
        raise ValueError("bar_chart needs at least one value.")
    if width < 2:
        raise ValueError("bar_chart needs a width of at least 2.")
    low = min(0.0, min(values))
    high = max(0.0, max(values))
    zero = _position(0.0, low, high, width)
    block = ASCII_BLOCK if ascii_only else UNICODE_BLOCK
    axis = ASCII_AXIS if ascii_only else UNICODE_AXIS
    labels = [format_number(value) for value in values]
    label_width = max(len(label) for label in labels)
    rows = [
        f"{label:>{label_width}}  {_bar_row(value, low, high, width, zero, block, axis)}"
        for value, label in zip(values, labels)
    ]
    return "\n".join(rows)


def stats_table(summary: Summary) -> str:
    """The human statistics block, one aligned `name  value` line per measurement."""
    rows = (
        ("count", str(summary.count)),
        ("sum", format_number(summary.total)),
        ("min", format_number(summary.minimum)),
        ("max", format_number(summary.maximum)),
        ("mean", format_number(summary.mean)),
        ("median", format_number(summary.median)),
        ("p90", format_number(summary.p90)),
        ("stdev", format_number(summary.stdev)),
    )
    label_width = max(len(label) for label, _ in rows)
    return "\n".join(f"{label:<{label_width}}  {text}" for label, text in rows)
