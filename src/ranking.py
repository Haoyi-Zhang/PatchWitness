"""Finite ranking identities; no fitted classifier or patch-label proxy."""
from __future__ import annotations
from fractions import Fraction


def _check(a, b, k):
    if type(k) is not int or k <= 0 or len(a) < k or len(b) < k:
        raise ValueError('invalid-k')
    if len(set(a)) != len(a) or len(set(b)) != len(b) or set(a) != set(b):
        raise ValueError('not-two-permutations-of-one-cohort')
    return set(a[:k]), set(b[:k])


def overlap_bound(a, b, k):
    aa, bb = _check(a, b, k)
    return Fraction(len(aa - bb), k)


def precision_difference(a, b, labels, k):
    aa, bb = _check(a, b, k)
    if set(labels) != set(a) or any(type(v) is not int or v not in (0, 1) for v in labels.values()):
        raise ValueError('missing-or-invalid-labels')
    return Fraction(sum(labels[x] for x in aa - bb) - sum(labels[x] for x in bb - aa), k)


def sharp_margin(a, b, k, positives):
    aa, bb = _check(a, b, k)
    n = len(a)
    if type(positives) is not int or not 0 <= positives <= n:
        raise ValueError('invalid-positive-count')
    return Fraction(min(len(aa - bb), positives, n - positives), k)
