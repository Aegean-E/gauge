"""Text renderers: sparklines, signed bar charts and a statistics table."""

import math
from typing import List, Sequence, Tuple

from gauge.series import BoxPlot, Histogram, Summary

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


def _edge_texts(low: float, high: float) -> Tuple[str, str]:
    """Labels for one bin's edges, adding digits only when six would collapse them."""
    for digits in (6, 9, 12, 15, 17):
        if digits == 6:
            left, right = format_number(low), format_number(high)
        else:
            left, right = f"{low:.{digits}g}", f"{high:.{digits}g}"
        if left != right:
            break
    return left, right


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
    rows = [
        ("count", str(summary.count)),
        ("sum", format_number(summary.total)),
        ("min", format_number(summary.minimum)),
        ("max", format_number(summary.maximum)),
        ("mean", format_number(summary.mean)),
        ("median", format_number(summary.median)),
    ]
    if summary.custom_percentiles is not None:
        for key, val in summary.custom_percentiles.items():
            label = key if key.startswith("p") else f"p{key}"
            rows.append((label, format_number(val)))
    else:
        rows.append(("p90", format_number(summary.p90)))
    rows.append(("stdev", format_number(summary.stdev)))
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
            low_text, high_text = _edge_texts(low, high)
            labels.append(f"[{low_text}, {high_text}{closing}")
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


def render_box(boxplot: BoxPlot, width: int = 40, ascii_only: bool = False) -> str:
    """Render a horizontal 5-number box plot and its summary row (ADR-007)."""
    if width < 5:
        raise ValueError("render_box needs a width of at least 5.")
    if boxplot.minimum == boxplot.maximum:
        ruler = f"[{format_number(boxplot.minimum)}]"
        summary_line = f"min: {format_number(boxplot.minimum)}  max: {format_number(boxplot.maximum)}"
        return f"{ruler}\n{summary_line}"

    whisker_left = "|" if ascii_only else "\u251c"   # ├
    whisker_right = "|" if ascii_only else "\u2524"  # ┤
    whisker_line = "-" if ascii_only else "\u2500"   # ─
    box_left = "["
    box_right = "]"
    box_fill = "=" if ascii_only else "\u2550"       # ═
    median_char = "|" if ascii_only else "\u2502"    # │

    low = boxplot.minimum
    high = boxplot.maximum

    pos_min = _position(low, low, high, width)
    pos_q1 = _position(boxplot.q1, low, high, width)
    pos_med = _position(boxplot.median, low, high, width)
    pos_q3 = _position(boxplot.q3, low, high, width)
    pos_max = _position(high, low, high, width)

    # Rounding can land the median on an edge; give it a cell inside the box when there is room.
    if pos_med == pos_q1 and pos_q1 > pos_min:
        pos_q1 -= 1
    if pos_med == pos_q3 and pos_q3 < pos_max:
        pos_q3 += 1
    # A collapsed box still needs two cells so both brackets survive.
    if pos_q3 == pos_q1:
        if pos_q3 < pos_max:
            pos_q3 += 1
        elif pos_q1 > pos_min:
            pos_q1 -= 1

    cells = [" "] * width

    # Whiskers
    for idx in range(pos_min, pos_q1):
        cells[idx] = whisker_line
    for idx in range(pos_q3 + 1, pos_max + 1):
        cells[idx] = whisker_line
    cells[pos_min] = whisker_left
    cells[pos_max] = whisker_right

    # Box body
    for idx in range(pos_q1, pos_q3 + 1):
        cells[idx] = box_fill

    # The brackets are structural, so they win any residual collision with the median.
    cells[pos_med] = median_char
    cells[pos_q1] = box_left
    cells[pos_q3] = box_right

    ruler = "".join(cells)
    summary_line = (
        f"min: {format_number(boxplot.minimum)}  "
        f"q1: {format_number(boxplot.q1)}  "
        f"med: {format_number(boxplot.median)}  "
        f"q3: {format_number(boxplot.q3)}  "
        f"max: {format_number(boxplot.maximum)}"
    )
    return f"{ruler}\n{summary_line}"
