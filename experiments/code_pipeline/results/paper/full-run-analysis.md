# Full run: the code pipeline under GraphLang, LangGraph and a single call

*Claude Sonnet 5.5 and Claude Haiku 4.5, 60 HumanEval tasks, one repetition each. Written 2026-10-26 from the two completed runs. Not peer reviewed.*

**Sources.** `results/full-claude-sonnet-5-5.db` and `results/full-claude-haiku-4-5.db` (180 runs each), and the reports `full-claude-sonnet-5-5-20261025-204421.txt` and `full-claude-haiku-4-5-20261025-225101.txt` in this folder. (`full-claude-sonnet-5-5-20261025-124453.txt` is an early six-task report from an interrupted attempt; it is superseded.) The design, arms and metrics are in `../../README.md`. Figures not in the reports were computed directly from the two databases and from the run logs.

---

## 1. Summary

1. **The orchestrator did not change correctness.** GraphLang and LangGraph, given the same prompts and gates, solved the same tasks. On Sonnet they have identical task-level outcomes (0 of 60 tasks differ). On Haiku they differ on 2 of 60 (McNemar p = 0.5). The result stated before the run ("indistinguishable pass rates; any difference is run-to-run variance") holds.
2. **The pipeline did not beat one call, and cost a great deal more.** A single `coder` call passed 60/60 (Sonnet) and 58/60 (Haiku). The pipelines passed 59/60 and 56 to 58/60. There is no task where a pipeline passed and the single call failed. The pipelines used 7 to 8 calls, 14 to 21 times the tokens and about 13 times the time.
3. **The pipeline's own tester is the weak part.** Across the four pipeline-by-model cells, 71% of its `FAILED` verdicts (25 of 35) were on code the hidden tests accept, each costing a retry cycle. Only 5 of 240 pipeline runs were repaired by a retry.
4. **The size claim does not favour the graph.** The GraphLang workflow is 145 lines of YAML; the LangGraph program is 81 lines of Python. If the GraphLang paper argues for the graph, it has to do so on checkability and safety, not on correctness, cost or size.
5. **The benchmark is saturated for these models.** With a ceiling near 100%, this experiment can show "no harm" and "equivalent within 10 points". It cannot show a benefit from review and retry, which is what the pipeline exists to provide.

---

## 2. Setup (what was run)

- **Tasks:** HumanEval, a stratified sample of 60 (20 per complexity group, by the branch count of the reference solution), seed 0, one repetition. Scored by the hidden unit tests in a separate process (`oracle.py`); no arm sees the tests.
- **Arms:** `single` (one coder call), `graflang` (`code_pipeline.graph.yaml` via `graf run`), `langgraph` (`lg_pipeline.py`). The `spl` arm was not run (it belongs to the TMLR revision; see the README), so **this run says nothing about GraphLang versus SPL.**
- **Held equal:** model and adapter (`claude_cli`), the step prompts (the two pipeline arms use the same templates), the `[READY]` spec gate, the `[PASSED]` retry gate, `max_cycles=3`, `clean_code`, and the deterministic function-name check.
- **Workflow:** the post-fix version (improve step sees the spec; a retry receives the previous code and its test result; see `workflow-fix.md`).
- **Tokens** are estimated as characters divided by four (the adapter reports no usage). They compare arms; they are not billing figures.

---

## 3. Results

### 3.1 Pass rate (hidden tests)

| Model | Arm | Passed | Rate | 95% CI (Wilson) | Failures |
|---|---|---|---|---|---|
| Sonnet 5.5 | single | 60/60 | 100.0% | 94.0 to 100 | none |
| | graflang | 59/60 | 98.3% | 91.1 to 99.7 | 1 wrong answer |
| | langgraph | 59/60 | 98.3% | 91.1 to 99.7 | 1 wrong answer |
| Haiku 4.5 | single | 58/60 | 96.7% | 88.6 to 99.1 | 1 wrong answer, 1 renamed |
| | graflang | 56/60 | 93.3% | 84.1 to 97.4 | 3 wrong answer, 1 renamed |
| | langgraph | 58/60 | 96.7% | 88.6 to 99.1 | 1 no code, 1 renamed |
| both, pooled | single | 118/120 | 98.3% | 94.1 to 99.5 | |
| | graflang | 115/120 | 95.8% | 90.6 to 98.2 | |
| | langgraph | 117/120 | 97.5% | 92.9 to 99.1 | |

The intervals overlap heavily everywhere.

**Paired comparisons (same tasks).** McNemar, b = only the first arm passed, c = only the second:

| Pair | Sonnet | Haiku |
|---|---|---|
| single vs graflang | b=1, c=0, p=1.0 | b=2, c=0, p=0.5 |
| single vs langgraph | b=1, c=0, p=1.0 | b=0, c=0, p=1.0 |
| graflang vs langgraph | b=0, c=0, p=1.0 | b=0, c=2, p=0.5 |

Paired equivalence (TOST, margin ±10 points, alpha 0.05) holds for every pair on both models. That margin is wide: with 60 tasks near the ceiling, the test rules out differences larger than 10 points and says nothing about smaller ones.

**By complexity group.** The failures sit in the medium and high groups; the low group is 20/20 for every arm and model. With one or two failures per cell, this is not enough to say that complexity matters.

### 3.2 Which tasks failed, and why

Four tasks account for every failure in both models (10 failed runs):

| Task | Who failed | Cause |
|---|---|---|
| `HumanEval/78` (`hex_key`) | Sonnet graflang and langgraph; Haiku graflang | **Over-engineering by the pipeline (verified).** On Sonnet the single call returns three lines and passes. The pipeline's review and improve steps add input validation (`TypeError` for a non-string, `ValueError` for characters that are not hex digits) that the spec did not ask for. The hidden test's last assertion calls `hex_key([])` and expects 0 (the spec says the input is a string or the empty string), and the added check raises `TypeError` (verified by running the stored code: 6 of 7 assertions hold). The pipeline's tester said `[PASSED]`. |
| `HumanEval/75` | Haiku graflang | 4 of 10 assertions held; the tester said `[PASSED]`. The single call passed. |
| `HumanEval/50` | Haiku, all three arms | **Harness convention.** The hidden test calls `encode_shift`, which is defined in the prompt, not in the function to write. The oracle prepends only the prompt's imports, so code that does not re-emit `encode_shift` fails with `NameError`. Sonnet re-emitted it in every arm; Haiku did not. |
| `HumanEval/32` | Haiku single and graflang (99 of 100 assertions); Haiku langgraph (no code) | One of 100 randomised assertions fails on a numeric tolerance. The langgraph run did not pass the spec gate. |

Of the 10 failed runs, 6 are on `/32` and `/50`, where every Haiku arm failed (a harness convention and a numeric tolerance, not the pipeline). The other 4 (`/78` on both models, `/75` on Haiku) are pipeline-only failures on tasks the single call passed. For `/78` the mechanism is verified: **review and improve make the code longer and more defensive, and that can break a hidden test that a three-line solution passes.** `/75` was not examined in the same detail. This is consistent with the code-hygiene numbers below.

### 3.3 Cost

| | calls / run | tokens / run (est.) | median seconds / run |
|---|---|---|---|
| Sonnet single | 1.0 | 343 | 4.3 |
| Sonnet graflang | 7.0 | 6,630 | 58.9 |
| Sonnet langgraph | 7.5 | 7,295 | 57.9 |
| Haiku single | 1.0 | 415 | 6.8 |
| Haiku graflang | 7.7 | 5,632 | 89.5 |
| Haiku langgraph | 7.8 | 5,869 | 83.6 |

Relative to the single call, the pipelines use 7 to 8 times the calls, 14 to 21 times the tokens (Sonnet 19 to 21 times, Haiku 14 times) and 12 to 14 times the median time. For tokens per passing run: single 343, graflang 6,742, langgraph 7,419 on Sonnet.

The two pipeline arms cost about the same. GraphLang used slightly fewer cycles (Sonnet 1.02 against 1.13; Haiku 1.17 against 1.24) and about 9% fewer tokens on Sonnet. The cause is not established: both arms send the same prompts, there is one run per cell, and Sonnet's LangGraph tester happened to reject correct code seven times against one for GraphLang. I would not read it as a property of either orchestrator.

**A timing outlier that is not a GraphLang cost.** The Haiku report shows a mean of 63.8 seconds per call for GraphLang against 13.6 for LangGraph, and the database shows one GraphLang run (`HumanEval/146`) at 23,226 seconds. This is the machine going to sleep: the log shows the run at 6h27m while the surrounding runs took about a minute, and the kernel log records an S3 suspend and resume (06:44) before that run finished at 06:46. Without that run the mean seconds per run are 104.0 (graflang) and 106.3 (langgraph) for Haiku. The medians in the table are not affected. The run passed (1 cycle, 7 calls). Any wall-clock figure from this run should use medians or exclude that run.

### 3.4 What the retry loop did

| | Passes on cycle 1 | Fixed by a retry | Never passes | Passed then failed | Retries after a cycle the hidden tests accept |
|---|---|---|---|---|---|
| Sonnet graflang | 58/59 | 0 | 1 | 0 | 1 |
| Sonnet langgraph | 58/60 | 1 | 1 | 0 | 7 |
| Haiku graflang | 55/60 | 1 | 4 | 0 | 7 |
| Haiku langgraph | 55/59 | 3 | 1 | 0 | 8 |

- **Repairs are rare.** 5 of 240 pipeline runs were fixed by a retry, against 23 retries triggered on code that was already correct.
- **No regressions.** No run passed on one cycle and ended failing.
- **The tester is mostly wrong when it says `FAILED`.** Across the four cells it said `FAILED` on 35 cycles, and the hidden tests accept the code on 25 of them (71%). It said `PASSED` on 236 cycles, and the hidden tests reject the code on 7 (3%). Each wrongly rejected cycle costs about four more calls.
- The pre-fix workflow could not repair (a retry regenerated from the spec alone). The post-fix retries do carry the failure forward, but with these models there was little left to repair, so this run cannot show whether the fix helps.

### 3.5 Partial correctness, hygiene and similarity

- **Partial correctness:** every arm holds 98.7% to 100% of the hidden assertions on average, and almost every failure is a near miss, except the Haiku `renamed` runs (no assertion ran).
- **Code size:** the pipelines more than triple the final code on Sonnet (mean 36 to 37 lines against 10 for single) and add about a third on Haiku (21 to 22 against 16). Argument names match the spec in 93% of pipeline runs against 100% for single (the improve step renames some arguments).
- **Similarity:** on Sonnet the pipelines' code is far from the single call's (difflib ratio 0.19 to 0.21) and only 0.36 between the two pipelines, despite identical prompts, so sampling variance in the review and improve steps is large. On Haiku all pairs are near 0.68.
- **Reliability:** no errors and no timeouts in any arm. One no-code run (Haiku langgraph, `HumanEval/32`, stopped at the spec gate). The spec gate is itself a sampled judgement, as the smoke tests found.

### 3.6 Orchestration size

| | lines |
|---|---|
| GraphLang workflow (`code_pipeline.graph.yaml`) | 145 (YAML) |
| LangGraph program (`lg_pipeline.py`) | 81 (Python), plus a pipeline-agnostic run harness |
| Shared step prompts and wrappers | 359 (eight `.spl` files), counted once |

The graph is larger than the LangGraph program, so a claim of "less to write" is not supported by this experiment.

---

## 4. Findings, and what they support

| # | Finding | Supported by |
|---|---|---|
| 1 | GraphLang and a Python LangGraph program give the same correctness on the same workflow | Sonnet 0/60 discordant, Haiku 2/60 (p=0.5), TOST equivalent on both models |
| 2 | GraphLang runs the workflow reliably | 180 runs per model, no errors and no timeouts (apart from the sleep artefact) |
| 3 | Review, improve and retry add no accuracy on HumanEval with these models | single passes ≥ every pipeline arm; no task where a pipeline passed and single failed |
| 4 | The pipeline costs about 7× the calls, 14 to 21× the tokens, 13× the time | §3.3 |
| 5 | The LLM tester rejects correct code more often than it catches wrong code | 25 of 35 `FAILED` verdicts wrong; 7 of 236 `PASSED` wrong |
| 6 | Extra review can break correct code by adding unrequested behaviour | `HumanEval/78` (cause verified by running the stored code), three failing runs; code length 3.6× on Sonnet |
| 7 | GraphLang does not shorten the orchestration | 145 lines YAML against 81 lines Python |

**For the GraphLang paper.** Findings 1 and 2 are the claim this experiment supports: the graph form costs nothing in correctness or reliability compared with an orchestration library. Finding 3 and the saturation (§5) mean the paper should not claim that the pipeline, or graph orchestration, improves results. Whatever case it makes for the graph rests on what this experiment did not measure: validation before running (`graf validate`), guards and policy on mutation, and traces. The README already says this; the data now confirms it.

---

## 5. Limits and threats to validity

1. **Saturation.** Sonnet single scores 100%. A pipeline cannot improve on that, and a ±10-point margin on 60 tasks cannot detect a small difference in either direction. The earlier pilot with a weaker model (Qwen 16k, 20 tasks) is where the arms differed (single 80%, spl 55%, graflang 50%, langgraph 30%); a model of that strength, or a harder benchmark, is where a pipeline benefit or harm would show.
2. **One repetition per cell.** Run-to-run variance is not measured (report item 6 says so), so the small cycle and token differences between the two pipelines cannot be called systematic.
3. **The workflow fix was designed on pilot tasks.** The fix (improve sees the spec; retry sees the previous attempt) was written after the pilot's failures, and 8 of the 20 pilot tasks are in the full sample of 60. A held-out sample would be cleaner.
4. **No clean before and after.** The pilot (pre-fix) and the full run (post-fix) use different task sets and different sizes, and the models differ: the Haiku pilot used `claude-haiku-5-5`, while the full run deliberately used the less capable `claude-haiku-4-5`. The two should not be compared as a controlled test of the fix. A fair test would rerun the pre-fix workflow on these 60 tasks.
5. **The oracle and prompt helper functions.** `oracle.py` prepends only the prompt's imports, not helper functions the prompt defines (`HumanEval/50`'s `encode_shift`, and `poly` in `/32`). A model that does not repeat a helper fails, whichever arm it is in. This applies equally to every arm, so it does not bias the comparison, but it makes some failures a convention of the harness rather than an error in the code.
6. **HumanEval may be in the models' training data**, which would also explain the ceiling. Nothing here measures this.
7. **Token counts are estimates** (characters ÷ 4), and wall-clock includes the cost of the CLI adapter.
8. **No SPL arm and no other model families.** Nothing here applies to SPL.py, to open models, or to safety (the README notes that `graf validate`'s guard check does not apply to this graph).
9. **Wall-clock integrity.** One run includes a machine sleep (§3.3). Use medians, or run long batches under `systemd-inhibit`.

---

## 6. Suggested next steps

1. **Repeat with `--reps 3`** on the same 60 tasks to measure run-to-run variance (needed for finding 1 to be stronger than "indistinguishable on one run").
2. **Add a regime where the arms can differ:** a weaker model (the earlier pilot used Qwen 16k) or a harder benchmark, on the same arms. This is where review and retry could show a benefit, or harm.
3. **Run the `spl` arm** so the GraphLang paper and the TMLR revision share the same table.
4. **Make the pre/post-fix comparison fair** by rerunning the pre-fix workflow (`baseline-prefix/`) on these 60 tasks.
5. **Look at the tester.** 71% wrong `FAILED` verdicts is the single largest cost in the pipeline. Gating retries on a deterministic check (run the spec's own examples) instead of an LLM verdict would test whether that cost is avoidable.
6. **Constrain the improve step** so that it does not add validation or behaviour the spec did not ask for (`HumanEval/78`), and see whether the gap between single and pipeline closes.
7. **Prepend the prompt's helper functions in the oracle**, or report `/32` and `/50` as a separate category, before the numbers go into a paper.
8. **Reproducibility notes for the paper:** commit these two databases (they hold every generated program, so the analysis can be redone without a model), and record the model IDs exactly as they ran.
