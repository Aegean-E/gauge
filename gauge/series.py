"""Numeric input parsing and summary statistics for gauge."""

import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List

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
    total = math.fsum(values)
    mean = total / count
    if count % 2:
        median = ordered[count // 2]
    else:
        median = (ordered[count // 2 - 1] + ordered[count // 2]) / 2.0
    variance = math.fsum((value - mean) ** 2 for value in values) / count
    return Summary(
        count=count,
        total=total,
        minimum=ordered[0],
        maximum=ordered[-1],
        mean=mean,
        median=median,
        p90=percentile(values, 0.9),
        stdev=math.sqrt(variance),
    )
