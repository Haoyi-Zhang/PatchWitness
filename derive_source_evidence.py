#!/usr/bin/env python3
"""Derive restricted source-evidence cases and typed abstentions from real retained diff context."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from public_study import load_json  # noqa: E402
from source_frontend import derive_evidence_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=ROOT / "data/public-study/candidates.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("output must not already exist")
    candidates = load_json(args.candidates.resolve())
    document = derive_evidence_document(candidates)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "cases": len(document["cases"]),
        "typed_abstentions": sum(row["status"] == "abstain" for row in document["diagnostics"]),
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
