# Bounded patch-source and same-information review

These scientific outputs supplement, rather than overwrite, historical
campaigns. No native compiler or upstream application was executed.

- `source-relationship.json`: local old/new line counts for all 39 hunk headers
  in 32 retained excerpts, plus represented common-context locations. Every
  hunk omits lines relative to its header; this is not an applicable patch archive.
- `label-free-comparison.json`: all 32 direct/checked flags and scores and
  complete rankings, written before the label file is opened.
- `same-information.json`: fixed-frame metrics with the unchanged bonus 4,
  rounding and tie rule. Direct and checked flags, scores and full rankings
  are identical; P@20 is 0.75 for each and selection gain is zero.
- `functional-inputs.json`, `functional-cases.json`,
  `functional-summary.json`: the 14 reviewed authored source pairs, their 414
  pair-input observations and eight accepted source-bound witnesses.
  Counts are 106 repairs, 38 new faults, 209 equal-defined outputs, 44
  changed-defined outputs and 17 both-faults. Direct baseline set gain is zero.
- `provenance.json`: command, interpreter, source/input bindings and successful
  finite and public-packet recomputation. The retained C11 report is historical;
  its native executions were not rerun here.

The direct arm consumes the same extracted predicates, common contexts, saved
assignments and destination-width assumptions, but no source record or trace.
It shares the extractor/profile and does not establish an old fault, external
security label, full-source correspondence or prospective detection accuracy.
This additional diagnostic is one process, not the retained two-process run.

From the artifact root, regenerate at an unused path:

```sh
python -B run_patch_source_review.py --output results/new-patch-review
```
