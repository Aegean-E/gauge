"""Unit tests for gauge's deterministic text renderers."""

import unittest

from gauge.render import (
    bar_chart,
    format_number,
    render_histogram,
    resample,
    sparkline,
    stats_table,
)
from gauge.series import build_histogram, summarize


class SparklineTests(unittest.TestCase):
    """Eight fixed levels, a flat middle and proportional resampling."""

    def test_a_rising_series_uses_every_level(self) -> None:
        self.assertEqual(
            "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588",
            sparkline([0, 1, 2, 3, 4, 5, 6, 7], width=20),
        )

    def test_a_flat_series_sits_in_the_middle_level(self) -> None:
        self.assertEqual("\u2585\u2585\u2585", sparkline([5, 5, 5], width=10))

    def test_the_ascii_twin_uses_its_own_middle_level(self) -> None:
        self.assertEqual("+++", sparkline([5, 5, 5], width=10, ascii_only=True))

    def test_a_short_series_is_not_padded_or_upsampled(self) -> None:
        self.assertEqual("\u2581\u2588", sparkline([0, 10], width=4))

    def test_a_long_series_resamples_to_exactly_the_width(self) -> None:
        rendered = sparkline(list(range(100)), width=20)
        self.assertEqual(20, len(rendered))

    def test_extreme_opposite_signs_render_without_overflow(self) -> None:
        self.assertEqual("\u2588\u2581", sparkline([1e308, -1e308], width=2))
        self.assertEqual(
            " 1e+308       |#####\n-1e+308  #####|",
            bar_chart([1e308, -1e308], width=11, ascii_only=True),
        )

    def test_an_empty_series_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            sparkline([], width=10)


class ResampleTests(unittest.TestCase):
    """Proportional buckets keep the shape of the original series."""

    def test_five_values_become_two_bucket_averages(self) -> None:
        self.assertEqual([0.5, 3.0], resample([0, 1, 2, 3, 4], 2))

    def test_a_series_within_the_width_is_unchanged(self) -> None:
        self.assertEqual([1, 2, 3], resample([1, 2, 3], 5))

    def test_bucket_averages_of_extreme_values_do_not_overflow(self) -> None:
        self.assertEqual([1e308], resample([1e308, 1e308], 1))
        self.assertEqual([5e307], resample([1e308, 0.0], 1))

    def test_a_zero_width_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            resample([1.0], 0)


class BarChartTests(unittest.TestCase):
    """Rows share a zero axis and keep a visible block for tiny values."""

    def test_positive_bars_grow_from_the_left_axis(self) -> None:
        self.assertEqual(
            "1  |###\n2  |######\n3  |#########",
            bar_chart([1, 2, 3], width=10, ascii_only=True),
        )

    def test_signed_bars_grow_outward_from_the_center(self) -> None:
        self.assertEqual(
            "-1  ###|\n 0     |\n 2     |#######",
            bar_chart([-1, 0, 2], width=11, ascii_only=True),
        )

    def test_all_zero_values_show_a_centered_axis(self) -> None:
        self.assertEqual("0    |\n0    |", bar_chart([0, 0], width=5, ascii_only=True))

    def test_an_empty_series_or_narrow_width_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            bar_chart([], width=10)
        with self.assertRaises(ValueError):
            bar_chart([1.0], width=1)


class StatsTableTests(unittest.TestCase):
    """The five-line table is a stable, aligned surface."""

    def test_the_table_matches_the_documented_example(self) -> None:
        self.assertEqual(
            "count   4\n"
            "sum     18\n"
            "min     2\n"
            "max     8\n"
            "mean    4.5\n"
            "median  4\n"
            "p90     8\n"
            "stdev   2.29129",
            stats_table(summarize([2.0, 3.0, 5.0, 8.0])),
        )

    def test_numbers_stay_compact_and_negative_zero_folds(self) -> None:
        self.assertEqual("0", format_number(-0.0))
        self.assertEqual("1e+20", format_number(1e20))
        self.assertEqual("0.816497", format_number(0.816496580927726))


class HistogramRenderTests(unittest.TestCase):
    """Bars scale to the largest count and every bin keeps a row."""

    def test_bars_scale_to_the_largest_count(self) -> None:
        self.assertEqual(
            "[0, 0.5)  ###         1\n"
            "[0.5, 1]  ##########  3",
            render_histogram(build_histogram([0.0, 1.0, 1.0, 1.0], 2), width=10, ascii_only=True),
        )

    def test_a_flat_series_uses_one_compact_label(self) -> None:
        self.assertEqual(
            "[5]  #####  3",
            render_histogram(build_histogram([5.0, 5.0, 5.0], 4), width=5, ascii_only=True),
        )

    def test_empty_bins_stay_visible(self) -> None:
        self.assertEqual(
            "[0, 3)  ######  1\n"
            "[3, 6)          0\n"
            "[6, 9]  ######  1",
            render_histogram(build_histogram([0.0, 9.0], 3), width=6, ascii_only=True),
        )

    def test_the_unicode_block_is_the_default(self) -> None:
        rendered = render_histogram(build_histogram([1.0, 1.0, 2.0], 2), width=4)
        self.assertIn("\u2588", rendered)

    def test_a_narrow_width_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            render_histogram(build_histogram([1.0, 2.0], 2), width=1)


if __name__ == "__main__":
    unittest.main()
