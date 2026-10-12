"""Exhaustively compare reviewed authored source pairs and their lowered IR.

No public dataset, compiler, network, or external program is invoked. This is
standard-library-only and requires a new directory under this artifact/results.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import checker
from functional_frontend import translate_pair, check_source_witness
from functional_reference import build_reference
from producer import Fuel, evaluate, find

KINDS = ("repair", "new-fault", "defined-equal", "defined-changed", "both-fault")


def partition(old, new):
    if old[0] == "fault":
        return "both-fault" if new[0] == "fault" else "repair"
    if new[0] == "fault":
        return "new-fault"
    return "defined-equal" if checker._typed_equal(old, new) else "defined-changed"


def analyze(spec):
    case = translate_pair(spec["id"], spec["width"], spec["domain"],
                          spec["before"], spec["after"])
    old_source = build_reference(spec["before"], spec["width"])
    new_source = build_reference(spec["after"], spec["width"])
    fuel = Fuel(200_000)
    rows = []
    counts = dict.fromkeys(KINDS, 0)
    first = {}
    baseline_repairs, baseline_faults, baseline_changes = [], [], []
    for values in itertools.product(*(range(lo, hi + 1) for lo, hi in spec["domain"])):
        values = list(values)
        ref0, ref1 = old_source(values), new_source(values)
        out0, trace0 = evaluate(case["before"], values, spec["width"], fuel)
        out1, trace1 = evaluate(case["after"], values, spec["width"], fuel)
        check0 = checker.replay(case["before"], values, spec["width"], fuel)
        check1 = checker.replay(case["after"], values, spec["width"], fuel)
        if not (checker._typed_equal(ref0, out0) and checker._typed_equal(ref1, out1)
                and checker._typed_equal([out0, trace0], list(check0))
                and checker._typed_equal([out1, trace1], list(check1))):
            raise ValueError(f"source/IR mismatch: {spec['id']} at {values}")
        kind = partition(out0, out1)
        counts[kind] += 1
        first.setdefault(kind, {"input": values, "before": ref0, "after": ref1})
        # Fair simple baseline: direct execution on exactly the same inputs.
        # It does not call partition(), the IR, find(), or replay().
        if ref0[0] == "fault" and ref1[0] == "u":
            baseline_repairs.append(values)
        elif ref0[0] == "u" and ref1[0] == "fault":
            baseline_faults.append(values)
        elif ref0[0] == ref1[0] == "u" and ref0[1] != ref1[1]:
            baseline_changes.append(values)
        rows.append({"input": values, "before": ref0, "after": ref1, "kind": kind})
    for kind, baseline in (("repair", baseline_repairs), ("new-fault", baseline_faults),
                           ("defined-changed", baseline_changes)):
        if [row["input"] for row in rows if row["kind"] == kind] != baseline:
            raise ValueError("simple-baseline-set-mismatch")
    certificate, explored = find(case, fuel)
    if bool(certificate) != bool(baseline_repairs):
        raise ValueError("witness-existence-mismatch")
    if certificate is not None:
        accepted, _ = check_source_witness(spec["id"], spec["width"], spec["domain"],
                                          spec["before"], spec["after"], certificate, fuel)
        if not accepted or certificate["input"] != baseline_repairs[0]:
            raise ValueError("source-bound-witness-mismatch")
    return {"id": spec["id"], "purpose": spec["purpose"], "ir": case,
            "assignments": len(rows), "counts": counts, "first_examples": first,
            "source_syntax_changed": spec["before"] != spec["after"],
            "certificate": certificate, "witness_search_assignments": explored,
            "simple_baseline_set_agreement": True, "observations": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to((ROOT / "results").resolve()):
        raise ValueError("output-must-be-under-artifact-results")
    if output.exists():
        raise ValueError("output-exists")
    started, cpu = time.perf_counter(), time.process_time()
    fixture = ROOT / "data" / "functional-programs.json"
    packet = json.loads(fixture.read_text(encoding="utf-8"))
    reports = [analyze(spec) for spec in packet["cases"]]
    totals = {kind: sum(r["counts"][kind] for r in reports) for kind in KINDS}
    sources = [fixture, Path(__file__), ROOT / "src" / "functional_frontend.py",
               ROOT / "src" / "functional_reference.py", ROOT / "src" / "checker.py",
               ROOT / "src" / "producer.py"]
    summary = {
        "scope": packet["scope"], "cases": len(reports),
        "assignments": sum(r["assignments"] for r in reports), "counts": totals,
        "accepted_source_bound_witnesses": sum(r["certificate"] is not None for r in reports),
        "mismatches": 0, "simple_baseline_set_mismatches": 0,
        "simple_baseline_gain": 0, "public_patch_cases_executed": 0,
        "environment": {"executable": sys.executable, "python": sys.version,
                        "platform": platform.platform(), "workers": 1},
        "command": [sys.executable, *sys.argv],
        "input_and_implementation_sha256": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources},
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - cpu,
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("cases.json", reports),
                        ("inputs.json", packet)):
        (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
