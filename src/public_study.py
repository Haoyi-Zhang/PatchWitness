"""Label-separated public microcohort analysis and restricted witness replay.

The freeze phase consumes only candidate, protocol, and restricted witness-case
files.  A separate process opens retrospective labels and computes descriptive
metrics.  The design is deliberately fail-closed: a prospective H1/H2 decision
is emitted only when every readiness fact is supported by machine-checkable
package evidence.  The retained microcohort does not meet that condition.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
import re
from typing import Any

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1
INT32_MIN = -(2**31)
MAX_PUBLIC_JSON_BYTES = 1_048_576
MAX_PUBLIC_JSON_DEPTH = 64
MAX_EXPR_NODES = 96
MAX_EXPR_DEPTH = 16
MAX_CANDIDATES = 600
MAX_TEXT = 16_384
MAX_SOURCE_TOKENS = 8
ALLOWED_OPS = {
    "const", "var", "not", "and", "or", "eq", "ne", "lt", "le",
    "gt", "ge", "add", "sub", "mul", "div",
}
BOOL_OPS = {"not", "and", "or"}
COMPARE_OPS = {"eq", "ne", "lt", "le", "gt", "ge"}
ARITH_OPS = {"add", "sub", "mul", "div"}
GATE_IDS = (
    "all_candidates_counted_with_typed_outcomes",
    "automatic_source_frontend",
    "candidate_selection_independent_of_labels",
    "complete_repository_time_window",
    "independent_replay_checker",
    "labels_sealed_before_method_development",
    "reference_count_at_least_55",
    "strongest_published_same_budget_baseline",
    "temporal_holdout",
)


class Invalid(ValueError):
    """Raised when a retained input violates the frozen contract."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Invalid(reason)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _scan_json_depth(raw: bytes) -> None:
    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                in_string = False
        elif byte == 34:
            in_string = True
        elif byte in (91, 123):
            depth += 1
            _require(depth <= MAX_PUBLIC_JSON_DEPTH, "json-depth-limit")
        elif byte in (93, 125):
            depth -= 1
            _require(depth >= 0, "invalid-json-nesting")
    _require(depth == 0 and not in_string, "invalid-json-nesting")


def load_json_value(path: Path) -> Any:
    """Read bounded JSON, rejecting duplicate keys and non-finite values."""
    with path.open("rb") as handle:
        raw = handle.read(MAX_PUBLIC_JSON_BYTES + 1)
    _require(len(raw) <= MAX_PUBLIC_JSON_BYTES, "json-byte-limit")
    _scan_json_depth(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise Invalid("json-utf8") from exc

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            _require(key not in out, "duplicate-json-key")
            out[key] = value
        return out

    def parse_int(text_value: str) -> int:
        _require(len(text_value.lstrip("-")) <= 19, "integer-encoding-limit")
        return int(text_value)

    def parse_float(text_value: str) -> float:
        _require(len(text_value) <= 32, "float-encoding-limit")
        value = float(text_value)
        _require(math.isfinite(value), "nonfinite-number")
        return value

    def reject_constant(_: str) -> Any:
        raise Invalid("nonfinite-number")

    try:
        data = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_int=parse_int,
            parse_float=parse_float,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
        raise Invalid("invalid-json") from exc
    return data


def load_json(path: Path) -> dict[str, Any]:
    """Read a bounded JSON object."""
    data = load_json_value(path)
    _require(isinstance(data, dict), "json-root")
    return data


def _require_int(value: Any) -> int:
    _require(type(value) is int and INT64_MIN <= value <= INT64_MAX, "integer-range")
    return value


def _require_text(value: Any, reason: str, *, minimum: int = 1, maximum: int = MAX_TEXT) -> str:
    _require(isinstance(value, str) and minimum <= len(value) <= maximum, reason)
    _require("\x00" not in value, reason)
    return value


def validate_expr(
    expr: Any,
    variables: set[str],
    depth: int = 0,
    counter: list[int] | None = None,
) -> str:
    """Validate an expression and return its static sort (``int`` or ``bool``)."""
    if counter is None:
        counter = [0]
    counter[0] += 1
    _require(counter[0] <= MAX_EXPR_NODES and depth <= MAX_EXPR_DEPTH, "expression-limit")
    _require(
        isinstance(expr, list)
        and bool(expr)
        and isinstance(expr[0], str)
        and expr[0] in ALLOWED_OPS,
        "expression-shape",
    )
    op = expr[0]
    arity = 1 if op in {"const", "var", "not"} else 2
    _require(len(expr) == arity + 1, "expression-arity")
    if op == "const":
        _require_int(expr[1])
        return "int"
    if op == "var":
        _require(isinstance(expr[1], str) and expr[1] in variables, "unknown-variable")
        return "int"
    child_sorts = [validate_expr(child, variables, depth + 1, counter) for child in expr[1:]]
    if op == "not":
        _require(child_sorts == ["bool"], "boolean-operand-type")
        return "bool"
    if op in {"and", "or"}:
        _require(child_sorts == ["bool", "bool"], "boolean-operand-type")
        return "bool"
    _require(child_sorts == ["int", "int"], "integer-operand-type")
    return "bool" if op in COMPARE_OPS else "int"


def _producer_trunc_div(a: int, b: int) -> int:
    """Exact truncation toward zero, without a floating-point conversion."""
    _require(b != 0, "division-by-zero")
    magnitude = abs(a) // abs(b)
    result = -magnitude if (a < 0) != (b < 0) else magnitude
    return _require_int(result)


def producer_eval(
    expr: list[Any],
    env: dict[str, int],
    trace: list[dict[str, Any]] | None = None,
) -> int | bool:
    """Recursive evaluator used only by the certificate producer."""
    if trace is None:
        trace = []
    op = expr[0]
    if op == "const":
        value: int | bool = _require_int(expr[1])
    elif op == "var":
        value = _require_int(env[expr[1]])
    elif op == "not":
        child = producer_eval(expr[1], env, trace)
        _require(type(child) is bool, "boolean-operand-type")
        value = not child
    elif op == "and":
        left = producer_eval(expr[1], env, trace)
        _require(type(left) is bool, "boolean-operand-type")
        if not left:
            value = False
        else:
            right = producer_eval(expr[2], env, trace)
            _require(type(right) is bool, "boolean-operand-type")
            value = right
    elif op == "or":
        left = producer_eval(expr[1], env, trace)
        _require(type(left) is bool, "boolean-operand-type")
        if left:
            value = True
        else:
            right = producer_eval(expr[2], env, trace)
            _require(type(right) is bool, "boolean-operand-type")
            value = right
    else:
        a = producer_eval(expr[1], env, trace)
        b = producer_eval(expr[2], env, trace)
        _require(type(a) is int and type(b) is int, "integer-operand-type")
        if op == "eq":
            value = a == b
        elif op == "ne":
            value = a != b
        elif op == "lt":
            value = a < b
        elif op == "le":
            value = a <= b
        elif op == "gt":
            value = a > b
        elif op == "ge":
            value = a >= b
        elif op == "add":
            value = _require_int(a + b)
        elif op == "sub":
            value = _require_int(a - b)
        elif op == "mul":
            value = _require_int(a * b)
        elif op == "div":
            value = _producer_trunc_div(a, b)
        else:  # pragma: no cover - guarded by validate_expr
            raise Invalid("operator")
    trace.append({"node": op, "value": value})
    return value


def replay(expr: list[Any], env: dict[str, int]) -> tuple[int | bool, list[dict[str, Any]]]:
    """Iterative replay machine used by the checker, independent of producer control flow."""
    instructions: list[tuple[str, Any]] = [("eval", expr)]
    vals: list[int | bool] = []
    trace: list[dict[str, Any]] = []
    while instructions:
        kind, payload = instructions.pop()
        if kind == "eval":
            node = payload
            op = node[0]
            if op == "const":
                value = _require_int(node[1])
                vals.append(value)
                trace.append({"node": op, "value": value})
            elif op == "var":
                value = _require_int(env[node[1]])
                vals.append(value)
                trace.append({"node": op, "value": value})
            elif op == "not":
                instructions.extend([("apply1", op), ("eval", node[1])])
            elif op in {"and", "or"}:
                instructions.extend([("lazy", (op, node[2])), ("eval", node[1])])
            else:
                instructions.extend([("apply2", op), ("eval", node[2]), ("eval", node[1])])
        elif kind == "lazy":
            op, right = payload
            left = vals.pop()
            _require(type(left) is bool, "boolean-operand-type")
            if (op == "and" and not left) or (op == "or" and left):
                vals.append(left)
                trace.append({"node": op, "value": left})
            else:
                instructions.extend([("lazy_finish", op), ("eval", right)])
        elif kind == "lazy_finish":
            value = vals.pop()
            _require(type(value) is bool, "boolean-operand-type")
            vals.append(value)
            trace.append({"node": payload, "value": value})
        elif kind == "apply1":
            child = vals.pop()
            _require(type(child) is bool, "boolean-operand-type")
            value = not child
            vals.append(value)
            trace.append({"node": payload, "value": value})
        elif kind == "apply2":
            b = vals.pop()
            a = vals.pop()
            op = payload
            _require(type(a) is int and type(b) is int, "integer-operand-type")
            if op == "eq":
                value = a == b
            elif op == "ne":
                value = a != b
            elif op == "lt":
                value = a < b
            elif op == "le":
                value = a <= b
            elif op == "gt":
                value = a > b
            elif op == "ge":
                value = a >= b
            elif op == "add":
                value = _require_int(a + b)
            elif op == "sub":
                value = _require_int(a - b)
            elif op == "mul":
                value = _require_int(a * b)
            elif op == "div":
                _require(b != 0, "division-by-zero")
                quotient = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    quotient = -quotient
                value = _require_int(quotient)
            else:  # pragma: no cover
                raise Invalid("operator")
            vals.append(value)
            trace.append({"node": op, "value": value})
        else:  # pragma: no cover
            raise Invalid("instruction")
    _require(len(vals) == 1, "stack")
    return vals[0], trace


def _norm_source(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_candidates(candidates: dict[str, Any]) -> list[dict[str, Any]]:
    _require(
        set(candidates) == {"schema", "identity_assignment", "records"},
        "candidate-top-schema",
    )
    _require(candidates.get("schema") == "rbw-public-candidates-v5", "candidate-schema-version")
    _require_text(candidates.get("identity_assignment"), "identity-assignment", maximum=512)
    records = candidates.get("records")
    _require(isinstance(records, list) and 21 <= len(records) <= MAX_CANDIDATES, "candidate-count")
    ids: set[str] = set()
    expected_order: list[tuple[str, str]] = []
    required = {
        "id", "identity_digest", "group", "commit", "filename", "message", "patch_excerpt",
    }
    for record in records:
        _require(isinstance(record, dict), "candidate-row")
        _require("label" not in record, "candidate-label-leakage")
        _require(set(record) == required, "candidate-schema")
        rid = _require_text(record["id"], "candidate-id", maximum=12)
        _require(rid not in ids, "duplicate-candidate")
        commit = _require_text(record["commit"], "candidate-commit", maximum=40)
        _require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "candidate-commit")
        group = _require_text(record["group"], "candidate-group", maximum=40)
        _require(group == commit, "group-binding")
        filename = _require_text(record["filename"], "candidate-filename", maximum=512)
        _require(not filename.startswith("/") and ".." not in Path(filename).parts, "candidate-filename")
        _require_text(record["message"], "candidate-message", maximum=4096)
        _require_text(record["patch_excerpt"], "candidate-excerpt", maximum=MAX_TEXT)
        digest = hashlib.sha256((commit + "\0" + filename).encode("utf-8")).hexdigest()
        _require(record["identity_digest"] == digest, "candidate-identity-digest")
        ids.add(rid)
        expected_order.append((digest, rid))
    _require(expected_order == sorted(expected_order), "candidate-neutral-order")
    _require(
        [record["id"] for record in records] == [f"U{i:03d}" for i in range(1, len(records) + 1)],
        "candidate-neutral-id",
    )
    return records


def validate_labels(label_doc: dict[str, Any], candidate_groups: dict[str, str]) -> dict[str, int]:
    _require(
        set(label_doc) == {"schema", "label_semantics", "labels", "positive_source", "negative_index_source", "provenance"},
        "label-top-schema",
    )
    _require(label_doc.get("schema") == "rbw-public-labels-v5", "label-schema")
    _require_text(label_doc.get("label_semantics"), "label-semantics", maximum=1024)
    provenance = label_doc.get("provenance")
    _require(
        isinstance(provenance, dict)
        and set(provenance) == {"selection_used_class_lists", "sealed_before_method_development", "temporal_holdout"}
        and all(type(provenance[key]) is bool for key in provenance),
        "label-provenance",
    )
    for key in ("positive_source", "negative_index_source"):
        source = label_doc.get(key)
        _require(
            isinstance(source, dict)
            and set(source) == {"repository", "path", "blob_sha"}
            and bool(re.fullmatch(r"[0-9a-f]{40}", source.get("blob_sha", ""))),
            "label-source",
        )
        _require_text(source["repository"], "label-source", maximum=128)
        _require_text(source["path"], "label-source", maximum=256)
    rows = label_doc.get("labels")
    _require(isinstance(rows, list), "label-schema")
    labels: dict[str, int] = {}
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {"id", "group", "label"}, "label-row")
        _require(row["id"] not in labels and type(row["label"]) is int and row["label"] in {0, 1}, "label-value")
        _require(row["id"] in candidate_groups and row["group"] == candidate_groups[row["id"]], "label-group-binding")
        labels[row["id"]] = row["label"]
    _require(set(labels) == set(candidate_groups), "label-coverage")
    return labels


def validate_witness_cases(witness_cases: dict[str, Any], candidate_ids: set[str]) -> list[dict[str, Any]]:
    _require(
        set(witness_cases) == {"schema", "construction", "cases"},
        "case-top-schema",
    )
    _require(witness_cases.get("schema") == "rbw-public-witness-cases-v6", "case-schema-version")
    construction = witness_cases.get("construction")
    _require(
        isinstance(construction, dict)
        and set(construction)
        == {
            "mode",
            "automatic_source_frontend",
            "source_translation_validated",
            "grammar",
            "validator",
        }
        and construction.get("mode") == "automatic-restricted-source-frontend"
        and construction.get("automatic_source_frontend") is True
        and construction.get("source_translation_validated") is True
        and construction.get("grammar") == "guard-expressions-v1"
        and construction.get("validator") == "independent-shunting-yard-and-c11-oracle",
        "case-construction",
    )
    cases = witness_cases.get("cases")
    _require(isinstance(cases, list) and 1 <= len(cases) <= len(candidate_ids), "case-schema")
    case_ids: set[str] = set()
    record_ids: set[str] = set()
    for case in cases:
        _require(isinstance(case, dict), "case-row")
        common = {"id", "kind", "record", "assignment", "source_tokens", "frontend_rule"}
        kind = case.get("kind")
        expected = common | ({"condition", "hazard", "trigger_value"} if kind == "predicate" else set())
        _require(kind in {"predicate", "widening"} and set(case) == expected, "case-fields")
        cid = _require_text(case["id"], "case-id", maximum=16)
        _require(bool(re.fullmatch(r"W\d{2,3}", cid)) and cid not in case_ids, "case-id")
        rid = _require_text(case["record"], "case-record", maximum=12)
        _require(rid in candidate_ids and rid not in record_ids, "case-record")
        assignment = case["assignment"]
        _require(isinstance(assignment, dict) and 1 <= len(assignment) <= 16, "case-assignment")
        for name, value in assignment.items():
            _require(isinstance(name, str) and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name)), "case-variable")
            _require_int(value)
        tokens = case["source_tokens"]
        _require(
            isinstance(tokens, list)
            and 1 <= len(tokens) <= MAX_SOURCE_TOKENS
            and len(set(tokens)) == len(tokens),
            "source-tokens",
        )
        for token in tokens:
            _require_text(token, "source-token", maximum=256)
        rule = case.get("frontend_rule")
        if kind == "predicate":
            _require(rule in {"require", "reject-if"}, "frontend-rule")
            _require(type(case["trigger_value"]) is bool, "trigger-value")
            _require(case["trigger_value"] is (rule == "reject-if"), "trigger-rule-binding")
            variables = set(assignment)
            _require(validate_expr(case["condition"], variables) == "bool", "condition-root-type")
            _require(validate_expr(case["hazard"], variables) == "bool", "hazard-root-type")
        else:
            _require(rule == "signed-negation-widening", "frontend-rule")
            _require(set(assignment) == {"concat_dim"}, "widening-assignment")
        case_ids.add(cid)
        record_ids.add(rid)
    return cases


def validate_protocol(protocol: dict[str, Any], candidate_count: int) -> dict[str, Any]:
    expected = {
        "schema", "analysis_scope", "expected_candidate_count", "top_k", "primary_k",
        "semantic_hint_bonus", "witness_bonus", "bonus_ablations", "bootstrap_replicates",
        "bootstrap_seed", "prediction_tie_break", "group_collapse", "h1_delta_threshold",
        "h2_coverage_threshold", "baseline", "readiness_gate_ids",
    }
    _require(set(protocol) == expected, "protocol-fields")
    _require(protocol.get("schema") == "rbw-public-protocol-v4", "protocol-schema")
    _require_text(protocol["analysis_scope"], "analysis-scope", maximum=512)
    _require(type(protocol["expected_candidate_count"]) is int and protocol["expected_candidate_count"] == candidate_count, "protocol-candidate-count")
    top_k = protocol["top_k"]
    _require(
        isinstance(top_k, list)
        and bool(top_k)
        and all(type(k) is int and 1 <= k <= candidate_count for k in top_k)
        and top_k == sorted(set(top_k)),
        "protocol-top-k",
    )
    _require(type(protocol["primary_k"]) is int and protocol["primary_k"] in top_k, "protocol-primary-k")
    for key in ("semantic_hint_bonus", "witness_bonus", "h1_delta_threshold", "h2_coverage_threshold"):
        value = protocol[key]
        _require(type(value) in (int, float) and math.isfinite(float(value)) and float(value) >= 0, "protocol-number")
    _require(0 <= float(protocol["h1_delta_threshold"]) <= 1 and 0 <= float(protocol["h2_coverage_threshold"]) <= 1, "protocol-threshold")
    ablations = protocol["bonus_ablations"]
    _require(
        isinstance(ablations, list)
        and 1 <= len(ablations) <= 20
        and all(type(value) in (int, float) and math.isfinite(float(value)) and float(value) >= 0 for value in ablations)
        and [float(value) for value in ablations] == sorted(set(float(value) for value in ablations)),
        "protocol-ablations",
    )
    _require(type(protocol["bootstrap_replicates"]) is int and 100 <= protocol["bootstrap_replicates"] <= 10_000, "protocol-bootstrap")
    _require(type(protocol["bootstrap_seed"]) is int and 0 <= protocol["bootstrap_seed"] <= INT64_MAX, "protocol-seed")
    _require(
        protocol["prediction_tie_break"] == ["descending score", "descending syntax score", "ascending unit id"],
        "protocol-tie-break",
    )
    _require_text(protocol["group_collapse"], "protocol-group-collapse", maximum=512)
    baseline = protocol["baseline"]
    _require(
        isinstance(baseline, dict)
        and set(baseline) == {"name", "kind", "published_same_budget_comparison"}
        and baseline.get("kind") == "transparent-lexical-syntactic-control"
        and type(baseline.get("published_same_budget_comparison")) is bool,
        "protocol-baseline",
    )
    _require_text(baseline["name"], "protocol-baseline", maximum=256)
    _require(protocol["readiness_gate_ids"] == list(GATE_IDS), "protocol-gates")
    return protocol


def validate_study_design(design: dict[str, Any]) -> dict[str, Any]:
    _require(
        set(design) == {"schema", "candidate_frame", "labels", "frontend", "baseline", "evidence"},
        "design-fields",
    )
    _require(design.get("schema") == "rbw-study-design-v1", "design-schema")
    expected_sections = {
        "candidate_frame": {"mode", "candidate_selection_independent_of_labels", "complete_repository_time_window", "temporal_holdout"},
        "labels": {"sealed_before_method_development"},
        "frontend": {"mode", "automatic_source_frontend", "source_translation_validated"},
        "baseline": {"name", "strongest_published_same_budget_baseline"},
    }
    for section, fields in expected_sections.items():
        value = design.get(section)
        _require(isinstance(value, dict) and set(value) == fields, "design-section")
    for section, key in (
        ("candidate_frame", "candidate_selection_independent_of_labels"),
        ("candidate_frame", "complete_repository_time_window"),
        ("candidate_frame", "temporal_holdout"),
        ("labels", "sealed_before_method_development"),
        ("frontend", "automatic_source_frontend"),
        ("frontend", "source_translation_validated"),
        ("baseline", "strongest_published_same_budget_baseline"),
    ):
        _require(type(design[section][key]) is bool, "design-boolean")
    _require_text(design["candidate_frame"]["mode"], "design-mode", maximum=128)
    _require_text(design["frontend"]["mode"], "design-mode", maximum=128)
    _require_text(design["baseline"]["name"], "design-baseline", maximum=256)
    evidence = design["evidence"]
    _require(isinstance(evidence, list) and len(evidence) >= 6, "design-evidence")
    seen: set[str] = set()
    for row in evidence:
        _require(
            isinstance(row, dict)
            and set(row) == {"gate", "status", "artifact_paths", "rationale"}
            and row.get("gate") in GATE_IDS
            and row.get("status") in {"pass", "fail"}
            and row["gate"] not in seen,
            "design-evidence-row",
        )
        _require(
            isinstance(row["artifact_paths"], list)
            and bool(row["artifact_paths"])
            and all(isinstance(path, str) and 1 <= len(path) <= 256 for path in row["artifact_paths"]),
            "design-evidence-paths",
        )
        _require_text(row["rationale"], "design-rationale", maximum=1024)
        seen.add(row["gate"])
    return design


def make_certificate(case: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    assignment = dict(case["assignment"])
    if case["kind"] == "widening":
        x = _require_int(assignment["concat_dim"])
        old = "overflow" if x == INT32_MIN else -x
        new = -x
        return {
            "case": case["id"],
            "record": record["id"],
            "assignment": assignment,
            "old_result": old,
            "new_result": new,
            "source_tokens": list(case["source_tokens"]),
        }
    variables = set(assignment)
    _require(validate_expr(case["condition"], variables) == "bool", "condition-root-type")
    _require(validate_expr(case["hazard"], variables) == "bool", "hazard-root-type")
    condition_trace: list[dict[str, Any]] = []
    hazard_trace: list[dict[str, Any]] = []
    condition = producer_eval(case["condition"], assignment, condition_trace)
    hazard = producer_eval(case["hazard"], assignment, hazard_trace)
    return {
        "case": case["id"],
        "record": record["id"],
        "assignment": assignment,
        "condition": condition,
        "hazard": hazard,
        "condition_trace": condition_trace,
        "hazard_trace": hazard_trace,
        "source_tokens": list(case["source_tokens"]),
    }


def check_certificate(case: dict[str, Any], record: dict[str, Any], cert: dict[str, Any]) -> tuple[bool, str]:
    required = {"case", "record", "assignment", "source_tokens"}
    if (
        not isinstance(cert, dict)
        or not required.issubset(cert)
        or cert.get("case") != case["id"]
        or cert.get("record") != record["id"]
    ):
        return False, "identity"
    if cert.get("assignment") != case["assignment"] or cert.get("source_tokens") != case["source_tokens"]:
        return False, "binding"
    source = _norm_source(record["patch_excerpt"])
    if any(_norm_source(token) not in source for token in case["source_tokens"]):
        return False, "source-token"
    try:
        if case["kind"] == "widening":
            x = _require_int(cert["assignment"]["concat_dim"])
            if (
                set(cert) != required | {"old_result", "new_result"}
                or x != INT32_MIN
                or cert.get("old_result") != "overflow"
                or cert.get("new_result") != 2**31
            ):
                return False, "widening-replay"
            return True, "accepted"
        if set(cert) != required | {"condition", "hazard", "condition_trace", "hazard_trace"}:
            return False, "certificate-fields"
        variables = set(cert["assignment"])
        _require(validate_expr(case["condition"], variables) == "bool", "condition-root-type")
        _require(validate_expr(case["hazard"], variables) == "bool", "hazard-root-type")
        condition, condition_trace = replay(case["condition"], cert["assignment"])
        hazard, hazard_trace = replay(case["hazard"], cert["assignment"])
    except (Invalid, KeyError, TypeError, IndexError, OverflowError):
        return False, "replay"
    if condition is not case["trigger_value"] or hazard is not True:
        return False, "relation"
    if (
        type(cert.get("condition")) is not bool
        or type(cert.get("hazard")) is not bool
        or cert.get("condition") != condition
        or cert.get("hazard") != hazard
        or cert.get("condition_trace") != condition_trace
        or cert.get("hazard_trace") != hazard_trace
    ):
        return False, "trace"
    return True, "accepted"


SECURITY_PHRASES = {
    "out of bound": 5.0,
    "out-of-bound": 5.0,
    "overflow": 4.0,
    "segfault": 5.0,
    "divide by zero": 5.0,
    "heap access": 5.0,
    "must not be negative": 3.0,
    "invalidargument": 2.0,
    "op_requires": 2.0,
    "bound check": 3.0,
    "fix ": 2.0,
    "error": 0.7,
    "check": 0.7,
}


def syntax_score(record: dict[str, Any]) -> float:
    text = (record["message"] + " " + record["patch_excerpt"]).lower()
    score = sum(weight * text.count(term) for term, weight in SECURITY_PHRASES.items())
    score += 0.12 * len(re.findall(r"(?:==|!=|<=|>=|<|>)", text))
    score += 0.05 * math.log1p(len(text))
    return round(score, 9)


def semantic_hint(record: dict[str, Any]) -> dict[str, int]:
    """Label-free static hints; they are not replay-validated relations."""
    text = record["patch_excerpt"].lower()
    features = {
        "added_guard": int(bool(re.search(r"\+\s*(?:if\s*\(|op_requires\s*\(|tf_lite_ensure)", text))),
        "range_relation": int(bool(re.search(r"(?:<=|>=|<|>)", text) and re.search(r"(?:dim|size|axis|bound|limit|index|elements|threads|width|stride)", text))),
        "error_return": int("invalidargument" in text or "op_requires" in text),
        "type_widening": int(bool(re.search(r"-\s*const\s+int\b.*\+\s*const\s+int64", text))),
        "overflow_division_guard": int(" / " in text and "overflow" in (record["message"] + text).lower()),
    }
    features["hint"] = int(any(features.values()))
    return features


def _rank(rows: list[dict[str, Any]], score_name: str) -> list[str]:
    return [
        row["id"]
        for row in sorted(rows, key=lambda row: (-row[score_name], -row["syntax_score"], row["id"]))
    ]


def freeze_predictions(
    candidates: dict[str, Any], witness_cases: dict[str, Any], protocol: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    records = validate_candidates(candidates)
    validate_protocol(protocol, len(records))
    by_id = {record["id"]: record for record in records}
    cases = validate_witness_cases(witness_cases, set(by_id))
    semantic_bonus = float(protocol["semantic_hint_bonus"])
    witness_bonus = float(protocol["witness_bonus"])

    accepted: set[str] = set()
    certificates: list[dict[str, Any]] = []
    case_outcomes: list[dict[str, Any]] = []
    for case in cases:
        rid = case["record"]
        cert = make_certificate(case, by_id[rid])
        ok, reason = check_certificate(case, by_id[rid], cert)
        certificates.append(cert)
        case_outcomes.append({"record": rid, "case": case["id"], "accepted": int(ok), "reason": reason})
        if ok:
            accepted.add(rid)

    rows: list[dict[str, Any]] = []
    by_outcome = {row["record"]: row for row in case_outcomes}
    outcomes: list[dict[str, Any]] = []
    for record in records:
        hint = semantic_hint(record)
        base = syntax_score(record)
        unvalidated = round(base + semantic_bonus * hint["hint"], 9)
        validated = round(base + witness_bonus * int(record["id"] in accepted), 9)
        row = {
            "id": record["id"],
            "group": record["group"],
            "syntax_score": base,
            "semantic_hint": hint["hint"],
            "semantic_features": hint,
            "unvalidated_score": unvalidated,
            "witness_accepted": int(record["id"] in accepted),
            "validated_score": validated,
        }
        rows.append(row)
        if record["id"] in by_outcome:
            outcomes.append(by_outcome[record["id"]])
        elif hint["hint"]:
            outcomes.append({"record": record["id"], "case": None, "accepted": 0, "reason": "unvalidated-only"})
        else:
            outcomes.append({"record": record["id"], "case": None, "accepted": 0, "reason": "unsupported"})

    predictions = {
        "schema": "rbw-public-predictions-v4",
        "phase": "label-free-freeze",
        "candidate_hash": canonical_hash(candidates),
        "witness_case_hash": canonical_hash(witness_cases),
        "protocol_hash": canonical_hash(protocol),
        "label_fields_present": False,
        "candidate_count": len(records),
        "records": rows,
        "rankings": {
            "syntax": _rank(rows, "syntax_score"),
            "unvalidated": _rank(rows, "unvalidated_score"),
            "validated": _rank(rows, "validated_score"),
        },
    }
    _require(all("label" not in row for row in rows), "prediction-label-leakage")
    return predictions, outcomes, certificates


def validate_predictions(
    predictions: dict[str, Any],
    candidates: dict[str, Any],
    witness_cases: dict[str, Any],
    protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    expected = {
        "schema", "phase", "candidate_hash", "witness_case_hash", "protocol_hash",
        "label_fields_present", "candidate_count", "records", "rankings",
    }
    _require(isinstance(predictions, dict) and set(predictions) == expected, "prediction-schema")
    _require(predictions.get("schema") == "rbw-public-predictions-v4" and predictions.get("phase") == "label-free-freeze", "prediction-schema")
    _require(predictions.get("candidate_hash") == canonical_hash(candidates), "prediction-candidate-binding")
    _require(predictions.get("witness_case_hash") == canonical_hash(witness_cases), "prediction-case-binding")
    _require(predictions.get("protocol_hash") == canonical_hash(protocol), "prediction-protocol-binding")
    _require(predictions.get("label_fields_present") is False, "prediction-label-leakage")
    rows = predictions.get("records")
    _require(isinstance(rows, list) and len(rows) == predictions.get("candidate_count"), "prediction-count")
    expected_row = {
        "id", "group", "syntax_score", "semantic_hint", "semantic_features",
        "unvalidated_score", "witness_accepted", "validated_score",
    }
    ids: set[str] = set()
    for row in rows:
        _require(isinstance(row, dict) and set(row) == expected_row and "label" not in row, "prediction-row")
        _require(row["id"] not in ids, "prediction-duplicate")
        _require(type(row["semantic_hint"]) is int and row["semantic_hint"] in {0, 1}, "prediction-hint")
        _require(type(row["witness_accepted"]) is int and row["witness_accepted"] in {0, 1}, "prediction-accepted")
        for key in ("syntax_score", "unvalidated_score", "validated_score"):
            _require(type(row[key]) in (int, float) and math.isfinite(float(row[key])), "prediction-score")
        features = row["semantic_features"]
        _require(
            isinstance(features, dict)
            and set(features) == {"added_guard", "range_relation", "error_return", "type_widening", "overflow_division_guard", "hint"}
            and all(type(value) is int and value in {0, 1} for value in features.values())
            and features["hint"] == row["semantic_hint"],
            "prediction-features",
        )
        ids.add(row["id"])
    rankings = predictions.get("rankings")
    _require(isinstance(rankings, dict) and set(rankings) == {"syntax", "unvalidated", "validated"}, "prediction-rankings")
    for name, score in (("syntax", "syntax_score"), ("unvalidated", "unvalidated_score"), ("validated", "validated_score")):
        _require(rankings[name] == _rank(rows, score), "prediction-ranking-binding")
    return rows


def validate_outcomes(outcomes: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _require(isinstance(outcomes, list) and len(outcomes) == len(rows), "outcome-count")
    row_by_id = {row["id"]: row for row in rows}
    seen: set[str] = set()
    allowed_reasons = {"accepted", "unvalidated-only", "unsupported", "identity", "binding", "source-token", "widening-replay", "certificate-fields", "replay", "relation", "trace"}
    for outcome in outcomes:
        _require(
            isinstance(outcome, dict)
            and set(outcome) == {"record", "case", "accepted", "reason"}
            and outcome["record"] in row_by_id
            and outcome["record"] not in seen
            and type(outcome["accepted"]) is int
            and outcome["accepted"] in {0, 1}
            and outcome["reason"] in allowed_reasons,
            "outcome-row",
        )
        _require(outcome["accepted"] == row_by_id[outcome["record"]]["witness_accepted"], "outcome-prediction-binding")
        if outcome["accepted"]:
            _require(isinstance(outcome["case"], str) and outcome["reason"] == "accepted", "outcome-accepted")
        else:
            _require(outcome["case"] is None or isinstance(outcome["case"], str), "outcome-case")
        seen.add(outcome["record"])
    return outcomes


def _precision(order: list[str], labels: dict[str, int], k: int) -> Fraction:
    _require(len(order) >= k, "top-k")
    return Fraction(sum(labels[rid] for rid in order[:k]), k)


def _average_precision(order: list[str], labels: dict[str, int]) -> float:
    positives = sum(labels.values())
    if positives == 0:
        return 0.0
    seen = 0
    total = 0.0
    for rank, rid in enumerate(order, 1):
        if labels[rid]:
            seen += 1
            total += seen / rank
    return total / positives


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _quantile(values: list[float], q: float) -> float:
    _require(bool(values), "empty-bootstrap")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def _collapse_groups(
    prediction_rows: list[dict[str, Any]], labels: dict[str, int]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prediction_rows:
        grouped[row["group"]].append(row)
    rows: list[dict[str, Any]] = []
    group_labels: dict[str, int] = {}
    for group in sorted(grouped):
        members = grouped[group]
        rows.append(
            {
                "id": group,
                "group": group,
                "syntax_score": max(row["syntax_score"] for row in members),
                "unvalidated_score": max(row["unvalidated_score"] for row in members),
                "validated_score": max(row["validated_score"] for row in members),
                "witness_accepted": max(row["witness_accepted"] for row in members),
                "semantic_hint": max(row["semantic_hint"] for row in members),
            }
        )
        group_labels[group] = max(labels[row["id"]] for row in members)
    return rows, group_labels


def _cluster_bootstrap(
    rows: list[dict[str, Any]], labels: dict[str, int], k: int, replicates: int, seed: int
) -> dict[str, list[float]]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row)
    groups = sorted(by_group)
    rng = random.Random(seed)
    deltas: list[float] = []
    semantic_deltas: list[float] = []
    coverages: list[float] = []
    for _ in range(replicates):
        sampled: list[dict[str, Any]] = []
        sample_labels: dict[str, int] = {}
        for draw in range(len(groups)):
            group = groups[rng.randrange(len(groups))]
            for row in by_group[group]:
                clone = dict(row)
                clone_id = f"{row['id']}@{draw}"
                clone["id"] = clone_id
                clone["group"] = f"{group}@{draw}"
                sampled.append(clone)
                sample_labels[clone_id] = labels[row["id"]]
        if len(sampled) < k:
            continue
        baseline = _rank(sampled, "syntax_score")
        semantic = _rank(sampled, "unvalidated_score")
        validated = _rank(sampled, "validated_score")
        baseline_precision = float(_precision(baseline, sample_labels, k))
        deltas.append(float(_precision(validated, sample_labels, k)) - baseline_precision)
        semantic_deltas.append(float(_precision(semantic, sample_labels, k)) - baseline_precision)
        positive = sum(sample_labels.values())
        accepted_positive = sum(sample_labels[row["id"]] * row["witness_accepted"] for row in sampled)
        coverages.append(accepted_positive / positive if positive else 0.0)
    _require(len(deltas) == replicates, "bootstrap-short-sample")
    return {
        "validated_minus_syntax": [_quantile(deltas, 0.025), _quantile(deltas, 0.975)],
        "unvalidated_minus_syntax": [_quantile(semantic_deltas, 0.025), _quantile(semantic_deltas, 0.975)],
        "unit_coverage": [_quantile(coverages, 0.025), _quantile(coverages, 0.975)],
    }


def derive_readiness(
    candidates: dict[str, Any],
    label_doc: dict[str, Any],
    witness_cases: dict[str, Any],
    protocol: dict[str, Any],
    design: dict[str, Any],
    prediction_rows: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    reference_verification_count: int,
    frontend_validation: dict[str, Any],
) -> dict[str, Any]:
    """Derive every gate fail-closed from package facts; no boolean gate list is trusted."""
    validate_study_design(design)
    provenance = label_doc["provenance"]
    construction = witness_cases["construction"]
    baseline = protocol["baseline"]
    candidate_frame = design["candidate_frame"]

    facts: dict[str, tuple[bool, list[str], str]] = {
        "all_candidates_counted_with_typed_outcomes": (
            len(outcomes) == len(prediction_rows)
            and {row["record"] for row in outcomes} == {row["id"] for row in prediction_rows},
            ["predictions-frozen.json", "outcomes.json"],
            "Every frozen candidate has exactly one typed outcome.",
        ),
        "automatic_source_frontend": (
            construction["automatic_source_frontend"] is True
            and construction["source_translation_validated"] is True
            and design["frontend"]["automatic_source_frontend"] is True
            and design["frontend"]["source_translation_validated"] is True
            and isinstance(frontend_validation, dict)
            and frontend_validation.get("schema") == "rbw-source-frontend-validation-v1"
            and frontend_validation.get("automatic_source_frontend") is True
            and frontend_validation.get("source_translation_validated") is True
            and frontend_validation.get("status") == "pass"
            and frontend_validation.get("mismatches") == 0
            and frontend_validation.get("semantic_obligations") == 900
            and frontend_validation.get("candidate_hash") == canonical_hash(candidates)
            and frontend_validation.get("witness_case_hash") == canonical_hash(witness_cases),
            [
                "data/public-study/witness-cases.json",
                "data/public-study/study-design.json",
                "results/source-frontend/summary.json",
            ],
            "The restricted guard-expression frontend is automatic and its retained translation packet passed independent parser and C11 replay checks.",
        ),
        "candidate_selection_independent_of_labels": (
            provenance["selection_used_class_lists"] is False
            and candidate_frame["candidate_selection_independent_of_labels"] is True,
            ["data/public-study/labels.json", "data/public-study/study-design.json"],
            "The retained cohort was assembled from published positive and negative class lists.",
        ),
        "complete_repository_time_window": (
            candidate_frame["complete_repository_time_window"] is True,
            ["data/public-study/study-design.json"],
            "No complete repository-by-time population frame is present.",
        ),
        "independent_replay_checker": (
            bool(outcomes)
            and any(row["accepted"] == 1 for row in outcomes)
            and all(row["reason"] == "accepted" for row in outcomes if row["accepted"] == 1),
            ["src/public_study.py", "certificates.json", "outcomes.json"],
            "Accepted cases were recomputed by the iterative replay machine and trace-bound.",
        ),
        "labels_sealed_before_method_development": (
            provenance["sealed_before_method_development"] is True
            and design["labels"]["sealed_before_method_development"] is True,
            ["data/public-study/labels.json", "data/public-study/study-design.json"],
            "Labels were known during mapping and cohort construction.",
        ),
        "reference_count_at_least_55": (
            type(reference_verification_count) is int and reference_verification_count >= 55,
            ["reference-verification.csv", "literature-screening.csv"],
            "At least 55 bibliography records have an artifact-side verification row.",
        ),
        "strongest_published_same_budget_baseline": (
            baseline["published_same_budget_comparison"] is True
            and design["baseline"]["strongest_published_same_budget_baseline"] is True,
            ["data/public-study/protocol.json", "data/public-study/study-design.json"],
            "The implemented comparator is a transparent control, not the strongest published same-budget baseline.",
        ),
        "temporal_holdout": (
            provenance["temporal_holdout"] is True
            and candidate_frame["temporal_holdout"] is True,
            ["data/public-study/labels.json", "data/public-study/study-design.json"],
            "The retained cohort is not a predeclared post-cutoff holdout.",
        ),
    }
    _require(set(facts) == set(GATE_IDS), "readiness-gate-set")
    gates = [
        {
            "id": gate,
            "status": "pass" if facts[gate][0] else "fail",
            "basis": "machine-derived-fail-closed",
            "evidence": facts[gate][1],
            "detail": facts[gate][2],
        }
        for gate in GATE_IDS
    ]
    failed = [row["id"] for row in gates if row["status"] == "fail"]
    return {
        "schema": "rbw-readiness-v2",
        "main_study_readiness": "passed" if not failed else "failed",
        "failed_readiness_gates": failed,
        "gates": gates,
    }


def evaluate_predictions(
    candidates: dict[str, Any],
    label_doc: dict[str, Any],
    witness_cases: dict[str, Any],
    protocol: dict[str, Any],
    study_design: dict[str, Any],
    predictions: dict[str, Any],
    outcomes: list[dict[str, Any]],
    reference_verification_count: int,
    frontend_validation: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidate_records = validate_candidates(candidates)
    validate_protocol(protocol, len(candidate_records))
    validate_witness_cases(witness_cases, {row["id"] for row in candidate_records})
    validate_study_design(study_design)
    labels = validate_labels(label_doc, {row["id"]: row["group"] for row in candidate_records})
    rows = validate_predictions(predictions, candidates, witness_cases, protocol)
    _require({row["id"] for row in rows} == set(labels), "prediction-coverage")
    outcomes = validate_outcomes(outcomes, rows)

    rankings = {
        "syntax": _rank(rows, "syntax_score"),
        "unvalidated": _rank(rows, "unvalidated_score"),
        "validated": _rank(rows, "validated_score"),
    }
    top_ks = protocol["top_k"]
    metrics: dict[str, Any] = {}
    for method, order in rankings.items():
        metrics[method] = {f"precision_at_{k}": float(_precision(order, labels, k)) for k in top_ks}
        metrics[method]["average_precision"] = _average_precision(order, labels)

    primary_k = protocol["primary_k"]
    baseline_top = rankings["syntax"][:primary_k]
    semantic_top = rankings["unvalidated"][:primary_k]
    validated_top = rankings["validated"][:primary_k]
    baseline_precision = _precision(baseline_top, labels, primary_k)
    delta = _precision(validated_top, labels, primary_k) - baseline_precision
    semantic_delta = _precision(semantic_top, labels, primary_k) - baseline_precision

    positive_units = sum(labels.values())
    _require(positive_units > 0, "no-positive-labels")
    accepted_positive_units = sum(labels[row["id"]] * row["witness_accepted"] for row in rows)
    unit_coverage = Fraction(accepted_positive_units, positive_units)

    group_rows, group_labels = _collapse_groups(rows, labels)
    group_rankings = {
        "syntax": _rank(group_rows, "syntax_score"),
        "unvalidated": _rank(group_rows, "unvalidated_score"),
        "validated": _rank(group_rows, "validated_score"),
    }
    group_positive = sum(group_labels.values())
    _require(group_positive > 0, "no-positive-groups")
    group_accepted = sum(group_labels[row["id"]] * row["witness_accepted"] for row in group_rows)
    group_coverage = Fraction(group_accepted, group_positive)
    group_k = min(primary_k, len(group_rows))
    group_metrics: dict[str, Any] = {}
    for method, order in group_rankings.items():
        group_metrics[method] = {
            f"precision_at_{group_k}": float(_precision(order, group_labels, group_k)),
            "average_precision": _average_precision(order, group_labels),
        }

    ablations: list[dict[str, Any]] = []
    accepted_ids = {row["id"] for row in rows if row["witness_accepted"]}
    for bonus_value in protocol["bonus_ablations"]:
        bonus = float(bonus_value)
        temporary = []
        for row in rows:
            clone = dict(row)
            clone["ablation_score"] = round(row["syntax_score"] + bonus * int(row["id"] in accepted_ids), 9)
            temporary.append(clone)
        order = _rank(temporary, "ablation_score")
        precision = _precision(order, labels, primary_k)
        ablations.append(
            {
                "witness_bonus": bonus,
                "precision_at_20": float(precision),
                "delta_from_syntax": float(precision - baseline_precision),
                "top20_symmetric_difference_size": len(set(order[:primary_k]) ^ set(baseline_top)),
            }
        )

    bootstrap = _cluster_bootstrap(
        rows,
        labels,
        primary_k,
        protocol["bootstrap_replicates"],
        protocol["bootstrap_seed"],
    )
    readiness = derive_readiness(
        candidates,
        label_doc,
        witness_cases,
        protocol,
        study_design,
        rows,
        outcomes,
        reference_verification_count,
        frontend_validation,
    )
    failed_gates = readiness["failed_readiness_gates"]
    reason_counts = Counter(row["reason"] for row in outcomes)

    ranks = {
        name: {rid: index + 1 for index, rid in enumerate(order)}
        for name, order in rankings.items()
    }
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
        scored_rows.append(
            {
                **row,
                "label": labels[row["id"]],
                "syntax_rank": ranks["syntax"][row["id"]],
                "unvalidated_rank": ranks["unvalidated"][row["id"]],
                "validated_rank": ranks["validated"][row["id"]],
            }
        )

    formal_h1 = (
        "threshold-met" if not failed_gates and delta >= Fraction(1, 10)
        else "threshold-not-met" if not failed_gates
        else "not-testable-with-label-selected-nontemporal-cohort"
    )
    formal_h2 = (
        "threshold-met" if not failed_gates and unit_coverage >= Fraction(3, 5)
        else "threshold-not-met" if not failed_gates
        else "not-testable-as-population-coverage"
    )
    summary = {
        "schema": "rbw-public-summary-v5",
        "scope": "32-unit label-selected TensorFlow file-change microcohort; descriptive audit only",
        "candidate_units": len(rows),
        "commit_groups": len(group_rows),
        "positive_units": positive_units,
        "accepted_positive_units": accepted_positive_units,
        "positive_commit_groups": group_positive,
        "accepted_positive_commit_groups": group_accepted,
        "labels_loaded_only_in_separate_evaluation_process": True,
        "prediction_records_contain_labels": False,
        "selection_independent_of_labels": False,
        "temporal_holdout": False,
        "metrics": metrics,
        "group_metrics": group_metrics,
        "primary_k": primary_k,
        "validated_minus_syntax_at_20": float(delta),
        "unvalidated_minus_syntax_at_20": float(semantic_delta),
        "validated_top20_symmetric_difference": sorted(set(validated_top) ^ set(baseline_top)),
        "unvalidated_top20_symmetric_difference": sorted(set(semantic_top) ^ set(baseline_top)),
        "accepted_source_witnesses": len(accepted_ids),
        "unit_witness_coverage": float(unit_coverage),
        "unit_witness_coverage_fraction": f"{accepted_positive_units}/{positive_units}",
        "unit_witness_coverage_wilson_95_descriptive": _wilson(accepted_positive_units, positive_units),
        "group_witness_coverage": float(group_coverage),
        "group_witness_coverage_fraction": f"{group_accepted}/{group_positive}",
        "group_witness_coverage_wilson_95_descriptive": _wilson(group_accepted, group_positive),
        "cluster_bootstrap_95": bootstrap,
        "bootstrap_replicates": protocol["bootstrap_replicates"],
        "bonus_ablations": ablations,
        "typed_outcomes": dict(sorted(reason_counts.items())),
        "microcohort_h1_analogue": "threshold-met" if delta >= Fraction(1, 10) else "threshold-not-met",
        "microcohort_h2_analogue": "threshold-met" if unit_coverage >= Fraction(3, 5) else "threshold-not-met",
        "formal_h1_decision": formal_h1,
        "formal_h2_decision": formal_h2,
        "main_study_readiness": readiness["main_study_readiness"],
        "failed_readiness_gates": failed_gates,
        "reference_verification_count": reference_verification_count,
        "obligations_this_analysis": protocol["bootstrap_replicates"] + len(rows) * (3 + len(protocol["bonus_ablations"])),
        "predictions_hash": canonical_hash(predictions),
        "labels_hash": canonical_hash(label_doc),
    }
    return summary, scored_rows, ablations, readiness
