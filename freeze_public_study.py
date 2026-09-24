#!/usr/bin/env python3
"""Create the immutable prediction packet from candidates and witness cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from public_study import freeze_predictions, load_json  # noqa: E402
from source_frontend import derive_witness_document  # noqa: E402


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/public-study")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
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
    cases = load_json(data_dir / "witness-cases.json")
    derived_cases, _ = derive_witness_document(candidates)
    if derived_cases != cases:
        raise ValueError("witness-cases-not-derived-from-candidates")
    protocol = load_json(data_dir / "protocol.json")
    predictions, outcomes, certificates = freeze_predictions(candidates, cases, protocol)

    out.mkdir(parents=True, exist_ok=False)
    dump(out / "predictions-frozen.json", predictions)
    dump(out / "outcomes.json", outcomes)
    dump(out / "certificates.json", certificates)
    summary = {
        "schema": "rbw-freeze-summary-v2",
        "phase": "prediction-freeze",
        "candidate_units": len(predictions["records"]),
        "accepted_certificates": sum(row["witness_accepted"] for row in predictions["records"]),
        "frontend_derived_cases": len(cases["cases"]),
        "candidate_hash": predictions["candidate_hash"],
        "witness_case_hash": predictions["witness_case_hash"],
        "protocol_hash": predictions["protocol_hash"],
        "cpu_seconds": (time.process_time_ns() - start_cpu) / 1e9,
        "wall_seconds": (time.monotonic_ns() - start_wall) / 1e9,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "workers": 1,
        "child_processes": 0,
        "exit_status": 0,
    }
    dump(out / "freeze-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TimeoutError, MemoryError, ValueError, OSError) as exc:
        print(json.dumps({"state": "resource-or-input-abstention", "reason": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)
