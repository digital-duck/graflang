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

**Held equal.** The model and the adapter (`claude_cli`, the same CLI for all four), the step prompts (the `graflang` and `langgraph` arms use the same templates, and `langgraph` reads them from the `.spl` files so they cannot drift; the `spl` arm runs its own copy in SPL.py, see below), `clean_code` post-processing, the `[READY]` gate, the `[PASSED]` retry gate, `max_cycles=3`, and `check_closure=false` (the closure check does not touch the code). The tasks, their order and the spec text are identical.

**Workflow as used for the full run (after the fixes of 2026-10-25).** Two changes apply to the `graflang` and `langgraph` arms, and to no others. (1) The improve step receives the specification, so it keeps the function name. (2) A retry receives the previous attempt's code and its test result. In addition, the test step runs a deterministic name check first (`cookbook/code_pipeline/tools.py`): if the code does not define the function the specification names, the attempt fails at once and the LLM tester is not called. The `spl` arm keeps the pre-fix templates; its numbers belong to the TMLR revision. The pre-fix pilot results are kept as the appendix baseline, with the workflow files in `results/paper/baseline-prefix/` and the change described in `results/paper/workflow-fix.md`.

**Not equal, on purpose.** The orchestration code itself. The SPL and GraphLang arms also call the step workflows through SPL.py's executor, and SPL.py writes its checkpoint database unless told not to (`--persistence none`).

## Tasks and oracle

HumanEval (164 Python problems, hidden unit tests), committed in `data/` (source, license and checksum in `data/README.md`). The spec every arm gets is the problem's signature and docstring plus one instruction line (`tasks.py`). The tests are never shown to any arm.

`oracle.py` runs the final code plus the tests in a separate process. A task passes only if the process exits 0 within 10 s. No code, a missing function, a wrong answer, a crash and a timeout all count as failures; a run that stops at the spec gate (`[READY]` never appears) counts as a failure too. `python run.py --verify-oracle` checks that all 164 canonical solutions pass and that a do-nothing stub passes none (done: no canonical failures, no stub passes).

The oracle executes model-written code. It is not a security sandbox (see the docstring); run the experiment in a container or throwaway account if that matters.

## What is measured

Primary: **pass rate against the hidden tests**, per adapter, model and arm, over (task, repetition) runs, with Wilson intervals. Unparseable or missing output is a failure; nothing is excluded.

`python analyze.py results/pilot.db` reports, per adapter and model:

| # | What | What it shows | Where it comes from |
|---|---|---|---|
| — | pass rate, failure kinds, paired bootstrap difference between arms | the headline | `results.passed`, `reason` |
| 1 | **partial correctness**: share of the hidden assertions that held | a near miss versus a wrong program | `assert_passed`, `assert_total` (runs where no assertion ran are counted separately) |
| 2 | **trajectory across cycles**: pass on cycle 1, fixed by a retry, never passes, passed then ended failing, pass rate per cycle | whether retries help, and whether they break working code | `cycles_detail`: each cycle's code scored against the hidden tests |
| 3 | **cost**: LLM calls, tokens per run, tokens per passing run, run time per call | what a method costs | `llm_calls`, `prompt_tokens`, `output_tokens` |
| 4 | **code hygiene** of the final code: signature matches the spec, `__main__` block, unittest code, other top-level statements, prints, lines | whether the output is something you would merge | the stored `code`, parsed (no hidden tests) |
| 5 | **paired exact McNemar test** between arms on the same tasks | whether a difference is larger than chance | `passed` per task |
| 6 | **consistency across repetitions**: tasks that gave the same verdict every time | stability | repetitions per (task, arm); needs `--reps 2` or more |
| 7 | **similarity of the final code** between arms (difflib ratio) | whether arms wrote the same code when both passed | `code` |
| 8 | **reliability**: errors, no code, timeouts | practical robustness | `status`, `reason` |

Also reported: the pipeline's own LLM tester against the hidden tests (it says `[PASSED]` on code the tests reject), the cycles used, and the orchestration size (lines of the graph YAML, the SPL orchestrator and the LangGraph file; the shared prompt files are counted once).

**What each run keeps:** every cycle's code and tester verdict (`cycles_detail`), the LLM calls and tokens, and the run folder under `output/<adapter>/<model>/<task>/<arm>-rep<N>/`. For `spl`, the tester's code per cycle is read back from the prompt files; for `graflang`, from the saved node outputs (one file per iteration); for `langgraph`, from the state's history. The cycle verdicts come from the loops themselves; the last one is the pipeline's own verdict.

**Tokens** are the dd-llm estimate, characters divided by four. The claude_cli adapter does not report usage, so they compare arms, but they are not billing figures.

Not measured, and not claimed: robustness to prompt injection, human auditing time, or anything about models other than the ones run. `graf validate`'s guard check does not apply to this graph (it has no risky node), so this experiment says nothing about safety.

## Expected result, stated before the run

The three pipeline arms run the same prompts with the same gates, so I expect their pass rates to be statistically indistinguishable, and any difference to come from run-to-run model variance. A difference larger than noise would point to a behavioural bug in one orchestrator (for example the graph's loop passing a different input), and that would itself be a finding. I also expect the pipelines to beat `single` only slightly, and the LLM tester to pass some wrong code. If the result is "no difference", the papers' case for graph orchestration rests on what is not correctness (checkability, guards, size), and should say so.

## Smoke tests (task 98, one run per arm)

Run before the pilots, to check the setup, not to compare models. One task and one run per cell is far too little to rank anything; the point is to see that every arm runs, that the records are right, and where the arms disagree. Databases: `results/smoke-*.db`, kept for reference.

| Model | Arm | Result | Cycles | LLM calls | Tokens (est.) | Seconds | Note |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | single | pass | 1 | 1 | 165 | 4 | |
| claude-sonnet-5-5 | spl | pass | 1 | 7 | 5,606 | 56 | |
| claude-sonnet-5-5 | graflang | pass | 1 | 7 | 6,806 | 62 | prompts identical to spl (see below) |
| claude-sonnet-5-5 | langgraph | pass | 3 | 15 | 12,530 | 117 | tester said FAILED twice on code the hidden tests accept |
| qwen2.5-coder-16k | single | pass | 1 | 1 | 241 | 3 | |
| qwen2.5-coder-16k | spl | pass | 1 | 7 | 3,466 | 30 | |
| qwen2.5-coder-16k | graflang | pass | 2 | 11 | 5,880 | 49 | tester said FAILED on code the hidden tests accept |
| qwen2.5-coder-16k | langgraph | fail | 2 | 11 | 5,730 | 46 | renamed the function (`count_upper` missing) |
| gemma4 (latest) | single | pass | 1 | 1 | 252 | 2 | |
| gemma4 (latest) | spl | no code | 0 | 1 | 909 | 6 | reasoning used the whole 512-token budget; no code |
| gemma4 (latest) | graflang | no code | 0 | 1 | 909 | 6 | same |
| gemma4 (latest) | langgraph | pass | 1 | 7 | 3,895 | 71 | |

What these runs taught us, and what changed as a result:

- **Context window.** Ollama's default context is 2,048 tokens, and it silently drops the start of a longer prompt. The default qwen run therefore read only 2,050 of about 8,200 tokens, and its pipeline numbers are invalid (`results/smoke-qwen.db`; not used above). The `qwen2.5-coder-16k` model (a 16,384-token context) reads the full prompt. `run_pilot-ollama.sh` now checks this before every run.
- **Reasoning models.** Gemma 4 writes its reasoning into a separate field that counts against the output budget. The pipeline steps have budgets of 512 to 2,048 tokens, so the reasoning used up the budget and the pipelines returned no code, while `single` (a larger budget) passed. Gemma 4 is therefore not used for the pilot. Fixing it means raising the budgets for every model, which changes the shared workflow.
- **Spec input.** The SPL arm stripped the trailing newline of the spec and the graflang arm did not, so the two arms were given different inputs. Fixed in `tasks.spec_for`. The claude runs above (`results/smoke-capture.db`) predate this fix; the prompt comparison below is after it.
- **Same prompts.** After the fixes, the `spl` and `graflang` arms send the same seven prompts in the same order, the spec-only prompts match byte for byte, and every prompt keeps its template's fixed text (`compare_prompts.py`, `results/smoke-prompts.db`). Later prompts depend on earlier model output, so their text differs between runs; the token totals differ slightly for that reason.
- **Tester errors.** On both models the pipeline's LLM tester rejected code that the hidden tests accepted (langgraph and graflang). Each such rejection costs a cycle and about four calls. The per-cycle analysis counts them.
- **The spec gate is sampled too.** On the pilot's first pass, qwen's langgraph arm judged task 98 `[VAGUE]` and stopped with no code, while its graflang arm passed the same gate on the same prompt. That is a variation between runs of one model, so it counts as a result, not a bug to hide; the pilot's `no_code` column records it.
- **Function renaming.** A pipeline's improve step can rename the function the spec asked for, which the hidden tests then reject (`renamed` in the failure kinds). It happened on qwen with langgraph here, and on haiku in the earliest smoke test.

Variation across arms on one task is the reason to run more tasks; it says nothing yet about which arm is better.

## Run

### Setup

```bash
conda create -n graf python=3.11
conda activate graf

cd ~/projects/digital-duck/graflang

pip install -e ".[dev]" && pip install -r requirements.txt     # requirements.txt: langgraph
pip install -e ~/projects/digital-duck/SPL.py

cd experiments/code_pipeline
python run.py --verify-oracle        # no LLM: checks the scorer itself (all 164 canonical solutions must pass, a do-nothing stub must not); ~7 s
```

### Ollama: a model with a longer context window

Ollama's default context is 2,048 tokens, and it drops the start of a longer prompt without an error. Make a variant of the model with a bigger window once; the name then records the setting, and the pilot uses it like any other model:

```bash
printf 'FROM qwen2.5-coder:latest\nPARAMETER num_ctx 16384\n' > Modelfile.qwen16k
ollama create qwen2.5-coder-16k -f Modelfile.qwen16k
ollama show qwen2.5-coder-16k            # "context length" should be 16384 in the parameters
```

To check that the server really reads the whole prompt, send a longer one and compare the token count it reports with the count you sent (`prompt_eval_count` from `/api/generate`, or the `prompt_tokens` in the OpenAI-style reply). `run_pilot-ollama.sh` does this check before every run and stops if the model reads too little.

A bigger window costs memory, so pick the smallest that holds your longest prompt (16,384 covers the pipeline's prompts here). To remove the variant: `ollama rm qwen2.5-coder-16k`. The base model is unchanged.

### The pilot in one go: `run_pilot.sh`

Runs the four arms on five tasks (`98,107,10,24,35` by default), checks the scorer first, writes a report at the end, and is safe to leave running:

```bash
conda activate graf
nohup ./run_pilot.sh > /dev/null 2>&1 &      # submit and walk away
tail -f logs/pilot-*.log                      # follow it later
TASKS="1,2,3,4,5" MODEL=claude-sonnet-5-5 ./run_pilot.sh      # other tasks or model
TASKS="" N=20 ./run_pilot.sh                  # a fixed random sample of 20 instead of a list
TASKS="98,107,10,24,35,41,55" ./run_pilot.sh  # add tasks later: the stored ones are reported and skipped, only the new ones run
EXISTING=append TASKS="98" ./run_pilot.sh    # run a stored task again as one more repetition (the stored rows are kept)
./run_pilot.sh --dry-run                      # only the plan
```

Everything lands inside this folder: `logs/pilot-<time>.log` (what the script printed), `results/pilot.db` (one row per run), `results/pilot-report-<time>.txt` (the analysis), and `output/<adapter>/<model>/<task>/<arm>-rep0/` per run with `code.py` (what was scored) plus the arm's own logs, every prompt sent (`spl`), every node's output (`graflang`) or the final state (`langgraph`); see `arms.py`. `logs/` and `output/` are git-ignored. `TASKS` is exported to `run.py`, which also reads it (`--tasks` overrides it). A task already in the database for this model and arm is reported and skipped by default (`--existing skip`, so a rerun continues where it stopped); `--existing append` (`EXISTING=append` in the script) keeps the stored rows and adds new repetitions after the last stored one. It is resumable: run the same command again and it continues with the runs not yet in the database.

### All four arms (the pilot, by hand)

```bash
python run.py --tasks 98,107,10,24,35 --model claude-sonnet-5-5 --dry-run     # exactly these tasks; or --n 20 for a fixed random sample. The plan only: runs, already done, to do (no LLM)
python run.py --n 20 --reps 1 --model claude-sonnet-5-5      # a fixed random sample of 20 tasks; stored in results/experiment.db
python analyze.py results/experiment.db                      # one block per model
sqlite3 results/experiment.db "SELECT * FROM arm_summary"     # or query it directly
```

Results go to a SQLite database (`--db`, default `results/experiment.db`; the tables and the `arm_summary` view are in `store.py`): a `results` table with one row per (task, arm, repetition, model), and a `batches` table with one row per invocation. Runs are sequential and resumable (a run already in the database for the same task, arm, repetition and model is skipped, so rerunning the same command continues where it stopped); the arm order is shuffled per task and repetition. Real LLM calls, so this costs money and time: see `results/` for measured timings. Each row holds the generated code, so the database can be committed and the analysis redone without calling a model. `python run.py --import-jsonl results/smoke.jsonl` loads rows from an older run into the database.

Each arm below can be run alone with `--arms`, and by hand on one spec. The by-hand commands are the ones `arms.py` runs. Set the model and a spec first (here, the spec of the first HumanEval task):

```bash
export MODEL=claude-sonnet-5-5
export SPEC="$(python -c 'import tasks; print(tasks.spec_for(tasks.load_all()[0]))')"
```

### Arm `single`

One `coder` call with the pipeline's step-1 prompt, no review and no gate.

```bash
python run.py --arms single --n 2 --model $MODEL --db results/try.db     # two tasks, this arm only

# by hand: there is no command-line tool for this arm, so call it from Python
python -c "import os, arms; r = arms.run_single(os.environ['SPEC'], os.environ['MODEL']); print(r.code)"
```

### Arm `langgraph`

The same pipeline as a Python LangGraph program (`lg_pipeline.py`), with the same prompts.

```bash
python run.py --arms langgraph --n 2 --model $MODEL --db results/try.db

# by hand: there is no command-line tool for this arm either
python -c "import os, arms; r = arms.run_langgraph(os.environ['SPEC'], os.environ['MODEL']); print(r.code, r.cycles, r.pipeline_verdict)"
```

### Arm `spl`

SPL.py's orchestrator, run by `spl3 run`.

```bash
python run.py --arms spl --n 2 --model $MODEL --db results/try.db

# by hand: the code lands in $LOGS/target/python/code.py, the LLM tester's verdict in $LOGS/tests/python/result.md
export LOGS=/tmp/spl_logs
(cd ~/projects/digital-duck/SPL.py/cookbook/050_code_pipeline &&
 spl3 run code_pipeline.spl --adapter claude_cli --model $MODEL --persistence none --no-log \
     -p spec="$SPEC" -p pipeline_model=$MODEL -p check_closure=false -p log_dir=$LOGS)
```

### Arm `graflang`

The graph, run by `graf run`.

```bash
python run.py --arms graflang --n 2 --model $MODEL --db results/try.db

# by hand: the code lands in cookbook/code_pipeline/.grafr/logs/target/python/code.py, which every run shares (clear it between runs)
(cd ~/projects/digital-duck/graflang &&
 graf run cookbook/code_pipeline/code_pipeline.graph.yaml --llm claude_cli:$MODEL --no-log \
     --output-dir /tmp/graf_out --param spec="$SPEC" --param check_closure=false)
```


The `try.db` runs are for trying an arm; keep them in their own database (as above) and delete it afterwards, so they do not mix with the real results.


### auto-run

```bash
cd ~/projects/digital-duck/graflang/experiments/code_pipeline
conda activate graf
nohup ./run_pilot.sh > /dev/null 2>&1 &
tail -f logs/pilot-*.log
```

### full-run

Three arms (`single`, `graflang`, `langgraph`) on 20 tasks from each complexity group (60 tasks), one repetition, seed 0. Both models use `claude_cli` and their own database (`results/full-claude-sonnet-5-5.db`, `results/full-claude-haiku-4-5.db`). The two runs are started one at a time, since they share an account. Plan first, then start:

```bash
cd ~/projects/digital-duck/graflang/experiments/code_pipeline
conda activate graf

PER_GROUP=2 ./run_full.sh --dry-run                          # the plan for the default model (sonnet)
PER_GROUP=2 MODEL=claude-haiku-4-5 ./run_full.sh --dry-run   # the plan for haiku

# start the sonnet run in the background
nohup ./run_full.sh > /dev/null 2>&1 &              # uses MODEL=claude-sonnet-5-5 by default

# when it has finished, start the haiku run the same way
MODEL=claude-haiku-4-5 nohup ./run_full.sh > /dev/null 2>&1 &

tail -f logs/full-*.log                          # follow it
```

**What the dry run does.** `./run_full.sh --dry-run` checks that `python`, `spl3` and `claude` are on the PATH, makes one short real call to the model (a bad model ID stops here), runs the scorer self-check, prints the plan (tasks × arms × repetitions, and how many runs are already in the database), and exits without running any arm. It writes a log in `logs/`. `python run.py --dry-run` only prints the plan; it makes no model calls, but it creates the database file if it is missing.

**Limiting the size.** `PER_GROUP` sets the number of tasks per complexity group, so a smaller dry run is a subset of the full one:

```bash
PER_GROUP=2 ./run_full.sh --dry-run                    # 6 tasks, 18 runs
python run.py --tasks 98,107 --arms single,graflang,langgraph --model claude-haiku-4-5 --dry-run   # named tasks
```

About 180 runs per model, roughly 2.5 hours each. It resumes from the database if it stops, and error runs are retried. When the account reports a session limit, the batch stops at once with exit code 3 and writes no report (the chain above then does not start Haiku); rerun the same command after the limit resets. Each model's report is written to `results/paper/`. The pre-fix pilot results are the appendix baseline and are not part of this run.

## Files

| File | Role |
|---|---|
| `tasks.py` | HumanEval download, the fixed sample, the spec text |
| `oracle.py` | the hidden-test oracle |
| `arms.py` | the four arms |
| `lg_pipeline.py` | the LangGraph baseline |
| `../../cookbook/code_pipeline/tools.py` | the deterministic name check (shared with the graph's procedures) |
| `run.py` | the runner (writes to SQLite) |
| `run_pilot.sh` | the pilot in one command: all four arms, logs, report |
| `run_full.sh` | the full run: three arms on the stratified sample, logs, report |
| `store.py` | the database: schema, `arm_summary` view, read and write helpers |
| `analyze.py` | the summary |
