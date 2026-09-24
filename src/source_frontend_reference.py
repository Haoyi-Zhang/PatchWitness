"""Independent shunting-yard parser/evaluator for frontend validation.

This module intentionally does not import the primary frontend parser.  It
reimplements normalization, postfix conversion, AST construction, and
short-circuit evaluation.
"""
from __future__ import annotations

import re
from typing import Any

INT32_MAX = 2**31 - 1
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


class ReferenceError(ValueError):
    pass


def normalize(text: str) -> str:
    substitutions = (
        (r"key_tensor\s*->\s*NumElements\s*\(\s*\)", "num_elements"),
        (r"input\s*\.\s*dims\s*\(\s*\)", "dims"),
        (r"dims\s*\(\s*i\s*\)", "dim"),
        (r"\baxis_\b", "axis"),
        (r"\bpad_width_\b", "pad_width"),
        (r"\bkint32max\b", str(INT32_MAX)),
        (r"\bkThreadLimit\b", "65536"),
    )
    value = text.strip()
    for pattern, replacement in substitutions:
        value = re.sub(pattern, replacement, value)
    return value


def lex(text: str) -> list[str]:
    value = normalize(text)
    pattern = re.compile(r"\s*(\|\||&&|==|!=|<=|>=|<|>|/|!|\(|\)|-|0[xX][0-9A-Fa-f]+|[0-9]+|[A-Za-z_][A-Za-z0-9_]*)")
    out: list[str] = []
    index = 0
    while index < len(value):
        match = pattern.match(value, index)
        if not match:
            raise ReferenceError(f"token:{value[index:index+20]}")
        out.append(match.group(1))
        index = match.end()
    if not out:
        raise ReferenceError("empty")
    return out


_PRECEDENCE = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3, "/": 4, "!": 5, "NEG": 5}
_RIGHT_ASSOC = {"!", "NEG"}


def to_postfix(text: str) -> list[str]:
    tokens = lex(text)
    output: list[str] = []
    operators: list[str] = []
    previous = "start"
    for token in tokens:
        if re.fullmatch(r"0[xX][0-9A-Fa-f]+|[0-9]+|[A-Za-z_][A-Za-z0-9_]*", token):
            output.append(token)
            previous = "operand"
            continue
        if token == "(":
            operators.append(token)
            previous = "open"
            continue
        if token == ")":
            while operators and operators[-1] != "(":
                output.append(operators.pop())
            if not operators:
                raise ReferenceError("parenthesis")
            operators.pop()
            previous = "operand"
            continue
        op = "NEG" if token == "-" and previous in {"start", "open", "operator"} else token
        if op not in _PRECEDENCE:
            raise ReferenceError(f"operator:{token}")
        while operators and operators[-1] in _PRECEDENCE:
            top = operators[-1]
            if (_PRECEDENCE[top] > _PRECEDENCE[op]) or (
                _PRECEDENCE[top] == _PRECEDENCE[op] and op not in _RIGHT_ASSOC
            ):
                output.append(operators.pop())
            else:
                break
        operators.append(op)
        previous = "operator"
    while operators:
        op = operators.pop()
        if op == "(":
            raise ReferenceError("parenthesis")
        output.append(op)
    return output


def parse_ast(text: str) -> tuple[Any, ...]:
    stack: list[tuple[Any, ...]] = []
    for token in to_postfix(text):
        if token in {"!", "NEG"}:
            if not stack:
                raise ReferenceError("stack")
            stack.append((token, stack.pop()))
        elif token in _PRECEDENCE:
            if len(stack) < 2:
                raise ReferenceError("stack")
            right = stack.pop()
            left = stack.pop()
            stack.append((token, left, right))
        elif re.fullmatch(r"0[xX][0-9A-Fa-f]+|[0-9]+", token):
            stack.append(("const", int(token, 0)))
        elif token in {"true", "false"}:
            stack.append(("bool", token == "true"))
        else:
            stack.append(("var", token))
    if len(stack) != 1:
        raise ReferenceError("stack-final")
    return stack[0]


def _div(a: int, b: int) -> int:
    if b == 0:
        raise ReferenceError("division-by-zero")
    magnitude = abs(a) // abs(b)
    result = -magnitude if (a < 0) != (b < 0) else magnitude
    if not INT64_MIN <= result <= INT64_MAX:
        raise ReferenceError("range")
    return result


def _eval(node: tuple[Any, ...], assignment: dict[str, int]) -> int | bool:
    op = node[0]
    if op == "const":
        return int(node[1])
    if op == "bool":
        return bool(node[1])
    if op == "var":
        if node[1] not in assignment:
            raise ReferenceError(f"variable:{node[1]}")
        return int(assignment[node[1]])
    if op == "!":
        return not bool(_eval(node[1], assignment))
    if op == "NEG":
        value = _eval(node[1], assignment)
        if type(value) is bool:
            raise ReferenceError("sort")
        return -int(value)
    if op == "&&":
        left = bool(_eval(node[1], assignment))
        return left and bool(_eval(node[2], assignment))
    if op == "||":
        left = bool(_eval(node[1], assignment))
        return left or bool(_eval(node[2], assignment))
    left = _eval(node[1], assignment)
    right = _eval(node[2], assignment)
    if type(left) is bool or type(right) is bool:
        raise ReferenceError("sort")
    a, b = int(left), int(right)
    if op == "==": return a == b
    if op == "!=": return a != b
    if op == "<": return a < b
    if op == "<=": return a <= b
    if op == ">": return a > b
    if op == ">=": return a >= b
    if op == "/": return _div(a, b)
    raise ReferenceError(f"op:{op}")


def evaluate(text: str, assignment: dict[str, int]) -> int | bool:
    return _eval(parse_ast(text), assignment)
