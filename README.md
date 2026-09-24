# Replayable bounded behavioral witnesses

This standalone repository implements and checks a deliberately narrow claim:
for a separately supplied bounded before/after representation, an accepted
certificate replays one same-input transition from an old fault to a defined new
unsigned result.  It also contains an automatic but restricted diff-expression
frontend, exact empirical-closure checks, and a descriptive 32-file TensorFlow
microcohort.  It does **not** claim a completed prospective security-patch
detector evaluation.

## Reproduce

Run from this directory with CPython 3.11 or newer.  The scientific Python code
uses only the standard library; `run_frontend_validation.py` additionally needs
a C11 compiler available as `cc`, `gcc`, or `clang`.  Every output path below
must be new.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 run_frontend_validation.py --output results/reproduced-frontend
PYTHONDONTWRITEBYTECODE=1 python3 run_closure_checks.py --output results/reproduced-closure
PYTHONDONTWRITEBYTECODE=1 python3 run_public_study.py --output results/reproduced-public
PYTHONDONTWRITEBYTECODE=1 python3 run.py --pilot --output results/reproduced-pilot
PYTHONDONTWRITEBYTECODE=1 python3 verify_results.py
```

The first command runs 42 tests.  Frontend validation compares a Pratt parser,
an independently implemented shunting-yard parser, the public producer, the
iterative replay evaluator, and a C11 oracle on 900 guard-predicate assignments.
The closure command performs 19,834 exact accounting obligations.  The public
command launches two sequential OS processes: a label-free freeze phase and a
later evaluation phase that opens labels.  Each child has a 20 s CPU limit, a
40 s wall alarm, a 512 MiB address-space cap, one worker, and no child workers.
The finite pilot has 1,552 obligations.  The retained 90,517-obligation full
finite result is reconciled rather than rerun during packaging.  The recorded
campaign total is 249,990 of the 250,000-obligation ceiling.

## Retained findings

- **Finite contract:** 25 cases, 3,712 assignments, 424 repair, 242 regression,
  2,990 both-defined, 56 both-fault, 13 accepted certificates, and zero observed
  disagreement among recursive evaluation, iterative replay, and direct family
  formulas.
- **Restricted frontend:** 10 of 32 excerpts are recognized (nine guard
  predicates and one declared widening rule); 22 abstain.  The 900 guard
  assignments have zero observed mismatches across the two parsers, two
  evaluators, traces, and C11 oracle.
- **Exact closure:** an incomplete selected candidate packet is compatible with
  full-window P@k equal to either 0 or 1 for every k=1..20; file- and group-level
  coverage have no universal ordering across 19,683 configurations; the paired
  top-k identity holds for all 64 checked labelings.
- **Microcohort:** syntax, unvalidated semantic hints, and validated witnesses
  obtain P@20 of 0.70, 0.75, and 0.70.  The validated top-20 set is identical to
  the syntax top-20.  Witness coverage is 10/16 by file and 10/10 after commit
  collapse.  These remain descriptive results on a label-selected sample.

## Why H1/H2 are not decided

`results/public-study/evaluation/readiness.json` passes the restricted automatic
frontend gate but fails five prerequisites: label-independent candidate
construction, a complete repository/time window, labels sealed before method
development, the strongest published same-budget baseline, and temporal
holdout.  Formal ranking-gain H1 and population-coverage H2 are therefore **not
testable** with this cohort.  Threshold analogues remain visible only for
auditability.

## Layout

- `src/producer.py`, `src/checker.py`: independent recursive production and
  iterative replay implementations for the finite unsigned IR.
- `src/source_frontend.py`, `src/source_frontend_reference.py`,
  `src/source_frontend_oracle.c`: primary restricted frontend, independent
  parser/evaluator, and C11 semantic oracle.
- `proofs/contract.md`, `proofs/source-frontend.md`: written finite-contract and
  frontend-boundary arguments; no proof assistant or full C++ semantics is
  claimed.
- `src/closure_checks.py`: exact non-identifiability, grouping, and paired-ranking
  checks.
- `freeze_public_study.py`, `evaluate_public_study.py`, `run_public_study.py`:
  physically separated public-audit phases.
- `data/public-study/`: neutral candidates, automatically derived restricted
  cases, protocol, design facts, labels, and provenance.
- `results/finite-check/`, `results/source-frontend/`,
  `results/closure-checks/`, `results/public-study/`, `results/pilot/`: canonical
  retained evidence.
- `reference-verification.csv`, `literature-screening.csv`,
  `literature-calibration.csv`: 61-source metadata/depth ledgers and the 22-paper
  calibration matrix.
- `claim_evidence_ledger.csv`: claim-to-evidence map.
- `AI-USE.md`: detailed disclosure of generative-AI use and the validation boundary.
- `THIRD-PARTY-NOTICES.md`, `licenses/`: attribution and license boundary for retained public excerpts.

## Trust boundary

Certificate acceptance is relative to the supplied representation.  The
restricted frontend validates deterministic extraction and finite expression
semantics only for its declared grammar and retained excerpts.  Neither result
establishes complete source-code correspondence, whole-patch correctness,
absence of regression, exploitability, security relevance, or population
utility.  The frontend does not model macros, aliases, pointer/heap behavior,
undefined behavior, build configuration, or whole-program state.  No TensorFlow
source tree, executable vulnerability trigger, private data, model service, or
external scientific compute is included or used.
