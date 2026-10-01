# Restricted public source-evidence contract and validation

This note specifies the public-source path used for the retained 32-file
microcohort.  It is separate from the finite-IR old-fault/new-defined certificate
in `proofs/contract.md`.

## 1. Input and extraction

Each candidate contains an immutable commit, original commit message, timestamp,
full file path, and minimal real unified-diff context copied from that file's
upstream patch.  Human file annotations are stored separately and are excluded
from extraction and scoring.

The extractor considers added source lines and supports:

1. a braced rejection guard `if (bad_predicate) { return errors::...; }`;
2. an admission guard `OP_REQUIRES(ctx, good_predicate, ...)`; and
3. one exact `int` to `int64` widening pattern for W01.

An added `if` used only to initialize helper state is not treated as a rejection
guard.  Malformed or unsupported source becomes a typed abstention with an
`extract`, `parse`, or `evaluate` stage.  Declared frontend failures are caught;
unexpected system exceptions propagate rather than being mislabeled as
unsupported syntax.

Extraction has one implementation, so the project does not claim independent
extractor agreement.  Its output is deterministically re-derived from the
candidate packet and bound by hashes and mutation tests.

## 2. Guard and source-difference records

A guard record binds:

- candidate and case identity;
- exact source and context tokens;
- one strictly typed integer assignment;
- replayed context results and traces;
- replayed guard result and trace; and
- a typed Boolean stating that the declared trigger value was reached.

It does **not** contain an old program outcome and does not assert old fault/new
defined behavior.  W01 is a different `source-difference` record: for
`concat_dim = INT32_MIN`, the old `int` negation is represented as the declared
signed-int32-overflow fault and the widened `int64` expression yields
2147483648.  That source relation still does not inherit the finite-IR theorem.

Nested equality is exact and typed: Boolean false is not integer zero, an integer
is not an equal-valued float, and unvisited assignment fields remain integers.
Trace entries are triples `(position, tag, payload)`; the operator at a position
is recovered from the bound AST, rather than copied into an untrusted trace.

## 3. W10 precondition and short circuit

The upstream UnravelIndex hunk already contained `dims(i) != 0` before the new
positivity and overflow conditions.  W10 therefore binds that unchanged
nonzero context requirement.  Its accepted assignment uses `dim=-1`,
`prod=1`, and `limit=INT32_MAX`: the context is true and the new conjunctive
admission guard is false at the positivity check, without evaluating division.

`dim=0` is deliberately **not** an accepted record.  It is retained only as a
static validation case for the C11 oracle: the left side of `&&` is false, so
`limit / dim` must not execute.  Additional mandatory W10 samples execute a
successful division and an overflow-rejecting division.

## 4. Parsing and evaluation cross-checks

The primary parser is Pratt-based.  A separate module implements normalization,
lexing, shunting-yard conversion, AST construction, and evaluation without
importing the primary parser.

For each of nine guard cases, the runner saves 100 assignments.  Before random
sampling it preserves the source record's assignment, an opposite truth branch,
W03's 65535/65536/65537 boundary points, and W10's protected-zero,
actual-division-true, and actual-division-false cases.  A seeded sampler then
adds unique points before any deterministic repeat, avoiding a Cartesian prefix
that could consume the budget before critical branches appear.

Each assignment is compared across:

- the primary expression evaluator;
- the independent parser/evaluator;
- the recursive typed producer;
- the iterative typed replay evaluator; and
- a compiled C11 postfix-bytecode oracle.

The C oracle implements actual `&&`/`||` short circuit by skipping the encoded
right-hand segment.  The retained run covers 900 guard assignments plus one W01
widening check and observes zero mismatches.

## 5. Limits

The validation covers only the retained excerpts and declared grammar.  It does
not establish raw-diff completeness, checked source-tree correspondence, macro
expansion, name/type resolution, aliases, pointer/heap semantics, build flags,
whole-program state, general undefined behavior, or a security label.  Those
missing facts remain explicit failed readiness gates.
