"""Record-free direct relation on the same validated extracted case.

No producer, evidence packet, replay, ranking, label or native-program imports.
This control shares the extractor/profile and signed-width assumptions. It is
not an independently validated extraction or a public old-fault analysis.
"""
from source_frontend_reference import evaluate, parse_ast


def _names(tree):
    if tree[0] == "var":
        return {tree[1]}
    if tree[0] in ("const", "bool"):
        return set()
    return set().union(*(_names(child) for child in tree[1:]))


def direct_relation(case):
    assignment = case["assignment"]
    if type(assignment) is not dict or any(type(v) is not int for v in assignment.values()):
        raise ValueError("exact-integer-assignment")
    if case["kind"] == "source-difference":
        if assignment != {"concat_dim": -(2 ** 31)}:
            raise ValueError("range-assignment")
        value = abs(assignment["concat_dim"])
        return not (-(2 ** 31) <= value < 2 ** 31) and -(2 ** 63) <= value < 2 ** 63
    if case["kind"] != "guard-trigger":
        raise ValueError("relation-kind")
    if type(case["trigger_value"]) is not bool or case["frontend_rule"] not in ("require", "reject-if"):
        raise ValueError("guard-trigger")
    operator = " && " if case["frontend_rule"] == "require" else " || "
    expression = operator.join("(" + token + ")" for token in case["source_tokens"])
    context = case["context_tokens"]
    expected_names = _names(parse_ast(expression))
    for token in context:
        expected_names.update(_names(parse_ast(token)))
    if set(assignment) != expected_names:
        raise ValueError("assignment-variable-set")
    for token in context:
        value = evaluate(token, assignment)
        if type(value) is not bool:
            raise ValueError("context-sort")
        if not value:
            return False
    value = evaluate(expression, assignment)
    if type(value) is not bool:
        raise ValueError("guard-sort")
    return value is case["trigger_value"]
