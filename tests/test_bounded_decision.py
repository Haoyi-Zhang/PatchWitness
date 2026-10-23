"""Benign partition-consumer checks over the fourteen reviewed owned sources."""
import copy
import json
from pathlib import Path
import sys
import subprocess
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bounded_decision import Budget, pack_retained, validate
from checker import Invalid
from functional_reference import build_reference


class BoundedDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = json.loads((ROOT / 'data/functional-programs.json').read_text())['cases']
        cls.retained = {r['id']: r for r in json.loads(
            (ROOT / 'results/functional-diagnostics/cases.json').read_text())}
        cls.records = {s['id']: pack_retained(s, cls.retained[s['id']]) for s in cls.specs}

    def pair(self, ident):
        return next(s for s in self.specs if s['id'] == ident), copy.deepcopy(self.records[ident])

    def test_every_input_against_independent_owned_source_reference(self):
        total, repairs, refinements = 0, 0, 0
        for spec in self.specs:
            record = self.records[spec['id']]
            result = validate(spec, record)
            before = build_reference(spec['before'], spec['width'])
            after = build_reference(spec['after'], spec['width'])
            found_repair, preserves = False, True
            for row in record['rows']:
                old, new = before(row['input']), after(row['input'])
                self.assertEqual(type(old[1]), type(row['before'][1]))
                self.assertEqual(type(new[1]), type(row['after'][1]))
                self.assertEqual(old, row['before'])
                self.assertEqual(new, row['after'])
                found_repair |= old[0] == 'fault' and new[0] == 'u'
                preserves &= old[0] != 'u' or old == new
                total += 1
            self.assertIs(result['bounded_refinement'], bool(found_repair and preserves))
            repairs += found_repair
            refinements += result['bounded_refinement']
        self.assertEqual((total, repairs, refinements), (414, 8, 6))

    def test_existential_repair_is_not_a_refinement_verdict(self):
        for ident in ('F06', 'F13'):
            spec, record = self.pair(ident)
            result = validate(spec, record)
            self.assertGreater(result['counts']['repair'], 0)
            self.assertGreater(result['counts']['new-fault'], 0)
            self.assertFalse(result['bounded_refinement'])
            record['bounded_refinement'] = True
            with self.assertRaises(Invalid):
                validate(spec, record)

    def test_missing_duplicated_reordered_or_added_inputs_fail(self):
        spec, base = self.pair('F06')
        mutations = []
        missing = copy.deepcopy(base); missing['rows'].pop(0); mutations.append(missing)
        duplicate = copy.deepcopy(base); duplicate['rows'][0] = duplicate['rows'][1]; mutations.append(duplicate)
        order = copy.deepcopy(base); order['rows'].reverse(); mutations.append(order)
        added = copy.deepcopy(base); added['rows'].append(added['rows'][0]); mutations.append(added)
        for record in mutations:
            with self.assertRaises(Invalid):
                validate(spec, record)

    def test_false_outcomes_counts_and_host_type_aliases_fail(self):
        spec, base = self.pair('F01')
        mutations = []
        outcome = copy.deepcopy(base); outcome['rows'][0]['after'] = ['u', 0]; mutations.append(outcome)
        count = copy.deepcopy(base); count['counts']['repair'] = 0; mutations.append(count)
        boolean = copy.deepcopy(base); boolean['rows'][0]['input'] = [False]; mutations.append(boolean)
        floating = copy.deepcopy(base); floating['counts']['repair'] = 1.0; mutations.append(floating)
        flag = copy.deepcopy(base); flag['bounded_refinement'] = 1; mutations.append(flag)
        for record in mutations:
            with self.assertRaises(Invalid):
                validate(spec, record)

    def test_source_binding_is_regenerated_from_separate_inputs(self):
        spec, record = self.pair('F01')
        changed = copy.deepcopy(spec)
        changed['after'] = 'def patch(x):\n    return 0\n'
        with self.assertRaises(Invalid):
            validate(changed, record)
        record['case']['id'] = 'Other'
        with self.assertRaises(Invalid):
            validate(spec, record)

    def test_faults_may_remain_but_old_defined_outputs_are_preserved(self):
        spec, record = self.pair('F08')
        result = validate(spec, record)
        self.assertTrue(result['bounded_refinement'])
        self.assertEqual(result['counts']['both-fault'], 8)
        spec, record = self.pair('F09')
        self.assertFalse(validate(spec, record)['bounded_refinement'])
        self.assertEqual(record['counts']['defined-changed'], 8)

    def test_resource_exhaustion_never_supplies_a_verdict(self):
        spec, record = self.pair('F01')
        with self.assertRaises(RuntimeError):
            validate(spec, record, Budget(0))
        for limit in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                Budget(limit)

    def test_cli_refuses_existing_destination_and_altered_comparison(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / 'existing'
            existing.mkdir()
            command = [sys.executable, '-B', str(ROOT / 'check_bounded_decisions.py')]
            result = subprocess.run(command + ['--output', str(existing)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('must be a new directory', result.stderr)
            self.assertEqual(list(existing.iterdir()), [])
            comparison = root / 'comparison'
            comparison.mkdir()
            (comparison / 'summary.json').write_text('{}')
            target = root / 'new-output'
            result = subprocess.run(command + ['--output', str(target),
                                               '--compare', str(comparison)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('output differs', result.stderr)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
