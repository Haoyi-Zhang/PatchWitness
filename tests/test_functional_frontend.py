"""Owned benign source-lowering checks; no third-party programs are executed."""
import copy
import itertools
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import checker
from fixtures import FAMILIES, make, oracle
from functional_frontend import Unsupported, lower, translate_pair, check_source_witness
from functional_reference import build_reference
from producer import Fuel, evaluate, find
from run_functional_diagnostics import analyze


class FunctionalFrontendTests(unittest.TestCase):
    def test_all_authored_pairs_and_same_information_baseline(self):
        specs = json.loads((ROOT / "data/functional-programs.json").read_text(encoding="utf-8"))["cases"]
        reports = {spec["id"]: analyze(spec) for spec in specs}
        self.assertEqual(reports["F06"]["counts"]["repair"], 1)
        self.assertEqual(reports["F06"]["counts"]["new-fault"], 1)
        self.assertEqual(reports["F06"]["counts"]["defined-changed"], 6)
        self.assertEqual(reports["F03"]["counts"]["defined-equal"], 64)
        self.assertIsNone(reports["F03"]["certificate"])
        self.assertEqual(reports["F09"]["counts"]["defined-changed"], 8)
        self.assertIsNone(reports["F09"]["certificate"])
        self.assertTrue(all(r["simple_baseline_set_agreement"] for r in reports.values()))

    def test_exact_mapping_and_lazy_fault_behavior(self):
        source = "def patch(a, b):\n    return checked_add(a, 1) if a < b else wrap_sub(a, 1)\n"
        names, expr = lower(source, 3)
        self.assertEqual(names, ["a", "b"])
        self.assertEqual(expr, ["if", ["lt", ["v", 0], ["v", 1]],
                                ["uadd", ["v", 0], ["c", 1]], ["sub", ["v", 0], ["c", 1]]])
        source = "def patch(x):\n    return checked_mul(7, 7) if x < 0 else 0\n"
        self.assertEqual(build_reference(source, 3)([0]), ["u", 0])
        source = "def patch(x):\n    return wrap_add(checked_add(7, 1), checked_mul(7, 7))\n"
        self.assertEqual(build_reference(source, 3)([0]), ["fault", "add-overflow"])

    def test_source_binding_and_wrong_guard_negative_control(self):
        before = "def patch(x, y):\n    return bounded_index(x, y)\n"
        after = "def patch(x, y):\n    return bounded_index(x, y) if x < y else 0\n"
        domain = [[0, 7], [0, 7]]
        case = translate_pair("Binding", 3, domain, before, after)
        certificate, _ = find(case, Fuel())
        self.assertTrue(check_source_witness("Binding", 3, domain, before, after, certificate, Fuel())[0])
        self.assertFalse(check_source_witness("Binding", 3, domain, before, before, certificate, Fuel())[0])
        bad = copy.deepcopy(case)
        bad["after"][1][0] = "le"  # valid IR, but not a valid lowering of this source
        checker.validate_case(bad)
        reference = build_reference(after, 3)
        mismatches = [values for values in itertools.product(range(8), repeat=2)
                      if reference(list(values)) != evaluate(bad["after"], list(values), 3, Fuel())[0]]
        self.assertEqual(mismatches, [(i, i) for i in range(8)])

    def test_reject_unsupported_and_ill_typed_source(self):
        invalid = [
            "def patch(x):\n    return x + 1\n",  # not modular by default
            "def patch(x):\n    return x[0]\n",
            "def patch(x):\n    return x.real\n",
            "def patch(x):\n    return print(x)\n",
            "def patch(x):\n    return True\n",
            "def patch(x):\n    return 0 if x else 1\n",  # no integer truthiness
            "def patch(x):\n    return 0 if x == 0 else x == 1\n",
            "def patch(x):\n    return 0 if x < 1 < 2 else 1\n",
            "def patch(x):\n    return checked_add(x, b=1)\n",
            "def patch(checked_add):\n    return checked_add(0, 1)\n",
            "def patch(x=0):\n    return x\n",
            "@unknown\ndef patch(x):\n    return x\n",
            "def patch(x):\n    while x:\n        pass\n    return x\n",
            "def patch(x):\n    return 8\n",
            "def patch(x):\n    return -1\n",
        ]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(Unsupported):
                lower(source, 3)
        source = "def patch(x):\n    return x\n"
        with self.assertRaises(Unsupported):
            translate_pair("Bad", 3, [[0, 7]], source, source.replace("x", "y"))
        with self.assertRaises(Unsupported):
            translate_pair("Bad", 3, [[0, 7], [0, 7]], source, source)
        with self.assertRaises(Unsupported):
            lower(source, True)
        with self.assertRaises(Unsupported):
            lower(" " * 4097, 3)
        deep = "x"
        for _ in range(14):
            deep = f"wrap_add({deep}, 0)"
        with self.assertRaises(Unsupported):
            lower(f"def patch(x):\n    return {deep}\n", 3)

    def test_reference_exact_input_types(self):
        reference = build_reference("def patch(x):\n    return x\n", 3)
        for values in ([True], [1.0], [8], [-1], [], [0, 0]):
            with self.assertRaises(ValueError):
                reference(values)

    def test_original_finite_counts_unchanged(self):
        protocol = json.loads((ROOT / "data/finite-protocol.json").read_text(encoding="utf-8"))
        counts = dict.fromkeys(("repair", "regression", "both-safe", "both-fault"), 0)
        fuel = Fuel(110_000)
        cases = [(family, width) for family in FAMILIES for width in protocol["widths_for_all_families"]]
        cases.append(("mixed-change", 5))
        for number, (family, width) in enumerate(cases):
            case = make(family, width, f"Original-{number}")
            checker.validate_case(case)
            for values in itertools.product(*(range(lo, hi + 1) for lo, hi in case["domain"])):
                old = evaluate(case["before"], list(values), width, fuel)
                new = evaluate(case["after"], list(values), width, fuel)
                self.assertEqual(old, checker.replay(case["before"], list(values), width, fuel))
                self.assertEqual(new, checker.replay(case["after"], list(values), width, fuel))
                kind = ("repair" if old[0][0] == "fault" and new[0][0] == "u" else
                        "regression" if old[0][0] == "u" and new[0][0] == "fault" else
                        "both-fault" if old[0][0] == "fault" else "both-safe")
                self.assertEqual(kind, oracle(family, width, *values))
                counts[kind] += 1
        self.assertEqual(counts, {"repair": 424, "regression": 242,
                                  "both-safe": 2990, "both-fault": 56})

    def test_retained_microqueue_zero_gain_arithmetic_only(self):
        # Read frozen ranks/labels only. Do not extract a guard, run a detector,
        # evaluate public source, or trigger an application behavior.
        base = ROOT / "results/public-study"
        summary = json.loads((base / "evaluation/summary.json").read_text(encoding="utf-8"))
        frozen = json.loads((base / "frozen/predictions-frozen.json").read_text(encoding="utf-8"))
        labels = json.loads((ROOT / "data/public-study/labels.json").read_text(encoding="utf-8"))
        label_map = {row["id"]: row["label"] for row in labels["labels"]}
        self.assertEqual(summary["rankings"], frozen["rankings"])
        ranks = frozen["rankings"]
        self.assertEqual(set(ranks["syntax"][:20]), set(ranks["validated"][:20]))
        self.assertEqual(sum(label_map[i] for i in ranks["syntax"][:20]), 15)
        self.assertEqual(sum(label_map[i] for i in ranks["validated"][:20]), 15)
        self.assertEqual(sum(label_map[i] for i in ranks["unvalidated"][:20]), 16)
        self.assertEqual(summary["validated_minus_syntax_at_20"], 0.0)
        self.assertEqual(summary["top20_symmetric_difference_validated_vs_syntax"], 0)


if __name__ == "__main__":
    unittest.main()
