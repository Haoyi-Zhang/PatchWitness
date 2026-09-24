"""Untrusted candidate generator for an owned, unsigned expression IR.

This module does not parse C/C++, execute source programs, or classify security
patches. The separate checker must accept any generated certificate before use.
"""
from __future__ import annotations
import copy
import itertools


class Fuel:
    def __init__(self, maximum: int = 110_000):
        self.maximum = maximum
        self.used = 0

    def tick(self):
        self.used += 1
        if self.used > self.maximum:
            raise RuntimeError('enumeration-budget-exhausted')


def evaluate(expr: list, values: list[int], width: int, fuel: Fuel):
    """Recursive, left-to-right semantics. Both outcomes and paths are explicit."""
    trace = []
    modulus = 1 << width

    def visit(e, path):
        fuel.tick()
        op = e[0]
        if op == 'v':
            ans = ('u', values[e[1]])
        elif op == 'c':
            ans = ('u', e[1])
        else:
            lhs = visit(e[1], path + '0')
            if lhs[0] == 'fault':
                ans = lhs
            elif op == 'if':
                chosen = 2 if lhs[1] else 3
                ans = visit(e[chosen], path + ('1' if chosen == 2 else '2'))
            else:
                rhs = visit(e[2], path + '1')
                if rhs[0] == 'fault':
                    ans = rhs
                else:
                    a, b = lhs[1], rhs[1]
                    if op == 'add': ans = ('u', (a + b) % modulus)
                    elif op == 'sub': ans = ('u', (a - b) % modulus)
                    elif op == 'mul': ans = ('u', (a * b) % modulus)
                    elif op == 'uadd':
                        ans = ('u', a + b) if a + b < modulus else ('fault', 'add-overflow')
                    elif op == 'umul':
                        ans = ('u', a * b) if a * b < modulus else ('fault', 'mul-overflow')
                    elif op == 'index':
                        ans = ('u', a) if a < b else ('fault', 'index-outside')
                    elif op == 'lt': ans = ('b', a < b)
                    elif op == 'le': ans = ('b', a <= b)
                    elif op == 'eq': ans = ('b', a == b)
                    else: raise ValueError('unsupported-operator')
        trace.append([path, ans[0], ans[1]])
        return ans

    outcome = visit(expr, '')
    return list(outcome), trace


def assignments(case: dict):
    return itertools.product(*(range(lo, hi + 1) for lo, hi in case['domain']))


def find(case: dict, fuel: Fuel):
    """Find the lexicographically first improvement, or a bounded-domain absence.

    Inputs to this producer are locally generated, validated fixtures. A producer
    failure is not a checker decision. The certificate includes structural input
    identity, not a self-supplied hash or an external source-fidelity assertion.
    """
    explored = 0
    for vals in assignments(case):
        explored += 1
        before, bt = evaluate(case['before'], list(vals), case['width'], fuel)
        after, at = evaluate(case['after'], list(vals), case['width'], fuel)
        if before[0] == 'fault' and after[0] == 'u':
            return {'case': copy.deepcopy(case), 'input': list(vals),
                    'before': before, 'after': after,
                    'before_trace': bt, 'after_trace': at}, explored
    return None, explored
