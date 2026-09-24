"""Tests of the owned certificate and ranking contracts, not security labels."""
import copy
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import checker
from producer import Fuel, evaluate, find
from fixtures import make
from ranking import overlap_bound, precision_difference, sharp_margin

FUEL = Fuel()
COUNTS = {'tampered_certificates': 0, 'ranking_labelings': 0, 'arithmetic_assignments': 0}


class ContractTests(unittest.TestCase):
    def certificate(self):
        case = make('guarded-index', 3, 'T01')
        cert, _ = find(case, FUEL)
        self.assertTrue(checker.check(case, cert, FUEL)[0])
        return case, cert

    def test_certificate_mutations(self):
        case, cert = self.certificate()
        variants = []
        for k in list(cert):
            c = copy.deepcopy(cert); del c[k]; variants.append(c)
        for field in ('before', 'after'):
            c = copy.deepcopy(cert); c[field] = ['u', 0]; variants.append(c)
        # after ['u', 0] is in fact valid: exclude that no-op mutation.
        variants.pop()
        for field in ('before_trace', 'after_trace'):
            c = copy.deepcopy(cert); c[field] = c[field][1:]; variants.append(c)
            c = copy.deepcopy(cert); c[field][-1][0] = 'x'; variants.append(c)
        c = copy.deepcopy(cert); c['input'] = [8, 0]; variants.append(c)
        c = copy.deepcopy(cert); c['input'] = [True, 0]; variants.append(c)
        c = copy.deepcopy(cert); c['input'] = [0]; variants.append(c)
        c = copy.deepcopy(cert); c['case']['id'] = 'Other'; variants.append(c)
        c = copy.deepcopy(cert); c['case']['width'] = True; variants.append(c)
        c = copy.deepcopy(cert); c['case']['after'] = ['load', ['v', 0], ['v', 1]]; variants.append(c)
        c = copy.deepcopy(cert); c['extra'] = 1; variants.append(c)
        c = copy.deepcopy(cert); c['after'] = ['u', False]; variants.append(c)
        c = copy.deepcopy(cert); c['after_trace'][-1][2] = False; variants.append(c)
        for c in variants:
            COUNTS['tampered_certificates'] += 1
            self.assertFalse(checker.check(case, c, FUEL)[0])

    def test_assignment_is_bound_to_domain(self):
        case = make('saturating-step', 3, 'T02')
        cert, _ = find(case, FUEL)
        expected = copy.deepcopy(case); expected['domain'][0] = [0, 6]
        self.assertFalse(checker.check(expected, cert, FUEL)[0])
        cert['case'] = copy.deepcopy(expected)
        self.assertFalse(checker.check(expected, cert, FUEL)[0])
        absent, _ = find(expected, FUEL)
        self.assertIsNone(absent)

    def test_improvement_does_not_exclude_regression(self):
        case = make('mixed-change', 3, 'T03')
        cert, _ = find(case, FUEL)
        self.assertTrue(checker.check(case, cert, FUEL)[0])
        old, _ = evaluate(case['before'], [0, 0], 3, FUEL)
        new, _ = evaluate(case['after'], [0, 0], 3, FUEL)
        self.assertEqual(old[0], 'u'); self.assertEqual(new[0], 'fault')

    def test_arithmetic_and_comparisons(self):
        for op in ('add', 'sub', 'mul', 'uadd', 'umul', 'index', 'lt', 'le', 'eq'):
            for a, b in itertools.product(range(8), repeat=2):
                COUNTS['arithmetic_assignments'] += 1
                expr = [op, ['v', 0], ['v', 1]]
                p, pt = evaluate(expr, [a, b], 3, FUEL)
                c, ct = checker.replay(expr, [a, b], 3, FUEL)
                self.assertEqual(p, c); self.assertEqual(pt, ct)
                if op == 'umul':
                    self.assertEqual(p, ['fault', 'mul-overflow'] if a*b >= 8 else ['u', a*b])

    def test_fault_short_circuit_and_lazy_branch(self):
        fault = ['uadd', ['c', 7], ['c', 1]]
        exprs = [['add', fault, ['mul', ['v', 0], ['v', 1]]],
                 ['if', ['lt', ['c', 0], ['c', 0]], fault, ['c', 0]],
                 ['if', ['lt', fault, ['c', 0]], ['c', 0], ['c', 1]]]
        for e in exprs:
            self.assertEqual(evaluate(e, [0, 0], 3, FUEL), checker.replay(e, [0, 0], 3, FUEL))
        _, tr = evaluate(exprs[1], [0, 0], 3, FUEL)
        self.assertNotIn('1', [r[0] for r in tr])

    def test_schema_limits(self):
        case = make('identical', 3, 'T04')
        invalid = []
        for width in (0, 6, True):
            c = copy.deepcopy(case); c['width'] = width; invalid.append(c)
        for expr in (['c', True], ['c', -1], ['c', 8], ['v', 2], ['call', ['c', 0]],
                     ['if', ['c', 0], ['c', 0], ['c', 0]], ['lt', ['c', 0], ['c', 1]]):
            c = copy.deepcopy(case); c['before'] = expr; invalid.append(c)
        for d in ([[1, 0], [0, 7]], [[0, 8], [0, 7]], [[0, 7], [0, 7], [0, 7]], []):
            c = copy.deepcopy(case); c['domain'] = d; invalid.append(c)
        e = ['c', 0]
        for _ in range(15): e = ['add', e, ['c', 0]]
        c = copy.deepcopy(case); c['before'] = e; invalid.append(c)
        for c in invalid:
            with self.assertRaises(checker.Invalid): checker.validate_case(c)

    def test_json_gate(self):
        cases = [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.0}',
                 b'{"a":123456}', b'\xff', b'['*2000+b']'*2000,
                 b' '* (checker.MAX_BYTES + 1),
                 b'{\x00\"\x00a\x00\"\x00:\x001\x00}\x00']
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'packet.json'
            for raw in cases:
                p.write_bytes(raw)
                with self.assertRaises(checker.Invalid): checker.read_json(p)
            for obj in ({'text': '[[[{\"quoted\"}\\]'}, {'text': '}'*1000},
                        [[0]], {'number': -1234}):
                p.write_text(json.dumps(obj), encoding='utf-8')
                self.assertEqual(checker.read_json(p), obj)
            p.write_bytes(b'['*checker.MAX_JSON_DEPTH + b'0' + b']'*checker.MAX_JSON_DEPTH)
            self.assertIsInstance(checker.read_json(p), list)
            p.write_bytes(b'['*(checker.MAX_JSON_DEPTH+1) + b'0' + b']'*(checker.MAX_JSON_DEPTH+1))
            with self.assertRaises(checker.Invalid): checker.read_json(p)

    def test_ranking_bounds_are_sharp(self):
        # Exhaustive labels are mathematical bit vectors, not security annotations.
        a = list(range(6)); b = [3, 4, 2, 0, 1, 5]; k = 3
        seen = {s: [] for s in range(7)}
        for ys in itertools.product((0, 1), repeat=6):
            FUEL.tick(); COUNTS['ranking_labelings'] += 1
            labels = dict(zip(a, ys))
            delta = precision_difference(a, b, labels, k)
            direct = (sum(labels[x] for x in a[:k]) - sum(labels[x] for x in b[:k])) / k
            self.assertAlmostEqual(float(delta), direct)
            self.assertLessEqual(abs(delta), overlap_bound(a, b, k))
            seen[sum(ys)].append(delta)
        for s, vals in seen.items():
            bound = sharp_margin(a, b, k, s)
            self.assertEqual(max(vals), bound); self.assertEqual(min(vals), -bound)

    def test_ranking_rejects_partial_or_unlabeled_inputs(self):
        a = [0, 1, 2]; b = [2, 1, 0]
        for labels in ({0: 1}, {0: True, 1: 0, 2: 1}, {0: 0, 1: 0, 2: 2}):
            with self.assertRaises(ValueError): precision_difference(a, b, labels, 2)
        for x, y, k in ((a, b, 4), (a, b, 0), ([0, 0], [0, 0], 1), (a, [0, 1, 3], 2)):
            with self.assertRaises(ValueError): overlap_bound(x, y, k)

    def test_budget_abstention(self):
        case, cert = self.certificate()
        ok, reason = checker.check(case, cert, Fuel(0))
        self.assertFalse(ok); self.assertEqual(reason, 'resource-abstention')
