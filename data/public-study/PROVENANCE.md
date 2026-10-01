# Public microcohort provenance and closure status

## Source anchors and units

The 32 retained TensorFlow file-change units derive from public
VFDetector/VulCurator release artifacts.  Positive rows are tied to
`ntgiang71096/vfdetector:tf_pos.csv` at blob
`6e78da5573fde984c260b91db87c0e3c52d3d32f`.  Negative identities follow
`selected_neg_sha.csv` at blob
`442adf5d475fd231c17cfec83a061ebee501585c`.

For every unit, `candidates.json` retains the immutable commit SHA, original
commit message, commit timestamp, full repository-relative file path, and a
minimal excerpt copied from that file's upstream unified patch.  Unrelated hunks
may be omitted, but retained line text is not paraphrased.  `source_asset`
records the extraction rule and separately stores a human file annotation.
Annotations are explicitly excluded from extraction and every ranking score.
This matters for commit `3218043...`: its upstream message remains exactly
`Internal change`; file-specific explanations are annotations, not invented
commit messages.

The unit is a changed file, not an independent vulnerability.  Sixteen positive
file units collapse to ten positive commits; the sixteen negative units are
distinct commits, giving 26 commit groups.  Results are reported by both units.

## Candidate/label separation

`candidates.json` contains no retrospective label or positive/negative list
identifier.  Units are renamed `U001`--`U032` after sorting
`SHA256(commit + NUL + full_file_path)`, so prefixes and row order do not encode
class.  `source-manifest.csv` binds every original message and retained hunk by
SHA-256 and likewise contains no label.

The freeze process re-derives source-evidence cases and typed abstentions from
candidate hunks, rejects any difference from the retained packet, and writes
label-free rankings, typed outcomes, and source records.  Only after that process
exits does a second process open `labels.json`.  This prevents accidental
in-run leakage.  It does **not** make the study prospective: class lists were
known before cohort and grammar development.

## Two evidence contracts

The finite-IR certificate theorem applies only to the owned finite before/after
IR in `src/producer.py` and `src/checker.py`.  Public TensorFlow records use a
different contract:

- a `guard-trigger` record proves that independently replayed typed context
  preconditions hold and the extracted guard takes its declared trigger value;
- a `source-difference` record for W01 replays one explicit int32-versus-int64
  boundary relation.

A public guard record has no independently modeled old fault and is not a finite
certificate.  In particular W10 preserves the upstream pre-existing
`dims(i) != 0` requirement and uses `dim=-1` for its accepted guard record.  The
`dim=0` assignment appears only in frontend validation to ensure that the C11
oracle actually short-circuits before division; it is not accepted source
evidence.

## Restricted frontend and typed outcomes

The extractor recognizes two guard styles and one declared widening pattern.
It derives ten source-evidence cases and 22 typed `unsupported-syntax` outcomes.
Extraction is not independently implemented; its exact retained output is bound
to the candidate packet and mutation-tested.  Parsing is cross-checked by Pratt
and shunting-yard implementations.  Evaluation is cross-checked by a recursive
producer, iterative replay, and compiled C11 oracle.

Nine guard expressions are evaluated on 100 assignments each.  The mandatory
schedule includes the saved assignment, the opposite truth branch, W03's
65535/65536/65537 boundaries, and W10's successful division, failing division,
and protected zero denominator; seeded unique random assignments fill the
remaining positions.  One separate W01 widening check yields 901 total semantic
obligations and zero observed mismatches.

## Descriptive results and denominators

All 32 units remain in all rankings.  Outcomes are 10 `accepted` and 22
`unsupported-syntax`.  Unsupported means only that the declared grammar does
not produce an accepted source record.

- syntax P@20 = 0.75;
- unvalidated-hint P@20 = 0.80;
- checker-accepted-source-evidence P@20 = 0.75;
- the syntax and checker-accepted top-20 sets are identical;
- positive-conditional coverage is 10/16 by file and 10/10 by commit;
- all-candidate availability is 10/32 by file and 10/26 by commit.

H2 is defined over all eligible file candidates, not only positives.  Because
this packet is label-selected, non-temporal, and not a complete window, formal
H1 and H2 remain not testable.  Six fail-closed design gates record the missing
raw/source-tree correspondence, label-independent acquisition, complete window,
pre-development label seal, published same-budget baseline, and temporal
holdout.
