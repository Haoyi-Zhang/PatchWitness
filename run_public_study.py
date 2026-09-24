#!/usr/bin/env python3
"""Run the public audit as two OS processes: freeze first, evaluate second."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT) or out == ROOT or out.exists():
        parser.error("output must be a new directory within the artifact root")
    out.mkdir(parents=True, exist_ok=False)
    frozen = out / "frozen"
    evaluation = out / "evaluation"
    environment = {"PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, str(ROOT / "freeze_public_study.py"), "--output", str(frozen)],
        cwd=ROOT,
        env={**__import__("os").environ, **environment},
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "evaluate_public_study.py"),
            "--frozen",
            str(frozen),
            "--output",
            str(evaluation),
        ],
        cwd=ROOT,
        env={**__import__("os").environ, **environment},
        check=True,
    )
    summary = json.loads((evaluation / "summary.json").read_text(encoding="utf-8"))
    summary["orchestrator_child_processes"] = 2
    (out / "run-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(json.dumps({"state": "phase-failure", "returncode": exc.returncode}), file=sys.stderr)
        raise SystemExit(2)
