"""Process-level policy controls; no upstream application execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bounded_decision import pack_retained


class ConsumerPolicyTests(unittest.TestCase):
    def invoke(self, ident, *flags, mutate=None):
        specs = json.loads((ROOT / 'data/functional-programs.json').read_text())['cases']
        saved = json.loads((ROOT / 'results/functional-diagnostics/cases.json').read_text())
        spec = next(s for s in specs if s['id'] == ident)
        record = pack_retained(spec, next(r for r in saved if r['id'] == ident))
        if mutate:
            mutate(record)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'spec.json').write_text(json.dumps(spec), encoding='utf-8')
            (folder / 'record.json').write_text(json.dumps(record), encoding='utf-8')
            process = subprocess.run([sys.executable, '-B', str(ROOT / 'consume_bounded_decision.py'),
                '--spec', str(folder / 'spec.json'), '--record', str(folder / 'record.json'), *flags],
                text=True, capture_output=True)
            return process.returncode, json.loads(process.stdout)

    def test_valid_false_record_is_not_a_preservation_policy_pass(self):
        code, result = self.invoke('F06')
        self.assertEqual(code, 0)
        self.assertTrue(result['record_validated'])
        self.assertFalse(result['bounded_refinement'])
        self.assertIsNone(result['policy_satisfied'])
        code, result = self.invoke('F06', '--require-preservation')
        self.assertEqual(code, 3)
        self.assertTrue(result['record_validated'])
        self.assertFalse(result['policy_satisfied'])

    def test_bounded_preservation_does_not_mean_total_safety(self):
        code, result = self.invoke('F08', '--require-preservation')
        self.assertEqual(code, 0)
        self.assertTrue(result['policy_satisfied'])
        self.assertEqual(result['counts']['both-fault'], 8)

    def test_incomplete_record_and_resource_abstention_have_no_policy_verdict(self):
        code, result = self.invoke('F01', '--require-preservation', mutate=lambda r:r['rows'].pop())
        self.assertEqual(code, 2)
        self.assertIsNone(result['policy_satisfied'])
        code, result = self.invoke('F01', '--require-preservation', '--budget', '0')
        self.assertEqual(code, 4)
        self.assertEqual(result['status'], 'resource-abstention')
        self.assertIsNone(result['bounded_refinement'])


if __name__ == '__main__':
    unittest.main()
