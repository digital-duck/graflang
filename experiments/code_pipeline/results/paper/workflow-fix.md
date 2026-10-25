# Workflow fix: what changed in the pipeline, and why

Status: implemented in the graflang cookbook and the LangGraph baseline; the spl arm is unchanged (it is not in the GraphLang paper's full run). Pre-fix pilot results are kept as the appendix baseline (`results/pilot.db`, `results/pilot-haiku.db`, `results/pilot-ollama.db`), and the pre-fix workflow files are saved in `results/paper/baseline-prefix/`.

## The problem

Two things in the pipeline discarded the signal that should have repaired a failed attempt.

1. **Retries did not use the failure.** On every cycle the pipeline regenerated the code from the specification alone. The tester's verdict (`[FAILED]` and its reason) never reached the next attempt. A retry was a fresh sample, not a repair.
2. **The improve step did not see the specification.** Its template took the code, the review feedback and the test result, and nothing about the required function name. So when the review suggested a clearer name, the improve step renamed the function, and the hidden tests then failed with a `NameError`. This was the dominant failure in every pilot (renamed functions in 10 to 11 of the failed pipeline runs with Haiku, and in most of the Qwen pipeline failures).

## The change

- **Improve step (`03_improve_code`):** takes the specification and states that the function name and signature must match it exactly. Used by `graflang` and `langgraph`.
- **Generate step on a retry (`01_generate_code`):** takes the previous attempt's code and its test result. On the first attempt both are empty, and the prompt says so. Used by `graflang` and `langgraph`.
- **Graph (`code_pipeline.graph.yaml`):** the loop carries `prior_code` (the code the tester saw) and `prior_test` (its verdict) from one iteration to the next, and the improve node reads the loop's specification.
- **LangGraph (`lg_pipeline.py`):** the same values come from the state.
- **Runtime (`procedures.py`):** a value that is `None` (a loop's carried value before the first iteration) is passed to the procedure as empty text, not as the string `None`.

Both pipeline arms send the same prompts, so `compare_prompts.py` will now report the coder and refactor templates as different from the SPL copy. That difference is the fix; the SPL arm keeps the old templates.

## What was checked

- `graf validate` passes on the changed graph.
- The test suite passes, except the 7 known Cedar failures.
- An end-to-end test with a fake model checks that the second attempt contains the first attempt's code and test result, that the first attempt has no `None`, and that the improve step contains the specification.
- Real-model smoke test: see the note at the end of this file.

## Open points

- The fix changes the pipeline's behaviour on every task, so the pre-fix runs are a baseline, not a comparison with the same workflow.
- Retries now repair rather than resample, so the cycle counts and tester statistics are not directly comparable with the pre-fix runs.
- The improve step still gets only the review feedback as its `feedback`, and the test verdict only reaches the next generation; a same-cycle test-driven repair is not in this design.
