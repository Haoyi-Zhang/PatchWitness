#!/usr/bin/env python3
"""Fail-closed consistency checks for the retained canonical results.

This command does not rerun the full experiment or bootstrap.  It reconciles the
retained finite, closure, and public-audit packets with their independently
checkable schemas, tables, certificates, and declared campaign accounting.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(ROOT / "src"))

from checker import check as finite_check  # noqa: E402
from producer import Fuel  # noqa: E402
from public_study import (  # noqa: E402
    canonical_hash,
    check_certificate,
    load_json,
    load_json_value,
    validate_candidates,
    validate_outcomes,
    validate_predictions,
    validate_protocol,
    validate_witness_cases,
)
from source_frontend import derive_witness_document  # noqa: E402

MAX_RESULT_BYTES = 4 * 1024 * 1024


class VerificationError(RuntimeError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise VerificationError(reason)


def read_json(path: Path, root_type: type | tuple[type, ...]) -> Any:
    raw = path.read_bytes()
    require(len(raw) <= MAX_RESULT_BYTES, f"oversized:{path.relative_to(ROOT)}")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            require(key not in out, f"duplicate-json-key:{path.relative_to(ROOT)}")
            out[key] = value
        return out

    def reject_constant(value: str) -> Any:
        raise VerificationError(f"nonfinite-json:{path.relative_to(ROOT)}:{value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid-json:{path.relative_to(ROOT)}") from exc
    require(isinstance(value, root_type), f"json-root:{path.relative_to(ROOT)}")
    return value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None, f"csv-header:{path.relative_to(ROOT)}")
        rows = list(reader)
    require(all(None not in row for row in rows), f"csv-width:{path.relative_to(ROOT)}")
    return list(reader.fieldnames), rows


def verify_finite() -> dict[str, int]:
    directory = RESULTS / "finite-check"
    summary = read_json(directory / "summary.json", dict)
    cases = read_json(directory / "cases.json", list)
    certificates = read_json(directory / "certificates.json", list)
    fields, rows = read_csv(directory / "cases.csv")
    expected_fields = [
        "case", "family", "width", "assignments", "repair", "regression",
        "both-safe", "both-fault", "search_assignments",
        "certificate_accepted", "obligations",
    ]
    require(fields == expected_fields, "finite-csv-schema")
    require(len(cases) == len(rows) == 25, "finite-case-count")
    require(len(certificates) == 13, "finite-certificate-count")

    case_by_id: dict[str, dict[str, Any]] = {}
    for item, row in zip(cases, rows, strict=True):
        require(isinstance(item, dict) and set(item) == {"case", "family"}, "finite-case-row")
        case = item["case"]
        require(isinstance(case, dict) and case.get("id") == row["case"], "finite-case-binding")
        require(item["family"] == row["family"], "finite-family-binding")
        require(case["id"] not in case_by_id, "finite-duplicate-case")
        case_by_id[case["id"]] = case

    replay_fuel = Fuel(20_000)
    accepted = 0
    for certificate in certificates:
        require(isinstance(certificate, dict), "finite-certificate-row")
        case_id = certificate.get("case", {}).get("id")
        require(case_id in case_by_id, "finite-certificate-case")
        ok, reason = finite_check(case_by_id[case_id], certificate, replay_fuel)
        require(ok, f"finite-certificate-replay:{case_id}:{reason}")
        accepted += 1

    numeric_fields = ("assignments", "repair", "regression", "both-safe", "both-fault")
    totals = {field: sum(int(row[field]) for row in rows) for field in numeric_fields}
    expected = {
        "case_count": 25,
        "assignments": 3712,
        "repair": 424,
        "regression": 242,
        "both-safe": 2990,
        "both-fault": 56,
        "accepted_certificates": 13,
        "mismatches": 0,
        "semantic_mismatches": 0,
        "obligations": 90517,
        "exit_status": 0,
    }
    for key, value in expected.items():
        require(summary.get(key) == value, f"finite-summary:{key}")
    for key, value in totals.items():
        require(summary[key] == value, f"finite-csv-total:{key}")
    require(accepted == summary["accepted_certificates"], "finite-replay-count")
    require(
        sum(int(row["certificate_accepted"]) for row in rows) == accepted,
        "finite-csv-certificate-count",
    )
    unit = summary.get("unit_tests")
    require(
        isinstance(unit, dict)
        and unit.get("tests_run") == 10
        and unit.get("failures") == 0
        and unit.get("errors") == 0
        and unit.get("tampered_certificates") == 20
        and unit.get("ranking_labelings") == 64
        and unit.get("arithmetic_assignments") == 576,
        "finite-unit-summary",
    )
    return {"cases": len(cases), "certificates_replayed": accepted, "assignments": totals["assignments"]}


def verify_pilot() -> dict[str, int]:
    directory = RESULTS / "pilot"
    summary = read_json(directory / "summary.json", dict)
    _, rows = read_csv(directory / "cases.csv")
    expected = {
        "case_count": 1,
        "assignments": 64,
        "repair": 8,
        "regression": 8,
        "both-safe": 48,
        "both-fault": 0,
        "accepted_certificates": 1,
        "mismatches": 0,
        "semantic_mismatches": 0,
        "obligations": 1552,
        "exit_status": 0,
    }
    for key, value in expected.items():
        require(summary.get(key) == value, f"pilot-summary:{key}")
    require(len(rows) == 1 and rows[0]["family"] == "mixed-change", "pilot-row")
    return {"cases": 1, "assignments": 64}


def verify_closure() -> dict[str, int]:
    summary = read_json(RESULTS / "closure-checks" / "summary.json", dict)
    require(summary.get("schema") == "rbw-closure-checks-v1", "closure-schema")
    require(summary.get("mismatches") == 0 and summary.get("exit_status") == 0, "closure-status")
    require(summary.get("obligations") == 19834, "closure-obligations")
    candidate = summary.get("candidate_frame_ambiguity")
    grouping = summary.get("grouping_sensitivity")
    paired = summary.get("paired_top_k_identity")
    require(
        isinstance(candidate, dict)
        and candidate.get("constructed_full_frames") == 40
        and candidate.get("full_window_precision_extremes") == [0.0, 1.0]
        and candidate.get("mismatches") == 0,
        "closure-candidate-frame",
    )
    require(
        isinstance(grouping, dict)
        and grouping.get("configurations") == 19683
        and grouping.get("both_gap_directions_observed") is True
        and grouping.get("mismatches") == 0
        and grouping.get("group_minus_unit_extreme", {}).get("gap_fraction") == "5/6"
        and grouping.get("unit_minus_group_extreme", {}).get("gap_fraction") == "5/12",
        "closure-grouping",
    )
    require(
        isinstance(paired, dict)
        and paired.get("labelings") == 64
        and paired.get("sharp_label_count_checks") == 7
        and paired.get("mismatches") == 0,
        "closure-paired",
    )
    return {"obligations": 19834, "grouping_configurations": 19683, "paired_labelings": 64}


def verify_frontend() -> dict[str, Any]:
    data = ROOT / "data" / "public-study"
    candidates = load_json(data / "candidates.json")
    retained = load_json(data / "witness-cases.json")
    derived, diagnostics = derive_witness_document(candidates)
    require(derived == retained, "frontend-retained-binding")
    summary = read_json(RESULTS / "source-frontend" / "summary.json", dict)
    mismatches = read_json(RESULTS / "source-frontend" / "mismatches.json", list)
    expected = {
        "schema": "rbw-source-frontend-validation-v1",
        "automatic_source_frontend": True,
        "source_translation_validated": True,
        "grammar": "guard-expressions-v1",
        "candidate_units": 32,
        "recognized_cases": 10,
        "predicate_cases": 9,
        "widening_cases": 1,
        "unsupported_units": 22,
        "unique_assignments_per_predicate": 100,
        "semantic_obligations": 900,
        "primary_parser": "Pratt",
        "independent_parser": "shunting-yard",
        "c11_oracle": "pass",
        "mismatches": 0,
        "status": "pass",
    }
    for key, value in expected.items():
        require(summary.get(key) == value, f"frontend-summary:{key}")
    require(summary.get("candidate_hash") == canonical_hash(candidates), "frontend-candidate-hash")
    require(summary.get("witness_case_hash") == canonical_hash(retained), "frontend-case-hash")
    require(mismatches == [], "frontend-mismatch-packet")
    recognized = [row for row in diagnostics if row.get("reason", "").startswith("recognized-")]
    require(len(recognized) == 10, "frontend-diagnostics")
    require(
        summary.get("case_counts")
        == {case["record"]: 100 for case in retained["cases"] if case["kind"] == "predicate"},
        "frontend-case-counts",
    )
    return {
        "candidate_units": 32,
        "recognized_cases": 10,
        "semantic_obligations": 900,
        "mismatches": 0,
    }


def verify_public() -> dict[str, Any]:
    data = ROOT / "data" / "public-study"
    candidates = load_json(data / "candidates.json")
    cases = load_json(data / "witness-cases.json")
    protocol = load_json(data / "protocol.json")
    candidate_rows = validate_candidates(candidates)
    validate_protocol(protocol, len(candidate_rows))
    case_rows = validate_witness_cases(cases, {row["id"] for row in candidate_rows})
    candidate_by_id = {row["id"]: row for row in candidate_rows}
    case_by_record = {row["record"]: row for row in case_rows}

    directory = RESULTS / "public-study"
    frozen = directory / "frozen"
    evaluation = directory / "evaluation"
    predictions = load_json(frozen / "predictions-frozen.json")
    outcomes = load_json_value(frozen / "outcomes.json")
    certificates = load_json_value(frozen / "certificates.json")
    prediction_rows = validate_predictions(predictions, candidates, cases, protocol)
    validate_outcomes(outcomes, prediction_rows)
    require(isinstance(certificates, list) and len(certificates) == 10, "public-certificate-count")
    for certificate in certificates:
        record = certificate.get("record") if isinstance(certificate, dict) else None
        require(record in case_by_record and record in candidate_by_id, "public-certificate-binding")
        ok, reason = check_certificate(case_by_record[record], candidate_by_id[record], certificate)
        require(ok, f"public-certificate-replay:{record}:{reason}")

    freeze_summary = load_json(frozen / "freeze-summary.json")
    require(
        freeze_summary.get("schema") == "rbw-freeze-summary-v2"
        and freeze_summary.get("candidate_units") == 32
        and freeze_summary.get("accepted_certificates") == 10
        and freeze_summary.get("frontend_derived_cases") == 10
        and freeze_summary.get("child_processes") == 0
        and freeze_summary.get("exit_status") == 0,
        "public-freeze-summary",
    )

    summary = load_json(evaluation / "summary.json")
    readiness = load_json(evaluation / "readiness.json")
    ablations = load_json_value(evaluation / "ablations.json")
    run_summary = load_json(directory / "run-summary.json")
    require(isinstance(ablations, list) and ablations == summary.get("bonus_ablations"), "public-ablation-binding")
    expected = {
        "schema": "rbw-public-summary-v5",
        "candidate_units": 32,
        "commit_groups": 26,
        "positive_units": 16,
        "accepted_positive_units": 10,
        "positive_commit_groups": 10,
        "accepted_positive_commit_groups": 10,
        "accepted_source_witnesses": 10,
        "unit_witness_coverage_fraction": "10/16",
        "group_witness_coverage_fraction": "10/10",
        "validated_minus_syntax_at_20": 0.0,
        "unvalidated_minus_syntax_at_20": 0.05,
        "validated_top20_symmetric_difference": [],
        "unvalidated_top20_symmetric_difference": ["U014", "U021"],
        "bootstrap_replicates": 4000,
        "obligations_this_analysis": 4256,
        "main_study_readiness": "failed",
        "formal_h1_decision": "not-testable-with-label-selected-nontemporal-cohort",
        "formal_h2_decision": "not-testable-as-population-coverage",
        "reference_verification_count": 61,
        "freeze_and_evaluation_are_separate_processes": True,
        "evaluation_process_read_labels": True,
        "exit_status": 0,
    }
    for key, value in expected.items():
        require(summary.get(key) == value, f"public-summary:{key}")
    metrics = summary.get("metrics", {})
    require(
        metrics.get("syntax", {}).get("precision_at_20") == 0.7
        and metrics.get("unvalidated", {}).get("precision_at_20") == 0.75
        and metrics.get("validated", {}).get("precision_at_20") == 0.7,
        "public-metrics",
    )
    require(
        summary.get("typed_outcomes") == {"accepted": 10, "unvalidated-only": 3, "unsupported": 19},
        "public-outcomes",
    )
    require(
        summary.get("cluster_bootstrap_95", {}).get("validated_minus_syntax") == [0.0, 0.0]
        and summary.get("cluster_bootstrap_95", {}).get("unvalidated_minus_syntax") == [0.0, 0.10000000000000009],
        "public-bootstrap",
    )
    failed = [
        "candidate_selection_independent_of_labels",
        "complete_repository_time_window",
        "labels_sealed_before_method_development",
        "strongest_published_same_budget_baseline",
        "temporal_holdout",
    ]
    require(summary.get("failed_readiness_gates") == failed, "public-failed-gates")
    require(readiness.get("failed_readiness_gates") == failed, "public-readiness-binding")
    require(readiness.get("main_study_readiness") == "failed", "public-readiness-status")
    require(run_summary.get("orchestrator_child_processes") == 2, "public-process-count")
    for key, value in summary.items():
        require(run_summary.get(key) == value, f"public-run-summary:{key}")

    manifest_fields, manifest_rows = read_csv(data / "source-manifest.csv")
    require(
        manifest_fields == ["id", "identity_digest", "commit", "group", "filename", "witness_case", "commit_url"],
        "public-manifest-schema",
    )
    require(len(manifest_rows) == 32 and len({row["id"] for row in manifest_rows}) == 32, "public-manifest-count")
    candidate_by_id = {row["id"]: row for row in candidates["records"]}
    case_by_record = {case["record"]: case["id"] for case in cases["cases"]}
    for row in manifest_rows:
        candidate = candidate_by_id.get(row["id"])
        require(candidate is not None, "public-manifest-candidate")
        require(
            row["identity_digest"] == candidate["identity_digest"]
            and row["commit"] == candidate["commit"]
            and row["group"] == candidate["group"]
            and row["filename"] == candidate["filename"]
            and row["witness_case"] == case_by_record.get(row["id"], ""),
            "public-manifest-binding",
        )

    score_fields, score_rows = read_csv(evaluation / "scores.csv")
    require(len(score_rows) == 32 and len({row["id"] for row in score_rows}) == 32, "public-score-count")
    require("label" in score_fields and {row["label"] for row in score_rows} <= {"0", "1"}, "public-score-labels")
    return {
        "units": 32,
        "certificates_replayed": 10,
        "syntax_p20": 0.7,
        "unvalidated_p20": 0.75,
        "validated_p20": 0.7,
    }


def verify_references() -> dict[str, int]:
    verification_fields, verification = read_csv(ROOT / "reference-verification.csv")
    screening_fields, screening = read_csv(ROOT / "literature-screening.csv")
    calibration_fields, calibration = read_csv(ROOT / "literature-calibration.csv")
    require(len(verification) == len(screening) == 61, "reference-count")
    require(len(calibration) == 22, "calibration-count")
    require(
        verification_fields
        == ["citation_key", "authoritative_url", "persistent_id", "metadata_status", "content_check", "checked_on", "notes"],
        "reference-verification-schema",
    )
    require("citation_key" in screening_fields, "reference-screening-schema")
    require(
        calibration_fields
        == [
            "citation_key", "calibration_group", "full_text_source", "selection_rationale",
            "motivating_problem", "general_principle", "proof_or_performance_argument",
            "practical_connection", "evaluation_breadth", "artifact_strength",
            "narrative_sequence", "section_pattern", "bibliography_role",
            "figure_table_role", "project_delta", "checked_on",
        ],
        "calibration-schema",
    )
    verification_keys = {row["citation_key"] for row in verification}
    screening_keys = {row["citation_key"] for row in screening}
    require(len(verification_keys) == 61 and verification_keys == screening_keys, "reference-key-binding")
    require(
        all(
            row["metadata_status"] == "verified"
            and row["content_check"] in {"full-text", "abstract", "metadata-only"}
            and row["persistent_id"]
            and row["authoritative_url"]
            for row in verification
        ),
        "reference-verification-status",
    )
    depths: dict[str, int] = {}
    for row in verification:
        depths[row["content_check"]] = depths.get(row["content_check"], 0) + 1
    require(depths == {"full-text": 22, "abstract": 33, "metadata-only": 6}, "reference-depths")
    groups: dict[str, int] = {}
    full_text_keys = {row["citation_key"] for row in verification if row["content_check"] == "full-text"}
    for row in calibration:
        groups[row["calibration_group"]] = groups.get(row["calibration_group"], 0) + 1
        require(row["citation_key"] in full_text_keys, "calibration-depth-binding")
        require(row["full_text_source"].startswith("https://"), "calibration-source")
        require(all(value.strip() for value in row.values()), "calibration-completeness")
    require(groups == {"closest": 12, "influential": 5, "adjacent": 5}, "calibration-groups")
    return {**depths, "calibrated_full_papers": 22}


def verify_campaign() -> dict[str, int]:
    campaign = read_json(RESULTS / "campaign.json", dict)
    require(campaign.get("overall_obligation_ceiling") == 250000, "campaign-ceiling")
    require(campaign.get("total_counted_obligations_through_clean_reproduction") == 249990, "campaign-total")
    require(campaign.get("remaining_to_overall_ceiling") == 10, "campaign-remaining")
    require(campaign.get("closure_check_campaign", {}).get("counted_obligations") == 39668, "campaign-closure")
    require(campaign.get("public_microcohort_campaign", {}).get("counted_obligations") == 21280, "campaign-public")
    require(campaign.get("finite_validation_campaign", {}).get("cumulative_counted_obligations") == 187242, "campaign-finite")
    require(campaign.get("source_frontend_validation_campaign", {}).get("counted_obligations") == 1800, "campaign-frontend")

    def check_paths(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "raw_result" and child is not None:
                    require(isinstance(child, str), "campaign-raw-result-type")
                    require((ROOT / child).is_file(), f"campaign-missing-raw-result:{child}")
                else:
                    check_paths(child)
        elif isinstance(value, list):
            for child in value:
                check_paths(child)

    check_paths(campaign)
    return {"total": 249990, "remaining": 10}


def verify_reproduction() -> dict[str, int]:
    summary = read_json(RESULTS / "reproduction/summary.json", dict)
    require(summary.get("schema") == "rbw-clean-reproduction-v2", "reproduction-schema")
    require(summary.get("status") == "pass", "reproduction-status")
    require(summary.get("tests") == {"run": 42, "failures": 0, "errors": 0}, "reproduction-tests")
    require(summary.get("frontend", {}).get("semantic_obligations") == 900, "reproduction-frontend")
    require(summary.get("frontend", {}).get("mismatches") == 0, "reproduction-frontend-mismatch")
    require(summary.get("closure", {}).get("obligations") == 19834, "reproduction-closure")
    require(summary.get("closure", {}).get("mismatches") == 0, "reproduction-closure-mismatch")
    require(summary.get("public", {}).get("obligations") == 4256, "reproduction-public")
    require(summary.get("public", {}).get("failed_readiness_gates") == [
        "candidate_selection_independent_of_labels",
        "complete_repository_time_window",
        "labels_sealed_before_method_development",
        "strongest_published_same_budget_baseline",
        "temporal_holdout",
    ], "reproduction-readiness")
    require(summary.get("pilot", {}).get("obligations") == 1552, "reproduction-pilot")
    test_log = (RESULTS / "reproduction/unit-tests.txt").read_text(encoding="utf-8")
    require("Ran 42 tests" in test_log and test_log.rstrip().endswith("OK"), "reproduction-test-log")
    return {"tests": 42, "frontend_obligations": 900, "closure_obligations": 19834}


def main() -> int:
    report = {
        "schema": "rbw-retained-result-verification-v1",
        "finite": verify_finite(),
        "pilot": verify_pilot(),
        "closure": verify_closure(),
        "frontend": verify_frontend(),
        "public": verify_public(),
        "references": verify_references(),
        "campaign": verify_campaign(),
        "reproduction": verify_reproduction(),
        "status": "pass",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError, VerificationError) as exc:
        print(json.dumps({"status": "fail", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
