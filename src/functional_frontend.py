"""Lower a bounded, pure single-return source profile to the existing finite IR.

This is an authored Python/helper language, not a C/C++ or public-patch frontend.
Unsupported syntax is rejected, never approximated by a constant or a no-fault
result. No source is executed by this module.
"""
from __future__ import annotations

import ast
import copy

import checker

HELPERS = {
    "wrap_add": "add", "wrap_sub": "sub", "wrap_mul": "mul",
    "checked_add": "uadd", "checked_mul": "umul", "bounded_index": "index",
}
COMPARISONS = {ast.Lt: "lt", ast.LtE: "le", ast.Eq: "eq"}
MAX_SOURCE_BYTES = 4096


class Unsupported(ValueError):
    """Input is outside the declared functional source profile."""


def lower(source: str, width: int):
    if type(source) is not str or not source.isascii() or len(source) > MAX_SOURCE_BYTES:
        raise Unsupported("source-bytes")
    if type(width) is not int or not 1 <= width <= checker.MAX_WIDTH:
        raise Unsupported("width")
    try:
        module = ast.parse(source, mode="exec")
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise Unsupported("source-syntax") from exc
    if sum(1 for _ in ast.walk(module)) > 256:
        raise Unsupported("source-nodes")
    if len(module.body) != 1 or type(module.body[0]) is not ast.FunctionDef:
        raise Unsupported("single-function")
    function = module.body[0]
    args = function.args
    if (function.name != "patch" or function.decorator_list or function.returns
            or getattr(function, "type_params", []) or function.type_comment
            or args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs
            or args.defaults or args.kw_defaults or not 1 <= len(args.args) <= 2
            or any(a.annotation or a.type_comment for a in args.args)
            or len(function.body) != 1 or type(function.body[0]) is not ast.Return):
        raise Unsupported("function-profile")
    names = [a.arg for a in args.args]
    if len(set(names)) != len(names) or any(n in HELPERS or n == "patch" for n in names):
        raise Unsupported("parameter-binding")
    count = 0

    def visit(node, depth=0):
        nonlocal count
        count += 1
        if count > checker.MAX_NODES or depth > checker.MAX_DEPTH:
            raise Unsupported("expression-limit")
        if type(node) is ast.Constant and type(node.value) is int:
            if not 0 <= node.value < (1 << width):
                raise Unsupported("literal-range")
            return ["c", node.value]
        if type(node) is ast.Name and node.id in names:
            return ["v", names.index(node.id)]
        if (type(node) is ast.Call and type(node.func) is ast.Name
                and node.func.id in HELPERS and not node.keywords and len(node.args) == 2):
            return [HELPERS[node.func.id], *(visit(a, depth + 1) for a in node.args)]
        if (type(node) is ast.Compare and len(node.ops) == 1
                and type(node.ops[0]) in COMPARISONS):
            return [COMPARISONS[type(node.ops[0])], visit(node.left, depth + 1),
                    visit(node.comparators[0], depth + 1)]
        if type(node) is ast.IfExp:
            return ["if", visit(node.test, depth + 1), visit(node.body, depth + 1),
                    visit(node.orelse, depth + 1)]
        raise Unsupported("expression-profile")

    expression = visit(function.body[0].value)
    # Reuse the exact finite type rules, including Boolean guards and u roots.
    # A small dummy second root avoids counting the same expression twice here;
    # pair-level validation below enforces the actual combined 96-node limit.
    try:
        checker.validate_case({"id": "Source", "width": width,
                               "domain": [[0, (1 << width) - 1] for _ in names],
                               "before": expression, "after": ["c", 0]})
    except checker.Invalid as exc:
        raise Unsupported(str(exc)) from exc
    return names, expression


def translate_pair(ident: str, width: int, domain: list, before: str, after: str):
    names0, old = lower(before, width)
    names1, new = lower(after, width)
    if names0 != names1:
        raise Unsupported("same-ordered-parameters-required")
    case = {"id": ident, "width": width, "domain": copy.deepcopy(domain),
            "before": old, "after": new}
    try:
        checker.validate_case(case)
    except checker.Invalid as exc:
        raise Unsupported(str(exc)) from exc
    if len(names0) != len(domain):
        raise Unsupported("source-domain-arity")
    return case


def check_source_witness(ident, width, domain, before, after, certificate, budget):
    """Reconstruct the expected IR from separate source inputs before replay.

    Acceptance is conditional on this frontend's preservation argument, helper
    meanings and runtime, not an authenticated repository or a security label.
    """
    expected = translate_pair(ident, width, domain, before, after)
    return checker.check(expected, certificate, budget)
