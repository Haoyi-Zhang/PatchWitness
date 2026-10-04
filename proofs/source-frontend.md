# Restricted source-evidence contract

This contract is not the finite-IR old-fault/new-defined relation in `contract.md`.

## Input and extraction

Each retained record has a commit identity, original message, timestamp, full path, and minimal real unified-diff context. Human file annotations are separate and excluded from scores and extraction. The single extractor operates on selected added lines, with a closed case-identity/profile registry and explicit normalization of source expressions to local integer variables. Its supported grammar covers rejection guards, admission guards and one exact destination-type change. It is not a complete diff parser or C/C++ frontend. Source-selection and context requirements are part of the trusted evidence specification.

Expected extraction, parse and evaluation limitations become typed per-record abstentions. An unclosed guard is retained with its stage and reason. Unexpected programming/system errors propagate; they are not converted to unsupported syntax. All 32 candidates remain in rankings.

## Guard relation

For bound record r, extracted guard g, context expressions p_1,...,p_m, integer assignment a and specified trigger t in {false,true}, acceptance requires: the exact candidate/case/record identities and tokens match; a is well typed for every declared variable including unvisited ones; each p_i evaluates to true; g evaluates to t; and the independently recomputed typed outcomes and traces match the record. A trigger does not establish either an old fault or safety of the new program. Local context is not a proof of reachability from an API entry point.

W09 binds the unchanged `key_tensor->NumElements() > 0` precondition. Its accepted assignment is `num_elements=2`, not zero. W10 binds the unchanged `dims(i) != 0` precondition. Its accepted assignment is `dim=-1, prod=1, limit=2147483647`; the new positivity guard rejects the negative local value and short-circuits the right side. The zero assignment in the expression test schedule is outside this common source precondition and is not an accepted public record.

Assignments are exact host integers in a variable map. Outcomes and trace payloads use explicit integer/Boolean tags. Recursively typed equality checks containers and each nested payload; it does not use Python's permissive cross-numeric equality. Guard traces belong to this source interpreter, not to the finite certificate schema.

## W01 range relation

The retained source changes the destination declaration from `int` to `int64`. Under explicitly assumed signed widths 32 and 64, take mathematical `concat_dim=-2^31` and v=abs(concat_dim)=2^31. Then v is outside [-2^31,2^31-1] and inside [-2^63,2^63-1]. The source record contains `mathematical_value`, `fits_old_destination`, `fits_new_destination` and `assumed_signed_widths`. It contains no old/new runtime outcomes and no claimed old overflow fault.

The checker computes the range relation with its own integer expressions rather than calling the producer. A changed destination declaration does not by itself establish the operand's type, arithmetic conversions, runtime behavior or whole-program correctness. The range record is not covered by the finite soundness theorem.

## Independence and validation

Extraction has one implementation. Pratt and shunting-yard parsing are separately implemented. Recursive Python evaluation and iterative replay are separately implemented, and a C11 program evaluates an encoded expression with short-circuit control segments. Encoding/normalization and the compiler remain trusted; an independently compiled evaluator does not make source extraction independently validated.

The fixed schedule evaluates nine guards 100 times each, with saved assignments, opposite truth branches, 65535/65536/65537 boundaries and protected/actual division cases before seeded unique samples and repeats. There are 900 checks but only 262 distinct case–assignment pairs; 847 checks satisfy all represented common contexts. W01 adds one range check. The exact rows and comparison traces are retained. Repeat counts are not evidence of additional semantic diversity. Unit tests separately exercise direct division by zero, signed division, MIN/-1 rejection, both short-circuit operators and strict schema substitutions using benign owned expressions.
