import sys
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from closure_checks import _coverage_from_units, candidate_frame_ambiguity, grouping_sensitivity, paired_top_k_identity, run_all


class ClosureCheckTests(unittest.TestCase):
    def test_materialized_unit_aggregation(self):
        self.assertEqual(_coverage_from_units((6, 6, 6), (1, 1, 1)), (Fraction(1, 6), Fraction(1)))
        self.assertEqual(_coverage_from_units((1, 1, 6), (0, 0, 6)), (Fraction(3, 4), Fraction(1, 3)))

    def test_grouping_check_detects_an_incorrect_aggregation(self):
        with patch('closure_checks._coverage_from_units', return_value=(Fraction(-1), Fraction(-1))):
            result = grouping_sensitivity(2)
        self.assertEqual(result['mismatches'], result['configurations'])

    def test_incomplete_frame_allows_zero_or_one_full_window_precision(self):
        result = candidate_frame_ambiguity(20)
        self.assertEqual(result["full_window_precision_extremes"], [0.0, 1.0])
        self.assertEqual(result["constructed_full_frames"], 40)
        self.assertEqual(result["mismatches"], 0)

    def test_group_and_unit_coverage_have_both_gap_directions(self):
        result = grouping_sensitivity(6)
        self.assertTrue(result["both_gap_directions_observed"])
        self.assertGreater(result["group_minus_unit_extreme"]["gap"], 0)
        self.assertGreater(result["unit_minus_group_extreme"]["gap"], 0)
        self.assertEqual(result["observed_microcohort"]["difference_fraction"], "3/8")
        self.assertEqual(result["mismatches"], 0)

    def test_paired_identity_is_exhaustive(self):
        result = paired_top_k_identity()
        self.assertEqual(result["labelings"], 64)
        self.assertEqual(result["mismatches"], 0)

    def test_all_closure_checks_pass(self):
        result = run_all()
        self.assertEqual(result["exit_status"], 0)
        self.assertEqual(result["mismatches"], 0)
        self.assertGreater(result["obligations"], 19000)


if __name__ == "__main__":
    unittest.main()
