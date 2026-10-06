"""Restricted extractor for real retained unified-diff context.

This module does *not* lower C/C++ functions to the finite IR used by the
paper's old-fault/new-defined certificate.  It recognizes only two source
patterns in added lines of retained, real upstream diff hunks:

* a rejection guard ``if (bad_predicate)``; and
* an admission guard ``OP_REQUIRES(ctx, good_predicate, ...)``.

It also recognizes one retained ``int`` to ``int64`` widening.  Its outputs are
``guard-trigger`` or ``source-difference`` records, never finite behavioral
certificates.  Extraction, parsing, and expression evaluation are distinct
stages with typed abstentions.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import re
from typing import Any, Iterable

INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


class FrontendError(ValueError):
    """A declared frontend boundary was reached."""

    def __init__(self, stage: str, reason: str):
        super().__init__(f"{stage}:{reason}")
        self.stage = stage
        self.reason = reason


@dataclass(frozen=True)
class Token:
    kind: str
    text: str


_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"key_tensor\s*->\s*NumElements\s*\(\s*\)"), "num_elements"),
    (re.compile(r"input\s*\.\s*dims\s*\(\s*\)"), "dims"),
    (re.compile(r"dims\s*\(\s*i\s*\)"), "dim"),
    (re.compile(r"\baxis_\b"), "axis"),
    (re.compile(r"\bpad_width_\b"), "pad_width"),
    (re.compile(r"\bkint32max\b"), str(INT32_MAX)),
    (re.compile(r"\bkThreadLimit\b"), "65536"),
)

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<op>\|\||&&|==|!=|<=|>=|<|>|/|!|\(|\)|-)"
    r"|(?P<hex>0[xX][0-9A-Fa-f]+)"
    r"|(?P<int>[0-9]+)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r")"
)

_BINARY_PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "==": 3,
    "!=": 3,
    "<": 3,
    "<=": 3,
    ">": 3,
    ">=": 3,
    "/": 4,
}
_AST_OP = {
    "||": "or",
    "&&": "and",
    "==": "eq",
    "!=": "ne",
    "<": "lt",
    "<=": "le",
    ">": "gt",
    ">=": "ge",
    "/": "div",
}


def _integer_literal(token: Token) -> int:
    # The scalar profile supports decimal and hexadecimal, not C octal syntax.
    if token.kind == "int" and len(token.text) > 1 and token.text.startswith("0"):
        raise FrontendError("parse", "unsupported-integer-literal")
    try:
        return int(token.text, 0)
    except ValueError as exc:
        raise FrontendError("parse", "integer-range") from exc


def normalize_expression(text: str) -> str:
    value = text.strip()
    for pattern, replacement in _REWRITES:
        value = pattern.sub(replacement, value)
    return value


def tokenize(text: str) -> list[Token]:
    normalized = normalize_expression(text)
    tokens: list[Token] = []
    pos = 0
    while pos < len(normalized):
        match = _TOKEN_RE.match(normalized, pos)
        if match is None:
            raise FrontendError("parse", f"unsupported-token:{normalized[pos:pos + 24]}")
        kind = match.lastgroup
        assert kind is not None
        tokens.append(Token(kind, match.group(kind)))
        pos = match.end()
    if not tokens:
        raise FrontendError("parse", "empty-expression")
    return tokens


class _PrattParser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> Token | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self) -> Token:
        token = self.peek()
        if token is None:
            raise FrontendError("parse", "unexpected-end")
        self.index += 1
        return token

    def parse(self) -> list[Any]:
        expression = self.parse_expression(0)
        if self.peek() is not None:
            raise FrontendError("parse", f"trailing-token:{self.peek().text}")
        return expression

    def parse_expression(self, min_precedence: int) -> list[Any]:
        left = self.parse_prefix()
        while True:
            token = self.peek()
            if token is None or token.kind != "op" or token.text not in _BINARY_PRECEDENCE:
                break
            precedence = _BINARY_PRECEDENCE[token.text]
            if precedence < min_precedence:
                break
            operator = self.take().text
            right = self.parse_expression(precedence + 1)
            left = [_AST_OP[operator], left, right]
        return left

    def parse_prefix(self) -> list[Any]:
        token = self.take()
        if token.kind == "op" and token.text == "!":
            return ["not", self.parse_expression(5)]
        if token.kind == "op" and token.text == "-":
            operand = self.take()
            if operand.kind not in {"int", "hex"}:
                raise FrontendError("parse", "unary-minus-only-for-constant")
            value = -_integer_literal(operand)
            if not INT64_MIN <= value <= INT64_MAX:
                raise FrontendError("parse", "integer-range")
            return ["const", value]
        if token.kind == "op" and token.text == "(":
            expression = self.parse_expression(0)
            close = self.take()
            if close.kind != "op" or close.text != ")":
                raise FrontendError("parse", "missing-close-parenthesis")
            return expression
        if token.kind in {"int", "hex"}:
            value = _integer_literal(token)
            if not INT64_MIN <= value <= INT64_MAX:
                raise FrontendError("parse", "integer-range")
            return ["const", value]
        if token.kind == "name":
            if token.text in {"true", "false"}:
                return ["const", 1 if token.text == "true" else 0]
            return ["var", token.text]
        raise FrontendError("parse", f"unexpected-token:{token.text}")


def parse_expression(text: str) -> list[Any]:
    return _PrattParser(tokenize(text)).parse()


def _balanced_content(text: str, open_index: int) -> tuple[str, int]:
    if open_index >= len(text) or text[open_index] != "(":
        raise FrontendError("extract", "expected-open-parenthesis")
    depth = 0
    in_string = False
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:index], index + 1
            if depth < 0:
                break
    raise FrontendError("extract", "unbalanced-parentheses")


def _split_top_level_arguments(content: str) -> list[str]:
    arguments: list[str] = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            arguments.append(content[start:index].strip())
            start = index + 1
    arguments.append(content[start:].strip())
    return arguments


def _added_source(diff_context: str) -> str:
    lines: list[str] = []
    for line in diff_context.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return "\n".join(lines)


def _extract_added_if_guards(text: str) -> list[str]:
    """Extract only added rejection guards, not every C/C++ ``if``.

    A supported rejection guard must have a braced body whose first bounded
    statement returns an error.  This deliberately ignores control flow used
    only to initialize helper values, such as W10's datatype-dependent limit.
    Unbalanced conditions still surface as typed extraction failures.
    """
    guards: list[str] = []
    for match in re.finditer(r"\bif\s*\(", text):
        open_index = text.find("(", match.start())
        content, after_condition = _balanced_content(text, open_index)
        cursor = after_condition
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "{":
            continue
        depth = 0
        end = cursor
        for end in range(cursor, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    break
        if depth != 0:
            raise FrontendError("extract", "unbalanced-braces")
        body = text[cursor + 1:end]
        if re.search(r"\breturn\s+errors::", body):
            guards.append(content.strip())
    return guards


def _extract_requires_guards(text: str) -> list[str]:
    guards: list[str] = []
    for match in re.finditer(r"\bOP_REQUIRES\s*\(", text):
        open_index = text.find("(", match.start())
        content, _ = _balanced_content(text, open_index)
        arguments = _split_top_level_arguments(content)
        if len(arguments) < 3:
            raise FrontendError("extract", "op-requires-arity")
        guards.append(arguments[1].strip())
    return guards


def _combine(expressions: list[list[Any]], operator: str) -> list[Any]:
    if not expressions:
        raise FrontendError("parse", "no-expressions")
    result = expressions[0]
    for expression in expressions[1:]:
        result = [operator, result, expression]
    return result


def variables(expression: list[Any]) -> set[str]:
    if expression[0] == "var":
        return {expression[1]}
    if expression[0] == "const":
        return set()
    result: set[str] = set()
    for child in expression[1:]:
        result.update(variables(child))
    return result


def trunc_div(a: int, b: int) -> int:
    if b == 0:
        raise FrontendError("evaluate", "division-by-zero")
    magnitude = abs(a) // abs(b)
    value = -magnitude if (a < 0) != (b < 0) else magnitude
    if not INT64_MIN <= value <= INT64_MAX:
        raise FrontendError("evaluate", "integer-range")
    return value


def evaluate(expression: list[Any], assignment: dict[str, int]) -> int | bool:
    op = expression[0]
    if op == "const":
        return int(expression[1])
    if op == "var":
        if expression[1] not in assignment:
            raise FrontendError("evaluate", f"missing-variable:{expression[1]}")
        value = assignment[expression[1]]
        if type(value) is not int:
            raise FrontendError("evaluate", f"non-integer-assignment:{expression[1]}")
        return value
    if op == "not":
        child = evaluate(expression[1], assignment)
        if type(child) is not bool:
            raise FrontendError("evaluate", "sort-error")
        return not child
    if op == "and":
        left = evaluate(expression[1], assignment)
        if type(left) is not bool:
            raise FrontendError("evaluate", "sort-error")
        return False if not left else evaluate_bool(expression[2], assignment)
    if op == "or":
        left = evaluate(expression[1], assignment)
        if type(left) is not bool:
            raise FrontendError("evaluate", "sort-error")
        return True if left else evaluate_bool(expression[2], assignment)
    left = evaluate(expression[1], assignment)
    right = evaluate(expression[2], assignment)
    if type(left) is not int or type(right) is not int:
        raise FrontendError("evaluate", "sort-error")
    if op == "eq": return left == right
    if op == "ne": return left != right
    if op == "lt": return left < right
    if op == "le": return left <= right
    if op == "gt": return left > right
    if op == "ge": return left >= right
    if op == "div": return trunc_div(left, right)
    raise FrontendError("evaluate", f"unsupported-op:{op}")


def evaluate_bool(expression: list[Any], assignment: dict[str, int]) -> bool:
    value = evaluate(expression, assignment)
    if type(value) is not bool:
        raise FrontendError("evaluate", "expected-bool")
    return value


def _domain(name: str) -> list[int]:
    if name in {"sx", "sy"}: return [0, 1, 2, -1]
    if name == "axis": return [-1, 0, 1, 2, 3, INT32_MAX]
    if name in {"dims", "input_dims"}: return [0, 1, 2, 3]
    if name == "batch_dim": return [-1, 0, 1, 2]
    if name == "dim": return [-1, 1, 2, 0, INT32_MAX]
    if name == "prod": return [1, 2, INT32_MAX, 0]
    if name == "limit": return [INT32_MAX, 65536, 1, 2]
    if name.endswith("_start"): return [-1, 0, 1, 2]
    if name.endswith("_end"): return [-1, 0, 1, 2]
    if name == "num_threads": return [-1, 0, 1, 65535, 65536, 65537]
    if name == "pad_width": return [-5, -1, 0, 1, 2]
    if name == "num_elements": return [0, 2, 1]
    return [0, -1, 1, 2, 3]


def assignment_domain(expressions: Iterable[list[Any]]) -> dict[str, list[int]]:
    names: set[str] = set()
    for expression in expressions:
        names.update(variables(expression))
    return {name: _domain(name) for name in sorted(names)}


def _find_assignment(
    guard: list[Any], trigger_value: bool, context_preconditions: list[list[Any]]
) -> dict[str, int]:
    domains = assignment_domain([guard, *context_preconditions])
    names = list(domains)
    for values in itertools.product(*(domains[name] for name in names)):
        assignment = dict(zip(names, values, strict=True))
        try:
            if not all(evaluate_bool(item, assignment) for item in context_preconditions):
                continue
            if evaluate_bool(guard, assignment) is trigger_value:
                return assignment
        except FrontendError:
            continue
    raise FrontendError("evaluate", "no-trigger-assignment")


def _is_widening_record(record: dict[str, Any]) -> bool:
    text = record["diff_context"]
    return bool(
        re.search(r"-\s*const\s+int\s+min_rank", text)
        and re.search(r"\+\s*const\s+int64\s+min_rank", text)
        and "concat_dim" in text
    )


def derive_case(record: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Derive one restricted source record or a typed abstention."""
    rid = record.get("id", "")
    if _is_widening_record(record):
        return ({
            "kind": "source-difference",
            "record": rid,
            "assignment": {"concat_dim": INT32_MIN},
            "source_tokens": ["const int min_rank", "const int64 min_rank"],
            "context_tokens": [],
            "context_preconditions": [],
            "frontend_rule": "signed-negation-widening",
        }, {"record": rid, "status": "supported", "stage": "extract", "reason": "recognized-widening"})

    try:
        added = _added_source(record["diff_context"])
        requires = _extract_requires_guards(added)
        added_ifs = _extract_added_if_guards(added)
    except FrontendError as exc:
        return None, {"record": rid, "status": "abstain", "stage": exc.stage, "reason": exc.reason}

    if requires and added_ifs:
        return None, {"record": rid, "status": "abstain", "stage": "extract", "reason": "mixed-guard-styles"}
    if not requires and not added_ifs:
        return None, {"record": rid, "status": "abstain", "stage": "extract", "reason": "no-supported-added-source-pattern"}

    try:
        rule = "require" if requires else "reject-if"
        raw_guards = requires if requires else added_ifs
        parsed = [parse_expression(text) for text in raw_guards]
        guard = _combine(parsed, "and" if rule == "require" else "or")
        raw_context = record["source_asset"].get("context_requirements", [])
        context = [parse_expression(text) for text in raw_context]
        normalized_hunk = re.sub(r"\s+", " ", record["diff_context"]).strip()
        for token in raw_context:
            if re.sub(r"\s+", " ", token).strip() not in normalized_hunk:
                raise FrontendError("extract", "context-requirement-not-in-real-hunk")
        trigger = rule == "reject-if"
        assignment = _find_assignment(guard, trigger, context)
    except FrontendError as exc:
        return None, {"record": rid, "status": "abstain", "stage": exc.stage, "reason": exc.reason}

    return ({
        "kind": "guard-trigger",
        "record": rid,
        "assignment": assignment,
        "guard": guard,
        "trigger_value": trigger,
        "source_tokens": raw_guards,
        "context_tokens": raw_context,
        "context_preconditions": context,
        "frontend_rule": rule,
    }, {"record": rid, "status": "supported", "stage": "evaluate", "reason": f"recognized-{rule}"})


_STABLE_CASE_IDS = {
    ("08d7b00c0a5a20926363849f611729f53f3ec022", "tensorflow/core/framework/common_shape_fns.cc"): "W01",
    ("f68fdab93fb7f4ddb4eb438c8fe052753c9413e8", "tensorflow/core/kernels/string_ngrams_op.cc"): "W02",
    ("e3749a6d5d1e8d11806d4a2e9cc3123d1a90b75e", "tensorflow/core/kernels/data/experimental/threadpool_dataset_op.cc"): "W03",
    ("b64638ec5ccaa77b7c1eb90958e3d85ce381f91b", "tensorflow/core/ops/array_ops.cc"): "W04",
    ("002408c3696b173863228223d535f9de72a101a9", "tensorflow/core/kernels/fractional_avg_pool_op.cc"): "W05",
    ("37c01fb5e25c3d80213060460196406c43d31995", "tensorflow/core/ops/array_ops.cc"): "W06",
    ("23968a8bf65b009120c43b5ebcceaf52dbc9e943", "tensorflow/core/kernels/dequantize_op.cc"): "W07",
    ("3218043d6d3a019756607643cf65574fbfef5d7a", "tensorflow/core/grappler/costs/op_level_cost_estimator.cc"): "W08",
    ("f57315566d7094f322b784947093406c2aea0d7d", "tensorflow/core/kernels/map_stage_op.cc"): "W09",
    ("58b34c6c8250983948b5a781b426f6aa01fd47af", "tensorflow/core/kernels/unravel_index_op.cc"): "W10",
}

def derive_evidence_document(candidates: dict[str, Any]) -> dict[str, Any]:
    records = candidates.get("records")
    if not isinstance(records, list):
        raise FrontendError("extract", "candidate-records")
    cases: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise FrontendError("extract", "candidate-row")
        case, diagnostic = derive_case(record)
        diagnostics.append(diagnostic)
        if case is not None:
            key = (record["commit"], record["file_path"])
            if key not in _STABLE_CASE_IDS:
                raise FrontendError("extract", "recognized-record-without-stable-case-id")
            cases.append({"id": _STABLE_CASE_IDS[key], **case})
    cases.sort(key=lambda row: row["id"])
    return {
        "schema": "rbw-public-source-evidence-v1",
        "construction": {
            "mode": "automatic-restricted-real-diff-frontend",
            "input_mode": "minimal-real-unified-diff-context",
            "raw_diff_or_source_tree_correspondence": False,
            "grammar": "guard-expressions-v2",
            "evidence_contract": "guard-trigger-or-source-difference-not-old-fault-new-defined",
            "parser_cross_check": "independent-shunting-yard",
            "evaluator_cross_check": "recursive-python-iterative-python-c11-short-circuit-oracle",
        },
        "cases": cases,
        "diagnostics": diagnostics,
    }


def ast_to_rpn(expression: list[Any], assignment: dict[str, int]) -> list[str]:
    """Encode short-circuit postfix bytecode for the independent C11 oracle.

    ``SCAND:n`` and ``SCOR:n`` precede a right-hand segment of *n* tokens.  If
    the left Boolean decides the result, the C evaluator skips both that segment
    and its final AND/OR instruction.  Thus a protected division is not executed.
    """
    op = expression[0]
    if op == "const":
        return [f"I:{int(expression[1])}"]
    if op == "var":
        value = assignment[expression[1]]
        if type(value) is not int:
            raise FrontendError("evaluate", "non-integer-assignment")
        return [f"I:{value}"]
    if op == "not":
        return ast_to_rpn(expression[1], assignment) + ["NOT"]
    if op in {"and", "or"}:
        left = ast_to_rpn(expression[1], assignment)
        right = ast_to_rpn(expression[2], assignment)
        marker = "SCAND" if op == "and" else "SCOR"
        finish = "AND" if op == "and" else "OR"
        return left + [f"{marker}:{len(right)}"] + right + [finish]
    tokens = ast_to_rpn(expression[1], assignment) + ast_to_rpn(expression[2], assignment)
    tokens.append({
        "eq": "EQ", "ne": "NE", "lt": "LT", "le": "LE",
        "gt": "GT", "ge": "GE", "div": "DIV",
    }[op])
    return tokens
