"""Check a complete bounded outcome partition against separately supplied source.

Unlike an existential repair witness, this record covers every admitted input.
Acceptance validates a record; only its separately returned refinement verdict
states preservation of all old defined outputs with at least one repaired fault.
No source is executed and no producer evaluator is imported.
"""
from __future__ import annotations

import itertools
import checker
from functional_frontend import translate_pair

KINDS = ('repair', 'new-fault', 'defined-equal', 'defined-changed', 'both-fault')


class Budget:
    def __init__(self, limit=checker.MAX_STATES * checker.MAX_NODES):
        if type(limit) is not int or limit < 0:
            raise ValueError('budget')
        self.remaining = limit

    def tick(self):
        if self.remaining == 0:
            raise RuntimeError('bounded-replay-budget')
        self.remaining -= 1


def classify(old, new):
    if old[0] == 'fault':
        return 'both-fault' if new[0] == 'fault' else 'repair'
    if new[0] == 'fault':
        return 'new-fault'
    return 'defined-equal' if checker._typed_equal(old, new) else 'defined-changed'


def refinement(counts):
    return counts['repair'] > 0 and counts['new-fault'] == counts['defined-changed'] == 0


def validate(spec, record, budget=None):
    """Return checked counts/verdict; malformed, stale or incomplete records fail.

    spec is supplied independently, not copied from record['case']. The trusted
    source lowering/helper semantics are the existing functional-profile ones.
    Resource exhaustion raises, and never supplies an accepting verdict.
    """
    expected = translate_pair(spec['id'], spec['width'], spec['domain'],
                              spec['before'], spec['after'])
    checker._fail(type(record) is dict and set(record) == {
        'case', 'rows', 'counts', 'bounded_refinement'}, 'partition-fields')
    checker.validate_case(record['case'])
    checker._fail(checker._typed_equal(expected, record['case']), 'source-binding')
    rows = record['rows']
    states = checker.validate_case(expected)
    checker._fail(type(rows) is list and len(rows) == states, 'complete-domain')
    counts = dict.fromkeys(KINDS, 0)
    fuel = budget if budget is not None else Budget()
    domain = itertools.product(*(range(lo, hi + 1) for lo, hi in expected['domain']))
    for values, row in zip(domain, rows, strict=True):
        checker._fail(type(row) is dict and set(row) == {'input', 'before', 'after'},
                      'partition-row')
        checker._fail(checker._typed_equal(row['input'], list(values)), 'ordered-input-cover')
        for key in ('before', 'after'):
            value = row[key]
            checker._fail(type(value) is list and len(value) == 2
                          and type(value[0]) is str and value[0] in ('u', 'fault')
                          and ((value[0] == 'u' and type(value[1]) is int
                                and 0 <= value[1] < 1 << expected['width'])
                               or (value[0] == 'fault' and type(value[1]) is str
                                   and len(value[1]) <= 20)), 'typed-outcome')
        old, _ = checker.replay(expected['before'], list(values), expected['width'], fuel)
        new, _ = checker.replay(expected['after'], list(values), expected['width'], fuel)
        checker._fail(checker._typed_equal(row['before'], old)
                      and checker._typed_equal(row['after'], new), 'outcome-replay')
        counts[classify(old, new)] += 1
    supplied = record['counts']
    checker._fail(type(supplied) is dict and set(supplied) == set(KINDS)
                  and all(type(v) is int and v >= 0 for v in supplied.values())
                  and checker._typed_equal(supplied, counts), 'partition-counts')
    verdict = refinement(counts)
    checker._fail(type(record['bounded_refinement']) is bool
                  and record['bounded_refinement'] is verdict, 'refinement-verdict')
    return {'counts': counts, 'bounded_refinement': verdict, 'inputs_checked': states}


def pack_retained(spec, retained):
    """Transfer retained outcomes; validation, not these fields, determines truth."""
    case = translate_pair(spec['id'], spec['width'], spec['domain'],
                          spec['before'], spec['after'])
    checker._fail(retained['id'] == spec['id'], 'retained-case-id')
    rows = [{key: row[key] for key in ('input', 'before', 'after')}
            for row in retained['observations']]
    counts = dict.fromkeys(KINDS, 0)
    for row in rows:
        counts[classify(row['before'], row['after'])] += 1
    record = {'case': case, 'rows': rows, 'counts': counts,
              'bounded_refinement': refinement(counts)}
    validate(spec, record)
    return record
