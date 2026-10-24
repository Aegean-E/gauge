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
- **Consequences**: The numbers match the common monitoring conventions and are documented in the README. A consumer expecting a sample standard deviation must adjust it; that alternative is deliberately not a flag in v1.

### ADR-003: Deterministic eight-level rendering with an ASCII twin
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Terminal capabilities, fonts and colour support vary, while fixed output is what makes rendering testable and pipeable. A terminal library would add a dependency for behaviour this tool does not need.
- **Decision**: Sparklines use the eight Unicode blocks `▁▂▃▄▅▆▇█` with half-up rounding and map a flat series to the middle level. `--ascii` swaps in `_.-=+*#@`; bars swap `█`/`│` for `#`/`|`. When standard output's encoding cannot represent the block character, the ASCII twin is selected automatically. There is no colour, cursor movement or terminal-width probing.
- **Consequences**: Golden tests pin every surface and a legacy pipe still produces valid output. Users choose `--width` explicitly and get no colour; the automatic fallback means the default glyphs depend on the output encoding, which is documented.

