# Bounded functional source to finite IR

## Domain and accepted syntax

This profile is an authored pure Python/helper language. It does not translate
TensorFlow, C/C++, repository patches, memory accesses, or machine undefined
behavior. A source is ASCII, at most 4,096 bytes and 256 Python AST nodes, and has
exactly one undecorated function `patch` with one or two distinct ordinary
parameters and exactly one `return E`. Defaults, annotations, type parameters,
positional-only/keyword-only/variadic parameters, other statements and other
functions are rejected. Parameters cannot shadow `patch` or a helper name.

An expression is an unsigned integer literal, a parameter, a two-argument call
to one of the six helpers, a single `<`, `<=` or `==` comparison, or `A if G else
B`. Bare Python `+`, `-` and `*` are rejected: silently assigning them modular
semantics would not preserve ordinary Python arithmetic. Comparisons require
unsigned operands, conditionals require Boolean guards and equal-sort branches,
and the returned expression must be unsigned. Boolean literals, integer
truthiness and chained comparisons are not admitted. The existing checker
enforces the finite types, widths 1..5, combined 96-node/depth-12 limits, domain
arity, inclusive intervals and at most 1,024 inputs. Both source versions must
have the same ordered parameter list and the domain must have that arity.

At width w let M=2^w. Source inputs and unsigned literals lie in [0,M-1].
`wrap_add`, `wrap_sub` and `wrap_mul` calculate their mathematical result modulo
M; `checked_add` and `checked_mul` return that result when it is less than M,
otherwise raise the designated `add-overflow` or `mul-overflow` ModelFault.
`bounded_index(a,b)` returns a when a<b and raises `index-outside` otherwise. It
does not index a container. These are explicit library meanings, not claims
about the host's integer width or memory safety. Calls evaluate arguments left
to right; a ModelFault aborts the remaining expression. Comparisons operate on
defined unsigned values. A conditional evaluates its guard first and only the
selected branch. `functional_reference.py` implements these helpers separately
and executes only reviewed authored sources through CPython compilation.

## Lowering and preservation argument

Let L map literal n to `[c,n]`, parameter j to `[v,j]`, helper calls to the
corresponding finite operator applied to their lowered arguments, comparisons
to `lt`, `le`, `eq`, and a conditional to `[if,L(G),L(A),L(B)]`. The parameter
mapping alpha is the identity vector in the declared order; no variables,
preconditions or values are inferred from a source hunk.

For every admitted expression E and admitted input x, its source outcome under
the stated helper semantics equals the finite denotation of L(E) at alpha(x),
including exact fault codes. This is a written structural induction, not a
mechanized compiler proof. Literals and parameters preserve their values by
definition. In a helper call, the induction hypothesis supplies the outcome of
the left argument. A left fault suppresses the right argument and propagates
the same code in both languages. Otherwise the hypothesis applies to the right
argument; a right fault also propagates identically. With both arguments defined,
the helper arithmetic and bound rule is exactly the corresponding finite rule.
Comparisons use the same operand-order/fault reasoning and return the same
Boolean. In a conditional, the hypothesis gives the same guard outcome; a fault
propagates in both. Otherwise Boolean typing gives the same selected branch,
whose outcome agrees by induction. Both source and lowered trees are finite,
and every evaluation step recurses into a proper child, so evaluation terminates.
The root's unsigned type gives an unsigned value or one designated fault.

Consequently the source and IR have exactly the same old-fault/new-defined input
set for an admitted pair. `check_source_witness` reconstructs the expected IR
from separately supplied source strings, width and domain before invoking the
existing structural certificate checker. Its acceptance and the preservation
argument compose to establish the pointwise source/helper relation. A source
pair that lowers to a different expected IR cannot reuse the previous pair's
certificate. Different source texts with identical lowerings share the same
finite statement: this binding is to reconstructed semantics, not raw bytes.
This remains conditional on the trusted AST parser, frontend, helper meanings,
checker and runtime, and on non-mutation during checking. The wrapper does not
authenticate source provenance or prove a security label. IR traces remain IR
node traces; they are not asserted to be CPython execution traces.

## Diagnostic and fair reference

For all inputs in a supplied finite rectangle the diagnostic partitions outcomes
into repair (fault/unsigned), new-fault (unsigned/fault), defined-equal,
defined-changed and both-fault. A defined output difference is not automatically
a bug: its intended behavior has not been specified. In particular, calling
every both-defined input "preserved" would be incorrect. Both-fault does not
require equal fault codes. No universal patch-correctness claim follows from a
positive repair witness.

The reference uses direct Python execution and independently coded helpers; it
does not import L, producer or checker. It shares the authored specification,
CPython AST parser and runtime, not independent authorship. Its same-information
simple baseline enumerates exactly the same inputs and directly collects repair,
new-fault and changed-defined sets without calling the IR partition. The sets
tie: no algorithmic, accuracy, ranking or speed advantage is claimed. In contrast
to simple execution, the bridge produces structurally bound finite certificates
with independently replayed IR traces. That is an interface property, not a
new semantic-differencing result.

The recorded run contains 14 source pairs and 414 pair-input assignments: 106
repairs, 38 new faults, 209 equal-defined outputs, 44 changed-defined outputs and
17 both-faults. Eight pairs have accepted source-bound repair witnesses. All
source outcomes agree with recursive IR evaluation and iterative replay; their
IR traces agree, and the simple baseline sets are identical. F06 has one repair,
one new fault and six changed-defined outputs; F03's commutation preserves all
64 outputs; F09 changes eight defined outputs without any repair witness. A
deliberately wrong `<` to `<=` lowering differs on exactly eight equality inputs
and is caught by the reference regression. This is an authored negative control,
not an observed external compiler failure. The original 25-case finite counts
and the stored public ranking's zero top-20 gain remain unchanged.

## Nearest work and remaining scope

SymDiff's source interface explicitly makes soundness depend on the translator's
faithfulness (Lahiri et al., CAV 2012, Sections 2--3). Alive2 checks LLVM function
refinement, including LLVM-specific undefined behavior (Lopes et al., PLDI 2021,
Section 1). This profile instead preserves a small deterministic pure/helper
language and exhaustively enumerates very small finite domains. It is neither
a competing implementation nor a new general translation-validation technique.
No source-tree correspondence obligation for the public excerpts is discharged.

Primary material read for this comparison on 2026-10-12:

- https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/paper-44.pdf
  (targeted full-text Sections 1--3; not an independent reproduction).
- https://users.cs.utah.edu/~regehr/alive2-pldi21.pdf
  (targeted full-text Section 1; no experiment or vulnerability execution).
- https://docs.python.org/3.12/reference/expressions.html#conditional-expressions
  and #evaluation-order (Sections 6.13 and 6.16).

No other bibliography entry is upgraded to full entailment verification here.
