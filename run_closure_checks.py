#!/usr/bin/env python3
"""Run the exact finite empirical-closure checks."""
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
from closure_checks import run_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT) or out == ROOT or out.exists():
        parser.error("output must be a new directory within the artifact root")
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("wall-limit")))
    signal.alarm(40)
    start_cpu = time.process_time_ns()
    start_wall = time.monotonic_ns()
    result = run_all()
    result.update(
        cpu_seconds=(time.process_time_ns() - start_cpu) / 1e9,
        wall_seconds=(time.monotonic_ns() - start_wall) / 1e9,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        workers=1,
        child_processes=0,
    )
    out.mkdir(parents=True, exist_ok=False)
    (out / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(result["exit_status"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TimeoutError, MemoryError, RuntimeError) as exc:
        print(json.dumps({"state": "resource-abstention", "reason": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)
