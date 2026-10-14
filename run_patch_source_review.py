"""Bounded static source/ranking audit and reviewed owned functional behavior.

Does not execute TensorFlow excerpts, call a compiler, fetch data or tune scores.
Every output goes to a new directory inside this artifact's results tree.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from public_study import (canonical_hash, freeze_predictions, load_json, typed_equal,
                          validate_candidates, validate_labels, validate_source_evidence)
from same_information import direct_relation
from source_frontend import derive_evidence_document
from run_functional_diagnostics import analyze, KINDS
from verify_results import verify_finite, verify_public_packet


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit_excerpt(record, case):
    header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    hunks = []
    current = None
    common = []
    for line in record["diff_context"].splitlines():
        match = header.match(line)
        if match:
            current = {"header": line, "declared_old_lines": int(match[2] or 1),
                       "declared_new_lines": int(match[4] or 1),
                       "retained_old_lines": 0, "retained_new_lines": 0}
            hunks.append(current)
        elif current is not None and line.startswith("+"):
            current["retained_new_lines"] += 1
        elif current is not None and line.startswith("-"):
            current["retained_old_lines"] += 1
        elif current is not None and line.startswith(" "):
            current["retained_old_lines"] += 1
            current["retained_new_lines"] += 1
            common.append(line[1:])
        else:
            require(line.startswith("\\ No newline"), "unexpected-excerpt-line-prefix")
    require(bool(hunks), "missing-hunk-header")
    for hunk in hunks:
        hunk["counts_match_header"] = (hunk["declared_old_lines"] == hunk["retained_old_lines"]
                                       and hunk["declared_new_lines"] == hunk["retained_new_lines"])
    common_text = re.sub(r"\s+", " ", "\n".join(common)).strip()
    context = [] if case is None else case["context_tokens"]
    return {"id": record["id"], "commit": record["commit"], "file_path": record["file_path"],
            "case": None if case is None else case["id"], "hunks": hunks,
            "all_hunk_counts_match": all(h["counts_match_header"] for h in hunks),
            "represented_context_in_unchanged_lines": [
                {"token": token, "present": re.sub(r"\s+", " ", token).strip() in common_text}
                for token in context],
            "complete_source_tree_correspondence": False,
            "native_program_execution": False}


def freeze_same_information(candidates, evidence, protocol):
    records = validate_candidates(candidates)
    derived = derive_evidence_document(candidates)
    require(typed_equal(derived, evidence), "current-extraction-drift")
    cases = validate_source_evidence(derived, {r["id"] for r in records})
    by_record = {case["record"]: case for case in cases}
    checked, outcomes, source_records = freeze_predictions(candidates, derived, protocol)
    checked_rows = {row["id"]: row for row in checked["records"]}
    rows = []
    for record in records:
        case = by_record.get(record["id"])
        # Direct arm consumes the same validated expected case, not accepted
        # flags, source records, producer traces or a reported score.
        direct = False if case is None else direct_relation(case)
        row = checked_rows[record["id"]]
        score = round(row["syntax_score"] + float(protocol["source_evidence_bonus"]) * int(direct), 9)
        require(int(direct) == row["source_evidence_accepted"], "same-information-flag-disagreement")
        require(score == row["validated_score"], "same-information-score-disagreement")
        rows.append({"id": record["id"], "syntax_score": row["syntax_score"],
                     "direct_relation": int(direct), "checked_relation": row["source_evidence_accepted"],
                     "direct_score": score, "checked_score": row["validated_score"]})
    # Same fixed score and tie rule, independently expressed; no coefficient search.
    order = [row["id"] for row in sorted(rows, key=lambda r: (-r["direct_score"], -r["syntax_score"], r["id"]))]
    require(order == checked["rankings"]["validated"], "same-information-order-disagreement")
    excerpts = [audit_excerpt(r, by_record.get(r["id"])) for r in records]
    return checked, rows, order, excerpts


def metrics(order, labels, cutoffs):
    result = {f"precision_at_{k}": float(Fraction(sum(labels[i] for i in order[:k]), k))
              for k in cutoffs}
    seen = 0
    total = Fraction(0)
    for position, rid in enumerate(order, 1):
        if labels[rid]:
            seen += 1
            total += Fraction(seen, position)
    result["average_precision"] = float(total / sum(labels.values())) if sum(labels.values()) else 0.0
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    require(not out.exists(), "output-exists")
    require(out.is_relative_to((ROOT / "results").resolve()), "output-outside-artifact-results")
    cpu, wall = time.process_time(), time.monotonic()
    data = ROOT / "data/public-study"
    candidates, evidence, protocol = [load_json(data / name) for name in
                                     ("candidates.json", "source-evidence-cases.json", "protocol.json")]
    checked, rows, order, excerpts = freeze_same_information(candidates, evidence, protocol)
    frozen = load_json(ROOT / "results/public-study/frozen/predictions-frozen.json")
    require(typed_equal(checked, frozen), "historical-scientific-prediction-drift")
    out.mkdir(parents=True, exist_ok=False)

    def dump(name, value):
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Freeze all selections before opening labels. This is one process, not a
    # blind study or a re-execution of the retained two-process supervisor.
    dump("label-free-comparison.json", {"rows": rows, "direct_ranking": order,
                                       "retained_rankings": checked["rankings"]})
    label_doc = load_json(data / "labels.json")
    labels = validate_labels(label_doc, {r["id"]: r["group"] for r in candidates["records"]})
    ranks = {**checked["rankings"], "same_information_direct": order}
    k = protocol["primary_k"]
    summaries = {name: metrics(rank, labels, protocol["top_k"]) for name, rank in ranks.items()}
    result = {"schema": "rbw-same-information-comparison-v1", "candidate_units": len(rows),
              "candidate_hash": canonical_hash(candidates), "source_evidence_hash": canonical_hash(evidence),
              "protocol_hash": canonical_hash(protocol), "primary_k": k,
              "fixed_bonus": protocol["source_evidence_bonus"], "tie_rule": protocol["prediction_tie_break"],
              "flag_mismatches": 0, "score_mismatches": 0, "complete_rankings_identical_direct_checked": True,
              "rankings": ranks, "metrics": summaries,
              "top20_checked_vs_direct_symmetric_difference": len(set(order[:k]) ^ set(ranks["validated"][:k])),
              "top20_checked_vs_syntax_symmetric_difference": len(set(ranks["validated"][:k]) ^ set(ranks["syntax"][:k])),
              "checked_minus_direct_p20": float(Fraction(sum(labels[i] for i in ranks["validated"][:k]) -
                                                        sum(labels[i] for i in order[:k]), k)),
              "checked_minus_syntax_p20": float(Fraction(sum(labels[i] for i in ranks["validated"][:k]) -
                                                        sum(labels[i] for i in ranks["syntax"][:k]), k)),
              "native_execution": False, "upstream_program_execution": False,
              "label_free_selections_written_before_label_read": True, "processes": 1,
              "scope": "Same extracted cases/context/assignments, signed-width assumptions and fixed scores; not an external strongest-detector or elapsed-time comparison"}
    dump("same-information.json", result)
    dump("source-relationship.json", {"schema": "rbw-retained-excerpt-relationship-v1", "units": excerpts,
         "units_with_mismatching_hunk_counts": sum(not r["all_hunk_counts_match"] for r in excerpts),
         "hunks": sum(len(r["hunks"]) for r in excerpts),
         "mismatching_hunks": sum(not h["counts_match_header"] for r in excerpts for h in r["hunks"]),
         "scope": "Local retained-line accounting, not upstream acquisition authentication or source-tree reconstruction"})

    packet = load_json(ROOT / "data/functional-programs.json")
    behavior = [analyze(spec) for spec in packet["cases"]]
    totals = {kind: sum(report["counts"][kind] for report in behavior) for kind in KINDS}
    dump("functional-inputs.json", packet)
    dump("functional-cases.json", behavior)
    dump("functional-summary.json", {"cases": len(behavior), "pair_inputs": sum(r["assignments"] for r in behavior),
         "counts": totals, "accepted_witnesses": sum(r["certificate"] is not None for r in behavior),
         "same_information_set_gain": 0, "mismatches": 0, "native_execution": False,
         "upstream_source_correspondence": False})
    finite = verify_finite()
    public = verify_public_packet(data, ROOT / "results/public-study", ROOT / "reference-verification.csv",
                                  ROOT / "results/source-frontend/summary.json", ROOT)
    sources = [Path(__file__), ROOT / "src/same_information.py", ROOT / "src/source_frontend.py",
               ROOT / "src/source_frontend_reference.py", ROOT / "src/public_study.py",
               ROOT / "run_functional_diagnostics.py", ROOT / "src/functional_frontend.py",
               ROOT / "src/functional_reference.py", ROOT / "src/checker.py", ROOT / "src/producer.py",
               ROOT / "data/functional-programs.json", *(data / n for n in
               ("candidates.json", "source-evidence-cases.json", "protocol.json", "labels.json"))]
    dump("provenance.json", {"schema": "rbw-bounded-patch-review-provenance-v1", "outcome": "PASS",
         "command": [sys.executable, *sys.argv], "python": sys.version, "platform": platform.platform(),
         "workers": 1, "native_execution": False, "upstream_program_execution": False,
         "finite_recheck": finite, "retained_public_packet_recheck": public,
         "C11_validation": "Historical retained report only; native oracle not run by this command",
         "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - wall,
         "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}})
    print(json.dumps({"outcome": "PASS", "candidate_units": len(rows), "same_information_p20": summaries["same_information_direct"]["precision_at_20"],
                      "checked_minus_direct_p20": result["checked_minus_direct_p20"],
                      "checked_minus_syntax_p20": result["checked_minus_syntax_p20"],
                      "functional_pairs": len(behavior), "functional_pair_inputs": sum(r["assignments"] for r in behavior),
                      "units_with_mismatching_hunk_counts": sum(not r["all_hunk_counts_match"] for r in excerpts),
                      "native_execution": False}, indent=2))


if __name__ == "__main__":
    main()
