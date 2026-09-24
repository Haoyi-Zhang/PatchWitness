# Generative-AI use in this research package

OpenAI ChatGPT (GPT-5.6 Sol Pro) was used interactively across the research
lifecycle. Its material uses were:

- comparing candidate formulations and identifying evidentiary failure modes;
- implementing and repairing the Python finite evaluator, producer/checker,
  restricted diff frontend, exact closure checks, runners, and tests;
- writing the small C11 semantic oracle and constructing benign bounded test
  inputs;
- executing local build, test, validation, rendering, and packaging commands;
- locating public scholarly and repository records, organizing the literature
  ledgers, and drafting the 22-paper calibration matrix;
- drafting and revising manuscript and artifact prose.

No model output is treated as an experimental observation, security label,
human judgment, baseline prediction, vulnerability trigger, or independent
review. Retained code paths are tested; numerical claims are rederived from raw
results by `verify_results.py`; source-case bindings are rederived by the
restricted frontend; and bibliography entries are checked against stable
scholarly records or full texts at the depth stated in the ledgers. The package
does not include chat transcripts or prompts. Human authors remain responsible
for inspecting the evidence, authorship, originality, policy compliance, and
any external submission.
