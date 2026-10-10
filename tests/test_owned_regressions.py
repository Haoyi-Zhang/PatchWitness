"""Authored scalar/schema regressions; no public dataset or upstream execution."""
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
import public_study as public
import source_frontend as frontend
import verify_results as verifier


def owned_source_case():
    record = {'id': 'owned', 'commit': 'owned-fixture', 'file_path': 'owned.cc',
              'commit_message': 'Authored scalar fixture',
              'diff_context': '+OP_REQUIRES(ctx, x > 0 && y > 0, errors::InvalidArgument("scalar"));',
              'source_asset': {'context_requirements': []}}
    case, diagnostic = frontend.derive_case(record)
    case = {'id': 'W99', **case}
    construction = {'mode': 'automatic-restricted-real-diff-frontend',
                    'input_mode': 'minimal-real-unified-diff-context',
                    'raw_diff_or_source_tree_correspondence': False,
                    'grammar': 'guard-expressions-v2',
                    'evidence_contract': 'guard-trigger-or-source-difference-not-old-fault-new-defined',
                    'parser_cross_check': 'independent-shunting-yard',
                    'evaluator_cross_check': 'recursive-python-iterative-python-c11-short-circuit-oracle'}
    document = {'schema': 'rbw-public-source-evidence-v1', 'construction': construction,
                'cases': [case], 'diagnostics': [diagnostic]}
    return record, case, document


class OwnedRegressions(unittest.TestCase):
    def test_exact_assignment_variable_set(self):
        _, _, document = owned_source_case()
        public.validate_source_evidence(document, {'owned'})
        document['cases'][0]['assignment']['unused'] = 1
        with self.assertRaisesRegex(public.Invalid, 'assignment-variable-set'):
            public.validate_source_evidence(document, {'owned'})

    def test_unvisited_assignment_is_still_exact_integer(self):
        record, case, document = owned_source_case()
        evidence = public.make_source_record(case, record)
        self.assertTrue(public.check_source_record(case, record, evidence)[0])
        self.assertFalse(any(row[0].startswith('1') for row in evidence['guard_trace']))
        for value in (True, 1.0):
            broken = copy.deepcopy(document)
            broken['cases'][0]['assignment']['y'] = value
            with self.assertRaises(public.Invalid):
                public.validate_source_evidence(broken, {'owned'})

    def test_zero_prefixed_literal_is_typed_abstention(self):
        for literal in ('01', '08', '-01'):
            record = {'id': 'owned', 'source_asset': {'context_requirements': []},
                      'diff_context': f'+OP_REQUIRES(ctx, x > {literal}, errors::InvalidArgument("scalar"));'}
            case, diagnostic = frontend.derive_case(record)
            self.assertIsNone(case)
            self.assertEqual((diagnostic['status'], diagnostic['stage'], diagnostic['reason']),
                             ('abstain', 'parse', 'unsupported-integer-literal'))
        self.assertEqual(frontend.parse_expression('0x10 > 0'),
                         ['gt', ['const', 16], ['const', 0]])

    def test_unexpected_system_error_still_propagates(self):
        record, _, _ = owned_source_case()
        with mock.patch.object(frontend, 'parse_expression', side_effect=RuntimeError('owned-system-error')):
            with self.assertRaisesRegex(RuntimeError, 'owned-system-error'):
                frontend.derive_case(record)

    def test_owned_context_must_hold_for_source_record(self):
        record, _, _ = owned_source_case()
        record['diff_context'] = ' OP_REQUIRES(ctx, x != 0, errors::InvalidArgument("context"));\n' + record['diff_context']
        record['source_asset']['context_requirements'] = ['x != 0']
        case, _ = frontend.derive_case(record)
        case = {'id': 'W98', **case}
        self.assertNotEqual(case['assignment']['x'], 0)
        evidence = public.make_source_record(case, record)
        self.assertTrue(public.check_source_record(case, record, evidence)[0])
        case['assignment']['x'] = 0
        evidence = public.make_source_record(case, record)
        self.assertFalse(public.check_source_record(case, record, evidence)[0])

    def test_owned_range_record_has_no_runtime_claim(self):
        record, _, _ = owned_source_case()
        record['diff_context'] = ('-const int min_rank = concat_dim < 0 ? -concat_dim : concat_dim + 1;\n'
                                  '+const int64 min_rank = concat_dim < 0 ? -concat_dim : concat_dim + 1;')
        case, _ = frontend.derive_case(record)
        case = {'id': 'W97', **case}
        evidence = public.make_source_record(case, record)
        with mock.patch.object(public, 'make_source_record', side_effect=RuntimeError('producer')):
            self.assertTrue(public.check_source_record(case, record, evidence)[0])
        self.assertNotIn('before', evidence)
        self.assertNotIn('after', evidence)
        self.assertEqual(evidence['mathematical_value'], {'tag': 'int', 'payload': 2**31})
        evidence['mathematical_value']['payload'] = float(2**31)
        self.assertFalse(public.check_source_record(case, record, evidence)[0])

    def test_finite_summary_rejects_cross_numeric_types(self):
        original = verifier.read_json
        for key, replacement in (('mismatches', False), ('case_count', 25.0), ('exit_status', False)):
            def substituted(path, root_type):
                obj = original(path, root_type)
                if path.name == 'summary.json':
                    obj[key] = replacement
                return obj
            with self.subTest(key=key), mock.patch.object(verifier, 'read_json', side_effect=substituted):
                with self.assertRaisesRegex(verifier.VerificationError, 'finite-summary'):
                    verifier.verify_finite()


if __name__ == '__main__':
    unittest.main()
