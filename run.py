#!/usr/bin/env python3
"""Run the owned finite-checking experiment with a bounded single process.

No downloads, C/C++ execution, real patch classification, model calls, or network.
All scientific numbers are regenerated. Timings and RSS vary across hosts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import csv
import io
import itertools
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
import checker
from fixtures import FAMILIES, classify, make, oracle
from producer import Fuel, evaluate, find


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def experiment(pilot, out):
    start_wall = time.monotonic()
    start_cpu = time.process_time()
    fuel = Fuel(110_000)
    rows, cases, certificates = [], [], []
    specs = [('mixed-change', 3, 'P01')] if pilot else [
        (family, width, f'C{1+i+8*(width-2):02d}')
        for width in (2, 3, 4) for i, family in enumerate(FAMILIES)] + [('mixed-change', 5, 'C25')]
    mismatches = 0
    for family, width, ident in specs:
        case = make(family, width, ident)
        states = checker.validate_case(case)
        counts = Counter()
        initial_fuel = fuel.used
        for vals in itertools.product(*(range(lo, hi + 1) for lo, hi in case['domain'])):
            old, ot = evaluate(case['before'], list(vals), width, fuel)
            new, nt = evaluate(case['after'], list(vals), width, fuel)
            co, cot = checker.replay(case['before'], list(vals), width, fuel)
            cn, cnt = checker.replay(case['after'], list(vals), width, fuel)
            fuel.tick()  # A separate direct-oracle assignment obligation.
            cls = classify(old, new)
            if cls != oracle(family, width, *vals) or (old, ot, new, nt) != (co, cot, cn, cnt):
                mismatches += 1
            counts[cls] += 1
        cert, searched = find(case, fuel)
        accepted = cert is not None and checker.check(case, cert, fuel)[0]
        if (counts['repair'] > 0) != accepted:
            mismatches += 1
        cases.append({'family': family, 'case': case})
        if cert is not None: certificates.append(cert)
        rows.append({'case': ident, 'family': family, 'width': width, 'assignments': states,
                     **{s: counts[s] for s in ('repair', 'regression', 'both-safe', 'both-fault')},
                     'search_assignments': searched, 'certificate_accepted': int(accepted),
                     'obligations': fuel.used-initial_fuel})
    semantic_mismatches = mismatches
    unit = None
    unit_text = ''
    if not pilot:
        import test_core
        test_core.FUEL = fuel
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_core)
        stream = io.StringIO()
        res = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        unit_text = stream.getvalue()
        unit = {'tests_run': res.testsRun, 'failures': len(res.failures), 'errors': len(res.errors),
                **test_core.COUNTS}
        if not res.wasSuccessful(): mismatches += 1
    totals = {s: sum(r[s] for r in rows) for s in ('assignments','repair','regression','both-safe','both-fault')}
    summary = {'scope': 'owned finite unsigned IR; not public security patches',
               'case_count': len(rows), **totals, 'mismatches': mismatches,
               'semantic_mismatches': semantic_mismatches,
               'accepted_certificates': len(certificates), 'unit_tests': unit,
               'obligations': fuel.used, 'obligation_limit': fuel.maximum,
               'max_width': max(r['width'] for r in rows),
               'max_assignments_per_case': max(r['assignments'] for r in rows),
               'cpu_seconds': time.process_time()-start_cpu,
               'wall_seconds': time.monotonic()-start_wall,
               'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'workers': 1, 'child_processes': 0,
               'real_patch_cases_evaluated': 0, 'precision_at_20_difference': None,
               'witness_coverage_on_real_patches': None,
               'exit_status': 0 if mismatches == 0 else 1}
    out.mkdir(parents=True, exist_ok=False)
    write_json(out/'summary.json', summary)
    write_json(out/'cases.json', cases)
    write_json(out/'certificates.json', certificates)
    with open(out/'cases.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    if unit is not None: (out/'unit-tests.txt').write_text(unit_text)
    print(json.dumps(summary, indent=2))
    return summary['exit_status']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--output', type=Path, required=True, help='new directory within the artifact root')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT) or out == ROOT or out.exists():
        parser.error('output must be a new directory within this artifact root')
    # Hard process limits; no worker or child is spawned.
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('wall-limit')))
    signal.alarm(40)
    # The tests' temporary files are confined under the reviewed output parent.
    import tempfile
    temp_root = ROOT / 'results'
    temp_root.mkdir(exist_ok=True)
    tempfile.tempdir = str(temp_root)
    return experiment(args.pilot, out)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (TimeoutError, MemoryError, RuntimeError) as exc:
        print(json.dumps({'state': 'resource-abstention', 'reason': type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)
