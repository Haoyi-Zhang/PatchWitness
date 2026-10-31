"""Consume a complete record against a separately supplied helper specification.

Exit 0: record checked (and any requested policy satisfied). Exit 3: truthful
record, but requested bounded-preservation policy false. Exit 4: replay budget
exhausted; no verdict. Exit 2: invalid/unavailable input. No source execution,
repository authentication or whole-patch approval.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
import checker
from bounded_decision import Budget, validate
from functional_frontend import Unsupported


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--require-preservation', action='store_true')
    parser.add_argument('--budget', type=int, default=checker.MAX_STATES * checker.MAX_NODES)
    args = parser.parse_args(argv)
    try:
        spec = checker.read_json(args.spec)
        checker._fail(type(spec) is dict and set(spec) in (
            {'id', 'width', 'domain', 'before', 'after'},
            {'id', 'width', 'domain', 'before', 'after', 'purpose'}), 'helper-spec-fields')
        result = validate(spec, checker.read_json(args.record), Budget(args.budget))
        policy = result['bounded_refinement'] if args.require_preservation else None
        print(json.dumps(dict(record_validated=True, **result,
            requested_policy='bounded-preservation' if args.require_preservation else 'record-validity-only',
            policy_satisfied=policy,
            scope='declared helper semantics/domain; not authenticated source or whole-patch approval'),
            sort_keys=True))
        return 3 if policy is False else 0
    except RuntimeError as exc:
        if str(exc) != 'bounded-replay-budget':
            raise
        print(json.dumps(dict(record_validated=False, status='resource-abstention',
                              bounded_refinement=None, policy_satisfied=None)))
        return 4
    except (checker.Invalid, Unsupported, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps(dict(record_validated=False, status='invalid-or-unavailable',
                              reason=str(exc), bounded_refinement=None, policy_satisfied=None)))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
