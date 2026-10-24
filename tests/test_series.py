"""Unit tests for gauge's input parsing and summary statistics."""

import math
import unittest

from gauge.series import build_boxplot, build_histogram, parse_numbers, percentile, summarize


class ParseNumbersTests(unittest.TestCase):
    """One strict reader for positional arguments, files and pipes."""

    def test_whitespace_commas_and_lines_split_the_same_way(self) -> None:
        self.assertEqual([1.0, 2.0, 3.0, 4.0], parse_numbers(["1, 2", "3\n4"]))

    def test_decimal_exponent_and_signed_forms_are_accepted(self) -> None:
        self.assertEqual([0.5, 2.0, 1000.0], parse_numbers([".5 +2 1e3"]))

    def test_a_generator_is_consumed_once(self) -> None:
        self.assertEqual([7.0, 8.0], parse_numbers(iter(["7 8"])))

    def test_a_non_numeric_token_is_named(self) -> None:
        with self.assertRaisesRegex(ValueError, "'oops' is not a number"):
            parse_numbers(["1 oops 3"])

    def test_non_finite_values_are_refused(self) -> None:
        for token in ("nan", "inf", "-inf", "Infinity"):
            with self.subTest(token=token):
                with self.assertRaisesRegex(ValueError, "not a finite number"):
                    parse_numbers([token])

    def test_empty_input_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no numbers were provided"):
            parse_numbers(["", "  ", ","])


class PercentileTests(unittest.TestCase):
    """The nearest-rank definition recorded in ADR-002."""

    def test_p90_is_the_ninth_of_ten_values(self) -> None:
        self.assertEqual(9.0, percentile([float(n) for n in range(1, 11)], 0.9))

    def test_a_single_value_is_its_own_percentile(self) -> None:
        self.assertEqual(4.0, percentile([4.0], 0.9))

    def test_an_out_of_range_fraction_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            percentile([1.0], 0.0)

    def test_an_empty_series_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            percentile([], 0.9)


class SummaryTests(unittest.TestCase):
    """Central values, spread and the stable JSON object."""

    def test_odd_series_has_its_middle_value_as_median(self) -> None:
        summary = summarize([2.0, 4.0, 6.0])
        self.assertEqual(3, summary.count)
        self.assertEqual(12.0, summary.total)
        self.assertEqual(2.0, summary.minimum)
        self.assertEqual(6.0, summary.maximum)
        self.assertEqual(4.0, summary.mean)
        self.assertEqual(4.0, summary.median)
        self.assertEqual(6.0, summary.p90)
        self.assertAlmostEqual(math.sqrt(8.0 / 3.0), summary.stdev)

    def test_even_series_averages_the_middle_pair(self) -> None:
        self.assertEqual(2.5, summarize([1.0, 2.0, 3.0, 4.0]).median)

    def test_stdev_is_the_population_form(self) -> None:
        self.assertAlmostEqual(0.816496580927726, summarize([1.0, 2.0, 3.0]).stdev)

    def test_a_flat_series_has_zero_stdev(self) -> None:
        self.assertEqual(0.0, summarize([5.0, 5.0, 5.0]).stdev)

    def test_extreme_opposite_signs_stay_finite(self) -> None:
        summary = summarize([1e308, -1e308])
        self.assertEqual(0.0, summary.total)
        self.assertEqual(0.0, summary.mean)
        self.assertEqual(0.0, summary.median)
        self.assertEqual(1e308, summary.stdev)
        self.assertEqual(1e308, summary.maximum)

    def test_even_median_of_extreme_values_does_not_overflow(self) -> None:
        self.assertEqual(5e307, summarize([1e308, 0.0]).median)

    def test_an_unrepresentable_sum_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum exceeds"):
            summarize([1e308, 1e308])

    def test_json_object_has_the_documented_keys(self) -> None:
        data = summarize([2.0, 3.0, 5.0, 8.0]).as_dict()
        self.assertEqual(
            {"count", "sum", "min", "max", "mean", "median", "p90", "stdev"},
            set(data),
        )
        self.assertEqual(4, data["count"])
        self.assertEqual(18.0, data["sum"])
        self.assertEqual(4.0, data["median"])

    def test_custom_percentiles_computed_and_included_in_dict(self) -> None:
        vals = [float(n) for n in range(1, 101)]
        summary = summarize(vals, percentiles=[50.0, 95.0, 99.0])
        self.assertIsNotNone(summary.custom_percentiles)
        self.assertEqual({"50": 50.0, "95": 95.0, "99": 99.0}, summary.custom_percentiles)
        data = summary.as_dict()
        self.assertIn("percentiles", data)
        self.assertEqual({"50": 50.0, "95": 95.0, "99": 99.0}, data["percentiles"])
        # Existing 8 keys still present
        for key in ("count", "sum", "min", "max", "mean", "median", "p90", "stdev"):
            self.assertIn(key, data)

    def test_invalid_custom_percentiles_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "in \\(0, 100\\]"):
            summarize([1.0, 2.0], percentiles=[0.0])
        with self.assertRaisesRegex(ValueError, "in \\(0, 100\\]"):
            summarize([1.0, 2.0], percentiles=[105.0])

    def test_an_empty_or_non_finite_series_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            summarize([])
        with self.assertRaises(ValueError):
            summarize([1.0, float("nan")])


class HistogramTests(unittest.TestCase):
    """The equal-width bin contract recorded in ADR-004."""

    def test_ten_values_split_evenly_across_five_bins(self) -> None:
        histogram = build_histogram([float(n) for n in range(10)], 5)
        self.assertEqual(6, len(histogram.edges))
        self.assertEqual((0.0, 9.0), (histogram.edges[0], histogram.edges[-1]))
        self.assertEqual((2, 2, 2, 2, 2), histogram.counts)
        self.assertEqual(10, sum(histogram.counts))

    def test_the_maximum_belongs_to_the_closed_last_bin(self) -> None:
        histogram = build_histogram([0.0, 10.0], 2)
        self.assertEqual((0.0, 5.0, 10.0), histogram.edges)
        self.assertEqual((1, 1), histogram.counts)

    def test_an_inner_edge_belongs_to_the_upper_bin(self) -> None:
        self.assertEqual((1, 2), build_histogram([0.0, 5.0, 10.0], 2).counts)

    def test_a_flat_series_is_one_bin(self) -> None:
        histogram = build_histogram([5.0, 5.0, 5.0], 4)
        self.assertEqual((5.0, 5.0), histogram.edges)
        self.assertEqual((3,), histogram.counts)

    def test_negative_ranges_bin_without_special_cases(self) -> None:
        histogram = build_histogram([-3.0, -2.0, -1.0, 0.0], 3)
        self.assertEqual((-3.0, -2.0, -1.0, 0.0), histogram.edges)
        self.assertEqual((1, 1, 2), histogram.counts)

    def test_extreme_opposite_signs_do_not_overflow(self) -> None:
        histogram = build_histogram([1e308, -1e308], 2)
        self.assertEqual((1, 1), histogram.counts)
        self.assertTrue(all(math.isfinite(edge) for edge in histogram.edges))

    def test_bin_counts_outside_the_bounds_are_refused(self) -> None:
        for bins in (0, 101):
            with self.subTest(bins=bins):
                with self.assertRaisesRegex(ValueError, "between 1 and 100"):
                    build_histogram([1.0], bins)

    def test_an_empty_or_non_finite_series_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty series"):
            build_histogram([], 10)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            build_histogram([1.0, float("inf")], 10)


class FieldAndDelimiterTests(unittest.TestCase):
    """Field and delimiter extraction rules (ADR-005)."""

    def test_field_extracts_column_from_lines(self) -> None:
        lines = ["host1 42 active\n", "host2 99 idle\n", "host3 15 active\n"]
        self.assertEqual([42.0, 99.0, 15.0], parse_numbers(lines, field=2))

    def test_delimiter_splits_custom_separator(self) -> None:
        text = ["10|20|30"]
        self.assertEqual([10.0, 20.0, 30.0], parse_numbers(text, delimiter="|"))

    def test_field_with_custom_delimiter_csv(self) -> None:
        csv_data = ["2026-10-24,GET,/api,200,45.5\n", "2026-10-24,POST,/login,200,120.2\n"]
        self.assertEqual([45.5, 120.2], parse_numbers(csv_data, field=5, delimiter=","))

    def test_field_out_of_bounds_raises(self) -> None:
        lines = ["only_one_col\n"]
        with self.assertRaisesRegex(ValueError, "fewer than 2 columns"):
            parse_numbers(lines, field=2)

    def test_invalid_field_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be 1 or greater"):
            parse_numbers(["10 20"], field=0)

    def test_empty_delimiter_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            parse_numbers(["10 20"], delimiter="")


class BoxPlotTests(unittest.TestCase):
    """The 5-number summary computation (ADR-007)."""

    def test_boxplot_computes_five_number_summary(self) -> None:
        vals = [float(n) for n in range(1, 101)]
        box = build_boxplot(vals)
        self.assertEqual(1.0, box.minimum)
        self.assertEqual(25.0, box.q1)
        self.assertEqual(50.5, box.median)
        self.assertEqual(75.0, box.q3)
        self.assertEqual(100.0, box.maximum)

    def test_boxplot_flat_series(self) -> None:
        box = build_boxplot([5.0, 5.0, 5.0])
        self.assertEqual(5.0, box.minimum)
        self.assertEqual(5.0, box.q1)
        self.assertEqual(5.0, box.median)
        self.assertEqual(5.0, box.q3)
        self.assertEqual(5.0, box.maximum)

    def test_boxplot_empty_or_non_finite_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty series"):
            build_boxplot([])
        with self.assertRaisesRegex(ValueError, "non-finite"):
            build_boxplot([1.0, float("nan")])


if __name__ == "__main__":
    unittest.main()
