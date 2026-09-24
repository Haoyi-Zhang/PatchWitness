"""Tests for the label-separated public audit and restricted replay contract."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from public_study import (  # noqa: E402
    INT64_MAX,
    INT64_MIN,
    Invalid,
    check_certificate,
    evaluate_predictions,
    freeze_predictions,
    load_json,
    load_json_value,
    make_certificate,
    producer_eval,
    replay,
    validate_candidates,
    validate_expr,
    validate_labels,
    validate_outcomes,
    validate_predictions,
    validate_protocol,
    validate_study_design,
    validate_witness_cases,
)
from source_frontend import derive_witness_document, parse_expression  # noqa: E402
from source_frontend_reference import evaluate as reference_frontend_evaluate  # noqa: E402


class PublicStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = ROOT / "data/public-study"
        cls.candidates = load_json(cls.data_dir / "candidates.json")
        cls.labels = load_json(cls.data_dir / "labels.json")
        cls.cases = load_json(cls.data_dir / "witness-cases.json")
        cls.protocol = load_json(cls.data_dir / "protocol.json")
        cls.design = load_json(cls.data_dir / "study-design.json")
        cls.frontend_validation = load_json(ROOT / "results/source-frontend/summary.json")
        cls.records = validate_candidates(cls.candidates)
        cls.by = {row["id"]: row for row in cls.records}

    def evaluate(self, *, reference_count: int = 61):
        predictions, outcomes, _ = freeze_predictions(self.candidates, self.cases, self.protocol)
        return evaluate_predictions(
            self.candidates,
            self.labels,
            self.cases,
            self.protocol,
            self.design,
            predictions,
            outcomes,
            reference_count,
            self.frontend_validation,
        )

    def test_all_input_schemas_validate(self):
        validate_protocol(self.protocol, 32)
        validate_witness_cases(self.cases, set(self.by))
        validate_labels(self.labels, {key: value["group"] for key, value in self.by.items()})
        validate_study_design(self.design)

    def test_candidate_file_is_label_free(self):
        self.assertNotIn('"label"', json.dumps(self.candidates, sort_keys=True))
        self.assertEqual(len(self.records), 32)

    def test_label_file_is_exact_and_separate(self):
        labels = validate_labels(self.labels, {key: value["group"] for key, value in self.by.items()})
        self.assertEqual(len(labels), 32)
        self.assertEqual(sum(labels.values()), 16)

    def test_candidate_label_or_class_metadata_is_rejected(self):
        for field, value, reason in (
            ("label", 1, "candidate-label-leakage"),
            ("selection_source", "positive", "candidate-schema"),
        ):
            bad = copy.deepcopy(self.candidates)
            bad["records"][0][field] = value
            with self.assertRaisesRegex(Invalid, reason):
                validate_candidates(bad)
        bad = copy.deepcopy(self.candidates)
        bad["positive_source"] = {"path": "known-positive.csv"}
        with self.assertRaisesRegex(Invalid, "candidate-top-schema"):
            validate_candidates(bad)

    def test_candidate_ids_are_neutral_and_hash_ordered(self):
        self.assertEqual([row["id"] for row in self.records], [f"U{i:03d}" for i in range(1, 33)])
        digests = []
        for row in self.records:
            self.assertRegex(row["id"], r"^U\d{3}$")
            digest = hashlib.sha256((row["commit"] + "\0" + row["filename"]).encode()).hexdigest()
            self.assertEqual(row["identity_digest"], digest)
            digests.append(digest)
        self.assertEqual(digests, sorted(digests))

    def test_candidate_type_and_length_limits(self):
        variants = []
        bad = copy.deepcopy(self.candidates); bad["records"][0]["message"] = 3; variants.append(bad)
        bad = copy.deepcopy(self.candidates); bad["records"][0]["filename"] = "../escape"; variants.append(bad)
        bad = copy.deepcopy(self.candidates); bad["records"][0]["commit"] = "not-a-sha"; variants.append(bad)
        bad = copy.deepcopy(self.candidates); bad["records"][0]["patch_excerpt"] = "x" * 20000; variants.append(bad)
        for bad in variants:
            with self.assertRaises(Invalid):
                validate_candidates(bad)

    def test_source_manifest_has_no_label_columns(self):
        with (self.data_dir / "source-manifest.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 32)
        self.assertFalse({"label", "selection_source"} & set(rows[0]))
        self.assertTrue(all(re.fullmatch(r"U\d{3}", row["id"]) for row in rows))

    def test_source_manifest_binds_candidates_and_derived_cases(self):
        with (self.data_dir / "source-manifest.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        by_id = {row["id"]: row for row in rows}
        expected_cases = {case["record"]: case["id"] for case in self.cases["cases"]}
        self.assertEqual(set(by_id), set(self.by))
        for unit_id, candidate in self.by.items():
            row = by_id[unit_id]
            self.assertEqual(row["identity_digest"], candidate["identity_digest"])
            self.assertEqual(row["commit"], candidate["commit"])
            self.assertEqual(row["group"], candidate["group"])
            self.assertEqual(row["filename"], candidate["filename"])
            self.assertEqual(row["witness_case"], expected_cases.get(unit_id, ""))

    def test_label_group_mismatch_and_duplicate_are_rejected(self):
        bad = copy.deepcopy(self.labels)
        bad["labels"][0]["group"] = "not-the-candidate-group"
        with self.assertRaisesRegex(Invalid, "label-group-binding"):
            validate_labels(bad, {key: value["group"] for key, value in self.by.items()})
        bad = copy.deepcopy(self.labels)
        bad["labels"][1]["id"] = bad["labels"][0]["id"]
        with self.assertRaisesRegex(Invalid, "label-value"):
            validate_labels(bad, {key: value["group"] for key, value in self.by.items()})

    def test_json_gate_rejects_duplicate_depth_size_and_nonfinite(self):
        samples = [
            b'{"a":1,"a":2}',
            b'{"a":NaN}',
            b'[' * 70 + b'0' + b']' * 70,
            b' ' * (1_048_576 + 1),
            b'\xff',
        ]
        with tempfile.TemporaryDirectory(dir=ROOT / "results") as directory:
            path = Path(directory) / "input.json"
            for raw in samples:
                path.write_bytes(raw)
                with self.assertRaises(Invalid):
                    load_json(path)
            path.write_text('{"a":-3,"b":0.125}', encoding="utf-8")
            self.assertEqual(load_json(path), {"a": -3, "b": 0.125})
            path.write_text('[1,{"x":2}]', encoding="utf-8")
            self.assertEqual(load_json_value(path), [1, {"x": 2}])
            with self.assertRaisesRegex(Invalid, "json-root"):
                load_json(path)

    def test_expression_static_types_are_enforced(self):
        variables = {"x"}
        self.assertEqual(validate_expr(["lt", ["var", "x"], ["const", 0]], variables), "bool")
        invalid = [
            ["and", ["const", 1], ["const", 0]],
            ["not", ["const", 1]],
            ["add", ["lt", ["var", "x"], ["const", 0]], ["const", 1]],
            ["eq", ["lt", ["var", "x"], ["const", 0]], ["const", 1]],
        ]
        for expression in invalid:
            with self.assertRaises(Invalid):
                validate_expr(expression, variables)

    def test_witness_case_schema_rejects_duplicate_and_bad_root(self):
        bad = copy.deepcopy(self.cases)
        bad["cases"][1]["id"] = bad["cases"][0]["id"]
        with self.assertRaisesRegex(Invalid, "case-id"):
            validate_witness_cases(bad, set(self.by))
        bad = copy.deepcopy(self.cases)
        predicate_index = next(index for index, case in enumerate(bad["cases"]) if case["kind"] == "predicate")
        bad["cases"][predicate_index]["condition"] = ["const", 1]
        with self.assertRaisesRegex(Invalid, "condition-root-type"):
            validate_witness_cases(bad, set(self.by))

    def test_exact_integer_division_at_64_bit_boundaries(self):
        values = [INT64_MIN, INT64_MIN + 1, -10, -3, -1, 0, 1, 3, 10, INT64_MAX]
        for a in values:
            for b in values:
                if b == 0:
                    continue
                expression = ["div", ["var", "a"], ["var", "b"]]
                env = {"a": a, "b": b}
                magnitude = abs(a) // abs(b)
                expected = -magnitude if (a < 0) != (b < 0) else magnitude
                if expected < INT64_MIN or expected > INT64_MAX:
                    with self.assertRaises(Invalid):
                        producer_eval(expression, env, [])
                    with self.assertRaises(Invalid):
                        replay(expression, env)
                else:
                    produced_trace = []
                    produced = producer_eval(expression, env, produced_trace)
                    replayed, replay_trace = replay(expression, env)
                    self.assertEqual(produced, expected)
                    self.assertEqual((produced, produced_trace), (replayed, replay_trace))
        # This quotient was miscomputed by int(a / b) because a / b is a float.
        expression = ["div", ["const", INT64_MAX], ["const", 3]]
        self.assertEqual(producer_eval(expression, {}, []), 3074457345618258602)

    def test_all_owned_source_witnesses_replay(self):
        for case in self.cases["cases"]:
            cert = make_certificate(case, self.by[case["record"]])
            self.assertEqual(check_certificate(case, self.by[case["record"]], cert), (True, "accepted"))

    def test_producer_and_checker_agree_on_retained_cases(self):
        for case in self.cases["cases"]:
            if case["kind"] != "predicate":
                continue
            for key in ("condition", "hazard"):
                trace = []
                produced = producer_eval(case[key], case["assignment"], trace)
                replayed, replay_trace = replay(case[key], case["assignment"])
                self.assertEqual((produced, trace), (replayed, replay_trace))

    def test_certificate_mutations_are_rejected(self):
        case = next(case for case in self.cases["cases"] if case["kind"] == "predicate")
        record = self.by[case["record"]]
        cert = make_certificate(case, record)
        variants = []
        changed = copy.deepcopy(cert)
        assignment_key = next(iter(changed["assignment"]))
        changed["assignment"][assignment_key] += 1
        variants.append(changed)
        changed = copy.deepcopy(cert); changed["condition"] = not cert["condition"]; variants.append(changed)
        changed = copy.deepcopy(cert); changed["condition_trace"] = []; variants.append(changed)
        changed = copy.deepcopy(cert); changed["source_tokens"][0] = "not in source"; variants.append(changed)
        changed = copy.deepcopy(cert); changed["extra"] = 1; variants.append(changed)
        for variant in variants:
            self.assertFalse(check_certificate(case, record, variant)[0])

    def test_prediction_freeze_contains_no_labels(self):
        predictions, outcomes, certificates = freeze_predictions(self.candidates, self.cases, self.protocol)
        self.assertFalse(predictions["label_fields_present"])
        self.assertTrue(all("label" not in row for row in predictions["records"]))
        self.assertEqual(len(predictions["records"]), 32)
        self.assertEqual(len(outcomes), 32)
        self.assertEqual(len(certificates), 10)
        validate_predictions(predictions, self.candidates, self.cases, self.protocol)
        validate_outcomes(outcomes, predictions["records"])

    def test_prediction_bindings_cover_candidates_cases_and_protocol(self):
        predictions, outcomes, _ = freeze_predictions(self.candidates, self.cases, self.protocol)
        variants = [
            (copy.deepcopy(self.candidates), self.cases, self.protocol, "prediction-candidate-binding"),
            (self.candidates, copy.deepcopy(self.cases), self.protocol, "prediction-case-binding"),
            (self.candidates, self.cases, copy.deepcopy(self.protocol), "prediction-protocol-binding"),
        ]
        variants[0][0]["records"][0]["message"] += " changed"
        variants[1][1]["cases"][0]["source_tokens"][0] += " changed"
        variants[2][2]["witness_bonus"] = 5.0
        for candidates, cases, protocol, reason in variants:
            with self.assertRaisesRegex(Invalid, reason):
                validate_predictions(predictions, candidates, cases, protocol)
        bad_outcomes = copy.deepcopy(outcomes)
        bad_outcomes[0]["accepted"] = 1 - bad_outcomes[0]["accepted"]
        with self.assertRaisesRegex(Invalid, "outcome-prediction-binding"):
            validate_outcomes(bad_outcomes, predictions["records"])

    def test_frontend_rederives_retained_cases(self):
        derived, diagnostics = derive_witness_document(self.candidates)
        self.assertEqual(derived, self.cases)
        self.assertEqual(len(derived["cases"]), 10)
        self.assertEqual(sum(row["reason"].startswith("recognized-") for row in diagnostics), 10)
        self.assertTrue(derived["construction"]["automatic_source_frontend"])
        self.assertTrue(derived["construction"]["source_translation_validated"])

    def test_frontend_validation_is_hash_bound_and_fail_closed(self):
        summary, _, _, readiness = self.evaluate()
        status = {row["id"]: row["status"] for row in readiness["gates"]}
        self.assertEqual(status["automatic_source_frontend"], "pass")
        self.assertNotIn("automatic_source_frontend", summary["failed_readiness_gates"])
        bad = copy.deepcopy(self.frontend_validation)
        bad["candidate_hash"] = "0" * 64
        predictions, outcomes, _ = freeze_predictions(self.candidates, self.cases, self.protocol)
        changed, _, _, changed_readiness = evaluate_predictions(
            self.candidates, self.labels, self.cases, self.protocol, self.design,
            predictions, outcomes, 61, bad
        )
        self.assertIn("automatic_source_frontend", changed["failed_readiness_gates"])
        changed_status = {row["id"]: row["status"] for row in changed_readiness["gates"]}
        self.assertEqual(changed_status["automatic_source_frontend"], "fail")

    def test_frontend_mutation_breaks_derivation_binding(self):
        bad_candidates = copy.deepcopy(self.candidates)
        target = next(row for row in bad_candidates["records"] if row["id"] == "U004")
        target["patch_excerpt"] = target["patch_excerpt"].replace("pad_width_ >= 0", "pad_width_ >= -1")
        derived, _ = derive_witness_document(bad_candidates)
        self.assertNotEqual(derived, self.cases)

    def test_independent_frontend_parser_agrees_on_retained_tokens(self):
        for case in self.cases["cases"]:
            if case["kind"] != "predicate":
                continue
            operator = " && " if case["frontend_rule"] == "require" else " || "
            raw = operator.join(f"({token})" for token in case["source_tokens"])
            primary = parse_expression(raw)
            self.assertEqual(primary, case["condition"])
            self.assertEqual(
                bool(reference_frontend_evaluate(raw, case["assignment"])),
                bool(producer_eval(case["condition"], case["assignment"], [])),
            )

    def test_evaluation_is_deterministic(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first, second)

    def test_microcohort_metrics_and_machine_derived_gate(self):
        summary, rows, ablations, readiness = self.evaluate()
        self.assertEqual(summary["candidate_units"], 32)
        self.assertEqual(summary["commit_groups"], 26)
        self.assertEqual(summary["accepted_source_witnesses"], 10)
        self.assertAlmostEqual(summary["unit_witness_coverage"], 0.625)
        self.assertEqual(summary["unit_witness_coverage_fraction"], "10/16")
        self.assertAlmostEqual(summary["group_witness_coverage"], 1.0)
        self.assertEqual(summary["group_witness_coverage_fraction"], "10/10")
        self.assertEqual(summary["accepted_positive_units"], 10)
        self.assertEqual(summary["accepted_positive_commit_groups"], 10)
        self.assertEqual(summary["formal_h1_decision"], "not-testable-with-label-selected-nontemporal-cohort")
        self.assertEqual(summary["main_study_readiness"], "failed")
        self.assertIn("temporal_holdout", summary["failed_readiness_gates"])
        self.assertEqual(len(rows), 32)
        self.assertEqual(len(ablations), 5)
        self.assertTrue(all(row["basis"] == "machine-derived-fail-closed" for row in readiness["gates"]))

    def test_readiness_cannot_be_forged_by_evidence_status(self):
        predictions, outcomes, _ = freeze_predictions(self.candidates, self.cases, self.protocol)
        design = copy.deepcopy(self.design)
        for row in design["evidence"]:
            row["status"] = "pass"
        summary, _, _, readiness = evaluate_predictions(
            self.candidates,
            self.labels,
            self.cases,
            self.protocol,
            design,
            predictions,
            outcomes,
            61,
            self.frontend_validation,
        )
        self.assertEqual(summary["main_study_readiness"], "failed")
        self.assertIn("candidate_selection_independent_of_labels", readiness["failed_readiness_gates"])
        self.assertNotIn("automatic_source_frontend", readiness["failed_readiness_gates"])

    def test_reference_gate_is_fail_closed(self):
        summary, _, _, readiness = self.evaluate(reference_count=54)
        self.assertIn("reference_count_at_least_55", summary["failed_readiness_gates"])
        status = {row["id"]: row["status"] for row in readiness["gates"]}
        self.assertEqual(status["reference_count_at_least_55"], "fail")

    def test_bonus_ablation_includes_frozen_value(self):
        summary, _, ablations, _ = self.evaluate()
        bonuses = [row["witness_bonus"] for row in ablations]
        self.assertEqual(bonuses, [0.0, 1.0, 2.0, 4.0, 8.0])
        frozen = next(row for row in ablations if row["witness_bonus"] == 4.0)
        self.assertAlmostEqual(frozen["precision_at_20"], summary["metrics"]["validated"]["precision_at_20"])

    def test_freeze_cli_runs_without_any_label_file(self):
        results_root = ROOT / "results"
        results_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=results_root) as directory:
            directory_path = Path(directory)
            data = directory_path / "data"
            data.mkdir()
            for name in ("candidates.json", "witness-cases.json", "protocol.json"):
                shutil.copy2(self.data_dir / name, data / name)
            output = directory_path / "frozen"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "freeze_public_study.py"),
                    "--data-dir",
                    str(data),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "predictions-frozen.json").exists())
            self.assertFalse((data / "labels.json").exists())


if __name__ == "__main__":
    unittest.main()
