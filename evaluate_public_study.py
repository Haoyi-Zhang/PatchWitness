#!/usr/bin/env python3
"""Open retrospective labels and evaluate a previously frozen prediction packet."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from public_study import evaluate_predictions, load_json, load_json_value  # noqa: E402


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verified_reference_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "citation_key", "authoritative_url", "persistent_id", "metadata_status",
            "content_check", "checked_on", "notes",
        }
        if reader.fieldnames is None or set(reader.fieldnames) != required:
            raise ValueError("reference-verification-schema")
        rows = list(reader)
    if len({row["citation_key"] for row in rows}) != len(rows):
        raise ValueError("duplicate-reference-verification")
    return sum(
        row["metadata_status"] == "verified"
        and row["content_check"] in {"full-text", "abstract", "metadata-only"}
        and bool(row["authoritative_url"])
        and bool(row["persistent_id"])
        for row in rows
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/public-study")
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--reference-verification", type=Path, default=ROOT / "reference-verification.csv")
    parser.add_argument(
        "--frontend-validation",
        type=Path,
        default=ROOT / "results/source-frontend/summary.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    frozen = args.frozen.resolve()
    out = args.output.resolve()
    if out.exists():
        parser.error("output must not already exist")

    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("wall-limit")))
    signal.alarm(40)
    start_cpu = time.process_time_ns()
    start_wall = time.monotonic_ns()

    candidates = load_json(data_dir / "candidates.json")
    labels = load_json(data_dir / "labels.json")
    cases = load_json(data_dir / "witness-cases.json")
    protocol = load_json(data_dir / "protocol.json")
    design = load_json(data_dir / "study-design.json")
    predictions = load_json(frozen / "predictions-frozen.json")
    outcomes = load_json_value(frozen / "outcomes.json")
    reference_count = verified_reference_count(args.reference_verification.resolve())
    frontend_validation = load_json(args.frontend_validation.resolve())

    summary, scored_rows, ablations, readiness = evaluate_predictions(
        candidates,
        labels,
        cases,
        protocol,
        design,
        predictions,
        outcomes,
        reference_count,
        frontend_validation,
    )
    summary.update(
        evaluation_process_read_labels=True,
        freeze_and_evaluation_are_separate_processes=True,
        cpu_seconds=(time.process_time_ns() - start_cpu) / 1e9,
        wall_seconds=(time.monotonic_ns() - start_wall) / 1e9,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        workers=1,
        child_processes=0,
        exit_status=0,
    )

    out.mkdir(parents=True, exist_ok=False)
    dump(out / "summary.json", summary)
    dump(out / "readiness.json", readiness)
    dump(out / "ablations.json", ablations)

    fieldnames = [
        "id", "group", "label", "syntax_score", "semantic_hint", "unvalidated_score",
        "witness_accepted", "validated_score", "syntax_rank", "unvalidated_rank",
        "validated_rank", "added_guard", "range_relation", "error_return",
        "type_widening", "overflow_division_guard",
    ]
    with (out / "scores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for original in scored_rows:
            row = dict(original)
            features = row.pop("semantic_features")
            writer.writerow({**row, **{key: features[key] for key in fieldnames if key in features}})

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TimeoutError, MemoryError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "resource-or-input-abstention", "reason": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)
