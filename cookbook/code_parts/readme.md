# code_parts

The first half of `code_pipeline` (check the spec, write the code, review it, improve it) with **no `.spl` files and no SPL.py**. Where `code_pipeline` runs each step as an SPL sub-workflow (`procedure_ref`), here each step is a *part*: a named subgraph, a small workflow file used as one node and expanded in place when the graph loads.

```
analyze -> gate --[READY]--> write -> review -> improve -> done
              \--(not ready)--> abort (run stops)
```

| | |
|---|---|
| Inputs | `spec` (TEXT, required), `lang` (TEXT, default `python`) |
| Outputs | `code` (TEXT, the improved code), `review` (TEXT, the review feedback) |
| LLM calls | 4 (1 if the spec is rejected) |
| Files | `code_parts.graph.yaml` (compact form), `parts/*.graph.yaml` (one part per step), `parts/prompts/*.md` |

## SPL sub-workflow or part

| In `code_pipeline` | Here |
|---|---|
| `01_generate_code.spl`: a `CREATE FUNCTION` with the prompt, a `WORKFLOW` that calls it and writes a file | `parts/write_code.graph.yaml` + `parts/prompts/write_code.md` |
| `procedure_ref: procedures.review_code`, run by SPL.py's executor | `use: parts.review_code`, expanded to ordinary nodes (`review__gen`) |
| `{spec}` placeholders | `{{in_spec}}` ports |
| `EVALUATE ... WHEN contains('[READY]')` | an `evaluate` step, with a `RECOVER` halt on the other branch |

The prompt text is the same as the `.spl` files' (`tests/test_code_parts.py` checks it). Left out on purpose: the artifact files the procedures write, the per-step `WITH OUTPUT BUDGET` and the exception handlers, none of which the graph needs; the graph's workflow outputs and the run folder's `nodes/` hold the results.

## Run

```bash
graf run cookbook/code_parts/code_parts.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --param spec="a function is_palindrome(s) that ignores case and punctuation"

graf run cookbook/code_parts/code_parts.graph.yaml --llm claude_cli:claude-haiku-5-5 --param spec="make something useful"   # stops after 1 call

graf vis cookbook/code_parts/code_parts.graph.yaml      # each part use drawn as a box; no mermaid needed
graf expand cookbook/code_parts/code_parts.graph.yaml   # the flat graph: analyze__gen, write__gen, ...
```

Each step may name its own LLM: add `llm: "ollama:gemma3"` to the `gen` node of a part, or to a `use` step's config, to give that step another model.

## What is not here

The test-gated retry loop, the Cedar guard, the documentation and the closure judge stay in `code_pipeline`. That recipe keeps its `.spl` procedures because the `code_pipeline` experiment runs the same procedures in all its arms.
