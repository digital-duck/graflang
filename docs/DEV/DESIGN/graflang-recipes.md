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
| code_pipeline_spl | `cookbook/code_pipeline` | `cookbook_v2/code_pipeline_spl` | **ported, offline-equivalent; not run with a real model** | top (4 boxes) / `understand`, `build` (loop, 6 steps), `finish` | validates clean; outputs and fired steps equal to the original under `echo` (with and without the closure check); a vague spec stops both under `mock`, the layered one with `E_SPEC_VAGUE` |
| compliance_audit | `cookbook/compliance_audit` | `cookbook_v2/compliance_audit` | **ported, offline-equivalent** (3 scripted paths) | top (load, assess, remediate, guard, 2 outputs) / `assess` (used twice), `remediate` (uses `assess`; exit `unfixed` E_STILL_NONCOMPLIANT) | released after redaction, escalated, clean first time: same output and model calls as the original |
| your_book | `cookbook/your_book` | `cookbook_v2/your_book` | **ported, offline-equivalent** | `outline`, `chapters` (the loop, review and revision), `compile` | same output, one scripted revision |
| agent_notes | `cookbook/agent_notes` | `cookbook_v2/agent_notes` | **ported, offline-equivalent** | guard, `research` (the loop; exit `gave_up` E_NO_ANSWER) | reads a note then answers; never answers |
| supervisor | `cookbook/supervisor` | `cookbook_v2/supervisor` | **ported, offline-equivalent** | `supervise` (first answer + review loop; exit `unapproved` E_NOT_APPROVED) | retries then approved; never approved |
| self_heal | `cookbook/self_heal` | `cookbook_v2/self_heal` | **ported, offline-equivalent** | `extract`, `heal` (loop; exit `invalid` E_STILL_INVALID) | heals; gives up |
| heartbeat | `cookbook/heartbeat` | `cookbook_v2/heartbeat` | **ported, offline-equivalent** (three beats, echo adapter) | guard, `news` (exit `quiet`), `announce` | the count is remembered between beats like the original; **one new input** `state_file` (see below) |
| stock_report | `cookbook/stock_copy` | `cookbook_v2/stock_report` (renamed) | **ported, offline-equivalent** | `gather` (the per-ticker loop), `report` | same output (the fetch tool falls back when offline) |
| ts_verify | `cookbook/ts_verify` | `cookbook_v2/ts_verify` | **ported, equivalent with Node** (test skips without Node + `npm install` in the original) | `repair` (the loop), top `finalize` | wrong first try then a right one: same output and model calls |
| notes_digest | `cookbook/notes_digest` | `cookbook_v2/notes_digest` | **ported, offline-equivalent** | guard, `read`, `digest`, `publish` | same output |
| chat_memory | `cookbook/chat_memory` | `cookbook_v2/chat_memory` | **ported, offline-equivalent** | guard, `recall`, `reply`, `remember` | same output |

| code_gen | new (uses `code_parts`' prompt and splitter) | `cookbook_v2/code_gen` | **new, offline-tested** (scripted model) | one graph: write, split | the reply becomes a project folder (modules, `__init__.py`, README) |
| code_pipeline | `cookbook/code_pipeline` + `cookbook/code_parts` | `cookbook_v2/code_pipeline` | **new, offline-tested (stub and real Docker); not run with a real model**. Deliberately NOT equivalent to the original | top / `analyze` (build plan, self-healing, exit `vague`), `build` (a loop over the plan's tasks), `appraise` (run the demo, judge, rework), `finish` (documents; optional closure check; prompts, no SPL.py) | scripted model: a thin plan is refused and healed, the project is built task by task with a fix pass, vague plans stop the run; verify runs in a container (preflight first); output `code` is FILES in `.graf/codes/<run>/` |

`code_pipeline` is the repository-capable recipe. A one-shot reply cannot hold a repository, so `analyze` first turns the spec into a build plan (JSON list of small tasks,
each with files and an acceptance test; a checker judges it and its complaints feed the next draft), then `build` loops over the tasks: each writes its files, they are merged
into the project, and the whole project is run (syntax, imports, its tests, an optional smoke test) in a Docker container with no network; a failed check gets one fix pass.
The faithful port of the original is `code_pipeline_spl`, kept for the equivalence check.

### code_pipeline_spl: what to try

```bash
graf validate cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml
graf vis      cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --depth 0     # then --depth 1, --depth all
graf describe cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --depth 0 -o -
graf expand   cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --depth 1     # one level opened, still loads
graf errors   E_SPEC_VAGUE --dir cookbook_v2/code_pipeline_spl
pytest tests/test_cookbook_v2.py -q                                            # the equivalence checks
# a real run (billed; capped at 8 calls by the bind file; the `understand` step needs a local Ollama, as in the original):
graf run cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --bind cookbook_v2/code_pipeline_spl/cheap.bind.yaml
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

### The second batch (ten recipes): what to try

Each runs from its own folder like the original; the offline checks are `pytest tests/test_cookbook_v2.py -q` (the original and the port, each in a
copy of its folder, with a scripted model that forces the retry, revision, escalation and give-up paths; outputs and model-call counts must be equal).

```bash
for r in compliance_audit your_book agent_notes supervisor self_heal heartbeat stock_report ts_verify notes_digest chat_memory; do
  graf vis cookbook_v2/$r/$r.graph.yaml --depth 0 --no-open; done           # then --depth 1 / all, and `graf describe ... --depth 0 -o -`
graf errors --dir cookbook_v2/compliance_audit                               # E_STILL_NONCOMPLIANT (each recipe with an error exit has its own file)
```

### What the second batch showed (feeds the design)

- **A subprocess command runs from the top graph's folder**, not the composite's. So `procedures/`, `tools/` and `examples/` stay beside the top
  graph (compliance_audit, stock_report, ts_verify) while prompts, `.spl` files and policies sit in the composite that uses them. A composite that
  runs a command is therefore not relocatable by itself. Open: anchor `command` and `parse.tool` paths to the part's folder as QUERY/EMIT `file` is?
- **A static QUERY/EMIT `file` is anchored to its composite's folder**, so two composites that must share a file cannot both name it. heartbeat
  passes the state path as a workflow input (`state_file`, default `output/state.txt`); that is a new input the original does not have. The
  `alerts.md` log now lands in `announce/output/`, the digest in `publish/output/`, and the notes are read from `read/input/`.
- **A composite holding a risky node (QUERY/EMIT) cannot validate alone**; the guard is in the graph that uses it. The test therefore validates
  each recipe's top graph, which opens its composites.
- **An input cannot go straight to a composite's OUTPUT** (notes_digest `publish` needed a pass-through step).
- **The same composite used twice** works: `compliance_audit` uses `assess` for the first check and, inside `remediate`, for the re-check.
- **A composite that uses a composite** works (`remediate` uses `assess`); the parts path is relative to the file that names it.
- **Error exits fit the "gave up / not approved / still invalid" endings** of the loop recipes: the loop moves into a composite and its failure
  to converge becomes a named exit with a code, where the originals test a flag afterwards.
- **inherits** cut the top-level plumbing in every port (a `use` line instead of a long `in:` map).
- **A `use` inside a loop body cannot read the loop's inputs** (known limit): every loop sits inside its own composite.

### What the first real run of the capable code_pipeline showed (doc-agent spec)

All 106 of the project's own tests passed and the output was a listing: the generated "tutorial" and "slide deck" enumerate each module's docstring and function names, with no
narrative. Causes, in the recipe, not the model: (1) the plan prompt told the planner "tests: no network, only these libraries (no model SDK)", and the planner removed the capability
instead (its assumption: "No LLM is called: content is derived deterministically"), because a documentation app that writes prose needs a model and a no-network test sandbox cannot call
one; (2) the tests the model wrote for itself only assert that headings and files exist, so `[PASSED]` measures nothing about quality; (3) nothing between plan and build asked whether the
plan delivers the spec. Fixes made: the plan separates the offline tests from the product (a model/service is called through an injectable interface, tests use fakes, SDKs are imported lazily),
it must list `deliverables` with a `mechanism` and a `quality_bar` (checked by `check_plan.py`), and a model reviews each plan that passes the check against the spec before building starts.
Then added: an `appraise` composite after the build that runs the finished product once on the plan's `demo` (offline, in the container, with an offline stand-in for any model) and has a model judge the output against each deliverable's quality bar, reworking a rejected product (max_appraisals). It catches structural failures (a listing, a missing feature, a crashing demo); it cannot judge the prose a real model would write.

A second real run showed the plan loop taking its three rounds: the reviewer rejected two drafts (12 and 9 defects, partly polish such as `.gitignore` or default model ids) and approved the third, while
the plan grew from 14 KB to 37 KB. Two changes: the reviewer is limited to 5 blocking defects and approves a plan without them; and running out of rounds is no longer fatal (the last draft that
passes the checker is used and the objections are an output, `plan_review`); only a plan that never passes the checker ends in the `vague` exit.

## Next candidates (not committed to; say which)

None left to port. The 14 core recipes that were still in `cookbook/` and already written in the compact form (`assembler`, `chain_of_thought`, `code_parts`, `container_demo`, `doc_it`, `expand_demo`, `guardrail`, `hello_world`, `lifted_tool`, `parts_demo`, `recipe_chain`, `release_approval`, `solver_check`, `stock_analysis`) were copied into `cookbook_v2/` with their paths fixed (`recipe_chain` needs the error codes of the parts it chains beside it: its own `graflang.errors.yaml`); each is offline-equivalent to its original (`tests/test_cookbook_core_v2.py`). Left out: `pocketflow` (the three R1 acceptance graphs; they stay in `cookbook/pocketflow/`). `stock_copy` is ported as `stock_report`.


## Solver and PocketFlow recipes (`cookbook_solvers_v2/`, `cookbook_pocketflow_v2/`)

Updated 2026-11-21. The lifted recipes of `cookbook_solvers/` and `cookbook_pocketflow/` are ported with `scripts/port_recipe.py` (compact, name every step after its tool or prompt, `graf group` into
composites, prettify, validate). Status: **all 47 solver recipes** (the four loop-heavy ones, `constraint_opt`, `symbolic_math`, `lean_proof`, `neurosymbolic`, by hand) and **all 42 PocketFlow recipes** (8 with composites, the staged ones; the other 34 flat with named steps: the retry-loop recipes are already one box at the top level). Every graph is offline-equivalent to its original on the mock adapter
(`tests/test_cookbook_solvers_v2.py`, `tests/test_cookbook_pocketflow_v2.py`). Not run with a real model.

The loop-heavy solver recipes: their retry loops are kept in long form, so no group could be inferred, but the trigger edges are a plain chain of stages, each with one entry and one way out. Porting them by hand found a second
bug: **`graf group` left behind a prompt or procedure used by a node inside a loop body** (it looked only at the selected nodes' own config), so the part did not validate (`procedures.step_rung__solve_chain_step ... does not exist`).
Fixed (`group.py` looks into loop bodies, as `ungroup` already did) with a test that fails without it.

What the port taught us: **`graf compact` could corrupt a long code string.** It wrote long quoted strings folded at the emitter's default width, and a fold could land inside an escape (`\n` read back as
`\ n`), so the report of `pandera_schema` lost a blank line; the "round trip verified" check compared objects in memory, not the text it wrote. Fixed: no wrapping anywhere (`yamlfmt.WIDTH`) and
`graf compact` reads its own output back before writing. A step is still best named after what it runs: the lifted ids (`tool_4`) told nothing.
