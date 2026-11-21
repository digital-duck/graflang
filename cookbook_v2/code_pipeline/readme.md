# code_pipeline (layered, repository-capable)

A spec in, a verified project folder and its documentation out. A one-shot prompt cannot write a repository (the reply is too long), so the work is split: a
**build plan** of small tasks first, then the project **one task at a time**.

```
code_pipeline.graph.yaml     preflight -> analyze -> build -> appraise -> finish -> exit        (stop on the error exit `vague`)
  analyze/                   spec -> build plan (JSON: deliverables and a list of tasks); a checker judges its form and a model reviews it against the spec; what either finds
                             wrong goes back for another draft (self-healing, max_plan_rounds); error exit `vague` (E_PLAN_VAGUE) when no usable plan comes out
  build/                     a loop over the plan's tasks: write the task's files, merge them into the project, RUN the whole project in a container, one fix pass if it fails
  appraise/                  run the finished product once on the plan's demo (offline, in the container, with an offline stand-in for any model) and have a model judge what it
                             wrote against each deliverable's quality bar; a rejected product is reworked and appraised again (max_appraisals)
  finish/                    document the code, then optionally derive a spec back from it and judge it against the original (three prompts in `finish/prompts/`; no SPL.py needed)
tools/                       check_plan.py, run_demo.py, task_context.py, collect_files.py (split a reply into files and merge them), render_files.py, verify_project.py, verify.Dockerfile
```

A **plan** is JSON: a `summary`, `assumptions`, `demo` (a command that runs the finished product on a small sample, offline, and the output files to read), `deliverables` (what the spec asks the product to produce, each with the `mechanism` that makes its content and the `quality_bar` that separates good from merely present), and `tasks`, each with an `id`, `title`, `description` (the functions and signatures to write), `files` (at most 5), `depends_on` and `acceptance`.
`tools/check_plan.py` refuses a plan with thin descriptions, tasks without files or acceptance, a file owned by two tasks, a task depending on a later one, too many tasks, or (Python) no
test file; its list of complaints is the next draft's feedback. A plan that passes is then **reviewed by a model against the spec** (`prompts/critique_plan.md`): every capability must have a task, a deliverable that
needs prose or reasoning may not be a template that lists names (the product calls a model through an injectable interface; the tests use a fake), the acceptance tests must be able to fail.
The reviewer's defects feed the next draft too. It reports at most 5 blocking defects (no polish, no features the spec does not ask for) and approves a plan with none; if the rounds run out with
the reviewer still unhappy, the last draft that passed the checker is used anyway and the objections are given as the `plan_review` output. Each task's writer sees the plan's summary, its own task and the files written so far, so no reply is larger than one task.

Outputs: `docs` (TEXT), `plan` (the build plan, JSON), `appraisal` (the verdict on the product's real output: `[ACCEPTED]`, or `[REWORK]` with the defects), `code` (FILES: real files in `.graf/codes/<run>/`, any layout, e.g. `backend/` and `frontend/`) and `report` (the last
verification of the whole project, `[PASSED]` or `[FAILED]`). The run's other files (`result.json`, every node's output under `nodes/`: the drafts of the plan, each task's reply)
are in `.graf/outputs/<run>/`.

```bash
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml          # cheap, capped
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind <a file with limits.max_llm_calls> \
    --param spec="a Flask backend with /api/todos (list, add) and a plain HTML/JS frontend that uses it"
```

Inputs: `spec`, `lang` (python), `reference` (API facts the model cannot know), `smoke` (Python run against the real libraries after each task's tests), `max_plan_rounds` (3), `max_appraisals` (2), `check_closure` (true).
Calls: per plan round 1 draft (+1 review when the draft passes the checker), 1 per task (+1 when its check fails), per appraisal round 1 judgement (+1 rework when rejected), then 3 for `finish` (closure check on) or 1.

## The appraisal: is the output any good?

Passing the project's own tests says little about quality (a model writes tests that a listing passes). So after the build the product is **run** on the plan's `demo` and its output is **judged**.
The container has no network, so a product that calls a model runs here with an **offline stand-in** (the plan requires one, switched by an option or environment variable; it returns placeholder
text that quotes the start of the prompt it received). The judge (`appraise/prompts/appraise.md`) reads the output files and, for the model-written parts, the prompts the model would get: does the
product hand the model the facts and ask for the right thing, or does it enumerate names itself? It compares each deliverable with its `quality_bar`; a rejection lists defects, a developer pass fixes
them (`rework.md`), the project is verified again and the demo re-run. This catches a structural failure (a listing where prose is wanted, a missing feature, a crashing demo). It cannot judge the prose a
real model would write: for that run the product yourself with a real provider and read the result.

## The verify container

Every check runs the generated code in a Docker container (no network, read-only root, 1 GB, 2 CPUs). Build the image once, with Docker running:

```bash
docker build -t graflang-verify:py3.12 -f cookbook_v2/code_pipeline/tools/verify.Dockerfile cookbook_v2/code_pipeline/tools
```

The `preflight` step (first, no model call) runs the verifier on a trivial project, so a missing Docker or image stops the run before anything is billed. The image has the common libraries
(pytest, click, streamlit, networkx, flask, fastapi, pandas, ...); a generated project may import only what is in it, because the container has no network (the plan prompt tells the model
which libraries it may use; edit the prompt and `tools/verify.Dockerfile` together to change them). Under Docker Desktop the recipe folder must be under your home directory.
Python projects only: other languages are reported as not checked.

Related: `cookbook_v2/code_gen` is the one-call version (no plan, no run); `cookbook_v2/code_pipeline_spl` is the faithful port of `cookbook/code_pipeline` (SPL procedures, one block of code).
