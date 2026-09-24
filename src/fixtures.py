"""Owned specification fixtures. They are not public security-patch examples."""
from __future__ import annotations
import copy

FAMILIES = ('saturating-step', 'identical', 'modular-commutation', 'guarded-index',
            'reverse-guard', 'mixed-change', 'dead-branch', 'incomplete-guard')


def make(family, width, ident):
    x, y, one, zero = ['v', 0], ['v', 1], ['c', 1], ['c', 0]
    high = (1 << width) - 1
    step = ['uadd', x, one]
    idx = ['index', x, y]
    guarded = ['if', ['lt', x, y], idx, zero]
    if family == 'saturating-step':
        before, after = step, ['if', ['eq', x, ['c', high]], ['c', high], step]
    elif family == 'identical': before, after = step, step
    elif family == 'modular-commutation': before, after = ['add', x, y], ['add', y, x]
    elif family == 'guarded-index': before, after = idx, guarded
    elif family == 'reverse-guard': before, after = guarded, idx
    elif family == 'mixed-change': before, after = step, ['uadd', ['sub', x, one], one]
    elif family == 'dead-branch':
        before, after = zero, ['if', ['lt', zero, zero], ['uadd', ['c', high], one], zero]
    elif family == 'incomplete-guard': before, after = idx, ['if', ['le', x, y], idx, zero]
    else: raise ValueError('unknown-fixture')
    return copy.deepcopy({'id': ident, 'width': width, 'domain': [[0, high], [0, high]],
                          'before': before, 'after': after})


def oracle(family, width, x, y):
    """Direct mathematical outcome oracle; no AST or evaluator is used here."""
    high = (1 << width) - 1
    if family == 'saturating-step': old, new = x == high, False
    elif family == 'identical': old, new = x == high, x == high
    elif family in ('modular-commutation', 'dead-branch'): old, new = False, False
    elif family == 'guarded-index': old, new = x >= y, False
    elif family == 'reverse-guard': old, new = False, x >= y
    elif family == 'mixed-change': old, new = x == high, x == 0
    elif family == 'incomplete-guard': old, new = x >= y, x == y
    else: raise ValueError('unknown-fixture')
    return ('repair' if old and not new else ('regression' if new and not old else
            ('both-fault' if old else 'both-safe')))


def classify(old, new):
    a, b = old[0] == 'fault', new[0] == 'fault'
    return 'repair' if a and not b else ('regression' if b and not a else ('both-fault' if a else 'both-safe'))
