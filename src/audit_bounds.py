"""Exact finite-frame bounds, not sampling intervals or prospective estimates.

The rankings, frame and known labels are trusted inputs. All arithmetic is
integer/Fraction. The functions do not fetch labels or select new candidates.
"""
from __future__ import annotations
from fractions import Fraction
from typing import Mapping, Sequence


def _weights(first: Sequence[str], second: Sequence[str], k: int) -> dict[str, int]:
    for order in (first, second):
        if not isinstance(order, (list, tuple)) or not order or any(type(x) is not str for x in order):
            raise ValueError('ranking-schema')
        if len(order) != len(set(order)):
            raise ValueError('duplicate-ranked-unit')
    if set(first) != set(second):
        raise ValueError('different-candidate-frames')
    if type(k) is not int or not 1 <= k <= len(first):
        raise ValueError('cutoff')
    a, b = set(first[:k]), set(second[:k])
    return {x: int(x in a) - int(x in b) for x in first}


def _labels(known: Mapping[str, int], weights: Mapping[str, int]) -> None:
    if type(known) is not dict or not set(known) <= set(weights):
        raise ValueError('label-frame')
    if any(type(y) is not int or y not in (0, 1) for y in known.values()):
        raise ValueError('binary-integer-labels-required')


def paired_bounds(first: Sequence[str], second: Sequence[str], k: int,
                  known: dict[str, int], positive_total: int | None = None
                  ) -> tuple[Fraction, Fraction]:
    """Tight min/max of P@k(first)-P@k(second) over compatible labels.

    Optional positive_total is a trusted exact count in the SAME complete
    frame. With no such count, common-set labels cancel, including unknowns.
    """
    weights = _weights(first, second, k)
    _labels(known, weights)
    fixed = sum(weights[x] * y for x, y in known.items())
    unknown = [w for x, w in weights.items() if x not in known]
    pos, neg, neutral = unknown.count(1), unknown.count(-1), unknown.count(0)
    if positive_total is None:
        lo, hi = fixed - neg, fixed + pos
    else:
        if type(positive_total) is not int:
            raise ValueError('positive-total-type')
        remaining = positive_total - sum(known.values())
        if not 0 <= remaining <= len(unknown):
            raise ValueError('infeasible-positive-total')
        # Place remaining positive labels on weights -1,0,+1 for the lower
        # endpoint and on +1,0,-1 for the upper endpoint.
        lo = fixed - min(remaining, neg) + max(0, remaining - neg - neutral)
        hi = fixed + min(remaining, pos) - max(0, remaining - pos - neutral)
    return Fraction(lo, k), Fraction(hi, k)


def correction_bounds(first: Sequence[str], second: Sequence[str], k: int,
                      labels: dict[str, int], max_corrections: int
                      ) -> tuple[Fraction, Fraction]:
    """Tight endpoints under AT MOST h arbitrary binary label corrections.

    This deterministic stress model is not an error probability or confidence
    interval. The trusted frame and both ranking orders must remain fixed.
    """
    weights = _weights(first, second, k)
    _labels(labels, weights)
    if set(labels) != set(weights):
        raise ValueError('complete-label-vector-required')
    if type(max_corrections) is not int or not 0 <= max_corrections <= len(weights):
        raise ValueError('correction-budget')
    fixed = sum(weights[x] * labels[x] for x in weights)
    changes = [weights[x] * (1 - 2 * labels[x]) for x in weights]
    lo = fixed - min(max_corrections, changes.count(-1))
    hi = fixed + min(max_corrections, changes.count(1))
    return Fraction(lo, k), Fraction(hi, k)


def precision_bounds(order: Sequence[str], k: int, known: dict[str, int]
                     ) -> tuple[Fraction, Fraction]:
    weights = _weights(order, order, k)
    _labels(known, weights)
    selected = order[:k]
    fixed = sum(known[x] for x in selected if x in known)
    missing = sum(x not in known for x in selected)
    return Fraction(fixed, k), Fraction(fixed + missing, k)


def insertion_precision_bounds(order: Sequence[str], k: int,
                               observed_labels: dict[str, int],
                               max_missing_selected: int
                               ) -> tuple[Fraction, Fraction]:
    """Sharp bounds if <=r missing units enter an insertion-stable top-k.

    Preconditions: scores/order of observed units do not change when missing
    units are inserted; all observed labels are known; the completion class
    permits r missing units to outrank the observed units with arbitrary labels.
    This conditional assumption is NOT established for the public packet.
    """
    weights = _weights(order, order, k)
    _labels(observed_labels, weights)
    if set(observed_labels) != set(weights):
        raise ValueError('all-observed-labels-required')
    if type(max_missing_selected) is not int or not 0 <= max_missing_selected <= k:
        raise ValueError('missing-selection-budget')
    r = max_missing_selected
    positives = sum(observed_labels[x] for x in order[:k-r])
    return Fraction(positives,k), Fraction(positives+r,k)
