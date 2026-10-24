"""Text renderers: sparklines, signed bar charts and a statistics table."""

import math
from typing import List, Sequence

from gauge.series import Histogram, Summary

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
        sampled.append(math.fsum(value / len(bucket) for value in bucket))
    return sampled


def _ratio(value: float, low: float, high: float) -> float:
    """Where `value` sits in [low, high], scaled when the raw span would overflow."""
    if high == low:
        return 0.5
    span = high - low
    if math.isfinite(span):
        return (value - low) / span
    scale = max(abs(low), abs(high))
    return ((value / scale) - (low / scale)) / ((high / scale) - (low / scale))


def _level(value: float, low: float, high: float, levels: int) -> int:
    """The half-up level of `value` between `low` and `high`; a flat series sits in the middle."""
    if high == low:
        return levels // 2
    scaled = _ratio(value, low, high) * (levels - 1)
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
    scaled = _ratio(value, low, high) * (width - 1)
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


def render_histogram(histogram: Histogram, width: int, ascii_only: bool = False) -> str:
    """One row per bin: a right-open range label, a scaled bar and the count."""
    if not histogram.counts:
        raise ValueError("render_histogram needs at least one bin.")
    if width < 2:
        raise ValueError("render_histogram needs a width of at least 2.")
    block = ASCII_BLOCK if ascii_only else UNICODE_BLOCK
    flat = len(histogram.counts) == 1 and histogram.edges[0] == histogram.edges[-1]
    if flat:
        labels = [f"[{format_number(histogram.edges[0])}]"]
    else:
        labels = []
        last = len(histogram.counts) - 1
        for index in range(len(histogram.counts)):
            low = histogram.edges[index]
            high = histogram.edges[index + 1]
            closing = "]" if index == last else ")"
            labels.append(f"[{format_number(low)}, {format_number(high)}{closing}")
    label_width = max(len(label) for label in labels)
    max_count = max(histogram.counts)
    count_width = len(str(max_count))
    rows = []
    for label, count in zip(labels, histogram.counts):
        length = 0 if max_count == 0 else int(count / max_count * width + 0.5)
        if count > 0:
            length = max(1, length)
        bar = block * length + " " * (width - length)
        rows.append(f"{label:>{label_width}}  {bar}  {count:>{count_width}}")
    return "\n".join(rows)
