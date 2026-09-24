"""Standalone structural and semantic replay checker.

No imports from producer, fixtures, or a C frontend. This is implementation
separation, not independent human authorship, verification, or blind review.
"""
from __future__ import annotations
import json
from pathlib import Path

MAX_BYTES = 131_072
MAX_JSON_DEPTH = 32
MAX_NODES = 96
MAX_DEPTH = 12
MAX_WIDTH = 5
MAX_STATES = 1_024
CASE_FIELDS = {'id', 'width', 'domain', 'before', 'after'}
CERT_FIELDS = {'case', 'input', 'before', 'after', 'before_trace', 'after_trace'}


class Invalid(ValueError):
    pass


def _fail(condition: bool, reason: str):
    if not condition:
        raise Invalid(reason)


def read_json(path: str | Path):
    """Bound bytes before decoding; reject duplicate keys and noninteger numbers."""
    with open(path, 'rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    _fail(len(raw) <= MAX_BYTES, 'byte-limit')
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise Invalid('invalid-utf8') from exc
    # Enforce nesting before the JSON decoder allocates nested containers.
    # Decoder recursion limits differ across Python implementations/releases.
    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 92:  # backslash
                escaped = True
            elif byte == 34:  # double quote
                in_string = False
        elif byte == 34:
            in_string = True
        elif byte in (91, 123):  # [ {
            depth += 1
            _fail(depth <= MAX_JSON_DEPTH, 'json-depth-limit')
        elif byte in (93, 125):  # ] }
            depth -= 1
            _fail(depth >= 0, 'invalid-json-nesting')
    # Matching delimiter types and all lexical rules remain json.loads' job.
    _fail(depth == 0 and not in_string, 'invalid-json-nesting')

    def pairs(items):
        out = {}
        for k, v in items:
            _fail(k not in out, 'duplicate-key')
            out[k] = v
        return out

    def number(s):
        _fail(len(s) <= 5, 'integer-encoding-limit')
        return int(s)

    def reject(_):
        raise Invalid('noninteger-number')

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_int=number,
                          parse_float=reject, parse_constant=reject)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise Invalid('invalid-json') from exc


def validate_case(case):
    _fail(type(case) is dict and set(case) == CASE_FIELDS, 'case-fields')
    _fail(type(case['id']) is str and 1 <= len(case['id']) <= 32
          and case['id'].isascii() and all(c.isalnum() or c == '-' for c in case['id']), 'case-id')
    width = case['width']
    _fail(type(width) is int and 1 <= width <= MAX_WIDTH, 'width')
    mod = 1 << width
    domain = case['domain']
    _fail(type(domain) is list and 1 <= len(domain) <= 2, 'domain-arity')
    states = 1
    for bounds in domain:
        _fail(type(bounds) is list and len(bounds) == 2
              and all(type(i) is int for i in bounds), 'domain-integers')
        lo, hi = bounds
        _fail(0 <= lo <= hi < mod, 'domain-bounds')
        states *= hi - lo + 1
    _fail(states <= MAX_STATES, 'state-limit')
    nodes = 0

    def sort(e, depth):
        nonlocal nodes
        nodes += 1
        _fail(nodes <= MAX_NODES and depth <= MAX_DEPTH, 'expression-limit')
        _fail(type(e) is list and len(e) >= 2 and type(e[0]) is str, 'node-shape')
        op = e[0]
        if op in ('v', 'c'):
            _fail(len(e) == 2 and type(e[1]) is int, 'leaf-shape')
            _fail(0 <= e[1] < (len(domain) if op == 'v' else mod), 'leaf-range')
            return 'u'
        if op == 'if':
            _fail(len(e) == 4, 'branch-arity')
            _fail(sort(e[1], depth + 1) == 'b', 'branch-guard-type')
            a, b = sort(e[2], depth + 1), sort(e[3], depth + 1)
            _fail(a == b, 'branch-result-type')
            return a
        _fail(op in ('add', 'sub', 'mul', 'uadd', 'umul', 'index', 'lt', 'le', 'eq')
              and len(e) == 3, 'operator')
        _fail(sort(e[1], depth + 1) == 'u' and sort(e[2], depth + 1) == 'u', 'operand-type')
        return 'b' if op in ('lt', 'le', 'eq') else 'u'

    _fail(sort(case['before'], 0) == 'u' and sort(case['after'], 0) == 'u', 'root-type')
    return states


def replay(root, assignment, width, budget):
    """Iterative continuation machine, separate from producer's recursive evaluator."""
    stack = [(root, '', 0, None)]
    value_stack = []
    trace = []
    high = (1 << width) - 1

    def emit(where, value):
        trace.append([where, value[0], value[1]])
        value_stack.append(value)

    while stack:
        e, where, phase, saved = stack.pop()
        op = e[0]
        if phase == 0:
            budget.tick()
            if op == 'c': emit(where, ('u', e[1])); continue
            if op == 'v': emit(where, ('u', assignment[e[1]])); continue
            stack.append((e, where, 1, None))
            stack.append((e[1], where + '0', 0, None))
        elif phase == 1:
            left = value_stack.pop()
            if left[0] == 'fault': emit(where, left); continue
            if op == 'if':
                index = 2 if left[1] else 3
                stack.append((e, where, 3, None))
                stack.append((e[index], where + str(index - 1), 0, None))
            else:
                stack.append((e, where, 2, left))
                stack.append((e[2], where + '1', 0, None))
        elif phase == 3:
            emit(where, value_stack.pop())
        else:
            right = value_stack.pop()
            if right[0] == 'fault': emit(where, right); continue
            a, b = saved[1], right[1]
            if op in ('lt', 'le', 'eq'):
                val = (a < b) if op == 'lt' else ((a <= b) if op == 'le' else (a == b))
                result = ('b', val)
            elif op == 'index':
                result = ('fault', 'index-outside') if a >= b else ('u', a)
            elif op == 'uadd':
                result = ('fault', 'add-overflow') if a > high - b else ('u', a + b)
            elif op == 'umul':
                # Division-side overflow test differs from the generator's product test.
                result = ('fault', 'mul-overflow') if b != 0 and a > high // b else ('u', a * b)
            else:
                raw = a + b if op == 'add' else (a - b if op == 'sub' else a * b)
                result = ('u', raw & high)
            emit(where, result)
    _fail(len(value_stack) == 1, 'internal-stack')
    return list(value_stack[0]), trace


def _typed_equal(a, b):
    """Prevent Python's True == 1 equivalence in outcomes and traces."""
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_typed_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_typed_equal(a[k], b[k]) for k in a)
    return a == b


def check(expected_case, certificate, budget):
    """Return (accept, reason); malformed or unbound inputs never produce acceptance.

    The expected_case is a separately supplied trusted object. Supplying it from
    certificate['case'] defeats the binding contract and is not supported usage.
    """
    try:
        validate_case(expected_case)
        _fail(type(certificate) is dict and set(certificate) == CERT_FIELDS, 'certificate-fields')
        validate_case(certificate['case'])
        _fail(_typed_equal(expected_case, certificate['case']), 'case-binding')
        vals = certificate['input']
        _fail(type(vals) is list and len(vals) == len(expected_case['domain'])
              and all(type(x) is int for x in vals), 'input-type')
        _fail(all(lo <= x <= hi for x, (lo, hi) in zip(vals, expected_case['domain'])), 'input-domain')
        # Bound the mutable evidence before comparing it recursively.
        for field in ('before_trace', 'after_trace'):
            tr = certificate[field]
            _fail(type(tr) is list and len(tr) <= MAX_NODES, 'trace-limit')
            for row in tr:
                _fail(type(row) is list and len(row) == 3
                      and type(row[0]) is str and len(row[0]) <= MAX_DEPTH
                      and type(row[1]) is str and row[1] in ('u', 'b', 'fault')
                      and type(row[2]) in (int, bool, str), 'trace-shape')
                _fail(type(row[2]) is not str or len(row[2]) <= 20, 'trace-scalar-limit')
        for field in ('before', 'after'):
            val = certificate[field]
            _fail(type(val) is list and len(val) == 2 and type(val[0]) is str
                  and type(val[1]) in (int, bool, str), 'outcome-shape')
            _fail(type(val[1]) is not str or len(val[1]) <= 20, 'outcome-scalar-limit')
        old, ot = replay(expected_case['before'], vals, expected_case['width'], budget)
        new, nt = replay(expected_case['after'], vals, expected_case['width'], budget)
        _fail(_typed_equal(old, certificate['before']) and _typed_equal(new, certificate['after']), 'outcome-mismatch')
        _fail(_typed_equal(ot, certificate['before_trace']) and _typed_equal(nt, certificate['after_trace']), 'trace-mismatch')
        _fail(old[0] == 'fault' and new[0] == 'u', 'not-improvement')
        return True, 'accepted-bounded-witness'
    except (Invalid, RecursionError, TypeError, KeyError, IndexError, OverflowError):
        return False, 'rejected'
    except RuntimeError:
        return False, 'resource-abstention'
