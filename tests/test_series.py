"""Unit tests for gauge's input parsing and summary statistics."""

import math
import unittest

from gauge.series import parse_numbers, percentile, summarize


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

    def test_an_empty_or_non_finite_series_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            summarize([])
        with self.assertRaises(ValueError):
            summarize([1.0, float("nan")])


if __name__ == "__main__":
    unittest.main()
