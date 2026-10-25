# Shared experiment: the code pipeline in three orchestrators

One workflow, the cookbook's `code_pipeline` (analyze the spec, then generate, review, improve and test in a loop of up to 3 cycles, then document), is run four ways on the same coding tasks and scored by the same hidden unit tests. The question it answers for both papers:

> Given identical prompts, model and gates, does the orchestrator (SPL.py, GraphLang, or a Python LangGraph program) change whether the final code is correct, what it costs, or how much has to be written and checked?

It is written to avoid the objections the TMLR Action Editor raised against the SPL paper: one independent oracle for every arm, no arm scored by a weaker criterion, a baseline written in Python with an orchestration library, and all code accounted for.

## Arms

| Arm | What runs | Orchestration |
|---|---|---|
| `single` | one call with the pipeline's `coder` prompt | none (the floor: no review, no gate) |
| `spl` | `SPL.py/cookbook/050_code_pipeline/code_pipeline.spl` via `spl3 run` | an SPL orchestrator |
| `graflang` | `cookbook/code_pipeline/code_pipeline.graph.yaml` via `graf run` | a graph |
| `langgraph` | `lg_pipeline.py`, a LangGraph `StateGraph` | Python |

**Held equal.** The model and the adapter (`claude_cli`, the same CLI for all four), the eight step prompts (the `spl` and `graflang` arms run the same `.spl` files; `langgraph` reads its prompts out of those files, so they cannot drift), `clean_code` post-processing, the `[READY]` gate, the `[PASSED]` retry gate, `max_cycles=3`, and `check_closure=false` (the closure check does not touch the code). The tasks, their order and the spec text are identical.

**Not equal, on purpose.** The orchestration code itself. The SPL and GraphLang arms also call the step workflows through SPL.py's executor, and SPL.py writes its checkpoint database unless told not to (`--persistence none`).

## Tasks and oracle

HumanEval (164 Python problems, hidden unit tests), committed in `data/` (source, license and checksum in `data/README.md`). The spec every arm gets is the problem's signature and docstring plus one instruction line (`tasks.py`). The tests are never shown to any arm.

`oracle.py` runs the final code plus the tests in a separate process. A task passes only if the process exits 0 within 10 s. No code, a missing function, a wrong answer, a crash and a timeout all count as failures; a run that stops at the spec gate (`[READY]` never appears) counts as a failure too. `python run.py --verify-oracle` checks that all 164 canonical solutions pass and that a do-nothing stub passes none (done: no canonical failures, no stub passes).

The oracle executes model-written code. It is not a security sandbox (see the docstring); run the experiment in a container or throwaway account if that matters.

## What is measured

Primary: **pass rate against the hidden tests**, per arm, over (task, repetition) runs, with Wilson intervals; the paired per-task difference between arms with a bootstrap interval. Unparseable or missing output is a failure; nothing is excluded.

Secondary:
- **The pipeline's own tester vs the oracle.** Step 4 of the pipeline is an LLM acting as a test suite, not executed tests. How often it says `[PASSED]` on code the hidden tests reject is the same "pass rate measures the wrong thing" problem the AE found in SPL's solver arm, measured here directly.
- Wall time per run (median) and failures by kind (tests, no code, error).
- Orchestration size: executable lines of the graph YAML, the SPL orchestrator and the LangGraph file; the shared prompt files are counted once, so prompts are not charged to one arm. Lines are a crude proxy for effort; the aim is to account for everything, not to claim a ratio.

Not measured, and not claimed: robustness to prompt injection, human auditing time, or anything about models other than the ones run. `graf validate`'s guard check does not apply to this graph (it has no risky node), so this experiment says nothing about safety.

## Expected result, stated before the run

The three pipeline arms run the same prompts with the same gates, so I expect their pass rates to be statistically indistinguishable, and any difference to come from run-to-run model variance. A difference larger than noise would point to a behavioural bug in one orchestrator (for example the graph's loop passing a different input), and that would itself be a finding. I also expect the pipelines to beat `single` only slightly, and the LLM tester to pass some wrong code. If the result is "no difference", the papers' case for graph orchestration rests on what is not correctness (checkability, guards, size), and should say so.

## Run

```bash
pip install -e ".[dev]" && pip install -r requirements.txt     # requirements.txt: langgraph
pip install -e /path/to/SPL.py
python run.py --verify-oracle
python run.py --n 20 --reps 1 --model claude-haiku-5-5 --out results/pilot.jsonl      # a fixed random sample of 20 tasks
python analyze.py results/pilot.jsonl
```

Runs are sequential and resumable; the arm order is shuffled per task and repetition. Real LLM calls, so this costs money and time: see `results/` for measured timings. Raw results (`results/*.jsonl`, each row holds the generated code) are committed so the analysis can be redone without calling a model.

## Files

| File | Role |
|---|---|
| `tasks.py` | HumanEval download, the fixed sample, the spec text |
| `oracle.py` | the hidden-test oracle |
| `arms.py` | the four arms |
| `lg_pipeline.py` | the LangGraph baseline |
| `run.py` | the runner |
| `analyze.py` | the summary |
