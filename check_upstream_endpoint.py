"""Produce/consume a local arithmetic record from an attributed upstream edit.

Only owned finite IR and Python mathematical formulas run. No Foundry code,
third-party package, vulnerable application, or exploit is executed.
"""
import argparse
import copy
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import checker
from bounded_decision import Budget, KINDS, classify, refinement, validate
from functional_frontend import translate_pair
import producer


def source_spec():
    return json.loads((ROOT / "data/upstream-foundry-endpoint.json").read_text(encoding="utf-8"))["spec"]


def direct(d, n, bits=64):
    """Record-free mathematical usize baseline, without lowering or IR replay."""
    high = 2**bits - 1
    total = high - d + n
    old = ["fault", "add-overflow"] if total > high else ["u", high - total]
    new = ["u", high - min(high, total)]
    return old, new


def produce(spec):
    case = translate_pair(spec["id"], spec["width"], spec["domain"], spec["before"], spec["after"])
    rows = []
    counts = dict.fromkeys(KINDS, 0)
    fuel = producer.Fuel(100000)
    for d, n in itertools.product(range(16), repeat=2):
        old, _ = producer.evaluate(case["before"], [d, n], 5, fuel)
        new, _ = producer.evaluate(case["after"], [d, n], 5, fuel)
        # Direct arithmetic is supplied the same local semantics and domain.
        if (old, new) != direct(d, n) or direct(d, n, 32) != direct(d, n, 64):
            raise ValueError("source-normalization-disagreement")
        rows.append(dict(input=[d, n], before=old, after=new))
        counts[classify(old, new)] += 1
    return dict(case=case, rows=rows, counts=counts, bounded_refinement=refinement(counts))


def consume(spec, record):
    budget = Budget()
    initial = budget.remaining
    result = validate(spec, record, budget)
    return dict(**result, replay_node_visits=initial-budget.remaining,
                decision="accept-local-preservation" if result["bounded_refinement"]
                else "do-not-approve-local-preservation")


def negative_controls(spec, record):
    mutations = {}
    missing = copy.deepcopy(record)
    missing["rows"].pop()
    mutations["missing-input"] = (spec, missing)
    false_outcome = copy.deepcopy(record)
    false_outcome["rows"][1]["after"] = ["u", 1]
    mutations["false-outcome"] = (spec, false_outcome)
    false_verdict = copy.deepcopy(record)
    false_verdict["bounded_refinement"] = False
    mutations["false-verdict"] = (spec, false_verdict)
    stale = copy.deepcopy(spec)
    stale["after"] = stale["before"]
    mutations["stale-source"] = (stale, record)
    rejected = {}
    for name, (expected, submitted) in mutations.items():
        try:
            consume(expected, submitted)
        except checker.Invalid as exc:
            rejected[name] = str(exc)
        else:
            raise ValueError("accepted-invalid-control: " + name)
    return rejected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path)
    p.add_argument("--record", type=Path, help="Consume an existing record against separate checked-in spec")
    args = p.parse_args()
    spec = source_spec()
    if args.record:
        record = checker.read_json(args.record)
        print(json.dumps(consume(spec, record), sort_keys=True))
        return
    if args.output is None or args.output.exists():
        p.error("--output must name a new directory")
    record = produce(spec)
    result = consume(spec, record)
    result["negative_controls"] = negative_controls(spec, record)
    direct_counts = dict.fromkeys(KINDS, 0)
    for d, n in itertools.product(range(16), repeat=2):
        old, new = direct(d, n)
        if old[0] == "fault":
            kind = "repair" if new[0] == "u" else "both-fault"
        elif new[0] == "fault":
            kind = "new-fault"
        else:
            kind = "defined-equal" if old == new else "defined-changed"
        direct_counts[kind] += 1
    direct_verdict = (direct_counts["repair"] > 0 and
                      direct_counts["new-fault"] == direct_counts["defined-changed"] == 0)
    if direct_counts != result["counts"] or direct_verdict != result["bounded_refinement"]:
        raise ValueError("direct-partition-disagreement")
    result["direct_baseline"] = dict(paired_inputs=256, outcome_evaluations=512,
        counts=direct_counts, bounded_refinement=direct_verdict,
        meaning="Same decisions without a portable outcome record; no speedup claim")
    encoded = json.dumps(record, indent=2, sort_keys=True) + "\n"
    result["record_utf8_bytes"] = len(encoded.encode("utf-8"))
    result["source_kind"] = "attributed-local-edit-with-owned-normalized-helper-model"
    args.output.mkdir(parents=True)
    (args.output / "record.json").write_text(encoded, encoding="utf-8", newline="\n")
    (args.output / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",
                                           encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
