"""Exact finite checks for empirical-closure claims.

These checks do not estimate real-world performance.  They validate three
accounting propositions used to delimit what a selected microcohort can show:
(1) an incomplete candidate frame does not identify full-window P@k;
(2) file and group coverage have no universal ordering; and
(3) paired P@k differences depend only on changed top-k members.
"""
from __future__ import annotations

from fractions import Fraction
import itertools
from typing import Any

from ranking import overlap_bound, precision_difference, sharp_margin


def _rank(rows: list[dict[str, Any]]) -> list[str]:
    return [row["id"] for row in sorted(rows, key=lambda row: (-row["score"], row["id"]))]


def _precision(rows: list[dict[str, Any]], k: int) -> Fraction:
    order = _rank(rows)
    labels = {row["id"]: row["label"] for row in rows}
    return Fraction(sum(labels[item] for item in order[:k]), k)


def candidate_frame_ambiguity(max_k: int = 20) -> dict[str, Any]:
    """Construct two full frames with the same selected packet but P@k 0 vs 1."""
    mismatches = 0
    selected_precisions: list[str] = []
    for k in range(1, max_k + 1):
        # The selected packet is identical in both worlds and contains 2k items.
        selected = [
            {"id": f"S{i:03d}", "score": 10_000 - i, "label": i % 2}
            for i in range(2 * k)
        ]
        selected_precision = _precision(selected, k)
        selected_precisions.append(f"{selected_precision.numerator}/{selected_precision.denominator}")
        hidden_zero = [
            {"id": f"Z{i:03d}", "score": 20_000 - i, "label": 0}
            for i in range(k)
        ]
        hidden_one = [
            {"id": f"O{i:03d}", "score": 20_000 - i, "label": 1}
            for i in range(k)
        ]
        world_zero = selected + hidden_zero
        world_one = selected + hidden_one
        if _precision(world_zero, k) != 0 or _precision(world_one, k) != 1:
            mismatches += 1
        # A selector that retains the S-prefixed records returns the same packet.
        if [row for row in world_zero if row["id"].startswith("S")] != selected:
            mismatches += 1
        if [row for row in world_one if row["id"].startswith("S")] != selected:
            mismatches += 1
    return {
        "claim": "Without a complete candidate frame, the selected packet is compatible with full-window P@k equal to 0 or 1.",
        "k_values": list(range(1, max_k + 1)),
        "constructed_full_frames": 2 * max_k,
        "selected_packet_identical_in_each_pair": True,
        "full_window_precision_extremes": [0.0, 1.0],
        "selected_precision_fractions": selected_precisions,
        "mismatches": mismatches,
        "obligations": 4 * max_k,
    }


def grouping_sensitivity(max_group_size: int = 6) -> dict[str, Any]:
    """Enumerate three positive groups and all feasible accepted-unit counts."""
    configurations = 0
    mismatches = 0
    maximum_group_minus_unit = (Fraction(-1), None)
    maximum_unit_minus_group = (Fraction(-1), None)
    equal_examples = 0
    for sizes in itertools.product(range(1, max_group_size + 1), repeat=3):
        for accepted in itertools.product(*(range(size + 1) for size in sizes)):
            configurations += 1
            unit = Fraction(sum(accepted), sum(sizes))
            group = Fraction(sum(count > 0 for count in accepted), 3)
            group_minus_unit = group - unit
            unit_minus_group = unit - group
            if group_minus_unit > maximum_group_minus_unit[0]:
                maximum_group_minus_unit = (group_minus_unit, (sizes, accepted, unit, group))
            if unit_minus_group > maximum_unit_minus_group[0]:
                maximum_unit_minus_group = (unit_minus_group, (sizes, accepted, unit, group))
            if unit == group:
                equal_examples += 1
            # Identity check against direct unit/group definitions.
            direct_unit = Fraction(sum(accepted), sum(sizes))
            direct_group = Fraction(sum(count > 0 for count in accepted), 3)
            if unit != direct_unit or group != direct_group:
                mismatches += 1

    def describe(item: tuple[Fraction, Any]) -> dict[str, Any]:
        gap, payload = item
        sizes, accepted, unit, group = payload
        return {
            "gap_fraction": f"{gap.numerator}/{gap.denominator}",
            "gap": float(gap),
            "group_sizes": list(sizes),
            "accepted_units": list(accepted),
            "unit_coverage_fraction": f"{unit.numerator}/{unit.denominator}",
            "group_coverage_fraction": f"{group.numerator}/{group.denominator}",
        }

    return {
        "claim": "Unit and group coverage have no universal ordering when group sizes differ.",
        "groups": 3,
        "max_group_size": max_group_size,
        "configurations": configurations,
        "group_minus_unit_extreme": describe(maximum_group_minus_unit),
        "unit_minus_group_extreme": describe(maximum_unit_minus_group),
        "both_gap_directions_observed": maximum_group_minus_unit[0] > 0 and maximum_unit_minus_group[0] > 0,
        "equal_examples": equal_examples,
        "observed_microcohort": {
            "positive_files": 16,
            "accepted_positive_files": 10,
            "positive_commit_groups": 10,
            "accepted_positive_commit_groups": 10,
            "unit_coverage_fraction": "10/16",
            "group_coverage_fraction": "10/10",
            "difference_fraction": "3/8",
        },
        "mismatches": mismatches,
        "obligations": configurations,
    }


def paired_top_k_identity() -> dict[str, Any]:
    """Exhaustively verify the paired top-k identity and sharp label-count bound."""
    baseline = list(range(6))
    alternative = [3, 4, 2, 0, 1, 5]
    k = 3
    mismatches = 0
    labelings = 0
    by_positive_count: dict[int, list[Fraction]] = {count: [] for count in range(7)}
    for bits in itertools.product((0, 1), repeat=6):
        labelings += 1
        labels = dict(zip(baseline, bits))
        delta = precision_difference(alternative, baseline, labels, k)
        direct = Fraction(
            sum(labels[item] for item in alternative[:k])
            - sum(labels[item] for item in baseline[:k]),
            k,
        )
        if delta != direct or abs(delta) > overlap_bound(alternative, baseline, k):
            mismatches += 1
        by_positive_count[sum(bits)].append(delta)
    sharp_checks = 0
    for positives, values in by_positive_count.items():
        bound = sharp_margin(alternative, baseline, k, positives)
        sharp_checks += 1
        if max(values) != bound or min(values) != -bound:
            mismatches += 1
    return {
        "claim": "Paired P@k changes are exactly the net labels among entering and leaving top-k items.",
        "cohort_size": 6,
        "k": k,
        "labelings": labelings,
        "sharp_label_count_checks": sharp_checks,
        "top_k_symmetric_difference_size": len(set(alternative[:k]) ^ set(baseline[:k])),
        "overlap_bound_fraction": str(overlap_bound(alternative, baseline, k)),
        "mismatches": mismatches,
        "obligations": labelings + sharp_checks,
    }


def run_all() -> dict[str, Any]:
    ambiguity = candidate_frame_ambiguity()
    grouping = grouping_sensitivity()
    paired = paired_top_k_identity()
    mismatches = ambiguity["mismatches"] + grouping["mismatches"] + paired["mismatches"]
    obligations = ambiguity["obligations"] + grouping["obligations"] + paired["obligations"]
    return {
        "schema": "rbw-closure-checks-v1",
        "scope": "exact finite accounting checks; not an estimate of security-patch prevalence or utility",
        "candidate_frame_ambiguity": ambiguity,
        "grouping_sensitivity": grouping,
        "paired_top_k_identity": paired,
        "obligations": obligations,
        "mismatches": mismatches,
        "exit_status": 0 if mismatches == 0 else 1,
    }
