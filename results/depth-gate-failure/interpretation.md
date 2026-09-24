# Interpretation of the retained failure

The first fixed-protocol run completed all 3,712 assignments. Its aggregate `mismatches: 1` includes the failed JSON-gate unit test; it is not a count of semantic disagreements. The JSON decoder accepted a deeply nested input rather than raising the anticipated recursion error. Relying on an interpreter recursion limit was not an explicit nesting contract. The source was repaired with a string-aware, bounded-depth scan before JSON decoding. No fixture, label, ranking threshold, oracle or finite-case selection changed.

The initial result, all cases, certificates, counts and unit-test output are retained. The traceback's absolute execution path is replaced below with an artifact-relative path only; no scientific result is removed. See the current source and the subsequent clean-reproduction result for the repaired gate.
