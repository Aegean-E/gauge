# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `10`
- **Total Classes**: `12`
- **Total Top-Level Functions**: `32`
- **Total Class Methods**: `55`
- **Total Source Lines**: `1035`

---

## 📦 Modules & Exported Symbols

### [`gauge/__init__.py`](gauge/__init__.py)
> *Gauge: a zero-dependency terminal ruler for numeric series.*

**Size**: `3` lines (`89` bytes)

---

### [`gauge/__main__.py`](gauge/__main__.py)
> *Allow `python -m gauge` as the command-line entry point.*

**Size**: `8` lines (`152` bytes)

---

### [`gauge/cli.py`](gauge/cli.py)
> *The gauge command line: read one numeric source, then render or summarize it.*

**Size**: `215` lines (`8005` bytes)

**Classes:**
- `class InputError` - *A request gauge cannot carry out, carrying the Why/Fix remediation triad.*
  - Method `.__init__(message, why, fix, exit_code)`

**Functions:**
- `def _parse_or_raise(chunks)` - *Parse chunks, translating a series error into the command-line triad.*
- `def _read_file(path_text)` - *Numbers from one UTF-8 file, with a read failure reported as a runtime error.*
- `def _read_values(args)` - *The series from arguments, `--file` or standard input, in that order of precedence.*
- `def _checked_width(width, default)` - *The requested chart width, bounded so every row stays renderable.*
- `def _stdout_supports_unicode()` - *Whether the output encoding can carry the block character, so a legacy pipe still works.*
- `def _use_ascii(forced)` - *`--ascii`, or automatically when the output encoding cannot represent the blocks.*
- `def _spark(args)` - *Print one sparkline, optionally labelled.*
- `def _bars(args)` - *Print one labelled row per value with a signed zero axis.*
- `def _stats(args)` - *Print the summary table, or its stable JSON object.*
- `def _demo(args)` - *A deterministic 24-point trace that shows both surfaces without any input.*
- `def _add_input_options(parser)` - *The source arguments every reading subcommand shares.*
- `def build_parser()` - *The CLI grammar: three reading surfaces plus a self-contained demo.*
- `def run(args)` - *Dispatch one parsed command through the registry.*
- `def main(argv)` - *Parse the command line, run it, and print the remediation triad on a refusal.*

---

### [`gauge/render.py`](gauge/render.py)
> *Text renderers: sparklines, signed bar charts and a statistics table.*

**Size**: `121` lines (`4540` bytes)

**Functions:**
- `def format_number(value)` - *A compact human label for one value, with negative zero folded to zero.*
- `def resample(values, width)` - *`values` unchanged when it already fits, else `width` bucket averages.*
- `def _level(value, low, high, levels)` - *The half-up level of `value` between `low` and `high`; a flat series sits in the middle.*
- `def sparkline(values, width, ascii_only)` - *One character per value, resampled to `width`; eight levels from lowest to highest.*
- `def _position(value, low, high, width)` - *The half-up column of `value` in a chart of `width` cells.*
- `def _bar_row(value, low, high, width, zero, block, axis)` - *One bar row with the zero axis kept visible; a tiny non-zero value keeps one block.*
- `def bar_chart(values, width, ascii_only)` - *One labelled row per value, bars growing from a shared zero axis.*
- `def stats_table(summary)` - *The human statistics block, one aligned `name  value` line per measurement.*

---

### [`gauge/series.py`](gauge/series.py)
> *Numeric input parsing and summary statistics for gauge.*

**Size**: `101` lines (`3182` bytes)

**Classes:**
- `class Summary` - *A series' count, extrema, centre and spread, with a stable JSON shape.*
  - Method `.as_dict()` - *The `stats --json` object: stable keys and raw floating-point values.*

**Functions:**
- `def parse_numbers(chunks)` - *Every finite number in whitespace- and comma-separated text chunks, in order.*
- `def percentile(values, fraction)` - *The nearest-rank percentile: the ceil(fraction * n)-th smallest value.*
- `def summarize(values)` - *The summary of a non-empty finite series.*

---

### [`tests/__init__.py`](tests/__init__.py)
> *Unit tests for gauge.*

**Size**: `1` lines (`28` bytes)

---

### [`tests/test_cli.py`](tests/test_cli.py)
> *Unit tests for the gauge command line: sources, surfaces, refusals and exit codes.*

**Size**: `148` lines (`5961` bytes)

**Classes:**
- `class _FakeStdin` - *A non-interactive or interactive standard input with fixed text.*
  - Method `.__init__(text, interactive)`
  - Method `.isatty()` - *Whether the command would see a terminal instead of a pipe.*
  - Method `.__iter__()` - *Yield the text as the lines a real stream would provide.*
- `class GaugeCliTests` - *The public command line, exercised in process for speed.*
  - Method `._run(argv, stdin)` - *Run one command line and return (exit code, stdout, stderr).*
  - Method `.test_spark_renders_every_level_by_default()`
  - Method `.test_ascii_flag_and_label_shape_the_sparkline()`
  - Method `.test_stats_json_has_the_documented_shape()`
  - Method `.test_stats_reads_piped_lines()`
  - Method `.test_stats_reads_a_file()`
  - Method `.test_an_empty_pipe_is_refused_with_the_triad()`
  - Method `.test_an_interactive_terminal_is_never_prompted()`
  - Method `.test_two_input_sources_are_refused()`
  - Method `.test_a_bad_token_is_named_and_refused()`
  - Method `.test_a_non_finite_token_is_refused()`
  - Method `.test_width_outside_the_bounds_is_refused()`
  - Method `.test_a_missing_file_is_a_runtime_error()`
  - Method `.test_signed_bars_keep_their_axis()`
  - Method `.test_demo_shows_both_surfaces()`
  - Method `.test_a_legacy_encoding_falls_back_to_ascii()`
  - Method `.test_version_prints_the_package_version()`

---

### [`tests/test_render.py`](tests/test_render.py)
> *Unit tests for gauge's deterministic text renderers.*

**Size**: `98` lines (`3508` bytes)

**Classes:**
- `class SparklineTests` - *Eight fixed levels, a flat middle and proportional resampling.*
  - Method `.test_a_rising_series_uses_every_level()`
  - Method `.test_a_flat_series_sits_in_the_middle_level()`
  - Method `.test_the_ascii_twin_uses_its_own_middle_level()`
  - Method `.test_a_short_series_is_not_padded_or_upsampled()`
  - Method `.test_a_long_series_resamples_to_exactly_the_width()`
  - Method `.test_an_empty_series_is_refused()`
- `class ResampleTests` - *Proportional buckets keep the shape of the original series.*
  - Method `.test_five_values_become_two_bucket_averages()`
  - Method `.test_a_series_within_the_width_is_unchanged()`
  - Method `.test_a_zero_width_is_refused()`
- `class BarChartTests` - *Rows share a zero axis and keep a visible block for tiny values.*
  - Method `.test_positive_bars_grow_from_the_left_axis()`
  - Method `.test_signed_bars_grow_outward_from_the_center()`
  - Method `.test_all_zero_values_show_a_centered_axis()`
  - Method `.test_an_empty_series_or_narrow_width_is_refused()`
- `class StatsTableTests` - *The five-line table is a stable, aligned surface.*
  - Method `.test_the_table_matches_the_documented_example()`
  - Method `.test_numbers_stay_compact_and_negative_zero_folds()`

---

### [`tests/test_series.py`](tests/test_series.py)
> *Unit tests for gauge's input parsing and summary statistics.*

**Size**: `95` lines (`3646` bytes)

**Classes:**
- `class ParseNumbersTests` - *One strict reader for positional arguments, files and pipes.*
  - Method `.test_whitespace_commas_and_lines_split_the_same_way()`
  - Method `.test_decimal_exponent_and_signed_forms_are_accepted()`
  - Method `.test_a_generator_is_consumed_once()`
  - Method `.test_a_non_numeric_token_is_named()`
  - Method `.test_non_finite_values_are_refused()`
  - Method `.test_empty_input_is_refused()`
- `class PercentileTests` - *The nearest-rank definition recorded in ADR-002.*
  - Method `.test_p90_is_the_ninth_of_ten_values()`
  - Method `.test_a_single_value_is_its_own_percentile()`
  - Method `.test_an_out_of_range_fraction_is_refused()`
  - Method `.test_an_empty_series_is_refused()`
- `class SummaryTests` - *Central values, spread and the stable JSON object.*
  - Method `.test_odd_series_has_its_middle_value_as_median()`
  - Method `.test_even_series_averages_the_middle_pair()`
  - Method `.test_stdev_is_the_population_form()`
  - Method `.test_a_flat_series_has_zero_stdev()`
  - Method `.test_json_object_has_the_documented_keys()`
  - Method `.test_an_empty_or_non_finite_series_is_refused()`

---

### [`tools/dogfood.py`](tools/dogfood.py)
> *Gauge's dogfood runner: use the product as a user does, then attack its input edge.*

**Size**: `245` lines (`9995` bytes)

**Classes:**
- `class Report` - *Collects step outcomes: the console sees a summary, the log sees everything.*
  - Method `.__init__()`
  - Method `.step(ok, label, detail)` - *Record one step's outcome and hand back whether it passed.*

**Functions:**
- `def terminate_tree(process)` - *Kill a child and everything it started, on Windows and POSIX alike.*
- `def supervised(command, box, env, use_stdin)` - *Run one child with captured output and a guaranteed process-tree teardown.*
- `def run_cli(box, *args, stdin_text, extra_env)` - *Run `python -m gauge ARGS` in the sandbox and return (exit code, stdout, stderr).*
- `def fingerprint()` - *The project's tracked and untracked state, so a run that dirties it fails.*
- `def golden_path(box, report)` - *Every reading surface and every source, once, in the sandbox.*
- `def chaos(box, report)` - *Empty, malformed and hostile input, plus a legacy output encoding.*
- `def main()` - *Run both tracks in one sandbox and print at most 15 lines.*

---
