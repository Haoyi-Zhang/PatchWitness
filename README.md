# Replayable bounded behavioral witnesses

This standalone artifact supports a journal-formatted research manuscript on checkable evidence contracts and the interpretation of software-engineering evaluations. It contains no external model calls, new public patch campaign, upstream application execution, or exploit reproduction.

## Evidence objects

The finite-IR checker accepts one same-input old-fault/new-defined relation against a separately supplied, bounded unsigned IR pair. Its written relative soundness argument does not establish correctness of Python, a source translator, or an entire patch.

The public-source checker has a different contract. It checks a guard trigger under explicit local context, or W01's assumed signed-destination range separation, in one retained static patch excerpt. It does not certify an old runtime fault. The single extractor uses an explicit closed case profile; parser and evaluator comparisons do not validate extraction, hidden context, macros, or whole-source semantics.

The evaluation layer retains all 32 file candidates and 26 commit groups. It separates observed-label ranking results, exact finite-frame sensitivity, and missing prospective evidence. Historical H1/H2 thresholds are not pass conditions for this research.

## Reproduce

Requirements: CPython 3.11 or later, a POSIX system providing Python's `resource` module, and a C11 compiler named `cc`, `gcc`, or `clang`. Python dependencies are standard-library only. No network is required. A new output directory is required; existing evidence is never overwritten.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 reproduce.py --output results/reproduced
```

This entry point runs the full unit suite, full finite experiment, pilot, source-expression validation, retained closure experiment, public two-process audit, the new exact finite-frame analysis, and retained-result verification. It compares fresh scientific outputs with the canonical outputs, separating host-dependent timing and memory observations. A failure leaves its logs and exits nonzero.

Individual diagnostic commands are:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 run.py --output results/reproduced-finite
PYTHONDONTWRITEBYTECODE=1 python3 run.py --pilot --output results/reproduced-pilot
PYTHONDONTWRITEBYTECODE=1 python3 run_frontend_validation.py --output results/reproduced-frontend
PYTHONDONTWRITEBYTECODE=1 python3 run_closure_checks.py --output results/reproduced-closure
PYTHONDONTWRITEBYTECODE=1 python3 run_public_study.py --output results/reproduced-public
PYTHONDONTWRITEBYTECODE=1 python3 run_contract_audit.py --output results/reproduced-frame
PYTHONDONTWRITEBYTECODE=1 python3 verify_results.py
```

The retained complete run recorded 65 passing tests. Seven authored tests have since been added without removing any existing test. The full finite runner's embedded core-test count is a subset, not an additional independent suite. All scientific executions are single-worker and sequential. The original reproduction supervisor applies a 120-second wall timeout to each command; inherited finite/public workers have tighter internal limits. The C program evaluates only benign owned expressions, not TensorFlow binaries.

For a bounded campaign that does not open the public dataset, including on Windows:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B run_owned_campaign.py --output D:/path/to/new-output
```

This runs 32 selected authored/finite tests, the complete 25-case finite experiment and its verifier, the pilot, all 26,808 exact-bound comparisons, all 19,834 closure checks, and 287 distinct authored scalar-expression probes. A measured Windows/CPython 3.12.14 replay passed in 1.531 seconds of supervisor wall time. Each worker has a 60-second wall timeout; this route does not enforce POSIX CPU/address-space limits or report peak RSS. Temporary test files and raw results stay under the supplied new output directory. It does not rerun the retained public study or claim that the entire expanded suite passed.

Add `--c11` on a host with an existing C11 compiler to cross-check the same authored expressions in the owned C oracle. The prepared `.github/workflows/scientific-checks.yml` in the complete project invokes that route, with no dependency installation or public-dataset execution. That workflow and the C11 extension were not executed in the measured Windows replay.

## Canonical evidence

| Object | Retained result | Scope |
|---|---|---|
| Finite IR | 25 cases; 3,712 assignments; 424 repair, 242 regression, 2,990 both-defined, 56 both-fault; 13 certificates | Exact small owned models, not public workload breadth |
| Source-expression agreement | 900 checks on 262 distinct case–assignment pairs, plus one range check; no observed disagreements | Two parsers, two Python evaluators and C11; one extractor |
| Context admissibility | 847 of the 900 scheduled checks satisfy every represented common precondition | Out-of-context checks test the interpreter, not source reachability |
| Retained closure checks | 19,834 comparisons | Incomplete frames, grouping and paired-set identities |
| Finite-frame bounds | 26,808 exact formula/oracle comparisons for n≤4 | Partial labels, trusted total positives, bounded corrections and bounded insertions |
| Microcohort P@20 | Syntax 0.75; unchecked hints 0.80; checked source evidence 0.75 | Retained-label, retrospective description |
| Evidence availability | 10/32 files and 10/26 commits | All candidate units |
| Positive-conditional coverage | 10/16 files and 10/10 commits | Labeled positives only |

The checked and syntax top-20 sets are identical, making their paired difference exactly zero for every common label completion. For the hint path, at most one label correction admits zero gain. These are fixed-frame results, not population confidence intervals or evidence of temporal generalization. Resampling numbers are retained as conditional algorithmic sensitivity, not deployment uncertainty.

W09 binds the unchanged nonempty check and uses `num_elements=2`. W10 binds the unchanged nonzero check and uses `dim=-1`; its zero-denominator input is an interpreter probe outside the source precondition. W01 proves only that a mathematical value falls outside an assumed signed 32-bit destination range and inside an assumed signed 64-bit range; operand types and runtime faults are not established by that record.

## Verification and trust

`verify_results.py` re-evaluates all finite assignments, independently replays accepted source records, reconstructs source assignments/coverage, recompiles the C11 oracle, and recomputes scores, complete rankings, top sets, all CSV columns and denominators. Exact nested typing rejects Boolean/integer/float substitutions, including in unvisited assignments. It checks a unique candidate–case–record–accepted-outcome correspondence. The finite-frame runner checks its formulas against explicit completion enumeration.

Readiness has three scientific evidence checks: two are live recomputations at evaluation and one refers to an input-bound retained cross-check report. The full verifier additionally re-executes that report. Bibliographic completeness is a separate editorial check, not a scientific validity condition. Six design conditions remain unsupported: checked source-tree correspondence; label-independent selection; complete repository/time window; pre-development label sealing; an appropriate strongest same-budget baseline; temporal holdout. Design declarations cannot authenticate historical events. The fixed retrospective design rejects Boolean/status promotion and has no automatic prospective-admission path.

## Files

- `src/producer.py`, `src/checker.py`, `proofs/contract.md`: finite contract, producer, replay and written proof.
- `src/source_frontend.py`, `src/source_frontend_reference.py`, `src/source_frontend_oracle.c`, `proofs/source-frontend.md`: restricted extraction, independent parser/evaluator, C11 oracle and distinct source contract.
- `src/audit_bounds.py`, `run_contract_audit.py`, `proofs/finite-frame-bounds.md`: exact bounds, independent enumeration and proof.
- `data/public-study/`: retained original messages, full paths, minimal real hunks, source/context provenance, annotations excluded from scoring, labels and protocol.
- `results/finite-check/`, `results/source-frontend/`, `results/closure-checks/`, `results/finite-frame-audit/`, `results/public-study/`: canonical scientific results.
- `results/clean-replay/`: a measured replay record and logs, not an independent external replication.
- `reference-verification.csv`, `literature-screening.csv`: 67 aligned reference records. `literature-calibration.csv` retains 22 inherited targeted full-paper records; the present preparation does not claim to have freshly read all 67 papers.
- `THIRD-PARTY-NOTICES.md`: source attribution and redistribution caveats.

`results/campaign.json` is inherited accounting. Its totals and incomplete historical run records are not a verified current CPU budget or a count of independent samples. The bounded journal validation is separately measured in reproduction logs; no unlogged historical totals are invented. The manuscript and all diagrams can be rebuilt in the separate complete project, but this repository never requires its `paper/` directory.
The grouping check compares its count formulas with a separate aggregation of explicit unit records. Its regression tests cover both coverage-order examples and confirm that an incorrect aggregation produces mismatches. The retained scientific totals are unchanged; historical resource measurements describe the runs that produced them.
