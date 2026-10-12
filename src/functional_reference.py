"""Direct CPython reference for reviewed authored functional fixtures only.

No imports from the lowering, producer or checker. Native function calls and
conditionals determine evaluation order. The explicit helper library supplies
the bounded arithmetic meanings. The allowlist is a profile gate, not a general
Python sandbox. Never use this runner on third-party or unreviewed programs.
"""
from __future__ import annotations

import ast


class ModelFault(Exception):
    pass


def build_reference(source: str, width: int):
    if type(width) is not int or not 1 <= width <= 5:
        raise ValueError("width")
    if type(source) is not str or not source.isascii() or len(source) > 4096:
        raise ValueError("source-bytes")
    tree = ast.parse(source)
    if len(tree.body) != 1 or type(tree.body[0]) is not ast.FunctionDef:
        raise ValueError("single-function")
    function = tree.body[0]
    args = function.args
    if (function.name != "patch" or function.decorator_list or function.returns
            or getattr(function, "type_params", []) or function.type_comment
            or args.defaults or args.posonlyargs or args.vararg or args.kwarg
            or args.kwonlyargs or args.kw_defaults or not 1 <= len(args.args) <= 2
            or any(a.annotation or a.type_comment for a in args.args)
            or len(function.body) != 1 or type(function.body[0]) is not ast.Return):
        raise ValueError("function-profile")
    high = 2**width - 1

    def checked_add(a, b):
        value = a + b
        if value > high:
            raise ModelFault("add-overflow")
        return value

    def checked_mul(a, b):
        value = a * b
        if value > high:
            raise ModelFault("mul-overflow")
        return value

    def bounded_index(a, b):
        if a >= b:
            raise ModelFault("index-outside")
        return a

    helpers = {
        "checked_add": checked_add, "checked_mul": checked_mul,
        "bounded_index": bounded_index,
        "wrap_add": lambda a, b: (a + b) % (high + 1),
        "wrap_sub": lambda a, b: (a - b) % (high + 1),
        "wrap_mul": lambda a, b: (a * b) % (high + 1),
    }
    names = [a.arg for a in args.args]
    if len(set(names)) != len(names) or any(n in helpers or n == "patch" for n in names):
        raise ValueError("parameter-binding")
    allowed = {ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
               ast.Name, ast.Load, ast.Constant, ast.Call, ast.Compare,
               ast.Lt, ast.LtE, ast.Eq, ast.IfExp}
    nodes = list(ast.walk(tree))
    if len(nodes) > 256:
        raise ValueError("source-nodes")
    for node in nodes:
        if type(node) not in allowed:
            raise ValueError("source-profile")
        if type(node) is ast.Name and node.id not in names and node.id not in helpers:
            raise ValueError("unknown-name")
        if type(node) is ast.Constant and (type(node.value) is not int or not 0 <= node.value <= high):
            raise ValueError("literal")
        if type(node) is ast.Call and (type(node.func) is not ast.Name
                or node.func.id not in helpers or len(node.args) != 2 or node.keywords):
            raise ValueError("call-profile")
        if type(node) is ast.Compare and len(node.ops) != 1:
            raise ValueError("comparison-profile")
    namespace = {"__builtins__": {}, **helpers}
    exec(compile(tree, "<owned-functional-fixture>", "exec"), namespace)
    patch = namespace["patch"]

    def execute(values):
        if (type(values) is not list or len(values) != len(names)
                or any(type(v) is not int or not 0 <= v <= high for v in values)):
            raise ValueError("assignment")
        try:
            result = patch(*values)
        except ModelFault as exc:
            return ["fault", str(exc)]
        if type(result) is not int or not 0 <= result <= high:
            raise ValueError("unsigned-root")
        return ["u", result]

    return execute
