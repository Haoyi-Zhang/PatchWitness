# Public microcohort provenance and closure status

## Source anchors and units

The 32 retained TensorFlow file-change units derive from public
VFDetector/VulCurator release artifacts. Positive rows are tied to
`ntgiang71096/vfdetector:tf_pos.csv` at blob
`6e78da5573fde984c260b91db87c0e3c52d3d32f`. Negative identities follow
`selected_neg_sha.csv` at blob
`442adf5d475fd231c17cfec83a061ebee501585c`. `source-manifest.csv` records
immutable commit identities, neutral unit identities, and the automatically
derived case ID where one exists.

The unit is a changed file, not an independent vulnerability. Sixteen positive
file units collapse to ten positive commits; the sixteen negative units are
distinct commits, giving 26 commit groups. Results are reported both by file and
after commit collapse.

## Candidate/label separation

`candidates.json` stores messages, excerpts, files, commits, and group identities
but no label or positive/negative source-list metadata. Units are renamed
`U001`--`U032` after sorting `SHA256(commit + NUL + filename)`, so prefixes and
row order do not encode class. `source-manifest.csv` likewise omits label and
selection-source columns. `labels.json` alone stores retrospective class labels
and the positive/negative release anchors.

The public runner first invokes a label-free process. That process re-derives the
restricted cases from candidate excerpts, rejects any difference from the
retained case document, writes frozen predictions and certificates, and exits.
A second process then opens `labels.json`. This physical separation prevents
accidental in-run leakage. It does **not** make the study prospective: the source
lists were labeled before the cohort and frontend were developed. The study
design therefore records `candidate_selection_independent_of_labels=false` and
`sealed_before_method_development=false`.

## Restricted automatic frontend and typed outcomes

The frontend automatically recognizes two guard styles and one declared
integer-widening pattern. It derives ten cases from the 32 retained excerpts and
returns typed abstentions for the other 22. Nine guard expressions are checked
on 900 deterministic assignments by two independently implemented parsers, the
producer, the iterative replay checker, and a compiled C11 oracle. The widening
case is an explicit abstract boundary relation, not a portable claim about all
C++ conversions. Full details and non-claims are in
`proofs/source-frontend.md`.

No TensorFlow source tree, build, test, model, or vulnerability trigger is
executed. The frontend does not model macros, aliases, pointer/heap behavior,
undefined behavior, build flags, slicing, or whole-program state. All 32 units
remain in the analysis. Outcomes are 10 `accepted`, 3 `unvalidated-only`, and 19
`unsupported`. Unsupported means only that the frozen restricted frontend has
no accepted case; it is not a security label and not evidence that no behavioral
witness exists.

## Selection bias and permitted claims

The sample is label-selected, positive-enriched, published-order, and not a
complete repository/time window. The syntax control is transparent but not the
strongest published repository-aware model. Consequently:

- 10/16 file coverage and 10/10 commit coverage are descriptive,
  denominator-sensitive measurements;
- syntax P@20 = 0.70, unvalidated P@20 = 0.75, and validated P@20 = 0.70
  describe only this cohort;
- the formal prospective H1/H2 hypotheses are not testable here; and
- no prevalence, temporal generalization, full-language frontend coverage, or
  population utility claim is permitted.

`protocol.json` and `results/public-study/evaluation/readiness.json` encode these
boundaries as an executable gate.
