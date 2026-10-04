#!/usr/bin/env python3
"""Bounded exact validation and finite-frame sensitivity on frozen rankings.

No new repositories, cases, human labels, training, or vulnerability execution.
The fixed validation limit is n<=4; the oracle enumerates completions independently
of the greedy bound formula. Synthetic vector counts are not workload breadth.
"""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
from itertools import combinations, product
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))
from audit_bounds import paired_bounds, correction_bounds, precision_bounds, insertion_precision_bounds
from public_study import load_json


def frac(x):
    return {'numerator': x.numerator, 'denominator': x.denominator, 'value': float(x)}


def require_exact(condition, reason):
    if not condition:
        raise ValueError(reason)

def exact_checks():
    counts = Counter()
    for n in range(1, 5):
        frame = [f'x{i}' for i in range(n)]
        vectors = [dict(zip(frame, ys)) for ys in product((0, 1), repeat=n)]
        for k in range(1, n+1):
            for sa in combinations(frame, k):
                for sb in combinations(frame, k):
                    first = list(sa) + [x for x in frame if x not in sa]
                    second = list(sb) + [x for x in frame if x not in sb]
                    def value(y):
                        return Fraction(sum(y[x] for x in sa)-sum(y[x] for x in sb), k)
                    for partial in product((None, 0, 1), repeat=n):
                        known = {x:y for x,y in zip(frame, partial) if y is not None}
                        compatible = [y for y in vectors if all(y[x] == v for x,v in known.items())]
                        vals = [value(y) for y in compatible]
                        require_exact(paired_bounds(first, second, k, known) == (min(vals), max(vals)), 'partial-bound-mismatch')
                        counts['partial_label_bound_checks'] += 1
                        for total in sorted({sum(y.values()) for y in compatible}):
                            vals_total = [value(y) for y in compatible if sum(y.values()) == total]
                            require_exact(paired_bounds(first, second, k, known, total) == (min(vals_total), max(vals_total)), 'fixed-total-bound-mismatch')
                            counts['fixed_total_bound_checks'] += 1
                    for observed in vectors:
                        for h in range(n+1):
                            neighbors = [y for y in vectors if sum(y[x] != observed[x] for x in frame) <= h]
                            vals = [value(y) for y in neighbors]
                            require_exact(correction_bounds(first, second, k, observed, h) == (min(vals), max(vals)), 'correction-bound-mismatch')
                            counts['label_correction_bound_checks'] += 1
    # Independent oracle inserts labelled hidden units at every possible slot,
    # preserving the visible order. This checks the stated completion class.
    for n in range(1,5):
        frame=[f'x{i}' for i in range(n)]
        for ys in product((0,1),repeat=n):
            labels=dict(zip(frame,ys))
            for k in range(1,n+1):
                for r in range(k+1):
                    values=[]
                    for j in range(r+1):
                        for positions in combinations(range(n+j),j):
                            for hidden_labels in product((0,1),repeat=j):
                                visible=iter(ys); hidden=iter(hidden_labels)
                                seq=[next(hidden) if i in positions else next(visible) for i in range(n+j)]
                                values.append(Fraction(sum(seq[:k]),k))
                    require_exact(insertion_precision_bounds(frame,k,labels,r)==(min(values),max(values)), 'insertion-bound-mismatch')
                    counts['missing_frame_insertion_bound_checks']+=1
    return dict(counts)


def packet_sensitivity():
    summary = load_json(ROOT/'results/public-study/evaluation/summary.json')
    lab = load_json(ROOT/'data/public-study/labels.json')
    # Inspect the actual label schema; each labels entry is tied to a group.
    labels = {r['id']:r['label'] for r in lab['labels']}
    rankings = summary['rankings']; baseline = rankings['syntax']
    result = []
    for method in ('unvalidated', 'validated'):
        order = rankings[method]
        for k in range(1, len(order)+1):
            a,b = set(order[:k]),set(baseline[:k]); diff = a ^ b
            # Hide exactly the labels whose coefficients are nonzero. Do not
            # modify real labels or claim that the hidden labels were sealed.
            known = {x:y for x,y in labels.items() if x not in diff}
            lo,hi = paired_bounds(order,baseline,k,known)
            full_lo,full_hi = paired_bounds(order,baseline,k,labels)
            c0,c1 = correction_bounds(order,baseline,k,labels,1)
            result.append({'method':method,'k':k,'symmetric_difference':len(diff),
                           'paired_delta':frac(full_lo), 'unknown_difference_bounds':[frac(lo),frac(hi)],
                           'one_label_correction_bounds':[frac(c0),frac(c1)],
                           'labels_needed_for_unconstrained_paired_identification':sorted(diff)})
            require_exact(full_lo == full_hi,'complete-label-interval-not-point')
    return result


def build_report():
    return {'schema':'rbw-finite-frame-audit-v1',
            'scope':'deterministic exact checks on benign n<=4 label vectors and fixed inherited rankings',
            'max_owned_frame_size':4, 'checks':exact_checks(),
            'public_sensitivity':packet_sensitivity(),
            'population_inference':False,'new_public_candidates':0,'status':'pass'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results'):
        parser.error('output must be a new results subdirectory')
    cpu=time.process_time();wall=time.monotonic();report=build_report()
    out.mkdir(parents=True)
    (out/'summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (out/'resources.json').write_text(json.dumps({'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'workers':1,'child_processes':0},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='public_sensitivity'},indent=2))

if __name__=='__main__': main()
