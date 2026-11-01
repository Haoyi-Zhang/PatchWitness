"""Repair validation: source-bound admission and unchanged saved decisions.

All inputs remain in memory. No output directory, bootstrap, native compiler,
upstream program, historical campaign or timing experiment is invoked.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
import public_study as public
from source_frontend import derive_evidence_document


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


class SourceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = 'data/public-study/'
        cls.candidates = read(data + 'candidates.json')
        cls.evidence = read(data + 'source-evidence-cases.json')
        cls.protocol = read(data + 'protocol.json')

    def pair(self, ident):
        case = copy.deepcopy(next(c for c in self.evidence['cases'] if c['id'] == ident))
        record = copy.deepcopy(next(r for r in self.candidates['records'] if r['id'] == case['record']))
        return case, record

    def test_changed_source_rejects_old_case_even_after_producer_rehashes(self):
        case, record = self.pair('W02')
        record['diff_context'] = record['diff_context'].replace('pad_width_ >= 0', 'pad_width_ >= -10')
        evidence = public.make_source_record(case, record)
        self.assertEqual(public.check_source_record(case, record, evidence),
                         (False, 'source-case-binding'))

    def test_changed_guard_ast_is_not_bound_by_unchanged_tokens(self):
        case, record = self.pair('W02')
        case['guard'][0] = 'gt'  # Still false at -5, but not the source predicate.
        evidence = public.make_source_record(case, record)
        self.assertEqual(public.check_source_record(case, record, evidence),
                         (False, 'source-case-binding'))

    def test_removed_context_and_alternate_assignment_are_not_source_cases(self):
        case, record = self.pair('W09')
        case['context_tokens'] = []
        case['context_preconditions'] = []
        case['assignment']['num_elements'] = 0
        evidence = public.make_source_record(case, record)
        self.assertEqual(public.check_source_record(case, record, evidence),
                         (False, 'source-case-binding'))

    def test_source_context_metadata_is_reextracted_not_only_hashed(self):
        case, record = self.pair('W09')
        evidence = public.make_source_record(case, record)
        record['source_asset']['context_requirements'] = ['key_tensor->NumElements() > 1']
        self.assertEqual(evidence['record_binding'], public._record_binding(record))
        self.assertEqual(public.check_source_record(case, record, evidence),
                         (False, 'source-case-binding'))

    def test_range_receiver_also_reextracts_the_rhs_premise(self):
        case, record = self.pair('W01')
        record['diff_context'] = record['diff_context'].replace(
            'concat_dim < 0 ? -concat_dim : concat_dim + 1', 'concat_dim')
        evidence = public.make_source_record(case, record)
        self.assertEqual(public.check_source_record(case, record, evidence),
                         (False, 'source-case-binding'))

    def test_direct_freeze_rejects_source_drift_without_outer_script(self):
        candidates = copy.deepcopy(self.candidates)
        record = next(r for r in candidates['records'] if r['id'] == 'U002')
        record['diff_context'] = record['diff_context'].replace('pad_width_ >= 0', 'pad_width_ >= -10')
        with self.assertRaisesRegex(public.Invalid, 'source-evidence-extraction-binding'):
            public.freeze_predictions(candidates, self.evidence, self.protocol)

    def test_direct_freeze_rejects_schema_valid_changed_or_missing_case(self):
        changed = copy.deepcopy(self.evidence)
        next(c for c in changed['cases'] if c['id'] == 'W02')['guard'][0] = 'gt'
        missing = copy.deepcopy(self.evidence)
        missing['cases'] = [c for c in missing['cases'] if c['id'] != 'W02']
        next(d for d in missing['diagnostics'] if d['record'] == 'U002').update(
            status='abstain', stage='extract', reason='no-supported-added-source-pattern')
        for evidence in (changed, missing):
            public.validate_source_evidence(evidence, {r['id'] for r in self.candidates['records']})
            with self.subTest(evidence=evidence['cases'][0]['id']):
                with self.assertRaisesRegex(public.Invalid, 'source-evidence-extraction-binding'):
                    public.freeze_predictions(self.candidates, evidence, self.protocol)

    def test_evaluation_rejects_stale_case_before_any_bootstrap(self):
        candidates = copy.deepcopy(self.candidates)
        record = next(r for r in candidates['records'] if r['id'] == 'U002')
        record['diff_context'] = record['diff_context'].replace('pad_width_ >= 0', 'pad_width_ >= -10')
        predictions = read('results/public-study/frozen/predictions-frozen.json')
        predictions['candidate_hash'] = public.canonical_hash(candidates)
        with mock.patch.object(public, '_cluster_bootstrap', side_effect=AssertionError('bootstrap forbidden')):
            with self.assertRaisesRegex(public.Invalid, 'source-evidence-extraction-binding'):
                public.evaluate_predictions(
                    candidates, read('data/public-study/labels.json'), self.evidence,
                    self.protocol, read('data/public-study/study-design.json'), predictions,
                    read('results/public-study/frozen/outcomes.json'), 67,
                    read('results/source-frontend/summary.json'),
                    read('results/public-study/frozen/source-records.json'), ROOT)

    def test_original_32_predictions_10_cases_22_abstentions_are_unchanged(self):
        derived = derive_evidence_document(self.candidates)
        self.assertTrue(public.typed_equal(derived, self.evidence))
        self.assertEqual(len(derived['cases']), 10)
        self.assertEqual(sum(d['status'] == 'abstain' for d in derived['diagnostics']), 22)
        products = public.freeze_predictions(self.candidates, self.evidence, self.protocol)
        for product, name in zip(products, ('predictions-frozen.json', 'outcomes.json', 'source-records.json')):
            self.assertTrue(public.typed_equal(product, read('results/public-study/frozen/' + name)))
        self.assertEqual(len(products[0]['records']), 32)
        for case in derived['cases']:
            record = next(r for r in self.candidates['records'] if r['id'] == case['record'])
            saved = next(e for e in products[2] if e['case'] == case['id'])
            self.assertTrue(public.check_source_record(case, record, saved)[0])

    def test_original_14_pairs_414_inputs_and_42_saved_policies_are_unchanged(self):
        from bounded_decision import validate, KINDS
        from consumer_policy import decide, direct
        from functional_reference import build_reference
        specs = {s['id']: s for s in read('data/functional-programs.json')['cases']}
        records = {r['case']['id']: r for r in read('results/bounded-decisions/records.json')}
        self.assertEqual(set(specs), set(records))
        self.assertEqual(len(specs), 14)
        checked = []
        for ident, spec in specs.items():
            checked.append(validate(spec, records[ident]))
            before = build_reference(spec['before'], spec['width'])
            after = build_reference(spec['after'], spec['width'])
            for row in records[ident]['rows']:
                self.assertTrue(public.typed_equal(row['before'], before(row['input'])))
                self.assertTrue(public.typed_equal(row['after'], after(row['input'])))
        self.assertEqual(sum(r['inputs_checked'] for r in checked), 414)
        self.assertEqual(sum(r['counts']['repair'] > 0 for r in checked), 8)
        self.assertEqual(sum(r['bounded_refinement'] for r in checked), 6)
        counts = {k: sum(r['counts'][k] for r in checked) for k in KINDS}
        self.assertEqual(counts, read('results/bounded-decisions/summary.json')['counts'])
        policies = read('results/usage-policies/registration.json')['policies']
        saved = read('results/usage-policies/records.json')
        seen = set()
        approvals = dict.fromkeys(policies, 0)
        for row in saved:
            key = (row['case'], row['policy_name'])
            self.assertNotIn(key, seen)
            seen.add(key)
            spec, record = specs[key[0]], records[key[0]]
            policy = dict(policies[key[1]])
            if key[1] == 'full_usage':
                policy['required_inputs'] = [r['input'] for r in record['rows']]
            actual, reference = decide(spec, record, policy), direct(spec, policy)
            self.assertTrue(public.typed_equal(policy, row['policy']))
            self.assertTrue(public.typed_equal(actual, row['checked']))
            self.assertTrue(public.typed_equal(reference, row['direct']))
            self.assertTrue(public.typed_equal(actual, reference))
            approvals[key[1]] += actual['approved']
        self.assertEqual(seen, {(ident, policy) for ident in specs for policy in policies})
        self.assertEqual(len(seen), 42)
        self.assertEqual(approvals, dict(partial_repair=6, total_repair=5, full_usage=7))
        self.assertEqual(approvals, read('results/usage-policies/summary.json')['approved'])


if __name__ == '__main__':
    unittest.main()
