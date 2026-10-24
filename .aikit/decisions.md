# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: One stateless text filter with stable text and JSON surfaces
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: A metrics viewer that keeps a daemon or a config file would need lifecycle, locking and persistence rules, while the common job is one pipe: numbers in, a readable shape out.
- **Decision**: `gauge` is one short-lived process with four subcommands (`spark`, `bars`, `stats`, `demo`). It reads exactly one source (arguments, `--file` or standard input), writes only to standard output, and exposes `stats --json` as the machine surface with fixed keys. It has no network access, no configuration and no stored state.
- **Consequences**: The tool composes in pipelines and its behaviour is fully covered by golden tests. There is no live refresh or history; changing a flag or a JSON key is a contract change that needs a new ADR.

### ADR-002: Population spread, nearest-rank p90 and an averaged even median
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Mean, median, p90 and standard deviation each have several defensible definitions; picking one silently per call site would make two reports of the same data disagree.
- **Decision**: The mean is `fsum(values) / n`; the median is the middle value, or the average of the middle pair when `n` is even; p90 is nearest-rank, the `ceil(0.9 * n)`-th smallest value; the standard deviation divides by `n` (population form). NaN and infinity are refused at parse time so no statistic can be undefined.
- **Consequences**: The numbers match the common monitoring conventions and are documented in the README. A consumer expecting a sample standard deviation must adjust it; that alternative is deliberately not a flag in v1. The calculation scales by the largest magnitude so extreme finite values stay finite, and a sum outside the float range is refused rather than shown as infinity.

### ADR-003: Deterministic eight-level rendering with an ASCII twin
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Terminal capabilities, fonts and colour support vary, while fixed output is what makes rendering testable and pipeable. A terminal library would add a dependency for behaviour this tool does not need.
- **Decision**: Sparklines use the eight Unicode blocks `▁▂▃▄▅▆▇█` with half-up rounding and map a flat series to the middle level. `--ascii` swaps in `_.-=+*#@`; bars swap `█`/`│` for `#`/`|`. When standard output's encoding cannot represent the block character, the ASCII twin is selected automatically. There is no colour, cursor movement or terminal-width probing.
- **Consequences**: Golden tests pin every surface and a legacy pipe still produces valid output. Users choose `--width` explicitly and get no colour; the automatic fallback means the default glyphs depend on the output encoding, which is documented.

### ADR-004: Equal-width histogram bins with a closed maximum
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: A histogram adds a distribution surface, but the bin boundaries, edge ownership and flat-series case can each be defined several ways. Leaving them to the renderer would make two runs disagree and the output impossible to pin.
- **Decision**: `hist` splits `[min, max]` into `--bins` equal-width bins (default 10, 1 to 100). A bin is right-open, `[low, high)`, except the last, which is closed, `[low, high]`; a value on an inner edge belongs to the upper bin, and the maximum is clamped into the last bin. A flat series is one bin labelled `[value]`. Every bin is printed, including empty ones; bar length is the count divided by the largest count, rounded half-up, with at least one cell for a non-zero count. Edges are weighted interpolations, `low * (1 - t) + high * t`, so a span near the float limit cannot overflow. Histogram bars use the same Unicode block and ASCII twin as the other surfaces.
- **Consequences**: Bins are deterministic and explainable, and the renderer has a golden contract. Printing every bin makes the output as tall as `--bins`, and very close edges can share the same six-significant-digit label; choosing fewer bins avoids that. This adds a fifth subcommand but leaves ADR-001's stateless-filter architecture unchanged.

### ADR-005: Field and delimiter extraction for structured input
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Tabular files, CSVs, TSVs and application logs contain numeric metrics embedded in specific columns alongside timestamps and labels. Users previously had to pipe through cut, awk, or jq before feeding gauge.
- **Decision**: Add `-f, --field N` (1-indexed, >= 1) and `-d, --delimiter CHAR` to all input-reading commands (spark, bars, hist, stats). When `--field` is specified, each non-empty line is split by `--delimiter` (or whitespace/comma if no delimiter is passed), and the N-th column is parsed as a finite float. A line with fewer than N columns raises an error with the Why/Fix triad. An empty delimiter or `--field < 1` is refused as a CLI usage error (exit 2).
- **Consequences**: gauge directly processes CSVs, TSVs, and delimited logs without external tools. The default behavior when -f and -d are omitted is completely unchanged.

### ADR-006: Extended percentiles on summary statistics
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Monitoring SLAs and tail latencies requires specific percentiles such as p50, p95, and p99. Previously, stats only output p90. G-001 binds both the text table and the stats --json key set as contracts requiring an ADR and golden tests.
- **Decision**: Add `--percentiles` to `stats`, taking a comma- or whitespace-separated list of numbers in (0, 100]. In text mode, the requested percentiles replace the single p90 row in ascending order. In JSON mode, all existing keys (count, sum, min, max, mean, median, p90, stdev) remain fixed, and a `"percentiles"` mapping is added when requested. Percentiles outside (0, 100] are refused with exit 2 and the Why/Fix triad.
- **Consequences**: Existing consumers and automated parsers remain 100% compatible. Callers can inspect arbitrary percentiles on demand.

### ADR-007: Horizontal 5-number box plot with deterministic glyphs and ASCII twin
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: A box plot provides an instant visualization of the 5-number summary (min, Q1, median, Q3, max), revealing central tendency, interquartile spread, and skewness in a single compact graphic.
- **Decision**: Add `box` subcommand. `build_boxplot` computes the 5-number summary using nearest-rank percentiles for Q1 (0.25) and Q3 (0.75) and the averaged even median. `render_box` renders a horizontal ruler across `--width` cells (default 40, minimum 5) using Unicode `├─[═│═]─┤` and ASCII `|-[=|=]-|`, followed by a line listing the 5 numbers. A flat series renders as `[value]`.
- **Consequences**: Adds a sixth subcommand without changing any existing contract. Golden tests pin the rendering across widths and flat series.




