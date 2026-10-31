# code_parts

The first half of `code_pipeline` (check the spec, write the code, review it, improve it) with **no `.spl` files and no SPL.py**. Where `code_pipeline` runs each step as an SPL sub-workflow (`procedure_ref`), here each step is a *part*: a named subgraph, a small workflow file used as one node and expanded in place when the graph loads.

```
analyze -> gate --[READY]--> write -> review -> improve -> collect -> done
              \--(not ready)--> abort (run stops)
```

| | |
|---|---|
| Inputs | `spec` (TEXT, required), `lang` (TEXT, default `python`) |
| Outputs | `code` (FILES, a project folder: `<run folder>/code/`), `review` (TEXT, `review.md`) |
| LLM calls | 4 (1 if the spec is rejected) |
| Files | `code_parts.graph.yaml` (compact form), `sub_graph/*.graph.yaml` (one part per step), `sub_graph/prompts/*.md` |

## SPL sub-workflow or part

| In `code_pipeline` | Here |
|---|---|
| `01_generate_code.spl`: a `CREATE FUNCTION` with the prompt, a `WORKFLOW` that calls it and writes a file | `sub_graph/write_code.graph.yaml` + `sub_graph/prompts/write_code.md` |
| `procedure_ref: procedures.review_code`, run by SPL.py's executor | `use: parts.review_code`, expanded to ordinary nodes (`review__gen`) |
| `{spec}` placeholders | `{{in_spec}}` ports |
| `EVALUATE ... WHEN contains('[READY]')` | an `evaluate` step, with a `RECOVER` halt on the other branch |

The prompt text is the `.spl` files' (`tests/test_code_parts.py` checks it); `write_code` and `improve_code` add one paragraph asking for the code as project files. Left out on purpose: the artifact files the procedures write, the per-step `WITH OUTPUT BUDGET` and the exception handlers, none of which the graph needs; the graph's workflow outputs and the run folder's `nodes/` hold the results.

## The generated code is a project folder

The model does not return one block of code. `write_code` and `improve_code` ask for files, each introduced by a line `=== FILE: path/to/file ===`: a `README.md` first, then the sources, split into modules that import each other when the spec has more than one concern. The `collect` step (`tools/collect_files.py`, a `SOLVE` with `backend: subprocess`) splits the reply, strips code fences, refuses paths that leave the folder, adds an `__init__.py` to every Python package folder so the imports work, and adds a `README.md` from the spec if the model wrote none. A reply with no markers becomes one file, `main.<ext>`.

The workflow output `code` is declared `type: FILES` (a mapping of relative path to text), so `graf run` writes it as a real folder instead of `code.md`:

```
output/code_parts-<adapter>-<model>-<time>/
  code/                  <- the generated project
    README.md
    slugger/__init__.py  slugger/core.py  slugger/cli.py
    tests/test_slugger.py
  review.md              <- the review feedback
  result.json  run.json  summary.json  nodes/
```

Run its tests from the project folder: `cd output/<run>/code && python -m unittest discover -s . -p "test_*.py"`.

## Run

```bash
graf run cookbook/code_parts/code_parts.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --param spec="a function is_palindrome(s) that ignores case and punctuation"

graf run cookbook/code_parts/code_parts.graph.yaml --llm claude_cli:claude-haiku-5-5 --param spec="make something useful"   # stops after 1 call

graf vis cookbook/code_parts/code_parts.graph.yaml      # each part use drawn as a box; no mermaid needed
graf expand cookbook/code_parts/code_parts.graph.yaml   # the flat graph: analyze__gen, write__gen, ...
```

Each step may name its own LLM: add `llm: "ollama:gemma3"` to a `use` step (`- review: {use: parts.review_code, llm: "ollama:gemma3", ...}`) and the part's `GENERATE` node uses it, unless the part file's node names its own.

## What is not here

The test-gated retry loop, the Cedar guard, the documentation and the closure judge stay in `code_pipeline`. That recipe keeps its `.spl` procedures because the `code_pipeline` experiment runs the same procedures in all its arms.
