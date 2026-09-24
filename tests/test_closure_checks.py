import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from closure_checks import candidate_frame_ambiguity, grouping_sensitivity, paired_top_k_identity, run_all


class ClosureCheckTests(unittest.TestCase):
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
