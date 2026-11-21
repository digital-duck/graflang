# cookbook_v2: recipes in the layered form

Twelve recipes from `cookbook/` and one new one (`code_gen`), rewritten as a short top graph plus composites, each composite in its own subfolder with the prompts, procedures and
policies it uses. The originals in `cookbook/` are left alone (the experiments and many tests run them). Status and what each port taught us:
`docs/DEV/DESIGN/graflang-recipes.md`. The design: `docs/DEV/DESIGN/graflang-layers.md`.

| Recipe | Top level reads | Composites |
|---|---|---|
| code_gen | write, split | none: one model call and a file splitter; the output is a project folder (`.graf/codes/<run>/`) |
| code_pipeline | preflight, analyze, build, appraise, finish | **repository-capable**: `analyze` (the spec -> a build plan of small tasks, self-healing, exit `vague`), `build` (a loop over the tasks: write, merge, RUN the project in a container, fix), `appraise` (run the finished product on the plan's demo, offline, and have a model judge the output against the quality bars; rework if rejected), `finish`; outputs `docs`, `plan`, `code` (FILES), `report`, `appraisal` |
| code_pipeline_spl | understand, build, finish | the faithful port of `cookbook/code_pipeline` (SPL procedures, one block of code; needs SPL.py) |
| compliance_audit | load, assess, remediate, guard, release or escalate | `assess` (used twice), `remediate` (exit `unfixed`) |
| your_book | outline, chapters, compile | `outline`, `chapters` (the loop), `compile` |
| agent_notes | guard, research | `research` (the loop; exit `gave_up`) |
| supervisor | supervise | `supervise` (exit `unapproved`) |
| self_heal | extract, heal | `extract`, `heal` (exit `invalid`) |
| heartbeat | guard, news, announce | `news` (exit `quiet`), `announce`; one extra input `state_file` |
| stock_copy | gather, report | `gather` (the per-ticker loop), `report` |
| ts_verify | repair, finalize | `repair` (the loop); needs Node 22.18+ and `npm install` here |
| notes_digest | guard, read, digest, publish | `read`, `digest`, `publish` |
| chat_memory | guard, recall, reply, remember | `recall`, `reply`, `remember` |

Run a recipe by path (named lookups such as `cookbook:name` and the Browse page only see `cookbook/`). Use the `graf` conda env.

## 1. Offline checks (free, no model)

```bash
pytest tests/test_cookbook_v2.py -q
```

Every top graph validates with no errors or warnings, and each port runs next to its original (each in a copy of its folder) with a scripted model
that forces the retry, revision, approval, give-up, redaction and escalation paths. Outputs and the number of model calls must be equal.
heartbeat runs three beats; the ts_verify check needs Node and skips without it.

## 2. Look at the levels, one recipe at a time

```bash
R=compliance_audit                                               # any recipe above
graf validate cookbook_v2/$R/$R.graph.yaml
graf vis      cookbook_v2/$R/$R.graph.yaml                       # depth 0: the top level, each composite one box
graf vis      cookbook_v2/$R/$R.graph.yaml --depth 1             # open one level; --depth all opens everything
graf describe cookbook_v2/$R/$R.graph.yaml --depth 0 -o -        # the workflow in words, composites as one line each
graf info     cookbook_v2/$R/$R.graph.yaml --depth 1             # node and edge counts at that depth
graf expand   cookbook_v2/$R/$R.graph.yaml --depth all           # the flat graph the runtime runs (ids <use>__<node>)
graf errors   --dir cookbook_v2/$R                               # the error codes this recipe defines
```

## 3. In the editor

```bash
graf vis --edit --src-dir cookbook_v2
```

`--src-dir` is needed: the editor's default work area is `~/.graflang/cookbook`, which does not hold these. On the Edit page try:

- **Level** select (level-0, level-1, level-2, all-levels, as-written): level-0 shows the few top boxes, all-levels the flat graph.
- **Group / Ungroup**: writes a new composite's folder beside the recipe and validates before saving. Do it on a copy, not on a port.
- **Opening a composite file on its own** (e.g. `compliance_audit/assess/assess.graph.yaml`): some report errors by themselves; for example `agent_notes/research`
  holds a risky QUERY whose guard is in the top graph. That is expected.
- **Run from the page** needs the model chosen in Settings and is billed. Not tried on these recipes yet. heartbeat, notes_digest and chat_memory write files
  next to their composites.

The editor was checked only by loading all eleven recipes and drawing the depth-0 view; the clicks above have not been exercised on them.

## 4. Real model runs (billed: always cap them)

Every real run needs a `--bind` file with `limits.max_llm_calls` (a loop that never converges would otherwise keep spending). `cheap.bind.yaml` in `code_pipeline/` and
`code_pipeline_spl/` is a ready one (a model, a small spec, 20 calls); `--param` on the command line beats its `params`. For the other recipes copy it, change `params`, and set
`max_llm_calls` from what `graf validate` suggests ("Model calls per run").

**`code_pipeline` runs the generated project in a Docker container** (no network, read-only root, 1 GB, 2 CPUs), so a model's tests cannot reach the network or touch your files.
Build the image once, with Docker running (the recipe folder must be under your home directory with Docker Desktop):

```bash
docker build -t graflang-verify:py3.12 -f cookbook_v2/code_pipeline/tools/verify.Dockerfile cookbook_v2/code_pipeline/tools
```

The run's first step, `preflight`, checks the container before any model call is paid for. The image carries the libraries a generated project may import (pytest, click, streamlit,
networkx, flask, fastapi, pandas, ...); the container has no network, so add yours to `tools/verify.Dockerfile` and rebuild.

```bash
SPEC="Write a documentation app called doc-agent. Given a GitHub URL or a local path it reads the codebase, builds a knowledge graph of it (modules, classes, functions,
imports, calls) and uses an LLM to write a styled Markdown document from that graph. The LLM writes real explanatory prose from the extracted facts (the architecture, how the
parts work together, how to use it), not a list of names and docstrings. Three styles: tutorial (a guided walk through the code in dependency order that explains the ideas),
user-guide (what it does, how to install and use it, task by task, with examples) and slide-deck (a short deck, one message per slide, slides separated by ---). A slide-deck
.md can be converted to a self-contained .html slide app. The app has a Streamlit UI with a preview of the generated document and downloads, and a click CLI that generates
documents for a list of repos in batch (a file with one URL or path per line) and carries on when one repo fails. It is a well-structured python repo (a package, the CLI, the UI,
tests, a README). The LLM provider is chosen by an option or an environment variable, and an offline mode lets the tests and a demo run without a model."

# the repository-capable pipeline: a build plan of small tasks, then the project task by task. Files: .graf/codes/<run>/; the plan, the report and every step's output: .graf/outputs/<run>/
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml \
    --llm claude_cli:claude-sonnet-5-5 --param spec="$SPEC" --param check_closure=false
```

Raise `max_llm_calls` in a copy of the bind file for a big spec: about 6 for the plan (drafts and reviews), 2 per planned task, 3 to 4 for the appraisal (a judgement, and a rework when it rejects) and 3 for `finish`. Read the `plan` output first (`.graf/outputs/<run>/plan.md`): it shows how the work was split.

```bash
# the one-call version: no plan, no review, no run, no container
graf run cookbook_v2/code_gen/code_gen.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml \
    --llm claude_cli:claude-sonnet-5-5 --param spec="a Flask backend with /api/todos and a plain HTML/JS frontend"
```

(`code_pipeline_spl`'s `understand` step names `ollama:gemma3` itself, so a local Ollama must be running there.)

Another example, a small recipe:

```bash
graf run cookbook_v2/self_heal/self_heal.graph.yaml --param text="Please mail Maria Lopez (maria@acme.example)" --param max_rounds=2 --llm claude_cli:claude-haiku-5-5
```

Not checked offline: real model output. The equivalence tests show the structure matches the original, not that a real run gives the same text.

## Where a run leaves its files

Everything a run produces sits in `.graf/` beside the recipe's top graph (git-ignored), never among the recipe's own files:

- `.graf/outputs/<recipe>-<adapter>-<model>-<time>/`: `result.json`, one file per workflow output (e.g. `docs.md`), and `nodes/`, one file per node output
  in firing order (`004-generate.out_code.md`, `006-improve.out_improved_code.md`, ...). Change the place with `--output-dir`.
- `.graf/codes/<same run name>/`: the code a run emits, as real files in any layout (an output declared `type: FILES`; e.g. a repository with `backend/` and `frontend/`). `cookbook/code_parts` does this; `code_gen` and `code_pipeline` do; `code_pipeline_spl` does not (one block of code).
- `.graf/logs/`: the side files a `procedure_ref` step writes (code_pipeline: `target/python/code.py` is the first draft, `tests/`, `spec/`).

(A recipe's own data files, such as heartbeat's `output/state.txt`, are not run results and stay where the recipe puts them.)

## Known differences from the originals

- **heartbeat** has an extra input `state_file` (default `output/state.txt`); its alerts log is in `announce/output/`.
- **notes_digest** reads `read/input/notes.md` and saves `publish/output/digest.md`.
- A subprocess `command` runs from the top graph's folder, so `procedures/`, `tools/` and `examples/` (compliance_audit, stock_copy, ts_verify) stay beside the top graph.
