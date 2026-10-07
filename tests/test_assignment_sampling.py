"""Portable pure-computation checks of the finite assignment schedule."""
from __future__ import annotations

import copy
import itertools
from pathlib import Path
import random
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import run_frontend_validation as sampling
from public_study import check_source_record, make_source_record, producer_eval, replay, typed_equal
from source_frontend import assignment_domain, evaluate, parse_expression
from source_frontend_reference import evaluate as reference_evaluate


def owned_cases():
    """Owned scalar expressions; no upstream files, tools, or saved results."""
    specs = [
        ("W02", "pad_width >= 0", {"pad_width": -5}, False, []),
        ("W03", "num_threads < 0 || num_threads >= 65536", {"num_threads": -1}, True, []),
        ("W05", "in_row_start >= 0 && in_row_end >= 0 && in_col_start >= 0 && in_col_end >= 0",
         {"in_row_start": -1, "in_row_end": -1, "in_col_start": -1, "in_col_end": -1}, False, []),
        ("W08", "sx == 0 || sy == 0", {"sx": 0, "sy": 0}, True, []),
        ("W09", "num_elements == 1", {"num_elements": 2}, False, ["num_elements > 0"]),
        ("W10", "dim > 0 && prod <= limit / dim", {"dim": -1, "prod": 1, "limit": 2**31-1},
         False, ["dim != 0"]),
    ]
    return [dict(id=ident, kind="guard-trigger", record="owned", guard=parse_expression(raw),
                 assignment=assignment, trigger_value=trigger, source_tokens=[raw],
                 frontend_rule="require" if not trigger else "reject-if", context_tokens=contexts,
                 context_preconditions=[parse_expression(x) for x in contexts])
            for ident, raw, assignment, trigger, contexts in specs]


def scan_prefix(case, domains):
    """Independent Cartesian/reference-parser specification of mandatory rows."""
    prefix = [{"class": "saved-assignment", "assignment": dict(case["assignment"])}]
    for point in itertools.product(*domains.values()):
        assignment = dict(zip(domains, point))
        if (all(reference_evaluate(x, assignment) for x in case["context_tokens"])
                and reference_evaluate(case["source_tokens"][0], assignment) is not case["trigger_value"]):
            prefix.append({"class": "opposite-truth-branch", "assignment": assignment})
            break
    else:
        raise ValueError("no opposite branch in owned fixture")
    if case["id"] == "W03":
        prefix.extend({"class": f"boundary-{n}", "assignment": {"num_threads": n}}
                      for n in (65535, 65536, 65537))
    if case["id"] == "W10":
        prefix.extend([
            {"class": "zero-denominator-short-circuit", "assignment": {"dim": 0, "prod": 1, "limit": 2**31-1}},
            {"class": "actual-division-true", "assignment": {"dim": 1, "prod": 1, "limit": 2**31-1}},
            {"class": "actual-division-false", "assignment": {"dim": 2, "prod": 2**31-1, "limit": 2**31-1}},
        ])
    return prefix


def first_occurrence_reference(domains, prefix, count, seed):
    """Specify the schedule by proposal ordinals, then cycle its finite prefix.

    This test-local reference builds its Cartesian universe and does not call
    the implementation's sampler, draw helper, or mandatory-scenario builder.
    """
    key = lambda assignment: tuple(sorted(assignment.items()))
    universe = {key(dict(zip(domains, point))) for point in itertools.product(*domains.values())}
    excluded = {key(row["assignment"]) for row in prefix}
    remaining = universe - excluded
    needed = max(0, count - len(prefix))
    first = {}
    rng = random.Random(seed)
    for ordinal in range(count * 500):
        if len(first) >= min(needed, len(remaining)):
            break
        proposal = {name: rng.choice(values) for name, values in domains.items()}
        signature = key(proposal)
        if signature in remaining and signature not in first:
            first[signature] = (ordinal, proposal)
    additions = [{"class": "seeded-random", "assignment": assignment}
                 for _, assignment in sorted(first.values(), key=lambda entry: entry[0])]
    base = prefix + additions
    repeated = [{**row, "class": "deterministic-repeat"}
                for row in itertools.islice(itertools.cycle(base), max(0, count - len(base)))]
    return (base + repeated)[:count]


class AssignmentSamplingTests(unittest.TestCase):
    def test_named_schedule_order_and_classes(self):
        for case in owned_cases():
            domains = assignment_domain([case["guard"], *case["context_preconditions"]])
            prefix = scan_prefix(case, domains)
            for seed, count in itertools.product((0, 7, sampling.SEED), (1, 5, 100)):
                with self.subTest(case=case["id"], seed=seed, count=count):
                    expected = first_occurrence_reference(domains, prefix, count, seed)
                    self.assertTrue(typed_equal(sampling._assignments(case, count, seed), expected))

    def test_complete_values_traces_contexts_and_independent_checker(self):
        record = dict(id="owned", commit="owned", file_path="owned/scalar", commit_message="owned",
                      diff_context="owned scalar fixture")
        for case in owned_cases():
            for row in sampling._assignments(case, 100, sampling.SEED):
                assignment = row["assignment"]
                raw = reference_evaluate(case["source_tokens"][0], assignment)
                self.assertIs(evaluate(case["guard"], assignment), raw)
                trace = []
                value = producer_eval(case["guard"], assignment, trace)
                self.assertTrue(typed_equal(value, {"tag": "bool", "payload": raw}))
                self.assertTrue(typed_equal((value, trace), replay(case["guard"], assignment)))
                selected = {**case, "assignment": assignment}
                evidence = make_source_record(selected, record)
                self.assertTrue(typed_equal(evidence["guard_trace"], trace))
                context = all(reference_evaluate(x, assignment) for x in case["context_tokens"])
                for expr, result, steps in zip(case["context_preconditions"], evidence["context_results"],
                                               evidence["context_traces"], strict=True):
                    self.assertTrue(typed_equal((result, steps), replay(expr, assignment)))
                self.assertEqual(check_source_record(selected, record, evidence),
                                 (False, "source-record-context-false") if not context else
                                 ((True, "accepted-guard-trigger") if raw is case["trigger_value"] else
                                  (False, "source-record-not-triggered")))
                bad = copy.deepcopy(evidence)
                bad["guard_result"]["payload"] = int(raw)
                self.assertFalse(check_source_record(selected, record, bad)[0])

    def test_duplicate_and_outside_mandatory_points_do_not_fake_exhaustion(self):
        case = owned_cases()[0]
        domains = {"x": [0, 1, 2]}
        prefix = [{"class": "mandatory", "assignment": assignment}
                  for assignment in ({"x": 0}, {"x": 0}, {"x": 99}, {"y": 1}, {"x": 1, "y": 1})]
        with mock.patch.object(sampling, "assignment_domain", return_value=domains), \
                mock.patch.object(sampling, "_mandatory", return_value=[(r["class"], r["assignment"]) for r in prefix]):
            actual = sampling._assignments(case, 20, 7)
        self.assertTrue(typed_equal(actual, first_occurrence_reference(domains, prefix, 20, 7)))
        self.assertEqual({r["assignment"]["x"] for r in actual if r["class"] == "seeded-random"}, {1, 2})

    def test_fully_covered_domain_has_no_random_draws_and_keeps_repeat_aliases(self):
        case = owned_cases()[0]
        for domains, prefix in (({}, [("a", {}), ("b", {})]),
                                 ({"x": [0, 0]}, [("a", {"x": 0}), ("b", {"x": 0})])):
            with mock.patch.object(sampling, "assignment_domain", return_value=domains), \
                    mock.patch.object(sampling, "_mandatory", return_value=prefix), \
                    mock.patch.object(sampling, "_random_assignment", wraps=sampling._random_assignment) as draw:
                actual = sampling._assignments(case, 100, 0)
            self.assertEqual(draw.call_count, 0)
            self.assertEqual(len(actual), 100)
            self.assertEqual([r["class"] for r in actual[:2]], ["a", "b"])
            self.assertIs(actual[2]["assignment"], actual[0]["assignment"])

    def test_exhaustion_reduces_draws_without_timing(self):
        case = owned_cases()[0]
        with mock.patch.object(sampling, "_random_assignment", wraps=sampling._random_assignment) as draw:
            rows = sampling._assignments(case, 100, sampling.SEED)
        self.assertEqual(len({tuple(sorted(r["assignment"].items())) for r in rows}), 5)
        self.assertLess(draw.call_count, 100 * 500)
        self.assertEqual(len(rows), 100)

    def test_attempt_cap_remains_when_domain_is_not_exhausted(self):
        with mock.patch.object(sampling, "assignment_domain", return_value={"x": [0, 1]}), \
                mock.patch.object(sampling, "_mandatory", return_value=[("mandatory", {"x": 0})]), \
                mock.patch.object(sampling, "_random_assignment", return_value={"x": 0}) as draw:
            rows = sampling._assignments(owned_cases()[0], 5, 0)
        self.assertEqual(draw.call_count, 2500)
        self.assertEqual([r["class"] for r in rows], ["mandatory"] + ["deterministic-repeat"] * 4)


if __name__ == "__main__":
    unittest.main()
