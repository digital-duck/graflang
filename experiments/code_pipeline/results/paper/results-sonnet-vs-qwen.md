# Pilot results: the code pipeline with two models (claude-sonnet-5-5 vs qwen2.5-coder-16k)

Status: pilot, one run per (task, arm), now with a Haiku control. Source data: `results/pilot.db` (Claude Sonnet, 80 runs) and `results/pilot-ollama.db` (Qwen, 80 runs). Full analysis output: `analysis-raw.txt` in this folder. Not yet peer reviewed.

## Setup

- **Tasks:** 20 HumanEval problems, the fixed random sample with seed 0 (task numbers 10, 24, 35, 41, 55, 64, 66, 72, 77, 91, 98, 103, 107, 122, 124, 129, 130, 136, 149, 154). Each task is scored by its hidden unit tests, which no arm sees. Scorer checked: all 164 canonical solutions pass, a do-nothing stub passes none.
- **Arms:** `single` (one coder call), `spl` (SPL.py's `code_pipeline.spl`), `graflang` (`code_pipeline.graph.yaml`), `langgraph` (the same pipeline as a Python LangGraph program). All arms send the same prompts (the `.spl` templates; checked by `compare_prompts.py`) and use the same gates, retry limit (3 cycles) and post-processing.
- **Models:** `claude-sonnet-5-5` through `claude_cli`; `qwen2.5-coder` through Ollama with a 16,384-token context window (a variant of the base model; Ollama's default 2,048-token window silently truncates longer prompts, so those runs were discarded).
- **Spec:** the same text for every arm. Trailing whitespace is stripped; before this fix the two arms received different inputs, and those runs are not used.
- **Timing caveat:** the two pilots ran partly at the same time on one machine, so wall-clock times are not comparable between models.
- **Claude session limit:** 7 of the Claude runs stopped on the account's session limit. They were re-run after the limit reset; the results below are from the re-run, not from the errors.

## Results

### Pass rate (hidden tests), 20 tasks, one run each

| Arm | Sonnet 5.5 | Qwen 16k | 95% CI (Sonnet) | 95% CI (Qwen) |
|---|---|---|---|---|
| single | 95% (19/20) | 80% (16/20) | 76–99% | 58–92% |
| spl | 95% (19/20) | 55% (11/20) | 76–99% | 34–74% |
| graflang | 95% (19/20) | 50% (10/20) | 76–99% | 30–70% |
| langgraph | 85% (17/20) | 30% (6/20) | 64–95% | 15–52% |

Within a model, paired exact McNemar tests (same tasks):

| Comparison | Sonnet 5.5 | Qwen 16k |
|---|---|---|
| single vs spl | b=1, c=1, p=1.00 | b=5, c=0, p=0.06 |
| single vs graflang | b=1, c=1, p=1.00 | b=6, c=0, p=0.03 |
| single vs langgraph | b=3, c=1, p=0.63 | b=11, c=1, p=0.006 |
| spl vs graflang | b=0, c=0, p=1.00 | b=4, c=3, p=1.00 |
| spl vs langgraph | b=3, c=1, p=0.63 | b=7, c=2, p=0.18 |
| graflang vs langgraph | b=3, c=1, p=0.63 | b=6, c=2, p=0.29 |

(b = only the first arm passed; c = only the second. With 20 tasks these tests have little power; a non-significant result is not evidence of equality.)

### Same arm, different model

Tasks on which the two models disagree on pass/fail, for the same arm: single 5/20, spl 10/20, graflang 9/20, langgraph 15/20.

### Partial correctness

Share of the hidden assertions that held, averaged over runs where at least one assertion ran: Sonnet 99–100% for every arm; Qwen single 90%, spl 80%, graflang 88%, langgraph 80%.

### Failure kinds (runs not passing)

- **Sonnet:** single 1 wrong answer; spl and graflang 1 "no code" each (task 149, see below); langgraph 2 renamed the function, 1 wrong answer.
- **Qwen:**
  - renamed function: spl 3, graflang 6, langgraph 7;
  - wrong answer: single 4, spl 3, graflang 4, langgraph 3;
  - no code: spl 3, langgraph 4. Of these 7, 4 are genuine `[VAGUE]` verdicts from the spec analyst, and 3 are correct `READY` verdicts written in bold without square brackets (`**Verdict: READY**`), which the gate, looking for `[READY]`, rejects.

### Tester behaviour (pipeline arms)

The pipeline's own LLM tester is compared with the hidden tests cycle by cycle.

- **Sonnet:** spl 26 cycles, the tester said PASSED on 19 (0 wrong), FAILED on 7 (5 of those were correct code); graflang 27 cycles, 6 false FAILED; langgraph 33 cycles, 10 false FAILED.
- **Qwen:** spl 23 cycles, PASSED on 15 (4 wrong), FAILED on 8 (1 correct); graflang 32 cycles, PASSED on 17 (7 wrong), FAILED on 15 (3 correct); langgraph 23 cycles, PASSED on 14 (8 wrong), FAILED on 9 (2 correct).

Each false FAILED costs a cycle and about four LLM calls. A PASSED on code the hidden tests reject sends wrong code on as final output.

### Cost (estimated)

| Arm | Sonnet calls / tokens per run | Qwen calls / tokens per run |
|---|---|---|
| single | 1.0 / 278 | 1.0 / 282 |
| spl | 8.1 / 7,510 | 7.3 / 4,207 |
| graflang | 8.3 / 7,421 | 9.4 / 5,024 |
| langgraph | 9.6 / 9,260 | 7.2 / 4,369 |

Tokens are the dd-llm estimate (characters / 4), because the claude_cli adapter does not report usage. They compare arms but are not billing figures.

## Interpretation

1. **The model made the largest difference in pass rate.** Sonnet passes 85–95% of tasks in every arm; Qwen passes 30–80%, and the gap is largest where the pipeline is involved.
2. **Single calls are close.** Sonnet 95% against Qwen 80%. Most of the model gap is in the multi-step arms.
3. **Qwen's pipeline failures are mainly renaming and gate formatting.** The improve step renames the function the spec asks for, and the spec gate rejects a correct verdict written in bold. Both are workflow properties that the same model handles more reliably; they are not reasoning failures of the orchestrator as such.
4. **Within Sonnet, the three pipelines are not distinguishable at this sample size.** spl and graflang agree on every task. langgraph is one to two tasks lower, and not significantly so.
5. **Within Qwen, single beats each pipeline (significantly for graflang and langgraph),** while spl, graflang and langgraph do not differ significantly from one another.
6. **The pipelines' own tester is unreliable with both models.** It rejects correct code in 5–10 cycles per arm for Sonnet and 1–3 for Qwen, and it accepts wrong code in 0–1 cycles for Sonnet and 4–8 for Qwen.

## Control: claude-haiku-5-5 through claude_cli

Same adapter as Sonnet, same 20 tasks, same prompts, one run per cell (`results/pilot-haiku.db`, analysis in `analysis-haiku.txt`; the all-models comparison is in `analysis-all-models.txt`). This separates model strength from the adapter for the Claude models.

| Arm | Haiku 5.5 | Sonnet 5.5 | Qwen 16k (Ollama) |
|---|---|---|---|
| single | 100% (20/20) | 95% (19/20) | 80% (16/20) |
| spl | 90% (18/20) | 95% (19/20) | 55% (11/20) |
| graflang | 80% (16/20) | 95% (19/20) | 50% (10/20) |
| langgraph | 70% (14/20) | 85% (17/20) | 30% (6/20) |

- **Single call:** Haiku is the best arm of any model here, which matches the pilot's finding that single-call coding is not what separates the models.
- **Pipelines:** Haiku trails Sonnet by 5 to 15 points in the three pipeline arms. Paired tests within Haiku: single beats langgraph (b=6, c=0, p=0.031) and beats graflang and spl in the same direction but not significantly; the three pipelines do not differ significantly from each other.
- **Failure kinds:** of the 12 failed pipeline runs with Haiku, 11 are renamed functions, the same bug as with Sonnet and Qwen.
- **What the control shows:** within one adapter, model strength changes the pipeline results by a modest amount. The Qwen gap (30 to 80 points in the pipelines) is much larger, so it is not explained by model strength alone, but it is also not separable from the adapter and the context setting, since Qwen differs on both.
- **Tester behaviour:** Haiku's tester rejected correct code in 11 langgraph cycles and 5 to 6 in spl and graflang, with fewer wrong acceptances than Qwen's.

## Limitations

- **One run per task and arm,** 20 tasks. The consistency analysis (repeated runs) needs at least two repetitions and is not available.
- **Model and adapter are confounded for Qwen.** Sonnet and Haiku share `claude_cli`, so their comparison is clean. Qwen runs through Ollama with a non-default context window, so its gap to the Claude models cannot be attributed to the model alone.
- **Paired-test power is low** with 20 tasks; differences smaller than about 25 percentage points are not detectable.
- **The pipelines carry a known wiring bug** (the improve step never sees the spec or the test verdict), so all pipeline numbers measure the pipeline as wired. Its share of failures is reported above (renamed functions).
- **The signature-match figure in the hygiene section** checks argument names only. A renamed parameter still passes the tests, so this measure is weak and is not used in the interpretation above.
- **Wall-clock times** are affected by the two pilots running at the same time, and by session-limit waits, so they are not used for comparison.
- **Workflow issues found during the pilot** are shared by all three pipeline arms and are part of what was measured: the improve step never sees the spec or the test verdict, so the tester's rejection cannot prevent a rename (see the pipeline's `refactor` template); and the spec gate requires the exact bracketed token. Fixing either would change every arm and needs a rerun.
- **No human evaluation** of code quality or audit effort.
