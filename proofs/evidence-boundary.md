# Evidence boundary

The package contains two non-interchangeable contracts.

## Finite IR

For a separately supplied bounded before/after IR case, an accepted finite
certificate proves one same-input old-fault/new-defined transition relative to
that IR and finite semantics.  It does not prove whole-patch correctness or
absence of regression.  The exact mixed family shows an accepted repair witness
coexisting with regression inputs.

## Public source excerpts

A public `guard-trigger` source record proves only that bound context
preconditions and an extracted guard replay to the declared typed results under
one assignment.  It does not independently model the old program fault.
`source-difference` W01 replays one specific widening boundary.  Neither record
is a finite certificate, and the finite theorem cannot be used to justify it.

The retained TensorFlow inputs are static commit/file excerpts.  No TensorFlow
build, model, test suite, executable vulnerability trigger, exploit, or service
is run.  Exact messages, full paths, minimal retained hunks, and extraction
provenance are stored; full source-tree correspondence is not established.

## Empirical interpretation

The 32-file packet is retrospective, label-selected, positive-enriched, and not
a complete time window.  Runtime label isolation prevents one class of leakage
but does not undo development-time knowledge.  Therefore its ranking and
coverage values are descriptive.  Formal prospective H1/H2 remain not testable,
and the readiness gate cannot be promoted by changing a status string.
