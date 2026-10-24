"""The gauge command line: read one numeric source, then render or summarize it."""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from gauge import __version__
from gauge.render import (
    UNICODE_BLOCK,
    bar_chart,
    render_box,
    render_histogram,
    sparkline,
    stats_table,
)
from gauge.series import build_boxplot, build_histogram, parse_numbers, summarize


class InputError(Exception):
    """A request gauge cannot carry out, carrying the Why/Fix remediation triad."""

    def __init__(self, message: str, why: str, fix: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.why = why
        self.fix = fix
        self.exit_code = exit_code


def _checked_field(field: Optional[int]) -> Optional[int]:
    """The requested field index, bounded to positive integers."""
    if field is None:
        return None
    if field < 1:
        raise InputError(
            f"--field must be 1 or greater, got {field}.",
            "column indices are 1-based, like cut and awk.",
            "choose a positive field index, for example -f 1 or --field 2.",
        )
    return field


def _checked_delimiter(delimiter: Optional[str]) -> Optional[str]:
    """The requested delimiter, which cannot be empty."""
    if delimiter is None:
        return None
    if not delimiter:
        raise InputError(
            "--delimiter cannot be empty.",
            "an empty delimiter cannot split input into columns.",
            "provide a non-empty delimiter character, for example -d , or --delimiter ':'",
        )
    return delimiter


def _parse_or_raise(chunks, field: Optional[int] = None,
                    delimiter: Optional[str] = None) -> List[float]:
    """Parse chunks, translating a series error into the command-line triad."""
    try:
        return parse_numbers(chunks, field=field, delimiter=delimiter)
    except ValueError as exc:
        raise InputError(
            str(exc),
            "gauge only accepts finite decimal numbers, and skipping text silently would hide "
            "a bad input row.",
            "check that the input and field selection match numeric data, then run the command again.",
        ) from None


def _read_file(path_text: str, field: Optional[int] = None,
               delimiter: Optional[str] = None) -> List[float]:
    """Numbers from one UTF-8 file, with a read failure reported as a runtime error."""
    path = Path(path_text)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return _parse_or_raise(handle, field=field, delimiter=delimiter)
    except (OSError, UnicodeError) as exc:
        detail = getattr(exc, "strerror", None) or str(exc)
        raise InputError(
            f"cannot read '{path}': {detail}.",
            "the file was named as the only input, and gauge will not silently draw an empty "
            "chart.",
            "check that the path exists and is readable, then run the command again.",
            exit_code=1,
        ) from None


def _read_values(args: argparse.Namespace) -> List[float]:
    """The series from arguments, `--file` or standard input, in that order of precedence."""
    field = _checked_field(getattr(args, "field", None))
    delimiter = _checked_delimiter(getattr(args, "delimiter", None))
    if args.values and args.file:
        raise InputError(
            "both positional numbers and --file were given.",
            "two sources could silently disagree about which series is drawn.",
            "keep the positional numbers or --file, not both.",
        )
    if args.values:
        return _parse_or_raise(args.values, field=field, delimiter=delimiter)
    if args.file:
        return _read_file(args.file, field=field, delimiter=delimiter)
    if sys.stdin is None or sys.stdin.isatty():
        raise InputError(
            "no numbers to read.",
            "an interactive terminal supplies no piped data, and gauge never prompts.",
            "pass numbers as arguments, use --file PATH, or pipe numbers on standard input.",
        )
    return _parse_or_raise(sys.stdin, field=field, delimiter=delimiter)


def _checked_width(width: Optional[int], default: int) -> int:
    """The requested chart width, bounded so every row stays renderable."""
    value = default if width is None else width
    if not 2 <= value <= 1000:
        raise InputError(
            f"--width must be between 2 and 1000, got {value}.",
            "a chart narrower than two cells cannot show a range or a zero axis, and a huge "
            "one is never a terminal.",
            "choose a width from 2 to 1000, for example --width 40.",
        )
    return value


def _checked_bins(bins: Optional[int]) -> int:
    """The requested bin count, bounded so every row stays readable."""
    value = 10 if bins is None else bins
    if not 1 <= value <= 100:
        raise InputError(
            f"--bins must be between 1 and 100, got {value}.",
            "a histogram needs at least one bin, and more than 100 bins is noise in a terminal.",
            "choose a bin count from 1 to 100, for example --bins 10.",
        )
    return value


def _checked_percentiles(raw: Optional[str]) -> Optional[List[float]]:
    """Parse and validate comma- or whitespace-separated percentiles in (0, 100]."""
    if raw is None:
        return None
    tokens = [t.strip() for t in re.split(r"[,\s]+", raw.strip()) if t.strip()]
    if not tokens:
        raise InputError(
            "--percentiles cannot be empty.",
            "at least one percentile value is required when the flag is given.",
            "provide percentages between 0 and 100, for example --percentiles 50,90,95,99.",
        )
    percentiles: List[float] = []
    for token in tokens:
        try:
            val = float(token)
        except ValueError:
            raise InputError(
                f"'{token}' is not a valid percentile number.",
                "percentiles must be numbers between 0 and 100.",
                "provide numbers between 0 and 100, for example --percentiles 50,90,95,99.",
            ) from None
        if not 0.0 < val <= 100.0:
            raise InputError(
                f"percentile {token} must be between 0 and 100 (exclusive of 0).",
                "percentiles outside (0, 100] are undefined.",
                "choose values between 0 and 100, for example --percentiles 50,95,99.",
            )
        percentiles.append(val)
    return percentiles


def _stdout_supports_unicode() -> bool:
    """Whether the output encoding can carry the block character, so a legacy pipe still works."""
    encoding = getattr(sys.stdout, "encoding", None)
    if not encoding:
        return True
    try:
        UNICODE_BLOCK.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _use_ascii(forced: bool) -> bool:
    """`--ascii`, or automatically when the output encoding cannot represent the blocks."""
    return forced or not _stdout_supports_unicode()


def _spark(args: argparse.Namespace) -> int:
    """Print one sparkline, optionally labelled."""
    values = _read_values(args)
    line = sparkline(values, _checked_width(args.width, 60), _use_ascii(args.ascii))
    print(f"{args.label} {line}" if args.label else line)
    return 0


def _bars(args: argparse.Namespace) -> int:
    """Print one labelled row per value with a signed zero axis."""
    values = _read_values(args)
    print(bar_chart(values, _checked_width(args.width, 40), _use_ascii(args.ascii)))
    return 0


def _hist(args: argparse.Namespace) -> int:
    """Print one row per equal-width bin, with the last bin closed."""
    values = _read_values(args)
    histogram = build_histogram(values, _checked_bins(args.bins))
    print(render_histogram(histogram, _checked_width(args.width, 40), _use_ascii(args.ascii)))
    return 0


def _box(args: argparse.Namespace) -> int:
    """Print a horizontal 5-number box plot and its summary row."""
    values = _read_values(args)
    boxplot = build_boxplot(values)
    width = _checked_width(args.width, 40)
    if width < 5:
        raise InputError(
            f"--width must be between 5 and 1000 for box, got {width}.",
            "a box plot needs at least five cells to display whiskers and box boundaries.",
            "choose a width from 5 to 1000, for example --width 40.",
        )
    print(render_box(boxplot, width, _use_ascii(args.ascii)))
    return 0


def _stats(args: argparse.Namespace) -> int:
    """Print the summary table, or its stable JSON object."""
    percentiles = _checked_percentiles(getattr(args, "percentiles", None))
    try:
        summary = summarize(_read_values(args), percentiles=percentiles)
    except ValueError as exc:
        raise InputError(
            str(exc),
            "gauge prints only finite statistics, so a sum outside the float range is refused "
            "instead of shown as infinity.",
            "summarize fewer or smaller values, or pre-scale the series before piping it.",
        ) from None
    if args.json:
        print(json.dumps(summary.as_dict(), indent=2, allow_nan=False))
    else:
        print(stats_table(summary))
    return 0


def _demo(args: argparse.Namespace) -> int:
    """A deterministic 24-point trace that shows both surfaces without any input."""
    values = [
        round(40.0 + 18.0 * math.sin(index / 3.0) + 6.0 * math.cos(index / 1.7), 2)
        for index in range(24)
    ]
    print("gauge demo: a deterministic 24-point latency trace (milliseconds)")
    print(sparkline(values, width=48, ascii_only=_use_ascii(False)))
    print()
    print(stats_table(summarize(values)))
    return 0


def _add_input_options(parser: argparse.ArgumentParser) -> None:
    """The source arguments every reading subcommand shares."""
    parser.add_argument("values", nargs="*", metavar="NUMBER",
                        help="numbers to read; omit to use --file or standard input")
    parser.add_argument("--file", metavar="PATH",
                        help="read numbers from PATH instead of arguments or standard input")
    parser.add_argument("-f", "--field", type=int, default=None, metavar="N",
                        help="extract the N-th column (1-indexed)")
    parser.add_argument("-d", "--delimiter", default=None, metavar="CHAR",
                        help="column delimiter (default: whitespace and commas)")


def build_parser() -> argparse.ArgumentParser:
    """The CLI grammar: four reading surfaces plus a self-contained demo."""
    parser = argparse.ArgumentParser(
        prog="gauge",
        description="Turn a numeric series into a sparkline, signed bars, a histogram or "
                    "summary statistics.",
    )
    parser.add_argument("--version", action="version", version=f"gauge {__version__}")
    commands = parser.add_subparsers(dest="command", required=True,
                                     metavar="{spark,bars,hist,box,stats,demo}")

    spark = commands.add_parser("spark", help="draw a sparkline of the series")
    _add_input_options(spark)
    spark.add_argument("--width", type=int, default=None,
                       help="chart width in cells, 2-1000 (default: 60)")
    spark.add_argument("--ascii", action="store_true",
                       help="use the ASCII twin instead of Unicode blocks")
    spark.add_argument("--label", metavar="TEXT", default="",
                       help="prefix the sparkline with TEXT")

    bars = commands.add_parser("bars", help="draw one signed bar per value")
    _add_input_options(bars)
    bars.add_argument("--width", type=int, default=None,
                      help="chart width in cells, 2-1000 (default: 40)")
    bars.add_argument("--ascii", action="store_true",
                      help="use the ASCII twin instead of Unicode blocks")

    hist = commands.add_parser("hist", help="draw an equal-width histogram of the series")
    _add_input_options(hist)
    hist.add_argument("--bins", type=int, default=None,
                      help="number of equal-width bins, 1-100 (default: 10)")
    hist.add_argument("--width", type=int, default=None,
                      help="bar width in cells, 2-1000 (default: 40)")
    hist.add_argument("--ascii", action="store_true",
                      help="use the ASCII twin instead of Unicode blocks")

    box = commands.add_parser("box", help="draw a horizontal 5-number box plot")
    _add_input_options(box)
    box.add_argument("--width", type=int, default=None,
                     help="chart width in cells, 5-1000 (default: 40)")
    box.add_argument("--ascii", action="store_true",
                     help="use the ASCII twin instead of Unicode glyphs")

    stats = commands.add_parser("stats", help="print count, extrema, mean, median, p90 and stdev")
    _add_input_options(stats)
    stats.add_argument("--json", action="store_true", help="print the summary as JSON")
    stats.add_argument("--percentiles", metavar="P1,P2...", default=None,
                       help="comma-separated list of percentiles (e.g. 50,95,99)")

    commands.add_parser("demo", help="show a deterministic sample trace")
    return parser


def run(args: argparse.Namespace) -> int:
    """Dispatch one parsed command through the registry."""
    return COMMANDS[args.command](args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse the command line, run it, and print the remediation triad on a refusal."""
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(f"Why: {exc.why}", file=sys.stderr)
        print(f"Fix: {exc.fix}", file=sys.stderr)
        return exc.exit_code
    except BrokenPipeError:
        return 0


COMMANDS = {
    "spark": _spark,
    "bars": _bars,
    "hist": _hist,
    "box": _box,
    "stats": _stats,
    "demo": _demo,
}
