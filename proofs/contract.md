# Certificate contract and written proofs

These are paper-and-pencil arguments for the explicitly defined finite expression
model. They are not proof-assistant certificates, a verified Python interpreter,
a C/C++ semantics proof, or a proof that a patch has a security label.

## 1. Model

Let w be an integer in [1,5], M=2^w, and U={0,...,M-1}. A case consists of an
identifier, w, one or two inclusive interval domains D_i contained in U, and
before/after expressions e0,e1. D is the Cartesian product of those intervals.
Every expression is a finite tree. There are at most 96 nodes across both trees
and depth at most 12, where a root has depth zero. The domain has at most 1,024
assignments. Booleans are not unsigned integers.

Leaves are a variable or a constant in U. Modular addition, subtraction and
multiplication return their result modulo M. Checked addition or multiplication
return an unsigned value when the mathematical result is less than M and a
specific fault code otherwise. The abstract index operator on (a,b) returns a
when a<b and `index-outside` otherwise. This operator never accesses memory.
Unsigned comparisons return a Boolean. A conditional evaluates a Boolean guard,
then precisely one branch. Both branches have the same static sort. Roots have
unsigned sort. Every operator propagates a fault from an evaluated operand;
binary operands are evaluated left to right, so a fault on the left suppresses
right evaluation. A fault in a conditional guard suppresses both branches.

An outcome is (u,a), (b,t), or (fault,f). The trace consists of postorder rows
(position,tag,value) for exactly the evaluated nodes. The root position is the
empty string. For a binary operator its left and right children append 0 and 1.
For a conditional its guard, then and else children append 0, 1 and 2. A parent
that propagates a fault emits its own row as well. An unchosen branch emits no
rows. Positions denote occurrences, not Python object identities.

## 2. Denotation and deterministic traces

Define E(e,x,p) by the recursive rules above, returning an outcome and trace.
Every child has strictly fewer nodes than its parent, and a conditional selects
only one of its two branch children. Thus evaluation terminates. Leaves have a
unique value under x. Inductively, each evaluated child has a unique outcome and
trace. Its tag uniquely determines whether evaluation stops, proceeds to the
right child, or chooses one conditional branch. Every arithmetic operator and
comparison is a total deterministic function on its admitted unsigned operands,
with fault codes explicitly specified. Concatenating the resulting child traces
and one parent row therefore gives a unique outcome and trace for every valid
expression and assignment. No arithmetic rule uses machine signed overflow.

## 3. Iterative replay invariant

The checker uses four continuation phases. A phase-0 frame denotes an unevaluated
expression at a fixed position. A phase-1 frame waits for its first child. A
phase-2 frame saves a defined unsigned first-child outcome while waiting for the
second. A phase-3 frame waits for the selected branch of a conditional.

Invariant: relative to any pre-existing stack and trace prefix, evaluating a
subtree consumes its scheduled work, leaves precisely its denotational outcome
on the value stack, appends exactly its denotational postorder trace, and does
not change earlier stack values or trace rows.

Proof is by structural induction, equivalently by the scheduled continuation
transitions. A leaf emits its value and row immediately. For a non-leaf, phase 0
pushes its first-child work above a waiting frame. The induction hypothesis gives
that child's exact outcome and trace. If this is a fault, phase 1 emits the same
fault at the parent and schedules no other child, which is exactly the recursive
rule. For a conditional with a defined guard, static typing guarantees a Boolean;
phase 1 selects the prescribed branch and phase 3 propagates its result after the
induction hypothesis applies. For an ordinary binary node, phase 1 saves the first
unsigned value and evaluates the right child. A right fault is propagated by
phase 2. Otherwise phase 2 computes the operator, using the two defined operands,
and emits the parent row. Each case preserves the prefix and leaves one result.
At the root, the initial prefix and value stack are empty, giving exactly one
result and the complete denotational trace.

The arithmetic implementations intentionally differ. For 0<=a,b<M, the checked
addition test a>M-1-b is equivalent to a+b>=M. For b>0, a>floor((M-1)/b) is
equivalent to ab>=M; for b=0 multiplication cannot overflow. Masking by M-1 is
equal to reduction modulo M for all mathematical integers, including negative
subtraction results, because M is a power of two. These identities establish
agreement of the checker's arithmetic rules with the mathematical rules; test
agreement alone is not the argument.

## 4. Acceptance theorem

Assumptions: the separately supplied expected case C is the trusted intended IR;
it is not selected from the certificate and is not mutated during checking.
The checker implementation, its execution substrate and the rules above are
trusted. The certificate producer is untrusted. File-level input uses the bounded
UTF-8 JSON reader and the structured values then pass the case/certificate gates.

Theorem: if check(C,W) returns accepted-bounded-witness, there exists x in C.D
such that E(C.before,x) has fault sort and E(C.after,x) has unsigned sort. The
reported outcomes and complete evaluated traces are the actual denotational
outcomes and traces for this same x and this same C.

Proof. Acceptance is reached only after both cases satisfy the exact structural
schema and strict typed equality binds the certificate's case to C. Input arity,
integer type and interval checks give x in D. Replay is performed on C's two
expressions, not on an alternative expression supplied only by the producer.
The invariant in Section 3 gives their exact outcomes and traces. Strict typed
comparison then checks all reported outcomes and rows against those recomputed
objects. The final predicate requires old fault and new unsigned. Those checks
establish every conjunct. A missing, malformed, unrelated, or resource-abstaining
certificate cannot reach this return branch. In particular, Python's equality
between Boolean false and integer zero is not used for certificate comparison.

The copied case is a transparent structural binding, not a cryptographic
commitment. It authenticates neither a repository revision nor a source-to-IR
translation. An attacker controlling the expected case controls the statement
being checked; acceptance then says nothing about another intended case.

## 5. Relative completeness and cost

For a valid case with n total before/after nodes and |D|=s, a single paired
evaluation visits at most n nodes and stores at most n trace rows. The exhaustive
producer considers assignments in lexicographic order. If it completes with
sufficient fuel and any x has old-fault/new-unsigned outcomes, it reaches the
first such x, constructs the correct evidence, and the checker accepts with
sufficient additional fuel. If no such x exists, full enumeration returns none.
Neither a timeout nor an exhausted fuel counter proves absence. The checker does
not accept a bare producer assertion that no witness exists.

Paired enumeration has at most sn evaluator-node visits; a subsequent positive
replay has at most n. This excludes Python interpreter overhead and the
separately bounded structural/JSON pass. Input bytes are at most 131,072, JSON
nesting at most 32, AST depth at most 12, and AST occurrences at most 96. Each
integer encoding is at most five characters. The whole scientific runner adds
process CPU, wall and address-space limits. These are finite-model bounds,
not cost predictions for real C/C++ slices.

## 6. A repair witness does not prove absence of regression

For every w>=1, let e0(x)=checked_add(x,1), and let
 e1(x)=checked_add((x-1) mod M,1).
At x=M-1, e0 faults and e1 returns M-1. At x=0, e0 returns 1 (M>=2) and e1
faults. At each 1<=x<=M-2, both are defined. Thus one accepted certificate and
a regression coexist. With a second unused variable y in U, repair and regression
sets each have M elements, and both-defined outcomes have M(M-2) elements. For
w=3 these counts are 8, 8 and 48. Their interpretation is pointwise; no security
label is assigned to this owned example. Exhaustiveness of this example does not
make the chosen examples representative of software workloads.

## 7. Label non-entailment and ranking identity

For two rankings of one N-element cohort, let A and B be their top-k sets and
P_A,P_B their binary-label precisions. Set d=|A\B|=|B\A|. Cancellation gives
 P_A-P_B = (sum_{i in A\B} y_i - sum_{i in B\A} y_i)/k.
The common intersection contributes nothing. Hence |P_A-P_B|<=d/k. If only
the total number S of positive labels is fixed, the sharp symmetric bound is
 min(d,S,N-S)/k.

For sharpness of the upper bound: if S<d, place all S positives in A\B. If
d<=S<=N-d, fill A\B with positives and distribute the remaining S-d in the
N-2d neutral positions. If S>N-d, make all N-S negatives lie in B\A. These
constructions achieve S, d and N-S excess positives respectively. Interchanging
A and B achieves the negative bound. The case d=0 is immediate. No random-label
model is needed for this deterministic identity.

Without empirical assumptions linking labels to the observed IR evidence, a
class containing both of these labelings cannot support a positive universal
precision guarantee for either ranking. This is a conditional non-entailment
statement, not a claim that real advisory labels are arbitrary. At k=20, fewer
than two changed top-set members rules out a gain of at least 0.10; two changed
members make such a gain possible but do not establish it. These are elementary
accounting facts, not a claimed new ranking theorem.
