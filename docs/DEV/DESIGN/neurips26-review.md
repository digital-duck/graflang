# A review of "Beyond Vibe Coding: Intent Invariance and Structured Prompt Language" (NeurIPS 2026 submission, v1.0)

Written 2026-11-05 from the PDF (`dd-work/docs/beyond-vibe-coding-neurips26-v1.0.pdf`, 13 pages with appendices) and the first part of `SPL.py/NeurIPS-26-lab/README.md` and `notes.md`. **I have not seen the official reviews**, so this is my own reading, written the way a reviewer would, to decide what the next experiment (Project B in `graflang-experiments.md`) must fix. If you paste the real reviews I will map them against this list. Line numbers are the PDF's.

## What the paper claims

SPL, a SQL-like intermediate representation (IR) between natural language and code, makes "intent drift" measurable and locatable. Intent invariance: `T^-1(T(I)) ≈ I` (L131-134). Evidence: 15 round trips (5 PocketFlow recipes x 3 models), scored 0-10 by an LLM judge (`spl compare`, claude-opus-4-6): means 8.15, 7.90, 7.30 (L292-296). The finding (L20-23, L297-303): low scores trace to ambiguous Mermaid diagrams at the human checkpoint, not to model capability, so SPL "is strictly better at finding where intent was lost" than vibe coding.

## Strengths

- A clear problem statement and a concrete, runnable protocol (S1-S6, Appendix D) that others can repeat.
- Honest limitations section (L270-285): no vibe baseline, one run per cell, a Claude judge for a Claude model.
- The syntactic/semantic layer split (section 5.3) is a clean idea, and the failure analysis (L258-265) shows real diagnosis work.

## Major weaknesses (ranked by how much each would cost in review)

1. **The central comparison is missing.** The paper's claim is relative ("beyond vibe coding", "strictly better", L299-303) but there is no vibe-coding arm. The limitations paragraph concedes this (L271-285) and moves it to future work (Appendix F.3). A reviewer cannot accept a superiority claim whose control is absent. The sentence "Even if a direct baseline were to show comparable final code quality, SPL is strictly better at finding where intent was lost" is an assertion, not a result.

2. **The metric is not validated.**
   - The score is one LLM judge's 0-10 opinion. There is no human agreement, no test-retest, no noise floor (what does `describe(original)` vs `describe(original)` score?), no negative control (what does an unrelated recipe score?). Without these, 8.15 vs 7.30 has no meaning.
   - The table shows the judge is noisy: the "Overall" is not a function of its three sub-scores. R1/Claude and R2/Gemini have Structure/Logic/Quality 8/8/8 and Overall 8.0; R2/Claude also has 8/8/8 and Overall 7.75; R3/Claude has 8/8/9 and Overall 8.0; R5/Claude 9/8/9 gives 9.0. The text says the overall is "aggregated" (L247-250) but it is not their mean.
   - Scores sit between 6 and 9 with half-point resolution: a ceiling and a coarse scale.
   - A Claude judge scores a Claude model's output (acknowledged, L243-246) and the judge prompt and rubric are not in the paper.
   - Naming: `ΔS = d(...)` is called a distance, but higher is better ("less drift", L138-139).

3. **n = 1 per cell, five recipes, no uncertainty.** "Each configuration is run once; results are indicative" (L245-246) and then the abstract and conclusion report means to two decimals and a "gradient" (L254, L292-296). A difference of 0.25 to 0.85 on integer-valued scores over five items is within the noise the table itself displays (point 2). No confidence intervals, no test.

4. **Confounds from the human and the tool.**
   - The protocol has a human review and fix each artifact "until working" at every checkpoint (README, lab protocol). The paper does not report how much was changed, so the finding "drift enters at the human checkpoint, not at the model" cannot be separated from "the human's review quality".
   - The lab notes I read record fixes to the generator itself (Mermaid post-processing, fence stripping, prompts) while the first runs were being made. The paper does not say whether the 15 reported scores come from one frozen version of the pipeline.

5. **"Locatable" is shown by three anecdotes.** Section 6.3 (L258-265) traces the lower scores by hand. There is no systematic procedure, no second rater, and no intervention: the claim "fixing the S2 diagram or the S3 SPL repairs the drift without touching the model" (L266-269) is never tested. The right test is a seeded fault: inject a known defect at a known stage and see whether the method finds it.

6. **What is measured is not "intent".** `I` is the S1 description of an existing PocketFlow program, not a requirement written in natural language, and the round trip compares two LLM descriptions (S1, S5). A pipeline that returns a faithful but vague code, or a describer that produces similar boilerplate for any workflow, scores high. Natural language to code, the thing vibe coding does, is never run.

7. **Selection and contamination.** The five recipes come from a public cookbook that models have likely seen; S4 is a deterministic transpiler and "all five recipes matched established patterns" (L149-152), so the model-dependent steps are only S1-S3, S5 and the judge. The set therefore tests the cases the compiler was built for, and says little about novel patterns, where the `--llm` fallback would be needed.

8. **No behavioural check.** The generated code is not shown to behave like the original (same outputs on the same inputs, same control flow). The only equivalence measure is the LLM-judged spec similarity. A deterministic oracle (as in code-generation work with hidden tests) is available and unused.

## Presentation and process issues

- **Anonymity.** The abstract and conclusion give `github.com/digital-duck/SPL.py`; Appendix D and E contain `~/projects/digital-duck/...` paths and the Momagrid repository. For a double-blind venue this is a likely desk-reject or a heavy penalty; use an anonymised mirror.
- **Scope.** Three contributions in 8 pages (a language, a pipeline, a test protocol) each get thin treatment; Appendix B (the CLI reference) and E (Momagrid) take space without supporting the claim.
- **Claims not supported by the paper:** "readable by non-programmers" (no user study), "more deterministic than prose" (no measurement), and the Related Work claim of a "distinct empirical concept" from semantic entropy is not demonstrated by any comparison.
- **Related work** misses the round-trip correctness line for code models (for example the unsupervised round-trip evaluation of code LLMs, Allamanis et al., ICML 2024; check the exact reference) and direct baselines such as spec-to-code with tests. Citing and positioning against it would answer the "why this metric" question.

## What would make the next version defensible

| Weakness | Remedy (built into Project B) |
|---|---|
| 1 no vibe arm | Direct NL-to-code arm, same model and same brief, in every comparison |
| 2 unvalidated judge | Noise floor, negative control, test-retest, two cross-family judges, human-labelled subset with agreement; **plus metrics that need no judge** (structure and behaviour) |
| 3 n = 1 | At least 25 recipes, 3 repeats per LLM cell, paired intervals |
| 4 human and tool confounds | Autonomous runs are primary; pipeline frozen by git hash; human edits logged and reported as a separate pass |
| 5 locatable by anecdote | Stage-wise structural diff plus a seeded-fault study with known locations |
| 6 not intent | Intent is a written requirement (a "brief") and the oracle is the reference program's behaviour |
| 7 selection | Add unseen recipes written for the study, and recipes that need the fallback |
| 8 no behavioural check | Record/replay oracle on the same scripted model replies |
| Anonymity | Anonymous mirror of the lab repo, no personal paths, pinned versions |
