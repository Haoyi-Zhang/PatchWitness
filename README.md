# Replayable bounded behavioral witnesses

This standalone repository contains two deliberately separate evidence paths.

1. **Finite-IR certificate contract.**  For a separately supplied bounded
   before/after IR case, an accepted certificate replays one same-input
   transition from an old fault to a defined new unsigned result.
2. **Restricted public source evidence.**  For retained TensorFlow file-patch
   excerpts, a different checker replays either a guard-trigger record under one
   typed assignment or one explicit integer-widening source difference.  These
   records are not finite-IR certificates and do not inherit the finite
   old-fault/new-defined theorem.

The repository also contains exact empirical-closure checks and a descriptive
32-file TensorFlow microcohort.  It does **not** claim a completed prospective
security-patch detector evaluation.

## Reproduce

Run from this directory with CPython 3.11 or newer.  The Python code uses only
the standard library; `run_frontend_validation.py` additionally needs a C11
compiler available as `cc`, `gcc`, or `clang`.  Every output path below must be
new.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 run_frontend_validation.py --output results/reproduced-frontend
PYTHONDONTWRITEBYTECODE=1 python3 run_closure_checks.py --output results/reproduced-closure
PYTHONDONTWRITEBYTECODE=1 python3 run_public_study.py --output results/reproduced-public
PYTHONDONTWRITEBYTECODE=1 python3 run.py --pilot --output results/reproduced-pilot
PYTHONDONTWRITEBYTECODE=1 python3 verify_results.py
```

The first command runs 46 tests.  Frontend validation separates extraction,
parsing, and evaluation: one declared extractor produces typed support or
abstention; a Pratt parser and separately implemented shunting-yard parser are
cross-checked; and recursive Python, iterative Python, and a compiled C11
short-circuit oracle are compared on 900 guard assignments.  One additional
widening check gives 901 semantic obligations.  The assignment schedule retains
each saved assignment, both Boolean branches, actual division, a protected
zero denominator, 65535/65536/65537 boundaries, and seeded random points before
any deterministic repeats.

The closure command performs 19,834 exact accounting obligations.  The public
command launches two sequential OS processes: a label-free freeze phase and a
later evaluation phase that opens labels.  Each child has a 20 s CPU limit, a
40 s wall alarm, a 512 MiB address-space cap, one worker, and no child workers.
The finite pilot has 1,552 obligations.  The retained 90,517-obligation full
finite result is reconciled rather than rerun during packaging.  The recorded
campaign total is 249,992 of the 250,000-obligation ceiling.

## Retained findings

- **Finite contract:** 25 cases, 3,712 assignments, 424 repair, 242 regression,
  2,990 both-defined, 56 both-fault, 13 accepted certificates, and zero observed
  disagreement among recursive evaluation, iterative replay, and direct family
  formulas.
- **Restricted source evidence:** 10 of 32 exact retained file excerpts are
  supported (nine guard records and one widening record); 22 receive typed
  `unsupported-syntax` outcomes.  The 900 guard assignments and one widening
  check have zero observed mismatches.
- **Exact closure:** an incomplete selected candidate packet is compatible with
  full-window P@k equal to either 0 or 1 for every k=1..20; file- and group-level
  coverage have no universal ordering across 19,683 configurations; the paired
  top-k identity holds for all 64 checked labelings.
- **Microcohort:** syntax, unvalidated source hints, and checker-accepted source
  evidence obtain P@20 of 0.75, 0.80, and 0.75.  Accepted source evidence changes
  no member of the syntax top-20.  Positive-conditional coverage is 10/16 by
  file and 10/10 after commit collapse; availability over all candidates is
  10/32 by file and 10/26 by commit.  All are descriptive results on a
  label-selected sample.

## Why H1/H2 are not decided

`results/public-study/evaluation/readiness.json` passes four machine-recomputed
checks but fails six requirements whose truth depends on separately supplied,
verifiable study-design evidence: raw-diff or checked source-tree
correspondence, label-independent candidate construction, a complete
repository/time window, labels sealed before method development, a reproduced
strongest published same-budget baseline, and temporal holdout.  Formal
ranking-gain H1 and full-cohort file-availability H2 are therefore **not
testable** with this cohort.  Editing a Boolean or an `accepted` string cannot
make those gates pass.

## Layout

- `src/producer.py`, `src/checker.py`: independent recursive production and
  iterative replay for the finite unsigned IR.
- `src/source_frontend.py`, `src/source_frontend_reference.py`,
  `src/source_frontend_oracle.c`: restricted real-hunk extractor/parser,
  independent parser/evaluator, and C11 short-circuit oracle.
- `derive_source_evidence.py`: derives the retained source-evidence packet and
  typed abstentions from candidate hunks.
- `proofs/contract.md`, `proofs/source-frontend.md`: the separate finite and
  public-source contracts.
- `src/closure_checks.py`: exact non-identifiability, grouping, and paired-ranking
  checks.
- `freeze_public_study.py`, `evaluate_public_study.py`, `run_public_study.py`:
  physically separated public-audit phases.
- `data/public-study/`: original commit messages, full file paths, exact retained
  minimal diff context, annotations excluded from scoring, labels, protocol,
  design facts, and provenance.
- `results/finite-check/`, `results/source-frontend/`,
  `results/closure-checks/`, `results/public-study/`, `results/pilot/`: canonical
  retained evidence.
- `reference-verification.csv`, `literature-screening.csv`,
  `literature-calibration.csv`: 61-source metadata/depth ledgers and the 22-paper
  calibration matrix.

## Trust boundary

Finite certificate acceptance is relative to the separately supplied finite IR.
Public guard-trigger acceptance is relative to the retained real hunk,
restricted extraction rule, typed assignment, and bound guard AST.  Neither
establishes complete source-code correspondence, whole-patch correctness,
absence of regression, exploitability, security relevance, or population
utility.  The source path does not model macros, aliases, pointer/heap behavior,
whole-program state, build configuration, or general C/C++ undefined behavior.
No TensorFlow source tree, executable vulnerability trigger, private data, model
service, or external scientific compute is included or used.
