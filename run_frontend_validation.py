#!/usr/bin/env python3
"""Cross-check extraction, parsing, and evaluation for restricted source evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from public_study import canonical_hash, load_json, producer_eval, replay, typed_equal  # noqa: E402
from source_frontend import (  # noqa: E402
    FrontendError, assignment_domain, ast_to_rpn, derive_evidence_document,
    evaluate as frontend_evaluate, parse_expression, variables,
)
from source_frontend_reference import evaluate as reference_evaluate, parse_ast as reference_parse_ast  # noqa: E402

SAMPLES_PER_GUARD = 100
SEED = 20211119


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _raw_expression(case: dict[str, Any]) -> str:
    operator = " && " if case["frontend_rule"] == "require" else " || "
    return operator.join(f"({token})" for token in case["source_tokens"])


def _random_assignment(names: list[str], domains: dict[str, list[int]], rng: random.Random) -> dict[str, int]:
    return {name: rng.choice(domains[name]) for name in names}


def _find_opposite(case: dict[str, Any], domains: dict[str, list[int]]) -> dict[str, int]:
    names = list(domains)
    # Small deterministic scan only for one opposite-branch witness; it does not
    # populate the full sample prefix.
    import itertools
    for values in itertools.product(*(domains[name] for name in names)):
        assignment = dict(zip(names, values, strict=True))
        try:
            if any(not bool(frontend_evaluate(expr, assignment)) for expr in case["context_preconditions"]):
                continue
            result = frontend_evaluate(case["guard"], assignment)
        except FrontendError:
            continue
        if type(result) is bool and result is not case["trigger_value"]:
            return assignment
    raise ValueError(f"no-opposite-branch:{case['id']}")


def _mandatory(case: dict[str, Any], domains: dict[str, list[int]]) -> list[tuple[str, dict[str, int]]]:
    rows: list[tuple[str, dict[str, int]]] = [("saved-assignment", dict(case["assignment"]))]
    rows.append(("opposite-truth-branch", _find_opposite(case, domains)))
    if case["id"] == "W03":
        rows.extend([
            ("boundary-65535", {"num_threads": 65535}),
            ("boundary-65536", {"num_threads": 65536}),
            ("boundary-65537", {"num_threads": 65537}),
        ])
    if case["id"] == "W10":
        rows.extend([
            ("zero-denominator-short-circuit", {"dim": 0, "prod": 1, "limit": 2**31 - 1}),
            ("actual-division-true", {"dim": 1, "prod": 1, "limit": 2**31 - 1}),
            ("actual-division-false", {"dim": 2, "prod": 2**31 - 1, "limit": 2**31 - 1}),
        ])
    return rows


def _assignments(case: dict[str, Any], count: int, seed: int) -> list[dict[str, Any]]:
    expressions = [case["guard"], *case["context_preconditions"]]
    domains = assignment_domain(expressions)
    names = list(domains)
    planned: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, int], ...]] = set()
    # Keep every named mandatory scenario even when two scenarios intentionally
    # reuse the same assignment (for example W10's opposite branch also
    # demonstrates an actually executed successful division).  Assignment-level
    # deduplication begins only for the seeded-random remainder.
    for class_name, assignment in _mandatory(case, domains):
        key = tuple(sorted(assignment.items()))
        seen.add(key)
        planned.append({"class": class_name, "assignment": assignment})
    # Only complete assignments inside the random domain count toward exhaustion;
    # mandatory scenarios may repeat a point or lie outside that domain.
    domain_values = {name: set(values) for name, values in domains.items()}
    domain_size = 1
    for values in domain_values.values():
        domain_size *= len(values)
    in_domain_seen = sum(
        len(key) == len(names) and all(
            name in domain_values and value in domain_values[name] for name, value in key
        )
        for key in seen
    )
    rng = random.Random(seed)
    attempts = 0
    while len(planned) < count and attempts < count * 500 and in_domain_seen < domain_size:
        attempts += 1
        assignment = _random_assignment(names, domains, rng)
        key = tuple(sorted(assignment.items()))
        if key in seen:
            continue
        seen.add(key); planned.append({"class": "seeded-random", "assignment": assignment})
        in_domain_seen += 1
    # If a tiny domain has fewer than count unique assignments, repeat only
    # after all unique points have been used, preserving the mandatory prefix.
    index = 0
    while len(planned) < count:
        clone = dict(planned[index % len(planned)])
        clone["class"] = "deterministic-repeat"
        planned.append(clone); index += 1
    return planned[:count]


def _parse_oracle(value: str) -> dict[str, Any] | None:
    if value == "ERR":
        return None
    if value.startswith("B:") and value[2:] in {"0", "1"}:
        return {"tag": "bool", "payload": value[2:] == "1"}
    if value.startswith("I:"):
        return {"tag": "int", "payload": int(value[2:])}
    raise ValueError(f"oracle-output:{value}")


def _run_c_oracle(lines: list[str], temporary_root: Path | None = None) -> tuple[list[str], str]:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("c11-compiler-unavailable")
    source = ROOT / "src/source_frontend_oracle.c"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(dir=temporary_root or ROOT / "results") as directory:
        binary = Path(directory) / ("oracle.exe" if sys.platform == "win32" else "oracle")
        subprocess.run(
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", str(source), "-o", str(binary)],
            check=True, cwd=ROOT, text=True, capture_output=True, timeout=20,
        )
        completed = subprocess.run(
            [str(binary)], input="\n".join(lines) + "\n", text=True,
            capture_output=True, check=True, timeout=20,
        )
    return completed.stdout.splitlines(), source_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT) or out == ROOT:
        parser.error("output must be a new directory within the artifact root")
    start_cpu = time.process_time_ns(); start_wall = time.monotonic_ns()

    candidates = load_json(ROOT / "data/public-study/candidates.json")
    retained = load_json(ROOT / "data/public-study/source-evidence-cases.json")
    derived = derive_evidence_document(candidates)
    if derived != retained:
        raise ValueError("source-evidence-not-derived-from-real-diff-context")

    guard_cases = [case for case in retained["cases"] if case["kind"] == "guard-trigger"]
    widening_cases = [case for case in retained["cases"] if case["kind"] == "source-difference"]
    assignments_packet: list[dict[str, Any]] = []
    oracle_lines: list[str] = []
    expected_oracle: list[dict[str, Any] | None] = []
    python_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for case_index, case in enumerate(guard_cases):
        raw = _raw_expression(case)
        # Parsing independence: primary Pratt AST must match retained AST;
        # reference parser is independently implemented and compared by value.
        if parse_expression(raw) != case["guard"]:
            mismatches.append({"case": case["id"], "stage": "primary-parse-binding"})
        reference_parse_ast(raw)  # must parse; structure is intentionally different
        planned = _assignments(case, SAMPLES_PER_GUARD, SEED + case_index)
        for sample_index, item in enumerate(planned):
            assignment = item["assignment"]
            assignments_packet.append({"case": case["id"], "sample": sample_index, "class": item["class"], "assignment": assignment})
            primary = frontend_evaluate(case["guard"], assignment)
            reference = reference_evaluate(raw, assignment)
            producer_trace: list[list[Any]] = []
            produced = producer_eval(case["guard"], assignment, producer_trace)
            replayed, replay_trace = replay(case["guard"], assignment)
            oracle_lines.append(" ".join(ast_to_rpn(case["guard"], assignment)))
            expected_oracle.append(produced)
            row = {
                "case": case["id"], "sample": sample_index, "class": item["class"],
                "assignment": assignment, "primary": primary, "reference": reference,
                "produced": produced, "replayed": replayed,
                "producer_trace": producer_trace, "replay_trace": replay_trace,
            }
            python_rows.append(row)
            if type(primary) is not bool or type(reference) is not bool or primary != reference or not typed_equal(produced, replayed) or not typed_equal(producer_trace, replay_trace) or produced != {"tag": "bool", "payload": primary}:
                mismatches.append({"case": case["id"], "sample": sample_index, "stage": "python-cross-check", "row": row})

    oracle_output, oracle_source_hash = _run_c_oracle(oracle_lines)
    if len(oracle_output) != len(expected_oracle):
        raise ValueError("oracle-line-count")
    for index, (actual_text, expected) in enumerate(zip(oracle_output, expected_oracle, strict=True)):
        actual = _parse_oracle(actual_text)
        python_rows[index]["c11_result"] = actual
        case = guard_cases[index // SAMPLES_PER_GUARD]
        python_rows[index]["context_admissible"] = all(
            frontend_evaluate(expr, python_rows[index]["assignment"]) is True
            for expr in case["context_preconditions"])
        if not typed_equal(actual, expected):
            row = python_rows[index]
            mismatches.append({"case": row["case"], "sample": row["sample"], "class": row["class"], "stage": "c11-evaluation", "expected": expected, "actual": actual_text})

    # W10's zero-denominator sample is the regression test for real C short
    # circuiting: it must produce false, not ERR, because dim > 0 is false.
    w10_zero = next(row for row in assignments_packet if row["case"] == "W10" and row["class"] == "zero-denominator-short-circuit")
    zero_index = next(i for i, row in enumerate(python_rows) if row["case"] == "W10" and row["class"] == "zero-denominator-short-circuit")
    if oracle_output[zero_index] != "B:0":
        mismatches.append({"case": "W10", "stage": "short-circuit-zero-denominator", "actual": oracle_output[zero_index], "assignment": w10_zero["assignment"]})

    # W01 is an explicitly assumed destination-range relation, not old C++
    # execution. Check the mathematical result and independently replay it.
    from public_study import make_source_record, check_source_record
    widening_observations = []
    records = {r["id"]:r for r in candidates["records"]}
    for case in widening_cases:
        evidence = make_source_record(case, records[case["record"]])
        ok, reason = check_source_record(case, records[case["record"]], evidence)
        if (not ok or evidence["mathematical_value"] != {"tag":"int","payload":2**31}
                or evidence["fits_old_destination"] != {"tag":"bool","payload":False}
                or evidence["fits_new_destination"] != {"tag":"bool","payload":True}):
            mismatches.append({"case":case["id"],"stage":"destination-range-relation"})
        widening_observations.append({"evidence":evidence,"accepted":ok,"reason":reason})
    if len(widening_observations) != 1:
        raise ValueError("widening-case-count")

    out.mkdir(parents=True, exist_ok=False)
    dump(out / "assignments.json", {"schema": "rbw-frontend-assignment-plan-v1", "seed": SEED, "samples_per_guard": SAMPLES_PER_GUARD, "rows": assignments_packet})
    dump(out / "mismatches.json", mismatches)
    dump(out / "observations.json", {"schema":"rbw-frontend-observations-v1",
        "guards":python_rows, "range_relations":widening_observations})
    from collections import Counter
    coverage = []
    for case in guard_cases:
        group = [r for r in python_rows if r["case"] == case["id"]]
        unique = {tuple(sorted(r["assignment"].items())) for r in group}
        coverage.append({"case":case["id"], "checks":len(group),
                        "unique_assignments":len(unique),
                        "true_results":sum(r["primary"] is True for r in group),
                        "false_results":sum(r["primary"] is False for r in group),
                        "context_admissible":sum(r["context_admissible"] for r in group),
                        "scenario_classes":dict(Counter(r["class"] for r in group))})
    dump(out / "coverage.json", {"schema":"rbw-frontend-coverage-v1","cases":coverage})
    summary = {
        "schema": "rbw-source-frontend-validation-v2",
        "status": "pass" if not mismatches else "fail",
        "candidate_hash": canonical_hash(candidates),
        "source_evidence_hash": canonical_hash(retained),
        "input_mode": "minimal-real-unified-diff-context",
        "automatic_extraction": True,
        "raw_diff_or_source_tree_correspondence": False,
        "supported_records": len(retained["cases"]),
        "typed_abstentions": len(retained["diagnostics"]) - len(retained["cases"]),
        "guard_cases": len(guard_cases),
        "guard_assignments": len(assignments_packet),
        "widening_checks": 1,
        "semantic_obligations": len(assignments_packet) + 1,
        "mismatches": len(mismatches),
        "unique_guard_assignments": sum(r["unique_assignments"] for r in coverage),
        "assignment_plan": {
            "saved_assignment_each_guard": True,
            "opposite_truth_branch_each_guard": True,
            "w03_boundaries": [65535, 65536, 65537],
            "w10_classes": ["zero-denominator-short-circuit", "actual-division-true", "actual-division-false"],
            "remaining_samples": "seeded-random-unique-before-repeat",
        },
        "independence": {
            "extraction": "single declared added-line extractor; errors become typed abstentions",
            "parsing": "Pratt parser versus separately implemented shunting-yard parser",
            "evaluation": "recursive Python producer, iterative Python replay, and compiled C11 short-circuit bytecode oracle",
        },
        "c11_oracle_sha256": oracle_source_hash,
        "cpu_seconds": (time.process_time_ns() - start_cpu) / 1e9,
        "wall_seconds": (time.monotonic_ns() - start_wall) / 1e9,
        "workers": 1,
        "child_processes": 1,
    }
    dump(out / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
