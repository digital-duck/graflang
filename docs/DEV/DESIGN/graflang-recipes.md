# Recipes ported to the layered form (`cookbook_v2/`)

This file tracks the port of the cookbook recipes to the layered form described in `graflang-layers.md`. The recipes in `cookbook/` (and
`cookbook_pocketflow/`, `cookbook_solvers/`) are left alone: the experiment arms (`experiments/code_pipeline`) and many tests run them, and the
comparison needs them unchanged. A ported recipe lives in `cookbook_v2/<name>/`, next to its original, and is checked against it.

Updated 2026-11-21.

## How a port is done and checked

1. Read the original; find its levels (the steps a person would name), and make each a composite in a subfolder that carries the procedures,
   prompts, tools and policies it uses. The top graph reads as the logic, a handful of boxes.
2. A failure branch becomes an **error exit** with a **code** defined in a `graflang.errors.yaml` beside the recipe (semantics 3d).
3. Keys the enclosing workflow already declares are passed with `inherits:`; the rest with `in:`.
4. Keep the original's prompts, models, gates and limits as they are: a port changes the structure, not the behaviour.
5. Every port has an offline equivalence test in `tests/test_cookbook_v2.py`: the original and the layered recipe run with the `echo` or `mock`
   adapter, and the outputs and the steps that ran must match. `pytest tests/test_cookbook_v2.py` runs them all. Every graph under
   `cookbook_v2/` must also validate with no errors and no warnings.
6. Not checked offline: real model output. The equivalence shows the structure is the same, not that a real run gives the same text.

Named lookups (`cookbook:name`) and the Browse page see only `cookbook/`; run a v2 recipe by path, or open the folder with
`graf vis --edit --src-dir cookbook_v2`.

## Status

| Recipe | Original | Layered | Status | Levels | Checked |
|---|---|---|---|---|---|
| code_pipeline | `cookbook/code_pipeline` | `cookbook_v2/code_pipeline` | **ported, offline-equivalent; not run with a real model** | top (4 boxes) / `understand`, `build` (loop, 6 steps), `finish` | validates clean; outputs and fired steps equal to the original under `echo` (with and without the closure check); a vague spec stops both under `mock`, the layered one with `E_SPEC_VAGUE` |

### code_pipeline: what to try

```bash
graf validate cookbook_v2/code_pipeline/code_pipeline.graph.yaml
graf vis      cookbook_v2/code_pipeline/code_pipeline.graph.yaml --depth 0     # then --depth 1, --depth all
graf describe cookbook_v2/code_pipeline/code_pipeline.graph.yaml --depth 0 -o -
graf expand   cookbook_v2/code_pipeline/code_pipeline.graph.yaml --depth 1     # one level opened, still loads
graf errors   E_SPEC_VAGUE --dir cookbook_v2/code_pipeline
pytest tests/test_cookbook_v2.py -q                                            # the equivalence checks
# a real run (billed; capped at 8 calls by the bind file; the `understand` step needs a local Ollama, as in the original):
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml
```

Layout: the top graph is 5 steps (`understand`, `stop`, `build`, `finish`, `done`); the flat graph is the same 11 nodes as the original.

### What the port showed (feeds the design)

- **The error exit is the right shape for the vague-spec gate.** The original wires a gate to a RECOVER node; the layered one declares `vague`
  on `understand`, so the top level says "if it is vague, stop" and the cause has a code and a remedy.
- **A part cannot read a loop's inputs**, so the loop body stays inside `build` as the loop's own level (one file, the loop and its six steps)
  rather than becoming a composite per iteration. `describe --depth 0` counts the loop with its body (`build` holds 7 steps).
- **`inherits` removed most of the plumbing** at the top level (`spec`, `lang`, `max_cycles`, `check_closure` are not written out).
- **Two OUTPUT nodes giving one output** (`ready` and `vague`) used to write the same data wire twice after expansion; it is written once now.
- The original's `.spl` files and `tools.py` are copied into the composite that uses them (a part is self-contained); nothing is shared.

## Next candidates (not committed to; say which)

`code_parts` (already uses parts, but the top level is flat), `self_heal`, `your_book`, `compliance_audit`, `stock_analysis`, `supervisor`.
