"""Unit tests for the gauge command line: sources, surfaces, refusals and exit codes."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gauge.cli import main


class _FakeStdin:
    """A non-interactive or interactive standard input with fixed text."""

    def __init__(self, text: str, interactive: bool = False) -> None:
        self._text = text
        self._interactive = interactive

    def isatty(self) -> bool:
        """Whether the command would see a terminal instead of a pipe."""
        return self._interactive

    def __iter__(self):
        """Yield the text as the lines a real stream would provide."""
        return iter(self._text.splitlines(keepends=True))


class GaugeCliTests(unittest.TestCase):
    """The public command line, exercised in process for speed."""

    def _run(self, argv, stdin=None):
        """Run one command line and return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            context = mock.patch("sys.stdin", stdin) if stdin is not None else contextlib.nullcontext()
            with context:
                code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_spark_renders_every_level_by_default(self) -> None:
        code, out, _ = self._run(["spark", "0", "1", "2", "3", "4", "5", "6", "7"])
        self.assertEqual(0, code)
        self.assertEqual("\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588", out.strip())

    def test_ascii_flag_and_label_shape_the_sparkline(self) -> None:
        code, out, _ = self._run(["spark", "1", "2", "3", "--ascii", "--label", "latency"])
        self.assertEqual(0, code)
        self.assertTrue(out.startswith("latency "))
        self.assertTrue(out.isascii())

    def test_stats_json_has_the_documented_shape(self) -> None:
        code, out, _ = self._run(["stats", "2", "3", "5", "8", "--json"])
        data = json.loads(out)
        self.assertEqual(0, code)
        self.assertEqual(4, data["count"])
        self.assertEqual(18.0, data["sum"])
        self.assertEqual(4.0, data["median"])

    def test_stats_reads_piped_lines(self) -> None:
        code, out, _ = self._run(["stats", "--json"], stdin=_FakeStdin("1, 2\n3 4\n"))
        self.assertEqual(0, code)
        self.assertEqual(4, json.loads(out)["count"])

    def test_stats_reads_a_file(self) -> None:
        box = tempfile.TemporaryDirectory()
        self.addCleanup(box.cleanup)
        path = Path(box.name) / "values.txt"
        path.write_text("4 5 6\n", encoding="utf-8")
        code, out, _ = self._run(["stats", "--file", str(path), "--json"])
        self.assertEqual(0, code)
        self.assertEqual(6.0, json.loads(out)["max"])

    def test_an_empty_pipe_is_refused_with_the_triad(self) -> None:
        code, _, err = self._run(["stats"], stdin=_FakeStdin(""))
        self.assertEqual(2, code)
        self.assertIn("no numbers were provided", err)
        self.assertIn("Why:", err)
        self.assertIn("Fix:", err)

    def test_an_interactive_terminal_is_never_prompted(self) -> None:
        code, _, err = self._run(["stats"], stdin=_FakeStdin("", interactive=True))
        self.assertEqual(2, code)
        self.assertIn("never prompts", err)

    def test_two_input_sources_are_refused(self) -> None:
        code, _, err = self._run(["spark", "1", "--file", "values.txt"])
        self.assertEqual(2, code)
        self.assertIn("both positional numbers and --file", err)

    def test_a_bad_token_is_named_and_refused(self) -> None:
        code, _, err = self._run(["stats", "1", "oops"])
        self.assertEqual(2, code)
        self.assertIn("'oops' is not a number", err)
        self.assertIn("Why:", err)

    def test_a_non_finite_token_is_refused(self) -> None:
        code, _, err = self._run(["spark", "1", "nan"])
        self.assertEqual(2, code)
        self.assertIn("not a finite number", err)

    def test_width_outside_the_bounds_is_refused(self) -> None:
        for width in ("1", "1001"):
            with self.subTest(width=width):
                code, _, err = self._run(["bars", "1", "2", "--width", width])
                self.assertEqual(2, code)
                self.assertIn("--width must be between 2 and 1000", err)

    def test_a_missing_file_is_a_runtime_error(self) -> None:
        box = tempfile.TemporaryDirectory()
        self.addCleanup(box.cleanup)
        missing = Path(box.name) / "absent.txt"
        code, _, err = self._run(["stats", "--file", str(missing)])
        self.assertEqual(1, code)
        self.assertIn("cannot read", err)
        self.assertIn("Fix:", err)

    def test_signed_bars_keep_their_axis(self) -> None:
        code, out, _ = self._run(["bars", "-1", "0", "2", "--ascii", "--width", "11"])
        lines = out.splitlines()
        self.assertEqual(0, code)
        self.assertEqual(3, len(lines))
        self.assertTrue(all("|" in line for line in lines))

    def test_extreme_opposite_signs_summarize_to_finite_values(self) -> None:
        code, out, _ = self._run(["stats", "1e308", "-1e308", "--json"])
        data = json.loads(out)
        self.assertEqual(0, code)
        self.assertEqual(0.0, data["mean"])
        self.assertEqual(1e308, data["stdev"])

    def test_an_unrepresentable_sum_is_refused_with_the_triad(self) -> None:
        code, _, err = self._run(["stats", "1e308", "1e308"])
        self.assertEqual(2, code)
        self.assertIn("sum exceeds", err)
        self.assertIn("Why:", err)
        self.assertIn("Fix:", err)

    def test_hist_renders_one_row_per_bin(self) -> None:
        code, out, _ = self._run(
            ["hist", "1", "2", "2", "3", "3", "3", "--bins", "3", "--width", "12", "--ascii"]
        )
        lines = out.splitlines()
        self.assertEqual(0, code)
        self.assertEqual(3, len(lines))
        self.assertTrue(all("[" in line and "#" in line for line in lines))
        self.assertTrue(out.isascii())

    def test_hist_flat_series_is_one_bin(self) -> None:
        code, out, _ = self._run(["hist", "5", "5", "5", "--bins", "10"])
        self.assertEqual(0, code)
        self.assertEqual(1, len(out.splitlines()))
        self.assertIn("[5]", out)

    def test_hist_bins_outside_the_bounds_are_refused(self) -> None:
        for bins in ("0", "101"):
            with self.subTest(bins=bins):
                code, _, err = self._run(["hist", "1", "2", "--bins", bins])
                self.assertEqual(2, code)
                self.assertIn("--bins must be between 1 and 100", err)

    def test_hist_extreme_values_stay_finite(self) -> None:
        code, out, _ = self._run(["hist", "1e308", "-1e308", "--bins", "2", "--ascii"])
        self.assertEqual(0, code)
        self.assertEqual(2, len(out.splitlines()))

    def test_demo_shows_both_surfaces(self) -> None:
        code, out, _ = self._run(["demo"])
        self.assertEqual(0, code)
        self.assertIn("gauge demo", out)
        self.assertIn("count", out)
        self.assertIn("median", out)

    def test_a_legacy_encoding_falls_back_to_ascii(self) -> None:
        with mock.patch("gauge.cli._stdout_supports_unicode", return_value=False):
            code, out, _ = self._run(["spark", "1", "2", "3"])
        self.assertEqual(0, code)
        self.assertTrue(out.isascii())

    def test_version_prints_the_package_version(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            main(["--version"])
        self.assertEqual(0, raised.exception.code)
        self.assertIn("gauge 1.1.0", out.getvalue())


if __name__ == "__main__":
    unittest.main()
