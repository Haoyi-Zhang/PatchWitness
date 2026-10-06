#!/usr/bin/env python3
"""Offline bounded authored-fixture campaign; never opens public-study data.

Preserves original POSIX runners. This supervisor imposes a 60-second wall
timeout per synchronous worker; Windows CPU/address-space/RSS are not measured
or enforced. All new outputs and test temporaries stay in the supplied new
output directory. The optional C11 route executes only the owned interpreter.
"""
from __future__ import annotations
import argparse
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def expression_checks():
    import source_frontend as primary
    import source_frontend_reference as reference
    import public_study as public
    expressions = [f'x {op} y' for op in ('<', '<=', '>', '>=', '==', '!=')]
    expressions += ['!(x < y)', 'x != 0 && y / x > 0', 'x == 0 || y / x < 0',
                    '(x < y) || (x == y && x != 0)', 'x / y', '-7 / x', '7 / x']
    probes = []
    for text in expressions:
        ast = primary.parse_expression(text)
        names = sorted(primary.variables(ast))
        for values in itertools.product((-2, -1, 0, 1, 2), repeat=len(names)):
            probes.append((text, ast, dict(zip(names, values))))
    text = '-9223372036854775808 / x'
    probes += [(text, primary.parse_expression(text), {'x': x}) for x in (-1, 1)]
    observations = []; bytecode = []; expected_c = []
    for text, ast, assignment in probes:
        values = []
        produced_trace = []; replay_trace = []
        routes = (lambda: primary.evaluate(ast, assignment),
                  lambda: reference.evaluate(text, assignment),
                  lambda: public.producer_eval(ast, assignment, produced_trace),
                  lambda: public.replay(ast, assignment))
        errors = (primary.FrontendError, reference.ReferenceError, public.Invalid, public.Invalid)
        for index, (route, error) in enumerate(zip(routes, errors)):
            try:
                value = route()
                if index == 3:
                    value, replay_trace = value
                if index < 2:
                    value = {'tag': 'bool' if type(value) is bool else 'int', 'payload': value}
                values.append(value)
            except error:
                values.append(None)
        if not all(public.typed_equal(values[0], value) for value in values[1:]):
            raise ValueError('owned-expression-outcome-disagreement')
        if values[0] is not None and not public.typed_equal(produced_trace, replay_trace):
            raise ValueError('owned-expression-trace-disagreement')
        observations.append({'expression': text, 'assignment': assignment, 'outcomes': values,
                             'producer_trace': produced_trace, 'replay_trace': replay_trace})
        bytecode.append(' '.join(primary.ast_to_rpn(ast, assignment)))
        expected_c.append(values[0])
    return observations, bytecode, expected_c


def owned_tests():
    # All retained tests remain discoverable. Select only authored finite tests;
    # the other modules' public-data tests are deliberately not executed here.
    names = ['test_core', 'test_closure_checks', 'test_owned_regressions']
    audit_names = [
        'test_exact_enumeration_detects_a_wrong_bound_formula',
        'test_unknown_intersection_labels_cancel',
        'test_unknown_difference_bounds_are_attainable',
        'test_fixed_total_tightens_unknown_label_bounds',
        'test_one_label_correction_can_erase_single_swap_gain',
        'test_equal_top_sets_force_zero_under_all_corrections',
        'test_bounds_reject_bool_labels_and_float_totals',
        'test_bounds_reject_mismatched_frames_and_impossible_totals',
        'test_bounded_missing_frame_narrows_only_under_stated_budget',
        'test_finite_verifier_rejects_duplicate_certificate',
        'test_finite_verifier_rejects_balanced_row_counter_tamper',
    ]
    names += ['test_audit_contracts.AuditContracts.' + name for name in audit_names]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
            'status': 'pass' if result.wasSuccessful() else 'fail'}


def phase(name, out):
    out.mkdir(parents=True, exist_ok=False)
    scratch = out / 'scratch'; scratch.mkdir()
    tempfile.tempdir = str(scratch)
    cpu = time.process_time(); wall = time.monotonic()
    if name in ('finite', 'pilot'):
        import run
        code = run.experiment(name == 'pilot', out / 'data')
        if code:
            return code
        if name == 'finite':
            from verify_results import verify_finite
            result = verify_finite(out / 'data')
        else:
            result = {'cases': 1, 'assignments': 64}
    elif name == 'bounds':
        from run_contract_audit import exact_checks
        result = exact_checks()
    elif name == 'closure':
        from closure_checks import run_all
        result = run_all()
        if result['exit_status']:
            return result['exit_status']
    elif name == 'tests':
        result = owned_tests()
        if result['status'] != 'pass':
            dump(out / 'summary.json', result)
            return 1
    elif name in ('expressions', 'c11'):
        observations, bytecode, expected = expression_checks()
        if name == 'c11':
            from run_frontend_validation import _run_c_oracle, _parse_oracle
            from public_study import typed_equal
            actual, digest = _run_c_oracle(bytecode, scratch)
            if len(actual) != len(expected) or not all(
                    typed_equal(_parse_oracle(a), e) for a, e in zip(actual, expected, strict=True)):
                raise ValueError('owned-c11-disagreement')
            for row, value in zip(observations, actual, strict=True):
                row['c11_result'] = value
        dump(out / 'observations.json', observations)
        dump(out / 'bytecode.json', bytecode)
        result = {'checks': len(observations), 'distinct_expression_assignments': len(observations),
                  'defined': sum(row['outcomes'][0] is not None for row in observations),
                  'error_controls': sum(row['outcomes'][0] is None for row in observations),
                  'mismatches': 0, 'c11_executed': name == 'c11'}
        if name == 'c11':
            result['oracle_source_sha256'] = digest
    else:
        raise ValueError('phase')
    dump(out / 'summary.json', result)
    dump(out / 'resources.json', {'wall_seconds': time.monotonic() - wall,
                                 'cpu_seconds': time.process_time() - cpu,
                                 'workers': 1, 'peak_rss_kib': None})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new raw-output directory')
    parser.add_argument('--c11', action='store_true', help='also compile the owned C11 oracle')
    parser.add_argument('--phase', choices=('tests', 'finite', 'pilot', 'bounds', 'closure', 'expressions', 'c11'))
    args = parser.parse_args(); out = args.output.resolve()
    if out.exists() or out == ROOT or ROOT.is_relative_to(out):
        parser.error('output must be a new directory, not the artifact or its ancestor')
    if args.phase:
        return phase(args.phase, out)
    out.mkdir(parents=True, exist_ok=False)
    stages = ['tests', 'finite', 'pilot', 'bounds', 'closure', 'expressions']
    if args.c11:
        stages.append('c11')
    report = {'scope': 'owned finite/formal/authored scalar fixtures only',
              'platform': platform.platform(), 'python': sys.version,
              'worker_wall_timeout_seconds': 60, 'workers': 1, 'commands': [],
              'posix_cpu_and_address_space_limits_enforced': False,
              'public_dataset_executed': False, 'network_used': False, 'status': 'running'}
    wall = time.monotonic()
    for name in stages:
        cmd = [sys.executable, '-B', str(Path(__file__).resolve()), '--phase', name,
               '--output', str(out / name)]
        started = time.monotonic()
        with (out / (name + '.stdout.txt')).open('w', encoding='utf-8') as so, \
                (out / (name + '.stderr.txt')).open('w', encoding='utf-8') as se:
            try:
                proc = subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONUTF8': '1',
                    'PYTHONDONTWRITEBYTECODE': '1'}, stdout=so, stderr=se, timeout=60, check=False)
                code = proc.returncode
            except subprocess.TimeoutExpired:
                # subprocess.run kills and reaps this exact worker. Only the
                # C11 phase spawns owned children, each with its own 20s timeout.
                code = 124
        report['commands'].append({'phase': name, 'command': cmd, 'exit_status': code,
                                   'wall_seconds': time.monotonic() - started})
        if code:
            report['status'] = 'fail'; report['failed_phase'] = name
            break
    else:
        report['status'] = 'pass'
    report['wall_seconds'] = time.monotonic() - wall
    report['c11_executed'] = args.c11 and report['status'] == 'pass'
    dump(out / 'campaign.json', report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
