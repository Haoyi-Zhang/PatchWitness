"""Same-input static comparisons; does not execute upstream source or native C."""
import copy
from fractions import Fraction
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from public_study import load_json
from run_patch_source_review import freeze_same_information, metrics
from same_information import direct_relation


def owned_case():
    return {"kind": "guard-trigger", "frontend_rule": "reject-if",
            "source_tokens": ["x < 0"], "context_tokens": ["y > 0"],
            "assignment": {"x": -1, "y": 1}, "trigger_value": True}


class SameInformationTests(unittest.TestCase):
    def test_record_free_arm_does_not_call_evidence_checker(self):
        with mock.patch("public_study.check_source_record", side_effect=AssertionError("evidence-use")):
            self.assertTrue(direct_relation(owned_case()))

    def test_false_context_is_not_promoted(self):
        case = owned_case()
        case["assignment"]["y"] = 0
        self.assertFalse(direct_relation(case))

    def test_all_assignment_names_and_exact_integer_types_checked(self):
        for change in ("bool", "float", "extra", "missing"):
            case = owned_case()
            if change == "bool": case["assignment"]["y"] = True
            if change == "float": case["assignment"]["y"] = 1.0
            if change == "extra": case["assignment"]["extra"] = 1
            if change == "missing": del case["assignment"]["y"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                direct_relation(case)

    def test_lazy_guard_uses_same_declared_context_and_input(self):
        case = {"kind": "guard-trigger", "frontend_rule": "require",
                "source_tokens": ["x > 0", "p <= limit / x"], "context_tokens": [],
                "assignment": {"x": 0, "p": 1, "limit": 7}, "trigger_value": False}
        self.assertTrue(direct_relation(case))  # No native zero division.

    def test_range_relation_is_not_a_runtime_fault(self):
        case = {"kind": "source-difference", "assignment": {"concat_dim": -(2**31)}}
        self.assertTrue(direct_relation(case))
        case["assignment"]["concat_dim"] = 0
        with self.assertRaises(ValueError):
            direct_relation(case)

    def test_current_all_32_flags_scores_order_and_top20(self):
        data = ROOT / "data/public-study"
        candidates, evidence, protocol = [load_json(data / name) for name in
            ("candidates.json", "source-evidence-cases.json", "protocol.json")]
        checked, rows, order, excerpts = freeze_same_information(candidates, evidence, protocol)
        retained = load_json(ROOT / "results/public-study/frozen/predictions-frozen.json")
        self.assertEqual(checked, retained)
        self.assertEqual(len(rows), 32)
        self.assertEqual(sum(row["direct_relation"] for row in rows), 10)
        self.assertEqual(order, checked["rankings"]["validated"])
        self.assertEqual(set(order[:20]), set(checked["rankings"]["syntax"][:20]))
        self.assertEqual(sum(not r["all_hunk_counts_match"] for r in excerpts), 32)
        labels = {r["id"]: r["label"] for r in load_json(data / "labels.json")["labels"]}
        self.assertEqual(metrics(order, labels, [20])["precision_at_20"], 0.75)
        delta = Fraction(sum(labels[i] for i in order[:20]) -
                         sum(labels[i] for i in checked["rankings"]["syntax"][:20]), 20)
        self.assertEqual(delta, 0)


if __name__ == "__main__":
    unittest.main()
