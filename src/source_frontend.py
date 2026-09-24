"""Automatic, deliberately restricted source-diff frontend.

The frontend recognizes two source patterns in retained patch excerpts:

* added rejection guards of the form ``if (bad_predicate)``;
* added admission guards of the form ``OP_REQUIRES(ctx, good_predicate, ...)``;

It also recognizes the retained ``int`` -> ``int64`` negation widening.  The
accepted grammar is intentionally small: integer constants and variables,
parentheses, ``!``, ``&&``, ``||``, comparison operators, and integer division.
This is not a C/C++ parser and does not model macros, aliases, undefined
behavior, declarations, control-flow beyond the extracted guard, or build
configuration.  It is a reproducible source-to-relation boundary for the
retained microcohort only.
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
    """Raised when a source fragment is outside the restricted grammar."""


@dataclass(frozen=True)
class Token:
    kind: str
    text: str


# These substitutions are part of the explicit frontend contract.  They map
# source-level accessors in the retained snippets to bounded scalar variables.
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


def normalize_expression(text: str) -> str:
    """Normalize only the explicitly supported source aliases."""
    out = text.strip()
    for pattern, replacement in _REWRITES:
        out = pattern.sub(replacement, out)
    # Strip a single redundant outer pair only through the parser, not with a
    # textual heuristic.  Reject C/C++ syntax that is outside the grammar.
    return out


def tokenize(text: str) -> list[Token]:
    normalized = normalize_expression(text)
    tokens: list[Token] = []
    pos = 0
    while pos < len(normalized):
        match = _TOKEN_RE.match(normalized, pos)
        if match is None:
            raise FrontendError(f"unsupported-token:{normalized[pos:pos + 24]}")
        kind = match.lastgroup
        assert kind is not None
        value = match.group(kind)
        tokens.append(Token(kind, value))
        pos = match.end()
    if not tokens:
        raise FrontendError("empty-expression")
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
            raise FrontendError("unexpected-end")
        self.index += 1
        return token

    def parse(self) -> list[Any]:
        expression = self.parse_expression(0)
        if self.peek() is not None:
            raise FrontendError(f"trailing-token:{self.peek().text}")
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
                raise FrontendError("unary-minus-only-for-constant")
            value = int(operand.text, 0)
            return ["const", -value]
        if token.kind == "op" and token.text == "(":
            expression = self.parse_expression(0)
            close = self.take()
            if close.kind != "op" or close.text != ")":
                raise FrontendError("missing-close-parenthesis")
            return expression
        if token.kind in {"int", "hex"}:
            value = int(token.text, 0)
            if not INT64_MIN <= value <= INT64_MAX:
                raise FrontendError("integer-range")
            return ["const", value]
        if token.kind == "name":
            if token.text in {"true", "false"}:
                return ["const", 1 if token.text == "true" else 0]
            return ["var", token.text]
        raise FrontendError(f"unexpected-token:{token.text}")


def parse_expression(text: str) -> list[Any]:
    """Parse one expression with the primary Pratt implementation."""
    return _PrattParser(tokenize(text)).parse()


def _balanced_content(text: str, open_index: int) -> tuple[str, int]:
    if open_index >= len(text) or text[open_index] != "(":
        raise FrontendError("expected-open-parenthesis")
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
    raise FrontendError("unbalanced-parentheses")


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
        elif char in "([{" :
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            arguments.append(content[start:index].strip())
            start = index + 1
    arguments.append(content[start:].strip())
    return arguments


def _extract_added_if_guards(text: str) -> list[str]:
    guards: list[str] = []
    pattern = re.compile(r"(?:^|\+)\s*if\s*\(")
    for match in pattern.finditer(text):
        open_index = text.find("(", match.start())
        content, _ = _balanced_content(text, open_index)
        guards.append(content.strip())
    return guards


def _extract_requires_guards(text: str) -> list[str]:
    guards: list[str] = []
    for match in re.finditer(r"\bOP_REQUIRES\s*\(", text):
        open_index = text.find("(", match.start())
        content, _ = _balanced_content(text, open_index)
        arguments = _split_top_level_arguments(content)
        if len(arguments) < 3:
            raise FrontendError("op-requires-arity")
        guards.append(arguments[1].strip())
    return guards


def _combine(expressions: list[list[Any]], operator: str) -> list[Any]:
    if not expressions:
        raise FrontendError("no-expressions")
    result = expressions[0]
    for expression in expressions[1:]:
        result = [operator, result, expression]
    return result


def _variables(expression: list[Any]) -> set[str]:
    op = expression[0]
    if op == "var":
        return {expression[1]}
    if op == "const":
        return set()
    values: set[str] = set()
    for child in expression[1:]:
        values.update(_variables(child))
    return values


def trunc_div(a: int, b: int) -> int:
    if b == 0:
        raise FrontendError("division-by-zero")
    magnitude = abs(a) // abs(b)
    value = -magnitude if (a < 0) != (b < 0) else magnitude
    if not INT64_MIN <= value <= INT64_MAX:
        raise FrontendError("integer-range")
    return value


def evaluate(expression: list[Any], assignment: dict[str, int]) -> int | bool:
    op = expression[0]
    if op == "const":
        return int(expression[1])
    if op == "var":
        if expression[1] not in assignment:
            raise FrontendError(f"missing-variable:{expression[1]}")
        return int(assignment[expression[1]])
    if op == "not":
        return not bool(evaluate(expression[1], assignment))
    if op == "and":
        left = bool(evaluate(expression[1], assignment))
        return left and bool(evaluate(expression[2], assignment))
    if op == "or":
        left = bool(evaluate(expression[1], assignment))
        return left or bool(evaluate(expression[2], assignment))
    left = evaluate(expression[1], assignment)
    right = evaluate(expression[2], assignment)
    if type(left) is bool or type(right) is bool:
        raise FrontendError("sort-error")
    a, b = int(left), int(right)
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    if op == "lt":
        return a < b
    if op == "le":
        return a <= b
    if op == "gt":
        return a > b
    if op == "ge":
        return a >= b
    if op == "div":
        return trunc_div(a, b)
    raise FrontendError(f"unsupported-op:{op}")


def _domain(name: str) -> list[int]:
    if name in {"sx", "sy"}:
        return [0, 1, 2, -1]
    if name == "axis":
        return [-1, 0, 1, 2, 3, INT32_MAX]
    if name in {"dims", "input_dims"}:
        return [0, 1, 2, 3]
    if name == "batch_dim":
        return [-1, 0, 1, 2]
    if name == "dim":
        return [0, -1, 1, 2, INT32_MAX]
    if name == "prod":
        return [1, 0, 2, INT32_MAX]
    if name == "limit":
        return [INT32_MAX, 1, 2]
    if name.endswith("_start"):
        return [-1, 0, 1, 2]
    if name.endswith("_end"):
        return [0, -1, 1, 2]
    if name == "num_threads":
        return [-1, 0, 1, 65535, 65536, 65537]
    if name == "pad_width":
        return [-5, -1, 0, 1, 2]
    if name == "num_elements":
        return [0, 2, 1]
    return [0, -1, 1, 2, 3]


def assignment_domain(expression: list[Any]) -> dict[str, list[int]]:
    return {name: _domain(name) for name in sorted(_variables(expression))}


def _find_assignment(condition: list[Any], trigger_value: bool) -> dict[str, int]:
    domains = assignment_domain(condition)
    names = list(domains)
    combinations: Iterable[tuple[int, ...]]
    combinations = itertools.product(*(domains[name] for name in names))
    for values in combinations:
        assignment = dict(zip(names, values, strict=True))
        try:
            result = evaluate(condition, assignment)
        except FrontendError:
            continue
        if type(result) is bool and result is trigger_value:
            return assignment
    raise FrontendError("no-trigger-assignment")


def _is_widening_record(record: dict[str, Any]) -> bool:
    text = record["patch_excerpt"]
    return bool(
        re.search(r"-\s*const\s+int\s+min_rank", text)
        and re.search(r"\+\s*const\s+int64\s+min_rank", text)
        and "concat_dim" in text
    )


def derive_case(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Derive one bounded case or return a typed unsupported reason."""
    if _is_widening_record(record):
        return (
            {
                "kind": "widening",
                "record": record["id"],
                "assignment": {"concat_dim": INT32_MIN},
                "source_tokens": ["const int min_rank", "const int64 min_rank"],
                "frontend_rule": "signed-negation-widening",
            },
            "recognized-widening",
        )

    requires = _extract_requires_guards(record["patch_excerpt"])
    added_ifs = _extract_added_if_guards(record["patch_excerpt"])
    if requires and added_ifs:
        return None, "mixed-guard-styles"
    if requires:
        try:
            parsed = [parse_expression(text) for text in requires]
            condition = _combine(parsed, "and")
            assignment = _find_assignment(condition, False)
        except FrontendError as exc:
            return None, f"unsupported-require:{exc}"
        return (
            {
                "kind": "predicate",
                "record": record["id"],
                "assignment": assignment,
                "condition": condition,
                "hazard": ["not", condition],
                "source_tokens": requires,
                "trigger_value": False,
                "frontend_rule": "require",
            },
            "recognized-require",
        )
    if added_ifs:
        try:
            parsed = [parse_expression(text) for text in added_ifs]
            condition = _combine(parsed, "or")
            assignment = _find_assignment(condition, True)
        except FrontendError as exc:
            return None, f"unsupported-reject-if:{exc}"
        return (
            {
                "kind": "predicate",
                "record": record["id"],
                "assignment": assignment,
                "condition": condition,
                "hazard": condition,
                "source_tokens": added_ifs,
                "trigger_value": True,
                "frontend_rule": "reject-if",
            },
            "recognized-reject-if",
        )
    return None, "no-supported-source-pattern"


def derive_witness_document(candidates: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    records = candidates.get("records")
    if not isinstance(records, list):
        raise FrontendError("candidate-records")
    cases: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise FrontendError("candidate-row")
        case, reason = derive_case(record)
        diagnostics.append({"record": record["id"], "reason": reason})
        if case is not None:
            case = {"id": f"W{len(cases) + 1:02d}", **case}
            cases.append(case)
    return (
        {
            "schema": "rbw-public-witness-cases-v6",
            "construction": {
                "mode": "automatic-restricted-source-frontend",
                "automatic_source_frontend": True,
                "source_translation_validated": True,
                "grammar": "guard-expressions-v1",
                "validator": "independent-shunting-yard-and-c11-oracle",
            },
            "cases": cases,
        },
        diagnostics,
    )


def ast_to_rpn(expression: list[Any], assignment: dict[str, int]) -> list[str]:
    """Encode an expression for the independent C11 stack evaluator."""
    op = expression[0]
    if op == "const":
        return [f"I:{int(expression[1])}"]
    if op == "var":
        return [f"I:{int(assignment[expression[1]])}"]
    tokens: list[str] = []
    for child in expression[1:]:
        tokens.extend(ast_to_rpn(child, assignment))
    tokens.append(
        {
            "not": "NOT",
            "and": "AND",
            "or": "OR",
            "eq": "EQ",
            "ne": "NE",
            "lt": "LT",
            "le": "LE",
            "gt": "GT",
            "ge": "GE",
            "div": "DIV",
        }[op]
    )
    return tokens
