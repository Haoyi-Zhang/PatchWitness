"""Label-separated descriptive microcohort and restricted source-evidence replay.

The finite old-fault/new-defined certificate lives in ``src/producer.py`` and
``src/checker.py``.  This module implements a different contract for public
patch excerpts: a bound guard is triggered under one typed assignment, or a
specific declaration widening separates two explicitly assumed destination ranges.  It never upgrades that
source evidence into a finite behavioral certificate.
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
INT32_MAX = 2**31 - 1
MAX_PUBLIC_JSON_BYTES = 1_048_576
MAX_PUBLIC_JSON_DEPTH = 64
MAX_EXPR_NODES = 96
MAX_EXPR_DEPTH = 16
MAX_CANDIDATES = 600
MAX_TEXT = 32_768
MAX_SOURCE_TOKENS = 8
ALLOWED_OPS = {"const", "var", "not", "and", "or", "eq", "ne", "lt", "le", "gt", "ge", "div"}
COMPARE_OPS = {"eq", "ne", "lt", "le", "gt", "ge"}
GATE_IDS = (
    "all_candidates_counted_with_typed_outcomes",
    "restricted_source_evidence_cross_checked",
    "raw_diff_or_checked_source_tree_correspondence",
    "candidate_selection_independent_of_labels",
    "complete_repository_time_window",
    "independent_source_record_checker",
    "labels_sealed_before_method_development",
    "strongest_published_same_budget_baseline",
    "temporal_holdout",
)


class Invalid(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Invalid(reason)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _scan_json_depth(raw: bytes) -> None:
    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        ch = chr(byte)
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            _require(depth <= MAX_PUBLIC_JSON_DEPTH, "json-depth-limit")
        elif ch in "]}":
            depth -= 1
            _require(depth >= 0, "json-balance")
    _require(depth == 0 and not in_string, "json-balance")


def load_json_value(path: Path) -> Any:
    raw = path.read_bytes()
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

    def parse_int(value: str) -> int:
        _require(len(value.lstrip("-")) <= 19, "integer-encoding-limit")
        return int(value)

    def parse_float(value: str) -> float:
        _require(len(value) <= 32, "float-encoding-limit")
        parsed = float(value)
        _require(math.isfinite(parsed), "nonfinite-number")
        return parsed

    def reject_constant(_: str) -> Any:
        raise Invalid("nonfinite-number")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_int=parse_int, parse_float=parse_float, parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
        raise Invalid("invalid-json") from exc


def load_json(path: Path) -> dict[str, Any]:
    value = load_json_value(path)
    _require(isinstance(value, dict), "json-root")
    return value


def _require_text(value: Any, reason: str, *, minimum: int = 1, maximum: int = MAX_TEXT) -> str:
    _require(type(value) is str and minimum <= len(value) <= maximum and "\x00" not in value, reason)
    return value


def _require_int(value: Any) -> int:
    _require(type(value) is int and INT64_MIN <= value <= INT64_MAX, "integer-range")
    return value


def typed_equal(left: Any, right: Any) -> bool:
    """Recursive equality that never equates bool/int or int/float."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def typed_int(value: int) -> dict[str, Any]:
    return {"tag": "int", "payload": _require_int(value)}


def typed_bool(value: bool) -> dict[str, Any]:
    _require(type(value) is bool, "typed-bool")
    return {"tag": "bool", "payload": value}


def typed_fault(reason: str) -> dict[str, Any]:
    return {"tag": "fault", "payload": _require_text(reason, "fault-reason", maximum=128)}


def validate_typed_value(value: Any) -> None:
    _require(type(value) is dict and set(value) == {"tag", "payload"}, "typed-value-schema")
    tag = value["tag"]
    if tag == "int":
        _require_int(value["payload"])
    elif tag == "bool":
        _require(type(value["payload"]) is bool, "typed-bool")
    elif tag == "fault":
        _require_text(value["payload"], "typed-fault", maximum=128)
    else:
        raise Invalid("typed-value-tag")


def validate_expr(expr: Any, variables: set[str], depth: int = 0, counter: list[int] | None = None) -> str:
    if counter is None:
        counter = [0]
    counter[0] += 1
    _require(counter[0] <= MAX_EXPR_NODES and depth <= MAX_EXPR_DEPTH, "expression-limit")
    _require(type(expr) is list and bool(expr) and type(expr[0]) is str and expr[0] in ALLOWED_OPS, "expression-shape")
    op = expr[0]
    arity = 1 if op in {"const", "var", "not"} else 2
    _require(len(expr) == arity + 1, "expression-arity")
    if op == "const":
        _require_int(expr[1]); return "int"
    if op == "var":
        _require(type(expr[1]) is str and expr[1] in variables, "unknown-variable"); return "int"
    child_sorts = [validate_expr(child, variables, depth + 1, counter) for child in expr[1:]]
    if op == "not":
        _require(child_sorts == ["bool"], "boolean-operand-type"); return "bool"
    if op in {"and", "or"}:
        _require(child_sorts == ["bool", "bool"], "boolean-operand-type"); return "bool"
    _require(child_sorts == ["int", "int"], "integer-operand-type")
    return "bool" if op in COMPARE_OPS else "int"


def _trunc_div(a: int, b: int) -> int:
    _require(b != 0, "division-by-zero")
    magnitude = abs(a) // abs(b)
    return _require_int(-magnitude if (a < 0) != (b < 0) else magnitude)


def _position(parent: str, child: int) -> str:
    return str(child) if parent == "" else f"{parent}.{child}"


def producer_eval(expr: list[Any], env: dict[str, int], trace: list[list[Any]] | None = None, position: str = "") -> dict[str, Any]:
    """Recursive producer; trace entries are ``(position, tag, payload)`` triples."""
    if trace is None:
        trace = []
    op = expr[0]
    if op == "const":
        value = typed_int(expr[1])
    elif op == "var":
        _require(expr[1] in env, "missing-variable")
        value = typed_int(env[expr[1]])
    elif op == "not":
        child = producer_eval(expr[1], env, trace, _position(position, 0))
        _require(child["tag"] == "bool", "boolean-operand-type")
        value = typed_bool(not child["payload"])
    elif op in {"and", "or"}:
        left = producer_eval(expr[1], env, trace, _position(position, 0))
        _require(left["tag"] == "bool", "boolean-operand-type")
        if op == "and" and not left["payload"]:
            value = typed_bool(False)
        elif op == "or" and left["payload"]:
            value = typed_bool(True)
        else:
            right = producer_eval(expr[2], env, trace, _position(position, 1))
            _require(right["tag"] == "bool", "boolean-operand-type")
            value = typed_bool(bool(right["payload"]))
    else:
        left = producer_eval(expr[1], env, trace, _position(position, 0))
        right = producer_eval(expr[2], env, trace, _position(position, 1))
        _require(left["tag"] == right["tag"] == "int", "integer-operand-type")
        a, b = left["payload"], right["payload"]
        if op == "eq": value = typed_bool(a == b)
        elif op == "ne": value = typed_bool(a != b)
        elif op == "lt": value = typed_bool(a < b)
        elif op == "le": value = typed_bool(a <= b)
        elif op == "gt": value = typed_bool(a > b)
        elif op == "ge": value = typed_bool(a >= b)
        elif op == "div": value = typed_int(_trunc_div(a, b))
        else: raise Invalid("operator")
    trace.append([position, value["tag"], value["payload"]])
    return value


def replay(expr: list[Any], env: dict[str, int]) -> tuple[dict[str, Any], list[list[Any]]]:
    """Iterative checker evaluator with independent control flow."""
    instructions: list[tuple[str, Any, str]] = [("eval", expr, "")]
    vals: list[dict[str, Any]] = []
    trace: list[list[Any]] = []
    while instructions:
        kind, payload, position = instructions.pop()
        if kind == "eval":
            node = payload; op = node[0]
            if op == "const":
                value = typed_int(node[1]); vals.append(value); trace.append([position, value["tag"], value["payload"]])
            elif op == "var":
                _require(node[1] in env, "missing-variable")
                value = typed_int(env[node[1]]); vals.append(value); trace.append([position, value["tag"], value["payload"]])
            elif op == "not":
                instructions.extend([("apply1", op, position), ("eval", node[1], _position(position, 0))])
            elif op in {"and", "or"}:
                instructions.extend([("lazy", (op, node[2]), position), ("eval", node[1], _position(position, 0))])
            else:
                instructions.extend([("apply2", op, position), ("eval", node[2], _position(position, 1)), ("eval", node[1], _position(position, 0))])
        elif kind == "lazy":
            op, right = payload
            left = vals.pop(); _require(left["tag"] == "bool", "boolean-operand-type")
            if (op == "and" and not left["payload"]) or (op == "or" and left["payload"]):
                value = typed_bool(bool(left["payload"])); vals.append(value); trace.append([position, value["tag"], value["payload"]])
            else:
                instructions.extend([("lazy_finish", op, position), ("eval", right, _position(position, 1))])
        elif kind == "lazy_finish":
            right = vals.pop(); _require(right["tag"] == "bool", "boolean-operand-type")
            value = typed_bool(bool(right["payload"])); vals.append(value); trace.append([position, value["tag"], value["payload"]])
        elif kind == "apply1":
            child = vals.pop(); _require(child["tag"] == "bool", "boolean-operand-type")
            value = typed_bool(not child["payload"]); vals.append(value); trace.append([position, value["tag"], value["payload"]])
        elif kind == "apply2":
            right = vals.pop(); left = vals.pop(); _require(left["tag"] == right["tag"] == "int", "integer-operand-type")
            a, b = left["payload"], right["payload"]
            op = payload
            if op == "eq": value = typed_bool(a == b)
            elif op == "ne": value = typed_bool(a != b)
            elif op == "lt": value = typed_bool(a < b)
            elif op == "le": value = typed_bool(a <= b)
            elif op == "gt": value = typed_bool(a > b)
            elif op == "ge": value = typed_bool(a >= b)
            elif op == "div": value = typed_int(_trunc_div(a, b))
            else: raise Invalid("operator")
            vals.append(value); trace.append([position, value["tag"], value["payload"]])
        else:
            raise Invalid("instruction")
    _require(len(vals) == 1, "stack")
    return vals[0], trace


def _validate_trace(trace: Any) -> None:
    _require(type(trace) is list and 1 <= len(trace) <= MAX_EXPR_NODES, "trace-schema")
    for item in trace:
        _require(type(item) is list and len(item) == 3 and type(item[0]) is str and type(item[1]) is str, "trace-entry")
        validate_typed_value({"tag": item[1], "payload": item[2]})


def validate_candidates(candidates: dict[str, Any]) -> list[dict[str, Any]]:
    _require(set(candidates) == {"schema", "identity_assignment", "records"}, "candidate-top-schema")
    _require(candidates.get("schema") == "rbw-public-candidates-v6", "candidate-schema-version")
    _require_text(candidates["identity_assignment"], "identity-assignment", maximum=512)
    records = candidates.get("records")
    _require(type(records) is list and 21 <= len(records) <= MAX_CANDIDATES, "candidate-count")
    required = {"id", "identity_digest", "group", "commit", "commit_timestamp", "commit_message", "file_path", "diff_context", "source_asset"}
    ids: set[str] = set(); ordered: list[tuple[str, str]] = []
    for record in records:
        _require(type(record) is dict and set(record) == required and "label" not in record, "candidate-schema")
        rid = _require_text(record["id"], "candidate-id", maximum=12)
        _require(rid not in ids, "duplicate-candidate")
        commit = _require_text(record["commit"], "candidate-commit", maximum=40)
        _require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)) and record["group"] == commit, "candidate-commit")
        _require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["commit_timestamp"])), "candidate-timestamp")
        _require_text(record["commit_message"], "candidate-message", maximum=8192)
        path = _require_text(record["file_path"], "candidate-path", maximum=512)
        _require(path.startswith("tensorflow/") and not path.startswith("/") and ".." not in Path(path).parts, "candidate-path")
        _require_text(record["diff_context"], "candidate-diff", maximum=MAX_TEXT)
        source = record["source_asset"]
        _require(type(source) is dict and set(source) == {"repository", "commit_url", "source_kind", "diff_selection", "file_annotation", "annotation_used_for_scoring", "context_requirements"}, "source-asset-schema")
        _require(source["repository"] == "tensorflow/tensorflow" and source["commit_url"].endswith(commit), "source-asset-binding")
        _require(source["source_kind"] == "github-commit-file-patch", "source-kind")
        _require_text(source["diff_selection"], "diff-selection", maximum=1024)
        _require_text(source["file_annotation"], "file-annotation", maximum=1024)
        _require(source["annotation_used_for_scoring"] is False, "annotation-score-leakage")
        _require(type(source["context_requirements"]) is list and len(source["context_requirements"]) <= 8 and all(type(x) is str for x in source["context_requirements"]), "context-requirements")
        digest = hashlib.sha256((commit + "\0" + path).encode("utf-8")).hexdigest()
        _require(record["identity_digest"] == digest, "candidate-identity-digest")
        ids.add(rid); ordered.append((digest, rid))
    _require(ordered == sorted(ordered), "candidate-neutral-order")
    _require([r["id"] for r in records] == [f"U{i:03d}" for i in range(1, len(records) + 1)], "candidate-neutral-id")
    return records


def validate_labels(document: dict[str, Any], candidate_groups: dict[str, str]) -> dict[str, int]:
    _require(set(document) == {"schema", "label_semantics", "labels", "positive_source", "negative_index_source", "provenance"}, "label-top-schema")
    _require(document.get("schema") == "rbw-public-labels-v6", "label-schema")
    _require_text(document["label_semantics"], "label-semantics", maximum=1024)
    for key in ("positive_source", "negative_index_source"):
        source = document[key]
        _require(type(source) is dict and set(source) == {"repository", "path", "blob_sha"} and bool(re.fullmatch(r"[0-9a-f]{40}", source["blob_sha"])), "label-source")
    provenance = document["provenance"]
    _require(type(provenance) is dict and set(provenance) == {"selection_method", "class_lists_used_for_selection", "label_seal_record", "method_freeze_timestamp", "temporal_cutoff"}, "label-provenance")
    _require(provenance["class_lists_used_for_selection"] is True and provenance["label_seal_record"] is None and provenance["method_freeze_timestamp"] is None and provenance["temporal_cutoff"] is None, "label-provenance-values")
    labels: dict[str, int] = {}
    for row in document["labels"]:
        _require(type(row) is dict and set(row) == {"id", "group", "label"}, "label-row")
        _require(row["id"] in candidate_groups and row["id"] not in labels and row["group"] == candidate_groups[row["id"]], "label-group-binding")
        _require(type(row["label"]) is int and row["label"] in {0, 1}, "label-value")
        labels[row["id"]] = row["label"]
    _require(set(labels) == set(candidate_groups), "label-coverage")
    return labels


def validate_source_evidence(document: dict[str, Any], candidate_ids: set[str]) -> list[dict[str, Any]]:
    _require(set(document) == {"schema", "construction", "cases", "diagnostics"}, "evidence-top-schema")
    _require(document.get("schema") == "rbw-public-source-evidence-v1", "evidence-schema")
    construction = document["construction"]
    _require(type(construction) is dict and set(construction) == {"mode", "input_mode", "raw_diff_or_source_tree_correspondence", "grammar", "evidence_contract", "parser_cross_check", "evaluator_cross_check"}, "evidence-construction")
    _require(construction["mode"] == "automatic-restricted-real-diff-frontend" and construction["input_mode"] == "minimal-real-unified-diff-context" and construction["raw_diff_or_source_tree_correspondence"] is False, "evidence-construction-values")
    _require(construction["evidence_contract"] == "guard-trigger-or-source-difference-not-old-fault-new-defined", "evidence-contract")
    diagnostics = document["diagnostics"]
    _require(type(diagnostics) is list and len(diagnostics) == len(candidate_ids), "diagnostic-count")
    diag_by_id: dict[str, dict[str, str]] = {}
    for row in diagnostics:
        _require(type(row) is dict and set(row) == {"record", "status", "stage", "reason"}, "diagnostic-row")
        _require(row["record"] in candidate_ids and row["record"] not in diag_by_id, "diagnostic-record")
        _require(row["status"] in {"supported", "abstain"} and row["stage"] in {"extract", "parse", "evaluate"}, "diagnostic-state")
        diag_by_id[row["record"]] = row
    cases = document["cases"]
    _require(type(cases) is list and 1 <= len(cases) <= len(candidate_ids), "case-count")
    seen_case: set[str] = set(); seen_record: set[str] = set()
    for case in cases:
        common = {"id", "kind", "record", "assignment", "source_tokens", "context_tokens", "context_preconditions", "frontend_rule"}
        expected = common | ({"guard", "trigger_value"} if case.get("kind") == "guard-trigger" else set())
        _require(type(case) is dict and set(case) == expected and case.get("kind") in {"guard-trigger", "source-difference"}, "case-fields")
        _require(bool(re.fullmatch(r"W\d{2,3}", case["id"])) and case["id"] not in seen_case, "case-id")
        rid = case["record"]
        _require(rid in candidate_ids and rid not in seen_record and diag_by_id[rid]["status"] == "supported", "case-record")
        assignment = case["assignment"]
        _require(type(assignment) is dict and 1 <= len(assignment) <= 16, "case-assignment")
        for name, value in assignment.items():
            _require(bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name)), "case-variable"); _require_int(value)
        for key in ("source_tokens", "context_tokens"):
            _require(type(case[key]) is list and len(case[key]) <= MAX_SOURCE_TOKENS and all(type(x) is str and x for x in case[key]), "source-tokens")
        _require(type(case["context_preconditions"]) is list and len(case["context_preconditions"]) == len(case["context_tokens"]), "context-preconditions")
        for expr in case["context_preconditions"]:
            _require(validate_expr(expr, set(assignment)) == "bool", "context-root-type")
        if case["kind"] == "guard-trigger":
            _require(case["frontend_rule"] in {"require", "reject-if"} and type(case["trigger_value"]) is bool, "guard-rule")
            _require(case["trigger_value"] is (case["frontend_rule"] == "reject-if"), "guard-trigger-binding")
            _require(validate_expr(case["guard"], set(assignment)) == "bool", "guard-root-type")
        else:
            _require(case["frontend_rule"] == "signed-negation-widening" and assignment == {"concat_dim": INT32_MIN}, "widening-case")
        seen_case.add(case["id"]); seen_record.add(rid)
    _require(sum(row["status"] == "supported" for row in diagnostics) == len(cases), "diagnostic-case-binding")
    return cases


# compatibility name for old callers
def validate_witness_cases(document: dict[str, Any], candidate_ids: set[str]) -> list[dict[str, Any]]:
    return validate_source_evidence(document, candidate_ids)


def validate_protocol(protocol: dict[str, Any], candidate_count: int) -> dict[str, Any]:
    expected = {"schema", "analysis_scope", "expected_candidate_count", "top_k", "primary_k", "semantic_hint_bonus", "source_evidence_bonus", "bonus_ablations", "bootstrap_replicates", "bootstrap_seed", "prediction_tie_break", "group_collapse", "h1_delta_threshold", "h2_availability_threshold", "h2_denominator", "baseline", "readiness_gate_ids"}
    _require(set(protocol) == expected and protocol.get("schema") == "rbw-public-protocol-v5", "protocol-schema")
    _require(protocol["expected_candidate_count"] == candidate_count and type(protocol["expected_candidate_count"]) is int, "protocol-candidate-count")
    top_k = protocol["top_k"]
    _require(type(top_k) is list and top_k == sorted(set(top_k)) and all(type(k) is int and 1 <= k <= candidate_count for k in top_k), "protocol-top-k")
    _require(protocol["primary_k"] in top_k and type(protocol["primary_k"]) is int, "protocol-primary-k")
    for key in ("semantic_hint_bonus", "source_evidence_bonus", "h1_delta_threshold", "h2_availability_threshold"):
        _require(type(protocol[key]) in {int, float} and math.isfinite(float(protocol[key])) and float(protocol[key]) >= 0, "protocol-number")
    _require(protocol["h2_denominator"] == "all-eligible-file-candidates", "h2-denominator")
    _require(type(protocol["bonus_ablations"]) is list and [float(x) for x in protocol["bonus_ablations"]] == sorted(set(float(x) for x in protocol["bonus_ablations"])), "protocol-ablations")
    _require(type(protocol["bootstrap_replicates"]) is int and 100 <= protocol["bootstrap_replicates"] <= 10000, "bootstrap-replicates")
    _require(type(protocol["bootstrap_seed"]) is int, "bootstrap-seed")
    _require(protocol["readiness_gate_ids"] == list(GATE_IDS), "readiness-gate-ids")
    baseline = protocol["baseline"]
    _require(type(baseline) is dict and set(baseline) == {"name", "kind", "published_reproduction_evidence"} and baseline["published_reproduction_evidence"] is None, "baseline-schema")
    return protocol


def validate_study_design(design: dict[str, Any]) -> dict[str, Any]:
    _require(set(design) == {"schema", "candidate_frame", "label_sealing", "source_correspondence", "baseline_reproduction", "temporal_split"} and design.get("schema") == "rbw-study-design-v2", "design-schema")
    cf = design["candidate_frame"]
    _require(type(cf) is dict and set(cf) == {"selection_method", "class_lists_used", "repository", "window_start", "window_end", "enumeration_manifest"}, "candidate-frame-schema")
    _require(cf["selection_method"] == "retrospective-label-indexed-microcohort" and cf["class_lists_used"] is True and cf["repository"] == "tensorflow/tensorflow" and cf["window_start"] is None and cf["window_end"] is None and cf["enumeration_manifest"] is None, "candidate-frame-values")
    ls = design["label_sealing"]
    _require(type(ls) is dict and set(ls) == {"seal_record", "method_freeze_timestamp"} and ls["seal_record"] is None and ls["method_freeze_timestamp"] is None, "label-sealing-schema")
    sc = design["source_correspondence"]
    _require(type(sc) is dict and set(sc) == {"input_mode", "raw_diff_archive", "source_tree_manifest", "checked_lowering_evidence"} and sc["input_mode"] == "minimal-real-unified-diff-context" and sc["raw_diff_archive"] is None and sc["source_tree_manifest"] is None and sc["checked_lowering_evidence"] is None, "source-correspondence-schema")
    br = design["baseline_reproduction"]
    _require(type(br) is dict and set(br) == {"implemented_control", "published_system", "same_budget_evidence"} and br["implemented_control"] == "deterministic lexical/syntactic control" and br["published_system"] is None and br["same_budget_evidence"] is None, "baseline-reproduction-schema")
    ts = design["temporal_split"]
    _require(type(ts) is dict and set(ts) == {"cutoff", "development_manifest", "holdout_manifest"} and ts["cutoff"] is None and ts["development_manifest"] is None and ts["holdout_manifest"] is None, "temporal-split-schema")
    return design


def _record_binding(record: dict[str, Any]) -> str:
    return canonical_hash({key: record[key] for key in ("id", "commit", "file_path", "commit_message", "diff_context")})


def make_source_record(case: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    if case["kind"] == "source-difference":
        concat_dim = case["assignment"]["concat_dim"]
        value = -concat_dim if concat_dim < 0 else concat_dim + 1
        # This is mathematical representability, NOT evaluation of the old C++
        # expression. The excerpt supplies destination declarations, not the
        # operand type or the language's conversion semantics.
        return {
            "schema": "rbw-source-record-v2", "kind": "source-difference", "case": case["id"], "record": case["record"],
            "record_binding": _record_binding(record), "assignment": dict(case["assignment"]),
            "source_tokens": list(case["source_tokens"]), "context_tokens": list(case["context_tokens"]),
            "relation": "destination-range-separation",
            "assumed_signed_widths": [32, 64],
            "mathematical_value": typed_int(value),
            "fits_old_destination": typed_bool(INT32_MIN <= value <= INT32_MAX),
            "fits_new_destination": typed_bool(INT64_MIN <= value <= INT64_MAX),
        }
    context_results: list[dict[str, Any]] = []
    context_traces: list[list[list[Any]]] = []
    for expr in case["context_preconditions"]:
        trace: list[list[Any]] = []
        context_results.append(producer_eval(expr, case["assignment"], trace))
        context_traces.append(trace)
    guard_trace: list[list[Any]] = []
    guard_result = producer_eval(case["guard"], case["assignment"], guard_trace)
    triggered = typed_bool(guard_result["payload"] is case["trigger_value"])
    return {
        "schema": "rbw-source-record-v2", "kind": "guard-trigger", "case": case["id"], "record": case["record"],
        "record_binding": _record_binding(record), "assignment": dict(case["assignment"]),
        "source_tokens": list(case["source_tokens"]), "context_tokens": list(case["context_tokens"]),
        "context_results": context_results, "context_traces": context_traces,
        "guard_result": guard_result, "guard_trace": guard_trace, "triggered": triggered,
    }


def check_source_record(case: dict[str, Any], record: dict[str, Any], evidence: dict[str, Any]) -> tuple[bool, str]:
    if type(evidence) is not dict or evidence.get("schema") != "rbw-source-record-v2" or evidence.get("kind") != case["kind"]:
        return False, "source-record-schema"
    common = {"schema", "kind", "case", "record", "record_binding", "assignment", "source_tokens", "context_tokens"}
    expected = common | ({"relation", "assumed_signed_widths", "mathematical_value", "fits_old_destination", "fits_new_destination"} if case["kind"] == "source-difference" else {"context_results", "context_traces", "guard_result", "guard_trace", "triggered"})
    if set(evidence) != expected:
        return False, "source-record-fields"
    if evidence["case"] != case["id"] or evidence["record"] != case["record"] or evidence["record_binding"] != _record_binding(record):
        return False, "source-record-binding"
    if not typed_equal(evidence["assignment"], case["assignment"]):
        return False, "source-record-assignment"
    if not typed_equal(evidence["source_tokens"], case["source_tokens"]) or not typed_equal(evidence["context_tokens"], case["context_tokens"]):
        return False, "source-record-token"
    try:
        if case["kind"] == "source-difference":
            # Independent arithmetic check; never call the record producer.
            operand = case["assignment"].get("concat_dim")
            if type(operand) is not int or operand != -(1 << 31):
                return False, "source-difference-domain"
            magnitude = abs(operand)
            expected_fields = {
                "relation": "destination-range-separation",
                "assumed_signed_widths": [32, 64],
                "mathematical_value": {"tag": "int", "payload": magnitude},
                "fits_old_destination": {"tag": "bool", "payload": magnitude < (1 << 31)},
                "fits_new_destination": {"tag": "bool", "payload": magnitude < (1 << 63)},
            }
            for key, value in expected_fields.items():
                if not typed_equal(evidence[key], value):
                    return False, f"source-record-{key}"
            return True, "accepted-source-difference"
        expected_results: list[dict[str, Any]] = []
        expected_traces: list[list[list[Any]]] = []
        for expr in case["context_preconditions"]:
            value, trace = replay(expr, case["assignment"])
            expected_results.append(value); expected_traces.append(trace)
        guard_value, guard_trace = replay(case["guard"], case["assignment"])
        triggered = typed_bool(guard_value["payload"] is case["trigger_value"])
        for value in expected_results + [guard_value, triggered]: validate_typed_value(value)
        for trace in expected_traces + [guard_trace]: _validate_trace(trace)
        if not typed_equal(evidence["context_results"], expected_results): return False, "source-record-context-results"
        if not typed_equal(evidence["context_traces"], expected_traces): return False, "source-record-context-traces"
        if not typed_equal(evidence["guard_result"], guard_value): return False, "source-record-guard-result"
        if not typed_equal(evidence["guard_trace"], guard_trace): return False, "source-record-guard-trace"
        if not typed_equal(evidence["triggered"], triggered): return False, "source-record-triggered"
        if not all(value == typed_bool(True) for value in expected_results): return False, "source-record-context-false"
        if triggered != typed_bool(True): return False, "source-record-not-triggered"
        return True, "accepted-guard-trigger"
    except (Invalid, KeyError, TypeError):
        return False, "source-record-replay"


SECURITY_PHRASES = {
    "out of bound": 5.0, "out-of-bound": 5.0, "overflow": 4.0, "segfault": 5.0,
    "divide by zero": 5.0, "heap access": 5.0, "must not be negative": 3.0,
    "invalidargument": 2.0, "op_requires": 2.0, "bound check": 3.0,
    "fix ": 2.0, "error": 0.7, "check": 0.7,
}


def syntax_score(record: dict[str, Any]) -> float:
    text = (record["commit_message"] + " " + record["diff_context"]).lower()
    score = sum(weight * text.count(term) for term, weight in SECURITY_PHRASES.items())
    score += 0.12 * len(re.findall(r"(?:==|!=|<=|>=|<|>)", text))
    score += 0.05 * math.log1p(len(text))
    return round(score, 9)


def semantic_hint(record: dict[str, Any]) -> dict[str, int]:
    text = record["diff_context"].lower()
    message = record["commit_message"].lower()
    features = {
        "added_guard": int(bool(re.search(r"^\+.*(?:if\s*\(|op_requires\s*\(|tf_lite_ensure)", text, re.M))),
        "range_relation": int(bool(re.search(r"(?:<=|>=|<|>)", text) and re.search(r"(?:dim|size|axis|bound|limit|index|elements|threads|width|stride)", text))),
        "error_return": int("invalidargument" in text or "op_requires" in text),
        "type_widening": int(bool(re.search(r"-\s*const\s+int\b", text) and re.search(r"\+\s*const\s+int64", text))),
        "overflow_division_guard": int("/" in text and "overflow" in (message + text)),
    }
    features["hint"] = int(any(features.values()))
    return features


def _rank(rows: list[dict[str, Any]], score_name: str) -> list[str]:
    return [row["id"] for row in sorted(rows, key=lambda row: (-row[score_name], -row["syntax_score"], row["id"]))]


def freeze_predictions(candidates: dict[str, Any], source_evidence: dict[str, Any], protocol: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    records = validate_candidates(candidates); validate_protocol(protocol, len(records))
    by_id = {r["id"]: r for r in records}
    cases = validate_source_evidence(source_evidence, set(by_id))
    case_by_record = {c["record"]: c for c in cases}
    diagnostic_by_record = {d["record"]: d for d in source_evidence["diagnostics"]}
    accepted: set[str] = set(); source_records: list[dict[str, Any]] = []
    case_outcomes: dict[str, dict[str, Any]] = {}
    for case in cases:
        evidence = make_source_record(case, by_id[case["record"]])
        ok, reason = check_source_record(case, by_id[case["record"]], evidence)
        source_records.append(evidence)
        case_outcomes[case["record"]] = {"record": case["record"], "case": case["id"], "accepted": int(ok), "typed_outcome": "accepted" if ok else "replay-rejected", "reason": reason}
        if ok: accepted.add(case["record"])

    rows: list[dict[str, Any]] = []; outcomes: list[dict[str, Any]] = []
    semantic_bonus = float(protocol["semantic_hint_bonus"]); evidence_bonus = float(protocol["source_evidence_bonus"])
    for record in records:
        hint = semantic_hint(record); base = syntax_score(record)
        accepted_flag = int(record["id"] in accepted)
        rows.append({
            "id": record["id"], "group": record["group"], "syntax_score": base,
            "semantic_hint": hint["hint"], "semantic_features": hint,
            "unvalidated_score": round(base + semantic_bonus * hint["hint"], 9),
            "source_evidence_accepted": accepted_flag,
            "validated_score": round(base + evidence_bonus * accepted_flag, 9),
        })
        if record["id"] in case_outcomes:
            outcomes.append(case_outcomes[record["id"]])
        else:
            diagnostic = diagnostic_by_record[record["id"]]
            typed_outcome = "unsupported-syntax" if diagnostic["reason"] == "no-supported-added-source-pattern" else f"abstain-{diagnostic['stage']}"
            outcomes.append({"record": record["id"], "case": None, "accepted": 0, "typed_outcome": typed_outcome, "reason": diagnostic["reason"]})

    predictions = {
        "schema": "rbw-public-predictions-v5", "phase": "label-free-freeze",
        "candidate_hash": canonical_hash(candidates), "source_evidence_hash": canonical_hash(source_evidence), "protocol_hash": canonical_hash(protocol),
        "label_fields_present": False, "candidate_count": len(records), "records": rows,
        "rankings": {"syntax": _rank(rows, "syntax_score"), "unvalidated": _rank(rows, "unvalidated_score"), "validated": _rank(rows, "validated_score")},
    }
    return predictions, outcomes, source_records


def validate_predictions(predictions: dict[str, Any], candidates: dict[str, Any], source_evidence: dict[str, Any], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    expected = {"schema", "phase", "candidate_hash", "source_evidence_hash", "protocol_hash", "label_fields_present", "candidate_count", "records", "rankings"}
    _require(set(predictions) == expected and predictions["schema"] == "rbw-public-predictions-v5" and predictions["phase"] == "label-free-freeze", "prediction-schema")
    _require(predictions["candidate_hash"] == canonical_hash(candidates), "prediction-candidate-binding")
    _require(predictions["source_evidence_hash"] == canonical_hash(source_evidence), "prediction-evidence-binding")
    _require(predictions["protocol_hash"] == canonical_hash(protocol), "prediction-protocol-binding")
    _require(predictions["label_fields_present"] is False, "prediction-label-leakage")
    rows = predictions["records"]
    row_fields = {"id", "group", "syntax_score", "semantic_hint", "semantic_features", "unvalidated_score", "source_evidence_accepted", "validated_score"}
    _require(type(rows) is list and len(rows) == predictions["candidate_count"], "prediction-count")
    seen: set[str] = set()
    for row in rows:
        _require(type(row) is dict and set(row) == row_fields and row["id"] not in seen and "label" not in row, "prediction-row")
        _require(type(row["semantic_hint"]) is int and row["semantic_hint"] in {0, 1} and type(row["source_evidence_accepted"]) is int and row["source_evidence_accepted"] in {0, 1}, "prediction-flag")
        _require(all(type(row[key]) in {int, float} and math.isfinite(float(row[key])) for key in ("syntax_score", "unvalidated_score", "validated_score")), "prediction-score")
        features = row["semantic_features"]
        _require(type(features) is dict and set(features) == {"added_guard", "range_relation", "error_return", "type_widening", "overflow_division_guard", "hint"} and all(type(v) is int and v in {0, 1} for v in features.values()) and features["hint"] == row["semantic_hint"], "prediction-features")
        seen.add(row["id"])
    _require(type(predictions["rankings"]) is dict and set(predictions["rankings"]) == {"syntax", "unvalidated", "validated"}, "prediction-rankings")
    for name, score in (("syntax", "syntax_score"), ("unvalidated", "unvalidated_score"), ("validated", "validated_score")):
        _require(predictions["rankings"][name] == _rank(rows, score), "prediction-ranking-binding")
    return rows


def validate_outcomes(outcomes: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _require(type(outcomes) is list and len(outcomes) == len(rows), "outcome-count")
    by_id = {row["id"]: row for row in rows}; seen: set[str] = set()
    for outcome in outcomes:
        _require(type(outcome) is dict and set(outcome) == {"record", "case", "accepted", "typed_outcome", "reason"}, "outcome-row")
        rid = outcome["record"]
        _require(rid in by_id and rid not in seen and type(outcome["accepted"]) is int and outcome["accepted"] in {0, 1}, "outcome-record")
        _require(outcome["accepted"] == by_id[rid]["source_evidence_accepted"], "outcome-prediction-binding")
        if outcome["accepted"]:
            _require(type(outcome["case"]) is str and outcome["typed_outcome"] == "accepted" and outcome["reason"] in {"accepted-guard-trigger", "accepted-source-difference"}, "outcome-accepted")
        else:
            _require(outcome["case"] is None or type(outcome["case"]) is str, "outcome-case")
            _require(outcome["typed_outcome"] in {"unsupported-syntax", "abstain-extract", "abstain-parse", "abstain-evaluate", "replay-rejected"}, "outcome-type")
        seen.add(rid)
    return outcomes


def validate_source_records(source_records: Any, cases: list[dict[str, Any]], candidates: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _require(type(source_records) is list, "source-record-list")
    case_by_id = {case["id"]: case for case in cases}; candidate_by_id = {r["id"]: r for r in candidates}
    accepted_outcomes = [o for o in outcomes if o["accepted"]]
    _require(len(source_records) == len(accepted_outcomes), "source-record-count")
    seen_cases: set[str] = set(); seen_records: set[str] = set()
    for evidence in source_records:
        _require(type(evidence) is dict and evidence.get("case") in case_by_id, "source-record-case")
        case = case_by_id[evidence["case"]]; rid = case["record"]
        _require(evidence["case"] not in seen_cases and rid not in seen_records, "source-record-duplicate")
        ok, reason = check_source_record(case, candidate_by_id[rid], evidence)
        _require(ok and reason in {"accepted-guard-trigger", "accepted-source-difference"}, "source-record-check")
        matching = [o for o in accepted_outcomes if o["case"] == case["id"] and o["record"] == rid]
        _require(len(matching) == 1, "source-record-outcome-uniqueness")
        seen_cases.add(case["id"]); seen_records.add(rid)
    return source_records


def _precision(order: list[str], labels: dict[str, int], k: int) -> Fraction:
    _require(len(order) >= k, "top-k")
    return Fraction(sum(labels[x] for x in order[:k]), k)


def _average_precision(order: list[str], labels: dict[str, int]) -> float:
    positives = sum(labels.values())
    if positives == 0: return 0.0
    seen = 0; total = 0.0
    for rank, rid in enumerate(order, 1):
        if labels[rid]:
            seen += 1; total += seen / rank
    return total / positives


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0: return [0.0, 0.0]
    p = successes / total; denominator = 1.0 + z*z/total
    center = (p + z*z/(2*total))/denominator
    margin = z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/denominator
    return [max(0.0, center-margin), min(1.0, center+margin)]


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values); position = (len(ordered)-1)*q; low = math.floor(position); high = math.ceil(position)
    return ordered[low] if low == high else ordered[low]*(high-position)+ordered[high]*(position-low)


def _collapse_groups(rows: list[dict[str, Any]], labels: dict[str, int]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows: grouped[row["group"]].append(row)
    result: list[dict[str, Any]] = []; group_labels: dict[str, int] = {}
    for group, units in sorted(grouped.items()):
        result.append({
            "id": group, "group": group,
            "syntax_score": max(r["syntax_score"] for r in units),
            "unvalidated_score": max(r["unvalidated_score"] for r in units),
            "validated_score": max(r["validated_score"] for r in units),
            "source_evidence_accepted": max(r["source_evidence_accepted"] for r in units),
        })
        group_labels[group] = max(labels[r["id"]] for r in units)
    return result, group_labels


def _cluster_bootstrap(rows: list[dict[str, Any]], labels: dict[str, int], k: int, replicates: int, seed: int) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows: groups[row["group"]].append(row)
    names = sorted(groups); rng = random.Random(seed); deltas: list[float] = []
    for _ in range(replicates):
        sample = [rng.choice(names) for _ in names]
        sampled_rows: list[dict[str, Any]] = []; sampled_labels: dict[str, int] = {}
        for draw_index, group in enumerate(sample):
            for unit in groups[group]:
                clone = dict(unit); clone["id"] = f"{draw_index}:{unit['id']}"; clone["group"] = str(draw_index)
                sampled_rows.append(clone); sampled_labels[clone["id"]] = labels[unit["id"]]
        kk = min(k, len(sampled_rows))
        base = _precision(_rank(sampled_rows, "syntax_score"), sampled_labels, kk)
        val = _precision(_rank(sampled_rows, "validated_score"), sampled_labels, kk)
        deltas.append(float(val-base))
    return {"replicates": replicates, "seed": seed, "validated_minus_syntax_percentile_95": [_quantile(deltas, .025), _quantile(deltas, .975)]}


def derive_readiness(candidates: dict[str, Any], labels_doc: dict[str, Any], source_evidence: dict[str, Any], protocol: dict[str, Any], design: dict[str, Any], rows: list[dict[str, Any]], outcomes: list[dict[str, Any]], source_records: list[dict[str, Any]], reference_count: int, frontend_validation: dict[str, Any], artifact_root: Path | None = None) -> dict[str, Any]:
    validate_study_design(design)
    candidate_rows = validate_candidates(candidates)
    validate_labels(labels_doc, {r["id"]: r["group"] for r in candidate_rows})
    cases = validate_source_evidence(source_evidence, {r["id"] for r in candidate_rows})
    validate_outcomes(outcomes, rows)
    validate_source_records(source_records, cases, candidate_rows, outcomes)
    artifact_root = artifact_root or Path(".")
    machine = {
        "all_candidates_counted_with_typed_outcomes": len(rows) == len(outcomes) == len(candidates["records"]) and {r["id"] for r in rows} == {o["record"] for o in outcomes},
        "restricted_source_evidence_cross_checked": frontend_validation.get("schema") == "rbw-source-frontend-validation-v2" and frontend_validation.get("status") == "pass" and frontend_validation.get("mismatches") == 0 and frontend_validation.get("candidate_hash") == canonical_hash(candidates) and frontend_validation.get("source_evidence_hash") == canonical_hash(source_evidence),
        "independent_source_record_checker": len(source_records) == sum(r["source_evidence_accepted"] for r in rows) and all(o["reason"] in {"accepted-guard-trigger", "accepted-source-difference"} for o in outcomes if o["accepted"]),
    }
    # validate_study_design accepts this packet's documented retrospective
    # design only. File existence/digests are not proof of history or consent.
    # No general prospective-study authenticator is implemented here.
    design_facts = {key: False for key in (
        "raw_diff_or_checked_source_tree_correspondence",
        "candidate_selection_independent_of_labels",
        "complete_repository_time_window",
        "labels_sealed_before_method_development",
        "strongest_published_same_budget_baseline", "temporal_holdout",
    )}
    details = {
        "all_candidates_counted_with_typed_outcomes": "Every retained file unit has exactly one typed outcome and remains in the ranking denominator.",
        "restricted_source_evidence_cross_checked": "The restricted expression packet is cross-checked; this does not establish raw-diff or source-tree correspondence.",
        "raw_diff_or_checked_source_tree_correspondence": "Only minimal real file hunks are retained; no full raw-diff archive or checked source-tree lowering exists.",
        "candidate_selection_independent_of_labels": "Published class lists were used to construct the retrospective microcohort.",
        "complete_repository_time_window": "No complete repository-by-time enumeration manifest is present.",
        "independent_source_record_checker": "Every accepted source record is uniquely bound and independently replayed.",
        "labels_sealed_before_method_development": "No verifiable label-seal record predating method freeze is present.",
        "strongest_published_same_budget_baseline": "No reproduced published same-budget baseline evidence is present.",
        "temporal_holdout": "No verifiable development/holdout manifests or cutoff are present.",
    }
    evidence_paths = {
        "all_candidates_counted_with_typed_outcomes": ["predictions-frozen.json", "outcomes.json"],
        "restricted_source_evidence_cross_checked": ["results/source-frontend/summary.json"],
        "raw_diff_or_checked_source_tree_correspondence": ["data/public-study/study-design.json"],
        "candidate_selection_independent_of_labels": ["data/public-study/study-design.json", "data/public-study/labels.json"],
        "complete_repository_time_window": ["data/public-study/study-design.json"],
        "independent_source_record_checker": ["source-records.json", "outcomes.json"],
        "labels_sealed_before_method_development": ["data/public-study/study-design.json"],
        "strongest_published_same_budget_baseline": ["data/public-study/study-design.json"],
        "temporal_holdout": ["data/public-study/study-design.json"],
    }
    gates = []
    for gate in GATE_IDS:
        if gate in machine:
            status = machine[gate]; basis = "retained-check-report-bound-to-inputs" if gate == "restricted_source_evidence_cross_checked" else "machine-recomputed"
        else:
            status = design_facts[gate]; basis = "documented-retrospective-design; no-history-authenticator"
        gates.append({"id": gate, "status": "pass" if status else "fail", "basis": basis, "evidence": evidence_paths[gate], "detail": details[gate]})
    failed = [g["id"] for g in gates if g["status"] == "fail"]
    return {"editorial_checks": {"minimum_references": 55, "verified_ledger_entries": reference_count, "reference_count_at_least_55": type(reference_count) is int and reference_count >= 55}, "schema": "rbw-readiness-v3", "main_study_readiness": "passed" if not failed else "failed", "failed_readiness_gates": failed, "gates": gates}


def evaluate_predictions(candidates: dict[str, Any], label_doc: dict[str, Any], source_evidence: dict[str, Any], protocol: dict[str, Any], study_design: dict[str, Any], predictions: dict[str, Any], outcomes: list[dict[str, Any]], reference_count: int, frontend_validation: dict[str, Any], source_records: list[dict[str, Any]] | None = None, artifact_root: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidate_records = validate_candidates(candidates); validate_protocol(protocol, len(candidate_records)); cases = validate_source_evidence(source_evidence, {r["id"] for r in candidate_records}); validate_study_design(study_design)
    labels = validate_labels(label_doc, {r["id"]: r["group"] for r in candidate_records})
    rows = validate_predictions(predictions, candidates, source_evidence, protocol); outcomes = validate_outcomes(outcomes, rows)
    source_records = source_records or []
    if source_records: validate_source_records(source_records, cases, candidate_records, outcomes)
    _require({r["id"] for r in rows} == set(labels), "prediction-coverage")
    rankings = {"syntax": _rank(rows, "syntax_score"), "unvalidated": _rank(rows, "unvalidated_score"), "validated": _rank(rows, "validated_score")}
    metrics: dict[str, Any] = {}
    for method, order in rankings.items():
        metrics[method] = {f"precision_at_{k}": float(_precision(order, labels, k)) for k in protocol["top_k"]}
        metrics[method]["average_precision"] = _average_precision(order, labels)
    k = protocol["primary_k"]; base = _precision(rankings["syntax"], labels, k); val = _precision(rankings["validated"], labels, k); hint = _precision(rankings["unvalidated"], labels, k)
    delta = val-base; hint_delta = hint-base
    positive_files = sum(labels.values()); accepted_files = sum(r["source_evidence_accepted"] for r in rows); accepted_positive_files = sum(labels[r["id"]]*r["source_evidence_accepted"] for r in rows)
    group_rows, group_labels = _collapse_groups(rows, labels); positive_groups = sum(group_labels.values()); accepted_groups = sum(r["source_evidence_accepted"] for r in group_rows); accepted_positive_groups = sum(group_labels[r["id"]]*r["source_evidence_accepted"] for r in group_rows)
    coverage = {
        "positive_file_conditional": {"successes": accepted_positive_files, "total": positive_files, "fraction": f"{accepted_positive_files}/{positive_files}", "value": accepted_positive_files/positive_files, "wilson_95": _wilson(accepted_positive_files, positive_files)},
        "positive_commit_conditional": {"successes": accepted_positive_groups, "total": positive_groups, "fraction": f"{accepted_positive_groups}/{positive_groups}", "value": accepted_positive_groups/positive_groups, "wilson_95": _wilson(accepted_positive_groups, positive_groups)},
        "all_candidate_file_availability": {"successes": accepted_files, "total": len(rows), "fraction": f"{accepted_files}/{len(rows)}", "value": accepted_files/len(rows), "wilson_95": _wilson(accepted_files, len(rows))},
        "all_candidate_commit_availability": {"successes": accepted_groups, "total": len(group_rows), "fraction": f"{accepted_groups}/{len(group_rows)}", "value": accepted_groups/len(group_rows), "wilson_95": _wilson(accepted_groups, len(group_rows))},
    }
    ablations=[]; accepted_ids={r["id"] for r in rows if r["source_evidence_accepted"]}
    for bonus_value in protocol["bonus_ablations"]:
        temp=[]
        for row in rows:
            clone=dict(row); clone["ablation_score"]=round(row["syntax_score"]+float(bonus_value)*int(row["id"] in accepted_ids),9); temp.append(clone)
        order=_rank(temp,"ablation_score"); p=_precision(order,labels,k)
        ablations.append({"source_evidence_bonus":float(bonus_value),"precision_at_20":float(p),"delta_from_syntax":float(p-base),"top20_symmetric_difference_size":len(set(order[:k])^set(rankings["syntax"][:k]))})
    readiness=derive_readiness(candidates,label_doc,source_evidence,protocol,study_design,rows,outcomes,source_records,reference_count,frontend_validation,artifact_root)
    failed=readiness["failed_readiness_gates"]
    ranks={name:{rid:i+1 for i,rid in enumerate(order)} for name,order in rankings.items()}
    scored=[]
    for row in rows:
        scored.append({**row,"label":labels[row["id"]],"syntax_rank":ranks["syntax"][row["id"]],"unvalidated_rank":ranks["unvalidated"][row["id"]],"validated_rank":ranks["validated"][row["id"]]})
    formal_h1 = "threshold-met" if not failed and delta >= Fraction(1,10) else "threshold-not-met" if not failed else "not-testable-with-label-selected-nontemporal-cohort"
    h2_value = Fraction(accepted_files, len(rows))
    formal_h2 = "threshold-met" if not failed and h2_value >= Fraction(3,5) else "threshold-not-met" if not failed else "not-testable-as-full-cohort-file-availability"
    summary={
        "schema":"rbw-public-summary-v6","scope":"32-unit label-selected TensorFlow file-change microcohort; descriptive source-evidence audit only",
        "candidate_units":len(rows),"commit_groups":len(group_rows),"positive_units":positive_files,"positive_commit_groups":positive_groups,
        "accepted_source_records":accepted_files,"typed_outcome_counts":dict(sorted(Counter(o["typed_outcome"] for o in outcomes).items())),
        "metrics":metrics,"validated_minus_syntax_at_20":float(delta),"unvalidated_minus_syntax_at_20":float(hint_delta),
        "top20_symmetric_difference_validated_vs_syntax":len(set(rankings["validated"][:k])^set(rankings["syntax"][:k])),
        "coverage":coverage,"h2_descriptive_denominator":"all-eligible-file-candidates","h2_descriptive_threshold_analogue":float(protocol["h2_availability_threshold"]),
        "formal_h1_decision":formal_h1,"formal_h2_decision":formal_h2,"main_study_readiness":readiness["main_study_readiness"],"failed_readiness_gates":failed,
        "bootstrap":_cluster_bootstrap(rows,labels,k,protocol["bootstrap_replicates"],protocol["bootstrap_seed"]),
        "rankings":rankings,
    }
    return summary, scored, ablations, readiness
