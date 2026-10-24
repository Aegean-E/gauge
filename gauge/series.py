"""Numeric input parsing, summary statistics and histogram binning for gauge."""

import math
import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

_SEPARATOR = re.compile(r"[,\s]+")


@dataclass(frozen=True)
class Summary:
    """A series' count, extrema, centre and spread, with a stable JSON shape."""

    count: int
    total: float
    minimum: float
    maximum: float
    mean: float
    median: float
    p90: float
    stdev: float

    def as_dict(self) -> Dict[str, object]:
        """The `stats --json` object: stable keys and raw floating-point values."""
        return {
            "count": self.count,
            "sum": self.total,
            "min": self.minimum,
            "max": self.maximum,
            "mean": self.mean,
            "median": self.median,
            "p90": self.p90,
            "stdev": self.stdev,
        }


@dataclass(frozen=True)
class Histogram:
    """Equal-width bins: `edges` holds one more boundary than `counts` holds counts."""

    edges: Tuple[float, ...]
    counts: Tuple[int, ...]


def parse_numbers(chunks: Iterable[str]) -> List[float]:
    """
    Every finite number in whitespace- and comma-separated text chunks, in order.

    Raises ValueError naming the first token that is not a finite decimal number, or when the
    combined text holds no number at all.
    """
    values: List[float] = []
    for chunk in chunks:
        for token in _SEPARATOR.split(chunk.strip()):
            if not token:
                continue
            try:
                value = float(token)
            except ValueError:
                raise ValueError(f"'{token}' is not a number.") from None
            if not math.isfinite(value):
                raise ValueError(f"'{token}' is not a finite number.")
            values.append(value)
    if not values:
        raise ValueError("no numbers were provided.")
    return values


def percentile(values: List[float], fraction: float) -> float:
    """The nearest-rank percentile: the ceil(fraction * n)-th smallest value."""
    if not values:
        raise ValueError("percentile needs at least one value.")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1].")
    rank = max(1, math.ceil(fraction * len(values)))
    return sorted(values)[rank - 1]


def summarize(values: List[float]) -> Summary:
    """
    The summary of a non-empty finite series.

    The median averages the middle pair for an even count, p90 is nearest-rank and the standard
    deviation is the population form (dividing by n), as ADR-002 records.
    """
    if not values:
        raise ValueError("cannot summarize an empty series.")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("cannot summarize a series with a non-finite value.")
    ordered = sorted(values)
    count = len(values)
    try:
        total = math.fsum(values)
    except OverflowError:
        raise ValueError("the sum exceeds the floating-point range.") from None
    if not math.isfinite(total):
        raise ValueError("the sum exceeds the floating-point range.")
    mean = total / count
    if count % 2:
        median = ordered[count // 2]
    else:
        # Halving before adding keeps a pair of huge same-sign values inside the range.
        median = ordered[count // 2 - 1] / 2.0 + ordered[count // 2] / 2.0
    scale = max(abs(value) for value in values)
    if scale == 0:
        stdev = 0.0
    else:
        # Normalizing by the largest magnitude keeps squares finite for values near 1e308.
        normalized_mean = math.fsum(value / scale for value in values) / count
        variance = math.fsum((value / scale - normalized_mean) ** 2 for value in values) / count
        stdev = min(scale, math.sqrt(variance) * scale)
    return Summary(
        count=count,
        total=total,
        minimum=ordered[0],
        maximum=ordered[-1],
        mean=mean,
        median=median,
        p90=percentile(values, 0.9),
        stdev=stdev,
    )


def build_histogram(values: List[float], bins: int) -> Histogram:
    """
    Equal-width bins over [min, max], right-open except the last, which is closed.

    A flat series is one bin holding every value, and edges are weighted interpolations so a span
    near the float limit cannot overflow. ADR-004 records the contract.
    """
    if not values:
        raise ValueError("cannot bin an empty series.")
    if not 1 <= bins <= 100:
        raise ValueError("bins must be between 1 and 100.")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("cannot bin a series with a non-finite value.")
    low = min(values)
    high = max(values)
    if low == high:
        return Histogram(edges=(low, high), counts=(len(values),))
    edges = tuple(
        math.fsum((low * (1.0 - index / bins), high * (index / bins)))
        for index in range(bins + 1)
    )
    counts = [0] * bins
    for value in values:
        index = bisect_right(edges, value) - 1
        counts[min(bins - 1, max(0, index))] += 1
    return Histogram(edges=edges, counts=tuple(counts))
