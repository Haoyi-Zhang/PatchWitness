#!/usr/bin/env python3
"""Validate the restricted source frontend with independent parsers and C11 replay."""
from __future__ import annotations

import argparse
import hashlib
import itertools
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
from public_study import canonical_hash, load_json, producer_eval, replay  # noqa: E402
from source_frontend import (  # noqa: E402
    FrontendError,
    ast_to_rpn,
    derive_witness_document,
    evaluate as frontend_evaluate,
)
from source_frontend_reference import evaluate as reference_evaluate  # noqa: E402

SAMPLES_PER_PREDICATE = 100
SEED = 20211119


def _raw_expression(case: dict[str, Any]) -> str:
    operator = " && " if case["frontend_rule"] == "require" else " || "
    return operator.join(f"({token})" for token in case["source_tokens"])


def _variables(expression: list[Any]) -> list[str]:
    found: set[str] = set()
    def walk(node: list[Any]) -> None:
        if node[0] == "var":
            found.add(node[1])
        else:
            for child in node[1:]:
                if isinstance(child, list):
                    walk(child)
    walk(expression)
    return sorted(found)


def _contains_divisor(expression: list[Any], variable: str) -> bool:
    if expression[0] == "div" and expression[2] == ["var", variable]:
        return True
    return any(
        isinstance(child, list) and _contains_divisor(child, variable)
        for child in expression[1:]
    )


def _value_pool(name: str, *, denominator: bool) -> list[int]:
    if denominator:
        return [value for value in range(-50, 51) if value != 0]
    if name == "num_elements":
        return list(range(0, 100))
    if name in {"dims", "input_dims"}:
        return list(range(0, 100))
    if name == "num_threads":
        return list(range(-50, 51)) + [65534, 65535, 65536, 65537, 2**31 - 1]
    if name == "pad_width":
        return list(range(-50, 50))
    if name == "axis":
        return list(range(-50, 51)) + [2**31 - 2, 2**31 - 1]
    if name == "limit":
        return list(range(1, 101))
    if name == "prod":
        return list(range(0, 100))
    return list(range(-50, 50))


def _assignments(case: dict[str, Any], count: int, seed: int) -> list[dict[str, int]]:
    expression = case["condition"]
    names = _variables(expression)
    pools = {
        name: _value_pool(name, denominator=_contains_divisor(expression, name))
        for name in names
    }
    if len(names) == 1:
        values = pools[names[0]][:count]
        if len(values) < count:
            raise RuntimeError("insufficient-one-variable-domain")
        return [{names[0]: value} for value in values]
    rng = random.Random(seed)
    seen: set[tuple[int, ...]] = set()
    rows: list[dict[str, int]] = []
    # Include a deterministic cartesian prefix before pseudo-random coverage.
    for values in itertools.islice(itertools.product(*(pools[name][:12] for name in names)), count):
        key = tuple(values)
        if key not in seen:
            seen.add(key)
            rows.append(dict(zip(names, values, strict=True)))
    while len(rows) < count:
        key = tuple(rng.choice(pools[name]) for name in names)
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(zip(names, key, strict=True)))
    return rows


def _run_c_oracle(lines: list[str]) -> tuple[list[str], str]:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("no-c11-compiler")
    source = ROOT / "src/source_frontend_oracle.c"
    with tempfile.TemporaryDirectory(prefix="rbw-frontend-") as directory:
        binary = Path(directory) / "oracle"
        compile_result = subprocess.run(
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-pedantic", str(source), "-o", str(binary)],
            text=True,
            capture_output=True,
            timeout=20,
        )
        if compile_result.returncode != 0:
            raise RuntimeError(f"c11-compile:{compile_result.stderr}")
        run_result = subprocess.run(
            [str(binary)],
            input="\n".join(lines) + "\n",
            text=True,
            capture_output=True,
            timeout=20,
        )
        if run_result.returncode != 0:
            raise RuntimeError(f"c11-run:{run_result.stderr}")
        return run_result.stdout.splitlines(), Path(compiler).name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/public-study")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error("output must not already exist")
    start = time.monotonic()
    candidates = load_json(args.data_dir.resolve() / "candidates.json")
    retained = load_json(args.data_dir.resolve() / "witness-cases.json")
    derived, diagnostics = derive_witness_document(candidates)
    if derived != retained:
        raise RuntimeError("retained-witness-cases-do-not-match-frontend")

    predicate_cases = [case for case in retained["cases"] if case["kind"] == "predicate"]
    if len(predicate_cases) != 9:
        raise RuntimeError("unexpected-predicate-case-count")

    c_lines: list[str] = []
    expected_c: list[str] = []
    mismatches: list[dict[str, Any]] = []
    case_counts: dict[str, int] = {}
    for index, case in enumerate(predicate_cases):
        raw = _raw_expression(case)
        assignments = _assignments(case, SAMPLES_PER_PREDICATE, SEED + index)
        case_counts[case["record"]] = len(assignments)
        for assignment in assignments:
            try:
                primary = frontend_evaluate(case["condition"], assignment)
                reference = reference_evaluate(raw, assignment)
                produced_trace: list[dict[str, Any]] = []
                produced = producer_eval(case["condition"], assignment, produced_trace)
                replayed, replay_trace = replay(case["condition"], assignment)
            except Exception as exc:  # retained as a typed mismatch, not hidden
                mismatches.append({"record": case["record"], "assignment": assignment, "error": type(exc).__name__})
                continue
            if not (type(primary) is bool and primary == reference == produced == replayed and produced_trace == replay_trace):
                mismatches.append(
                    {
                        "record": case["record"],
                        "assignment": assignment,
                        "primary": primary,
                        "reference": reference,
                        "producer": produced,
                        "replay": replayed,
                    }
                )
            c_lines.append(" ".join(ast_to_rpn(case["condition"], assignment)))
            expected_c.append("1" if bool(primary) else "0")

    c_output, compiler = _run_c_oracle(c_lines)
    if len(c_output) != len(expected_c):
        mismatches.append({"c_output_count": len(c_output), "expected_count": len(expected_c)})
    else:
        for index, (observed, expected) in enumerate(zip(c_output, expected_c, strict=True)):
            if observed != expected:
                mismatches.append({"c_index": index, "observed": observed, "expected": expected})

    recognized = [row for row in diagnostics if row["reason"].startswith("recognized-")]
    unsupported = [row for row in diagnostics if not row["reason"].startswith("recognized-")]
    summary = {
        "schema": "rbw-source-frontend-validation-v1",
        "automatic_source_frontend": True,
        "source_translation_validated": not mismatches,
        "grammar": retained["construction"]["grammar"],
        "candidate_hash": canonical_hash(candidates),
        "witness_case_hash": canonical_hash(retained),
        "candidate_units": len(candidates["records"]),
        "recognized_cases": len(retained["cases"]),
        "predicate_cases": len(predicate_cases),
        "widening_cases": 1,
        "unsupported_units": len(unsupported),
        "unique_assignments_per_predicate": SAMPLES_PER_PREDICATE,
        "semantic_obligations": len(predicate_cases) * SAMPLES_PER_PREDICATE,
        "primary_parser": "Pratt",
        "independent_parser": "shunting-yard",
        "c11_oracle": "pass" if not mismatches else "fail",
        "c11_compiler": compiler,
        "mismatches": len(mismatches),
        "case_counts": case_counts,
        "diagnostics": diagnostics,
        "elapsed_seconds": time.monotonic() - start,
        "status": "pass" if not mismatches else "fail",
    }
    out.mkdir(parents=True, exist_ok=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "mismatches.json").write_text(json.dumps(mismatches, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())
