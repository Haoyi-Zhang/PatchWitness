#!/usr/bin/env python3
"""Derive the retained restricted witness cases from candidate patch excerpts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from public_study import load_json  # noqa: E402
from source_frontend import derive_witness_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=ROOT / "data/public-study/candidates.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path)
    args = parser.parse_args()
    if args.output.exists() or (args.diagnostics and args.diagnostics.exists()):
        parser.error("outputs must not already exist")
    candidates = load_json(args.candidates.resolve())
    document, diagnostics = derive_witness_document(candidates)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.diagnostics:
        args.diagnostics.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(document["cases"]), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
