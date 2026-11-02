"""Bounded consumer regressions; no bootstrap, native run or evidence rewrite."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
import check_consumer_policies as policies
import public_study as public
import source_frontend as frontend


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def owned(guard, context=None):
    context = context or []
    record = dict(id='owned', commit='owned-fixture', file_path='owned.cc',
                  commit_message='Owned scalar fixture',
                  diff_context='\n'.join(' if (' + token + ') {}' for token in context)
                  + '\n+if (' + guard + ') { return errors::owned(); }',
                  source_asset={'context_requirements': context})
    case, diagnostic = frontend.derive_case(record)
    if case is None:
        raise ValueError(diagnostic)
    return record, {'id': 'W99', **case}


class SourceAdmissionTests(unittest.TestCase):
    def test_ill_typed_unvisited_guard_rejects_without_outer_document(self):
        record, case = owned('x > 0 || y')
        self.assertEqual(case['assignment'], {'x': 1, 'y': 0})
        evidence = public.make_source_record(case, record)
        with self.assertRaisesRegex(public.Invalid, 'boolean-operand-type'):
            public.validate_source_case(case)
        with mock.patch.object(public, 'replay', side_effect=AssertionError('must admit before replay')):
            self.assertFalse(public.check_source_record(case, record, evidence)[0])

    def test_unvisited_context_is_admitted_eagerly_too(self):
        record, case = owned('x > 0', ['x > 0 || y'])
        evidence = public.make_source_record(case, record)
        with self.assertRaisesRegex(public.Invalid, 'boolean-operand-type'):
            public.validate_source_case(case)
        self.assertFalse(public.check_source_record(case, record, evidence)[0])

    def test_complete_case_schema_and_assignment_types(self):
        record, base = owned('x > 0 || y > 0')
        mutations = [
            lambda c: c.update(extra=True),
            lambda c: c.update(kind=[]),
            lambda c: c.update(id=99),
            lambda c: c.update(record=None),
            lambda c: c['assignment'].update(x=True),
            lambda c: c['assignment'].update(y=0.0),
            lambda c: c['assignment'].update(unused=1),
            lambda c: c['assignment'].update({'9bad': 0}),
            lambda c: c['assignment'].update({f'z{i}': 0 for i in range(17)}),
            lambda c: c.update(trigger_value=1),
            lambda c: c.update(source_tokens=['x'] * 9),
            lambda c: c.update(source_tokens=['']),
            lambda c: c.update(context_tokens=['x > 0']),
        ]
        for index, mutate in enumerate(mutations):
            case = copy.deepcopy(base)
            mutate(case)
            with self.subTest(index=index):
                with self.assertRaises(public.Invalid):
                    public.validate_source_case(case)
                self.assertFalse(public.check_source_record(case, record, {})[0])

    def test_case_node_and_depth_limits_include_skipped_trees(self):
        _, base = owned('x > 0')
        leaf = ['gt', ['var', 'x'], ['const', 0]]
        deep = copy.deepcopy(leaf)
        for _ in range(public.MAX_EXPR_DEPTH):
            deep = ['not', deep]
        wide = copy.deepcopy(leaf)
        for _ in range(5):
            wide = ['or', wide, copy.deepcopy(wide)]
        for guard in (deep, wide):
            case = copy.deepcopy(base)
            case['guard'] = ['or', copy.deepcopy(leaf), guard]
            with self.assertRaisesRegex(public.Invalid, 'expression-limit'):
                public.validate_source_case(case)

    def test_valid_lazy_division_and_retained_cases_still_pass(self):
        record, case = owned('1 > 0 || 1 / y > 0')
        self.assertEqual(case['assignment'], {'y': 0})
        public.validate_source_case(case)
        self.assertTrue(public.check_source_record(case, record, public.make_source_record(case, record))[0])
        candidates = read('data/public-study/candidates.json')
        evidence = read('data/public-study/source-evidence-cases.json')
        protocol = read('data/public-study/protocol.json')
        products = public.freeze_predictions(candidates, evidence, protocol)
        for actual, name in zip(products, ('predictions-frozen.json', 'outcomes.json', 'source-records.json')):
            self.assertTrue(public.typed_equal(actual, read('results/public-study/frozen/' + name)))
        self.assertEqual(len(products[2]), 10)


class ParserLimitTests(unittest.TestCase):
    def test_deep_small_input_is_a_typed_parse_abstention(self):
        for depth, reason in ((500, 'expression-token-limit'), (100, 'expression-syntax-depth')):
            record = dict(id='owned', source_asset={'context_requirements': []},
                diff_context='+if (' + '(' * depth + 'x > 0' + ')' * depth + ') { return errors::owned(); }')
            self.assertLess(len(record['diff_context']), 1200)
            case, diagnostic = frontend.derive_case(record)
            with self.subTest(depth=depth):
                self.assertIsNone(case)
                self.assertEqual((diagnostic['status'], diagnostic['stage'], diagnostic['reason']),
                                 ('abstain', 'parse', reason))

    def test_syntax_depth_boundary_is_explicit(self):
        limit = frontend.MAX_PARSE_DEPTH
        self.assertEqual(frontend.parse_expression('(' * limit + 'x' + ')' * limit), ['var', 'x'])
        with self.assertRaisesRegex(frontend.FrontendError, 'expression-syntax-depth'):
            frontend.parse_expression('(' * (limit + 1) + 'x' + ')' * (limit + 1))

    def test_unary_flat_nodes_tokens_and_text_are_bounded(self):
        balanced = 'x > 0'
        for _ in range(5):
            balanced = '(' + balanced + ') || (' + balanced + ')'
        for text, reason in [
            ('!' * (frontend.MAX_PARSE_DEPTH + 1) + '(x > 0)', 'expression-syntax-depth'),
            (balanced, 'expression-limit'),
            ('x ' * (frontend.MAX_PARSE_TOKENS + 1), 'expression-token-limit'),
            (' ' * 32769, 'expression-text-limit'),
        ]:
            with self.subTest(reason=reason), self.assertRaisesRegex(frontend.FrontendError, reason):
                frontend.parse_expression(text)

    def test_constructed_tree_boundaries_match_consumer_limits(self):
        self.assertEqual(frontend.MAX_EXPR_NODES, public.MAX_EXPR_NODES)
        self.assertEqual(frontend.MAX_EXPR_DEPTH, public.MAX_EXPR_DEPTH)
        leaf = ['gt', ['var', 'x'], ['const', 0]]
        depth_boundary = copy.deepcopy(leaf)
        for _ in range(public.MAX_EXPR_DEPTH - 1):
            depth_boundary = ['not', depth_boundary]
        level = [copy.deepcopy(leaf) for _ in range(24)]
        while len(level) > 1:
            level = [['or', level[i], level[i + 1]] if i + 1 < len(level) else level[i]
                     for i in range(0, len(level), 2)]
        node_boundary = ['not', level[0]]  # 24*3 + 23 + 1 = 96 nodes.
        for tree in (depth_boundary, node_boundary):
            self.assertIs(frontend._limit_expression(tree), tree)
            self.assertEqual(public.validate_expr(tree, {'x'}), 'bool')
            with self.assertRaisesRegex(frontend.FrontendError, 'expression-limit'):
                frontend._limit_expression(['not', tree])
            with self.assertRaisesRegex(public.Invalid, 'expression-limit'):
                public.validate_expr(['not', tree], {'x'})

    def test_combining_guards_is_bounded_before_assignment_search(self):
        record = dict(id='owned', source_asset={'context_requirements': []},
                      diff_context='\n'.join('+if (x > 0) { return errors::owned(); }' for _ in range(25)))
        with mock.patch.object(frontend, '_find_assignment', side_effect=AssertionError('search forbidden')):
            case, diagnostic = frontend.derive_case(record)
        self.assertIsNone(case)
        self.assertEqual((diagnostic['stage'], diagnostic['reason']), ('parse', 'expression-limit'))

    def test_unexpected_runtime_errors_are_not_laundered_into_abstention(self):
        with mock.patch.object(frontend, 'parse_expression', side_effect=RuntimeError('owned-system-error')):
            with self.assertRaisesRegex(RuntimeError, 'owned-system-error'):
                owned('x > 0')


class SavedPolicyPacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.originals = {name: read('results/usage-policies/' + name) for name in
                          ('registration.json', 'records.json', 'summary.json')}
        shutil.copytree(ROOT / 'results/usage-policies/source-preimage', self.path / 'source-preimage')
        self.reset_packet()

    def reset_packet(self):
        for name, data in self.originals.items():
            self.write(name, data)

    def write(self, name, data):
        (self.path / name).write_text(json.dumps(data), encoding='utf-8')

    def check(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            policies.check_saved(self.path)
        return json.loads(stream.getvalue())

    def cli(self):
        flags = ['-X', 'utf8', '-B']
        if sys.flags.optimize:
            flags.insert(0, '-O')
        return subprocess.run([sys.executable, *flags, str(ROOT / 'check_consumer_policies.py'),
                               '--check', str(self.path)], capture_output=True, text=True,
                              encoding='utf-8', timeout=15)

    def test_untouched_packet_and_historical_preimage_are_accepted(self):
        result = self.check()
        self.assertEqual(result['decisions'], 42)
        self.assertEqual(result['approved'], dict(partial_repair=6, total_repair=5, full_usage=7))
        self.assertEqual(result['measured_sources_differ_from_current'], ['src/consumer_policy.py'])
        run = self.cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), result)

    def test_every_reported_row_field_and_nested_type_is_checked(self):
        mutations = [
            lambda r: r.update(case=[]),
            lambda r: r.update(policy_name='unknown'),
            lambda r: r['policy'].update(require_repair=1),
            lambda r: r['checked'].update(approved=int(r['checked']['approved'])),
            lambda r: r['direct'].update(approved=int(r['direct']['approved'])),
            lambda r: r['checked']['counts'].update(repair=float(r['checked']['counts']['repair'])),
            lambda r: r['direct']['counts'].update(**{'new-fault': False}),
            lambda r: r['checked'].update(reasons=['invented']),
            lambda r: r['checked'].update(required_faulting_inputs=[[False]]),
            lambda r: r.update(legacy_bounded_refinement='false'),
            lambda r: r.update(legacy_bounded_refinement=int(r['legacy_bounded_refinement'])),
            lambda r: r.update(input_count=-1),
            lambda r: r.update(input_count=float(r['input_count'])),
            lambda r: r.update(extra=0),
            lambda r: r.pop('input_count'),
        ]
        for index, mutate in enumerate(mutations):
            self.reset_packet()
            rows = copy.deepcopy(self.originals['records.json'])
            mutate(rows[0])
            self.write('records.json', rows)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.check()

    def test_every_summary_field_is_bound_to_recalculation(self):
        base = self.originals['summary.json']
        replacements = dict(status='FAIL', source_pairs=999, decisions=1, same_information_agreements=0,
            approved={}, refinement_insufficient_for_policy=999, new_independent_programs=1,
            source_bindings={}, performance_claim=True)
        self.assertEqual(set(base), set(replacements))
        for key, value in replacements.items():
            self.reset_packet()
            summary = copy.deepcopy(base)
            summary[key] = value
            self.write('summary.json', summary)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check()
        for value in (42.0, True):
            self.write('summary.json', dict(base, decisions=value))
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check()

    def test_registration_fields_and_complete_binding_inventory_are_required(self):
        base = self.originals['registration.json']
        mutations = [
            lambda r: r.update(source_bindings={}),
            lambda r: r.update(pairs=999),
            lambda r: r.update(scope='invented'),
            lambda r: r.update(same_information='invented'),
            lambda r: r.update(performance_claim=True),
            lambda r: r['policies']['total_repair'].update(allow_old_faults=True),
            lambda r: r.update(extra=0),
            lambda r: r['source_bindings'].update({'../outside': '0' * 64}),
            lambda r: r['source_bindings'].update({'src/consumer_policy.py': True}),
            lambda r: r['source_bindings'].update({'src/consumer_policy.py': 'g' * 64}),
        ]
        mutations += [lambda r, key=key: r['source_bindings'].pop(key) for key in policies.SOURCE_FILES]
        mutations += [lambda r, key=key: r.pop(key) for key in base]
        for index, mutate in enumerate(mutations):
            self.reset_packet()
            registration = copy.deepcopy(base)
            mutate(registration)
            self.write('registration.json', registration)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.check()

    def test_summary_and_registration_numeric_aliases_are_not_equality(self):
        for key, value in self.originals['summary.json'].items():
            if type(value) in (int, bool):
                self.reset_packet()
                summary = copy.deepcopy(self.originals['summary.json'])
                summary[key] = float(value) if type(value) is int else int(value)
                self.write('summary.json', summary)
                with self.subTest(summary=key), self.assertRaises(ValueError):
                    self.check()
        self.reset_packet()
        summary = copy.deepcopy(self.originals['summary.json'])
        summary['approved']['partial_repair'] = 6.0
        self.write('summary.json', summary)
        with self.assertRaises(ValueError):
            self.check()
        self.reset_packet()
        registration = copy.deepcopy(self.originals['registration.json'])
        registration['pairs'] = 14.0
        self.write('registration.json', registration)
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_keys_wrong_roots_and_coverage_fail_closed(self):
        for name, data in [('registration.json', []), ('records.json', {}), ('summary.json', None)]:
            self.reset_packet()
            self.write(name, data)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check()
        self.reset_packet()
        rows = copy.deepcopy(self.originals['records.json'])
        rows[-1] = copy.deepcopy(rows[0])
        self.write('records.json', rows)
        with self.assertRaisesRegex(ValueError, 'policy coverage'):
            self.check()
        self.reset_packet()
        text = (self.path / 'summary.json').read_text(encoding='utf-8')
        (self.path / 'summary.json').write_text('{"status":"PASS",' + text[1:], encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate-json-key'):
            self.check()

    def test_wrong_or_missing_historical_preimage_is_not_resealed(self):
        preimage = self.path / 'source-preimage/src/consumer_policy.py'
        original = preimage.read_bytes()
        preimage.write_bytes(b'wrong owned preimage')
        with self.assertRaisesRegex(ValueError, 'preimage missing or differs'):
            self.check()
        preimage.write_bytes(original)
        preimage.unlink()
        with self.assertRaisesRegex(ValueError, 'preimage missing or differs'):
            self.check()

    def test_actual_cli_rejects_all_audit_mutation_classes(self):
        for kind in ('summary-lie', 'row-type-lie', 'empty-bindings'):
            self.reset_packet()
            if kind == 'summary-lie':
                self.write('summary.json', dict(self.originals['summary.json'], status='FAIL', decisions=1,
                    same_information_agreements=0, source_pairs=999, performance_claim=True))
            elif kind == 'row-type-lie':
                rows = copy.deepcopy(self.originals['records.json'])
                for row in rows:
                    row['checked']['approved'] = int(row['checked']['approved'])
                    row['direct']['approved'] = int(row['direct']['approved'])
                    row.update(input_count=-1, legacy_bounded_refinement='false')
                self.write('records.json', rows)
            else:
                self.write('registration.json', dict(self.originals['registration.json'], source_bindings={}))
            run = self.cli()
            with self.subTest(kind=kind):
                self.assertNotEqual(run.returncode, 0)
                self.assertNotIn('"status": "PASS"', run.stdout)


class EvaluationOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = read('data/public-study/candidates.json')
        cls.evidence = read('data/public-study/source-evidence-cases.json')
        cls.protocol = read('data/public-study/protocol.json')
        cls.labels = read('data/public-study/labels.json')
        cls.design = read('data/public-study/study-design.json')
        cls.predictions = read('results/public-study/frozen/predictions-frozen.json')
        cls.outcomes = read('results/public-study/frozen/outcomes.json')
        cls.records = read('results/public-study/frozen/source-records.json')
        cls.frontend = read('results/source-frontend/summary.json')

    def evaluate(self, outcomes):
        return public.evaluate_predictions(self.candidates, self.labels, self.evidence, self.protocol,
            self.design, self.predictions, outcomes, 67, self.frontend, self.records, ROOT)

    def test_fabricated_nonaccepting_fields_and_order_fail_before_bootstrap(self):
        mutations = [('case', 'W999'), ('reason', 'invented-replay-failure'),
                     ('reason', False), ('typed_outcome', 'replay-rejected')]
        for key, value in mutations:
            outcomes = copy.deepcopy(self.outcomes)
            next(row for row in outcomes if not row['accepted'])[key] = value
            with self.subTest(key=key, value=value), mock.patch.object(public, '_cluster_bootstrap',
                    side_effect=AssertionError('bootstrap forbidden')) as bootstrap:
                with self.assertRaisesRegex(public.Invalid, 'outcome-reconstruction'):
                    self.evaluate(outcomes)
                bootstrap.assert_not_called()
        with mock.patch.object(public, '_cluster_bootstrap', side_effect=AssertionError('bootstrap forbidden')) as bootstrap:
            with self.assertRaisesRegex(public.Invalid, 'outcome-reconstruction'):
                self.evaluate(list(reversed(self.outcomes)))
            bootstrap.assert_not_called()

    def test_valid_counts_scores_and_design_are_unchanged_without_resampling(self):
        sentinel = {'not_run': 'bounded regression; no resampling'}
        with mock.patch.object(public, '_cluster_bootstrap', return_value=sentinel):
            summary, _, ablations, readiness = self.evaluate(self.outcomes)
        retained = read('results/public-study/evaluation/summary.json')
        for field in ('metrics', 'rankings', 'coverage', 'typed_outcome_counts', 'failed_readiness_gates',
                      'formal_h1_decision', 'formal_h2_decision'):
            self.assertTrue(public.typed_equal(summary[field], retained[field]), field)
        self.assertEqual(summary['typed_outcome_counts'], {'accepted': 10, 'unsupported-syntax': 22})
        self.assertEqual(summary['validated_minus_syntax_at_20'], 0.0)
        self.assertEqual(len(summary['failed_readiness_gates']), 6)
        self.assertTrue(public.typed_equal(ablations, read('results/public-study/evaluation/ablations.json')))
        self.assertTrue(public.typed_equal(readiness, read('results/public-study/evaluation/readiness.json')))
        self.assertEqual(summary['bootstrap'], sentinel)


if __name__ == '__main__':
    unittest.main()
