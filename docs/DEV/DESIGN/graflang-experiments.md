# GraphLang experiments: plan

Status (2026-11-05): **Project A is built; Project B is revised after reading the rejected NeurIPS-26 paper and is waiting for your review. Nothing in Project B is built.** Experiments move to a new repository, **graflang-lab** (section 4), outside this one: **scaffolded 2026-11-05 at `~/projects/digital-duck/graflang-lab`** (library, gateway, templates, offline tests; uncommitted). Its `docs/DESIGN.md` and `experiments/roundtrip/` now hold the working version of this plan.

- Project A: record the compliance-audit batch in SQLite and analyse it. Built (section 2).
- Project B: repeat the intent-invariance round trip of the NeurIPS-26 paper with GraphLang in the loop, **fixing the paper's weaknesses** (section 3, review in `neurips26-review.md`).

## 1. Observability: where things stand

`OBSERVE`, `summary.json` (calls, tokens, per-node milliseconds), per-node output files, JSONL logs and `graf trace` are enough to record an experiment. What was missing was a store and an analysis layer, not new node types. `claude_cli` token counts are estimates (characters / 4), so compare calls and seconds first.

## 2. Project A (built): SQLite store and analysis for the compliance batch

`cookbook/compliance_audit/`: `batch_test.py` runs documents x variants x models x `--repeat N`, writes every result into `output/experiments.db` (`batch_store.py`; `--resume` skips finished cells), sets each run's model-call cap from the graph's count plus 50% (`graf validate` prints it), and can score stored results again against changed keys (`--rescore`). `batch_analyze.py` reports rates with Wilson intervals, elapsed time (median, p90, model vs rules), leaks, a per-document grid, consistency across repeats and a paired McNemar comparison; several `--db` files can be compared side by side. First haiku batch (54 runs, no false release) and the answer-key and prompt changes that followed are recorded in that recipe's readme.

## 3. Project B (revised): does a checkable IR reduce or locate intent drift?

### 3.1 What the review changes

The paper's design (S1 to S6: describe, Mermaid, SPL, code, describe, LLM-judge compare) has eight weaknesses (`neurips26-review.md`): no vibe baseline; an unvalidated, noisy judge; n = 1 over 5 recipes; human and tool confounds; localisation by anecdote; "intent" defined as a description of existing code; selection and contamination; no behavioural check. This plan keeps the S1 to S6 idea and the "drift is locatable" question, and changes the design so that each weakness has an answer.

**The claim to test, narrowed:** *Given the same written requirement and the same model, a pipeline that passes through a checkable IR (SPL, or a GraphLang graph) produces programs that behave and are structured more like the reference than a direct one-shot generation does, and when it does not, the stage where it diverged can be identified without a judge.* Either outcome is reported.

### 3.2 Design

**Units.** Recipes. At least 25: the 5 of the paper (to connect to it), further recipes from the PocketFlow cookbook (the lifted copies are in `cookbook/pocketflow`; the count is checked in phase 0), and **5 new recipes written for this study** that are in no public repository (contamination control), at least two using a pattern the compiler's library does not cover (so the model-assisted fallback is exercised).

**Intent is a written requirement, not a description of code.** Per recipe, a short **brief** (3 to 8 sentences: inputs, outputs, control flow in words, no code), written by a person from the reference's readme and frozen before any run. The reference program (the original PocketFlow code, or for the new recipes a hand-written one) is the oracle's source. The paper's S1 description is kept only as a secondary input.

**Arms (every arm gets the same brief and the same model; all autonomous, no human edits):**

| arm | path | what it tests |
|---|---|---|
| `vibe` | brief -> PocketFlow code, one shot | the missing control |
| `spl` | brief -> Mermaid -> SPL -> code (the paper's pipeline, frozen at a git commit) | the paper's claim |
| `graflang` | brief -> graph (`graf create`, checked by `graf validate`) -> code (`graf compile --lang pocketflow`, template) | this repository's claim |
| `lifted` | reference -> graph (`spl2graph`) -> code, no model | ceiling: loss from the IR and the compile alone |

A second, small pass keeps the paper's human checkpoint for `spl` only: every human edit is logged (lines changed, minutes) and the artifact scored before and after, so the human's contribution is **measured, not assumed**.

**Measurements (the first three need no LLM judge):**

1. **Behaviour (primary).** Record the reference's model replies on k = 3 inputs per recipe, replay them (a scripted model: the same replies keyed by prompt order) into each generated program, and compare final outputs, the order of node transitions, and the number of model calls. Score per input: equal / same outputs different path / different. GraphLang already has record and replay (`RecordingLLM`, `ReplayLLM` in `grafr/metering.py`); the PocketFlow side needs a small stub of `call_llm`.
2. **Structure.** Extract the flow graph from each program with Python's `ast` (node classes, action-labelled edges, loops) and compare with the reference's by edge-set F1 and normalised graph edit distance. Deterministic.
3. **Stage-wise localisation.** The IR artifacts carry a flow too (Mermaid edges, the SPL workflow, the graph YAML). Extract and compare each against the reference's structure: the **first stage at which structure diverges** is the localisation. No judge, no anecdote.
4. **Seeded-fault study (tests the "locatable" claim and the metrics' sensitivity).** Inject a known defect at a known stage (drop an edge, swap a branch, remove a loop bound, rename a node) into a correct IR, compile downstream deterministically, and ask each metric: did it detect the defect, and did it point at the right stage? Report detection rate and localisation accuracy for behaviour, structure and the judge.
5. **LLM-judged spec similarity (the paper's ΔS), secondary and validated:**
   - *Noise floor:* two independent `describe` of the same program, compared. *Negative control:* describes of two different recipes, compared. ΔS is reported on the scale these two anchor.
   - *Test-retest:* the same pair judged 3 times.
- *Judges (decided: gemma4, with one rule added):* the judge is never the generator's family, and gemma4 is also a generator. So **gemma4 judges the Claude generators' artifacts, and haiku-5-5 judges gemma4's**; where both judge the same pairs (a subset, 20%) their agreement is reported. A local judge costs nothing, so the noise floor, negative control and test-retest can be run many times; it is also the weakest judge in the set, so its agreement with the 30 human-labelled pairs decides whether its scores are used at all (below the threshold in the pre-registration, only the judge-free metrics are reported).
   - *Human check:* 30 pairs labelled by two people; report agreement (kappa or rank correlation) between judge and humans.
   - The judge's prompt and rubric are published in the repository.
6. **Cost:** model calls, tokens (estimates), seconds, human minutes (0 for autonomous arms).

**Models (decided 2026-11-05).** Three generators: haiku-5-5, sonnet-5-5 and gemma4 (local, Ollama); the pilot uses haiku-5-5. Exact model ids and the adapter are stored in every row.

**Repeats.** At least 3 per model-using cell, with the temperature and seed policy recorded. The deterministic compile and extraction steps run once.

**Freezing.** The pipeline versions (SPL tool commit, graflang commit, the lab commit, prompt hashes) are recorded per batch and **frozen before the measured runs**; no fix to a generator during a measured batch (fixes are made, committed, and the batch restarted).

### 3.3 Analysis

Per arm: mean behavioural equivalence and structure F1 with a paired bootstrap interval across recipes (pair by recipe, within model); McNemar for pass/fail on behaviour; effect sizes, not only p-values; failures counted by the **first failing stage** (does not compile, does not run, wrong path, wrong output), never averaged away. With 25 recipes x 3 repeats the intervals are wide enough to say so; the write-up reports what the data cannot tell.

**Pre-registered expectations (to be checked, not assumed; written before any run):**
- (a) `lifted` has near-ceiling behaviour and structure: if not, the compile is the problem, not intent.
- (b) `vibe` is competitive on the simple recipes (linear pipelines) and loses on recipes with loops or branches; I expect the IR arms to win clearly only on the latter.
- (c) `graflang` fails earlier and more visibly (validation errors, a compile refusal) than `spl` or `vibe` (a program that runs but does the wrong thing); that is a detectability advantage, not necessarily an accuracy one.
- (d) The judge's ΔS correlates only moderately with behaviour; the seeded-fault study shows the judge missing some structural faults that the structure metric catches, and flagging some harmless rewording.
- **What would count against GraphLang:** `graflang` not above `vibe` on behaviour for the recipes with control flow, or the template compile needing a runtime shim for most recipes. **What would count against the paper's claim:** `spl` not above `vibe`. Both are reported.

### 3.4 What must be built

1. `graf compile --lang pocketflow` (template, no model first; new backend in `grafe/`). Node types with no PocketFlow equivalent (GUARD, MUTATE, DECISION, RUN_CODE, QUERY/EMIT) are refused with a clear message.
2. A PocketFlow flow extractor (`ast`) and a flow comparer (edge-set F1, graph edit distance).
3. A stage-wise extractor for Mermaid edges, the SPL workflow and the graph YAML.
4. The record/replay harness for PocketFlow programs.
5. A fault injector for the three IRs.
6. A judge-validation tool: noise floor, negative control, test-retest, cross-judge, human-label import.
7. The driver, store and analysis (`run.py`, `store.py`, `analyze.py`), reusing the compliance batch's store and the code-pipeline experiment's statistics (Wilson, paired bootstrap, McNemar), moved into a shared module in graflang-lab.
8. The briefs and the 5 new reference recipes (a human task, not a model task).

### 3.5 Risks

- PocketFlow's shared store and action strings do not map one to one to token-passing dataflow; the template compile may need a small runtime shim (would be reported as such).
- Scripted-model replay assumes the generated program calls the model in the same order; a correct program that reorders calls is scored "same outputs, different path", which is why path and outputs are scored separately.
- The paper's own SPL tool is another repository; the `spl` arm pins its commit and re-runs it (not reusing the paper's files), so the models and the judge are equal across arms.
- 25 recipes x 3 repeats x 3 models x 4 arms is about 900 generations; at roughly 3 to 8 model calls each that is on the order of thousands of calls. Phase 5 is billed: the budget and caps are agreed per phase; the pilot (one recipe, one model) gives the real figure.
- Claims in the write-up stay inside the data: no "strictly better" without a result.

## 4. The graflang-lab repository

For experiments that are not part of the GraphLang product: Project B, the compliance batch's larger runs, `doc_it` model comparisons, the code-pipeline experiment's successors.

**Proposed layout**

```
graflang-lab/
  README.md              what is here, how to reproduce, how results are released
  pyproject.toml         depends on graflang (pinned by commit or tag); installs lab_common
  lab_common/            store.py (batches/results tables), stats.py (Wilson, paired bootstrap, McNemar),
                         judge.py (validated-judge tools), provenance.py (git shas, model ids, prompt hashes)
  experiments/
    roundtrip/           Project B: PREREGISTRATION.md (frozen by a git tag before measured runs), briefs/, references/,
                         run.py, analyze.py, faults/, README.md
    compliance_batch/    moved from graflang later (batch_test.py, store, analysis) with its answer keys
    doc_it_models/       model comparison for `graf docs`
  data/                  small inputs checked in (briefs, answer keys, manifests)
  results/               databases and reports: git-ignored; released snapshots go to tagged releases
  tests/                 offline only (stub model); no billed call in CI
```

**Rules**
- Every row stores the graflang commit, the lab commit, model id and adapter, prompt hashes, and the batch's arguments.
- `held equal`, oracle independence and the stated expectation come first in each experiment's README, as in `experiments/code_pipeline/`.
- A frozen pipeline per measured batch; a change means a new batch id.
- Billed phases need a stated cap before they start.
- A **double-blind mirror** (anonymous repository, no personal paths, no org names in the code or the data) is built from a tagged commit for any submission.
- graflang stays free of experiment code; the lab imports graflang, never the reverse. What the lab needs from graflang (for example `graf compile --lang pocketflow`) is built in graflang, tested there, and used by the lab through its CLI.

**What stays in graflang:** the compliance recipe and its small batch tools (they are the recipe's own test and demo); `doc_it`; `graf compile --lang pocketflow` and the flow extractor, if they are useful beyond the lab (my view: the compiler yes, the extractor no).

## 5. Phases and review points

| Phase | Work | Needs a model | Review |
|---|---|---|---|
| 0 | Read the 5 originals, the lifted graphs and the lab sources; count usable recipes; list node types; write briefs for the first 5; draft `PREREGISTRATION.md`; scaffold graflang-lab | no | **You review scope, briefs and the pre-registration** |
| 1 | `lab_common` (extract the store and statistics), offline tests | no | |
| 2 | `graf compile --lang pocketflow` (template), flow extractor, compile the lifted graphs, replay them against the references | no | Does `lifted` reach the ceiling? |
| 3 | Stage-wise extractor, fault injector, judge tools; dry run with the stub model | no | |
| 4 | Pilot: 1 recipe, 1 model, 3 repeats, 4 arms, capped; judge validation on the pilot pairs | yes, small | Cost, noise floor, failure stages |
| 5 | Full grid, 25+ recipes | yes, billed; budget agreed first | |
| 6 | Seeded-fault study; the human-checkpoint pass | yes, small | |
| 7 | Report: results against the stated expectations, including where they were wrong. (A double-blind mirror is built only if a submission is planned; there is none now.) | no | |

## 6. Decisions (2026-11-05) and what follows from them

1. ~~graflang-lab~~: created (scaffold).
2. ~~The briefs~~: written by you.
3. **Models: haiku-5-5, sonnet-5-5, gemma4.** Adopted (section 3.2). One consequence: all three are also the candidate judges, so the judge rule below matters.
4. **Judge: gemma4.** Adopted with one change. My constraint was "never the generator's own family", and gemma4 is a generator, so gemma4 cannot judge gemma4's own output. Assignment: gemma4 judges the Claude generators; haiku-5-5 judges gemma4. The 30 human-labelled pairs decide whether gemma4's scores are trusted: it is the weakest judge here, and in the compliance batch it was the model that leaked. Cheap repeated judging is the benefit.
5. **No rush to write a paper; focus on comparative studies.** Adopted. Changes: the double-blind mirror and the paper framing are dropped from the critical path; the pre-registration stays (it is what makes a comparison credible, paper or not); and the next work is ordered so that comparisons that need no briefs and no judge come first.

**Order of work now**
- **a.** Finish the compliance comparison: v3 (3 models x 3 repeats), the `hard_encoded_mix` key and `redact.md` fix with its v4 check, then the consensus-vote simulation on the stored extractions (offline).
- **b.** An **execution** comparison of one workflow in all five frameworks (graflang, pocketflow, langgraph, crewai, autogen) through the gateway with scripted replies: same outputs? same path? lines of code, wall time, behaviour at a failing step. It needs no briefs and no judge, and it is what exercises the CrewAI and AutoGen adapters. Start with the workflow in `tests/fixtures/toy_agent` (a decide/search/answer loop).
- **c.** `roundtrip` once the briefs exist (authoring comparison, as planned).
- **d.** `graf docs` across the three models (authoring), with the judge validation reused.

**Still open**
- Whether the first execution comparison uses the toy agent or a recipe from the original five (my suggestion: the toy agent first, then recipe R1).
- The agreement threshold for trusting gemma4 as a judge (my suggestion: Cohen's kappa of at least 0.6 against the humans on the pairs, written into the pre-registration before labelling).
