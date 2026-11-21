# code_pipeline (layered, repository-capable)

A spec in, a verified project folder and its documentation out. A one-shot prompt cannot write a repository (the reply is too long), so the work is split: a
**build plan** of small tasks first, then the project **one task at a time**.

```
code_pipeline.graph.yaml     preflight -> analyze -> build -> finish -> exit        (stop on the error exit `vague`)
  analyze/                   spec -> build plan (JSON list of tasks); a checker judges it and what is wrong goes back for another draft (self-healing, max_plan_rounds);
                             error exit `vague` (E_PLAN_VAGUE) when no usable plan comes out
  build/                     a loop over the plan's tasks: write the task's files, merge them into the project, RUN the whole project in a container, one fix pass if it fails
  finish/                    document the code, then optionally derive a spec back from it and judge it against the original (SPL procedures 05-07; needs SPL.py)
tools/                       check_plan.py, task_context.py, collect_files.py (split a reply into files and merge them), render_files.py, verify_project.py, verify.Dockerfile
```

A **plan** is JSON: a `summary`, `assumptions`, and `tasks`, each with an `id`, `title`, `description` (the functions and signatures to write), `files` (at most 5), `depends_on` and `acceptance`.
`tools/check_plan.py` refuses a plan with thin descriptions, tasks without files or acceptance, a file owned by two tasks, a task depending on a later one, too many tasks, or (Python) no
test file; its list of complaints is the next draft's feedback. Each task's writer sees the plan's summary, its own task and the files written so far, so no reply is larger than one task.

Outputs: `docs` (TEXT), `plan` (the build plan, JSON), `code` (FILES: real files in `.graf/codes/<run>/`, any layout, e.g. `backend/` and `frontend/`) and `report` (the last
verification of the whole project, `[PASSED]` or `[FAILED]`). The run's other files (`result.json`, every node's output under `nodes/`: the drafts of the plan, each task's reply)
are in `.graf/outputs/<run>/`.

```bash
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml          # cheap, capped
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind <a file with limits.max_llm_calls> \
    --param spec="a Flask backend with /api/todos (list, add) and a plain HTML/JS frontend that uses it"
```

Inputs: `spec`, `lang` (python), `reference` (API facts the model cannot know), `smoke` (Python run against the real libraries after each task's tests), `max_plan_rounds` (3), `check_closure` (true).
Calls: 1 to `max_plan_rounds` for the plan, 1 per task (+1 when its check fails), then 3 for `finish` (closure check on) or 1.

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
