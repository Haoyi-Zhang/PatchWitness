# Restricted source-frontend contract and validation

This note specifies the automatic source-to-relation boundary used only for the
retained 32-unit public microcohort.  It is a deliberately restricted diff
recognizer, not a C/C++ parser, compiler frontend, or whole-program verifier.

## 1. Accepted source forms

The frontend scans added lines in each retained patch excerpt and recognizes:

1. rejection guards of the form `if (bad_predicate)`;
2. admission guards of the form `OP_REQUIRES(ctx, good_predicate, ...)`; and
3. one declared type-widening pattern changing `const int min_rank` to
   `const int64 min_rank` in an expression containing `concat_dim`.

For guards, the grammar contains decimal or hexadecimal integer constants,
scalar identifiers, parentheses, unary `!` and unary minus on constants,
`&&`, `||`, the six comparisons, and integer division.  Seven explicit accessor
rewrites map the retained source spellings (for example,
`key_tensor->NumElements()` and `input.dims()`) to scalar variables.  No other
rewrite is permitted.  Unsupported syntax yields a typed abstention and remains
in the ranking denominator.

For `OP_REQUIRES`, all extracted predicates are conjoined and the frontend
searches a fixed, deterministic bounded domain for an assignment making the
conjunction false.  For added `if` guards, predicates are disjoined and the
frontend searches for an assignment making the disjunction true.  The result is
a finite Boolean relation and one deterministic trigger assignment.  The
widening rule creates a separate bounded relation at `concat_dim = INT32_MIN`:
the old abstract 32-bit result is `overflow`, while the widened abstract result
is `2^31`.  This is an explicit model of the retained diff pattern, not a claim
about all C++ conversion or undefined-behavior cases.

## 2. Determinism and binding

Candidate records are processed in their frozen neutral-ID order.  Within one
predicate, variables are ordered lexicographically and fixed finite domains are
enumerated lexicographically.  The first triggering assignment is retained.
The derived case document is compared byte-for-byte as a parsed JSON value with
the retained case document before prediction freezing.  Candidate, case, and
protocol hashes are embedded in the frozen prediction packet.  A later change
to a patch excerpt, source token, assignment, relation, or hash therefore causes
a fail-closed mismatch rather than silent reuse of the old result.

## 3. Independent validation

The primary implementation uses a Pratt parser.  A second module independently
implements normalization, lexing, shunting-yard conversion, AST construction,
and short-circuit evaluation; it does not import the primary parser.  For each
of the nine recognized guard predicates, the validation runner constructs 100
unique deterministic assignments and compares:

- the primary frontend evaluator;
- the independent parser/evaluator;
- the public-study producer evaluator;
- the separately written iterative replay evaluator; and
- a compiled C11 postfix-expression oracle.

The retained validation therefore contains 900 predicate assignments.  It
observes zero parser, evaluator, trace, or C11-oracle mismatches.  The widening
rule is checked as a separate exact boundary relation and mutation-tested; it is
not counted among the 900 guard-expression assignments because C signed
conversion behavior would not be a portable oracle for the abstract relation.

## 4. What the validation does not establish

Passing validation establishes deterministic extraction and finite semantic
agreement for the declared grammar on the retained excerpts.  It does not
establish macro expansion, name or type resolution, alias analysis, pointer or
heap semantics, build-flag fidelity, control/data-flow slicing, compiler
conformance, absence of undefined behavior, or equivalence to a complete
TensorFlow build.  It also does not assign a security label.  Consequently the
frontend gate can pass while the prospective utility study still fails its
candidate-frame, label-sealing, baseline, and temporal-holdout gates.
