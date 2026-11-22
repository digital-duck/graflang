# GraphLang

**A physics-inspired, topologically grounded language for self-revising agentic workflows.**

GraphLang flips the script on agentic AI. Where LangGraph and AutoGen use Python code to *describe* a graph, GraphLang treats the graph as the **primary, executable source of truth**. The topology is the program. The LLM doesn't write code — it mutates the graph.

> **What it is for:** multi-step, agentic work with branches, loops, risky actions, policy, audit or a person in the loop. It is **not a general-purpose language**: for one model call or a script, write the call or the script. See [what GraphLang is for](docs/DEV/DESIGN/graflang-use-cases.md), including how to write Hello World.  
> **Status:** Early prototype. Private development repository.  
> **Companion:** [SPL.py](https://github.com/digital-duck/SPL.py) — the declarative workflow language that GraphLang elevates.  
> **Paper:** *GraphLang: A Physics-Inspired, Topologically Grounded Language for Self-Revising Agentic Workflows* (in preparation; no draft in this repository yet)

---

## The Paradigm Shift

| | Imperative Frameworks (LangGraph, AutoGen) | GraphLang |
|---|---|---|
| **Source of truth** | Python code that describes a graph | The graph itself |
| **LLM's role** | Generate text/code | Mutate the topology |
| **Parallelism** | `asyncio.gather` + race conditions | Explicit `FORK` / `JOIN` nodes in the topology |
| **Safety** | Scattered `if/else` guardrails | Declarative Cedar policies, enforced at runtime |
| **Self-revision** | Rewrite the Python file | Output a validated graph delta |
| **Visualization** | Lossy Mermaid translation | First-class, interactive topology |

---

## Two graph formats, one family

GraphLang workflows live in `*.graph.yaml` and are run, checked and drawn by the one command `graf`. They are not
[zinet](https://github.com/digital-duck/zinet) graphs: zinet stores a *static* dependency graph (`primitives:`, `concepts:`,
`applications:`), while a workflow is *executable* (typed nodes with ports, `triggers` and `binds` edges, loops and retries,
Cedar policies). Both are plain YAML that persists a graph, and the file name is only a convention, so `graf` tells the files
apart by content (`workflow:` with `nodes:` and `edges:` is a workflow) and says what a zinet or ConceptBook file is instead of
failing on a schema error. The two share graph code: `graf vis` draws through zinet's engines (`zinet.vis`).

## Core Innovations

### 1. Physics-Inspired Execution
A workflow runs as tokens passing through typed nodes. Each node type plays one role:

- **`GENERATE`** — probabilistic agents (LLM calls)
- **`SOLVE` / `ASSERT`** — deterministic agents: an expression, a persistent Python kernel, or any program run as a subprocess (SymPy, Z3, Lean, a Rust binary), read through a declared parser
- **`FORK` / `JOIN`** — explicit fan-out and barrier (parallelism without race conditions)
- **`LOOP`** — cyclic control flow (test-gated retry)
- **`MUTATE`** — the self-revising operator (LLM outputs validated graph deltas)
- **`GUARD`** — policy checkpoints backed by Cedar

### 2. Three-Tier Composition
Keep the topology clean while preserving the full expressive power of SPL:

- **Tier 1 (Inline):** Tiny prompts and expressions directly in the YAML
- **Tier 2 (Reference):** External `.spl` procedures, `.md` prompts, `.cedar` policies
- **Tier 3 (Sub-graph):** Composite nodes — a graph within a graph (e.g., a `LOOP` node encapsulating a 5-step internal topology)

### 3. Policy-Grounded Safety
Safety isn't an afterthought. [Cedar](https://www.cedarpolicy.com/) policies are first-class topological constructs (`GUARD` nodes) that are:
- Evaluated at runtime (dynamic, hot-reloadable)

The LLM can propose mutations, but only those that pass the Cedar policy check are applied.

---

## Quick Start

```bash
# Install (development)
pip install -e ".[dev]"        # `claude_cli`, `ollama`, `openai`, `openrouter` work as is; `.[anthropic]`, `.[gemini]` add SDKs

# Look first, no model needed: check a workflow, read it in words, draw it
graf validate cookbook_v2/code_pipeline/code_pipeline.graph.yaml
graf describe cookbook_v2/code_pipeline          # writes RECIPE.spec.md: inputs, steps, data flow, cost
graf vis cookbook_v2/code_pipeline/code_pipeline.graph.yaml --depth 1

# Run a workflow (the default is `--adapter claude_cli --model claude-sonnet-5-5`)
graf run cookbook/code_pipeline/code_pipeline.graph.yaml \
    --adapter ollama \
    --param spec="Write a binary search function"

# Or describe an app in a sentence and let a model draft the graph (checked, then dry-run on the mock adapter)
graf create --name notes --spec "Summarise each file in a folder, then write one index"
```

`graf run` calls a real model and bills it unless the adapter is `mock` or local: give a `--bind` file with `limits.max_llm_calls` when you try a loop.

---

## The Flagship Example: `code_pipeline.graph.yaml`

A neurosymbolic, self-revising code generation pipeline. This single file demonstrates the entire paradigm:

```yaml
version: "1.0-graph"

workflow:
  name: "code_pipeline"
  inputs:
    - {name: "spec", type: "TEXT"}
    - {name: "max_cycles", type: "INTEGER", default: 3}
  outputs:
    - {name: "docs", type: "TEXT"}

resources:
  procedures:
    analyze_spec: "./00_analyze_spec.spl"
    generate_code: "./01_generate_code.spl"
    review_code: "./02_review_code.spl"
    test_code: "./04_test_code.spl"
    # ... (8 procedures in the full file, 00-07)
  policies:
    mutation_safety: "./policies/mutation_safety.cedar"

nodes:
  - id: "analyze"
    type: "GENERATE"
    config: {procedure_ref: "procedures.analyze_spec"}
    ports: ["trigger", "complete", "in_spec", "out_analysis"]

  - id: "spec_gate"
    type: "EVALUATE"
    config: {condition: "contains(@in_analysis, '[READY]')"}   # @in_analysis is this node's own in_* port, fed by a `binds` edge
    ports: ["trigger", "pass", "fail", "in_analysis"]

  - id: "test_gated_loop"
    type: "LOOP"
    config:
      # @in_max_cycles is a LOOP input port; @test_passed and @cycle are loop state
      # (the previous iteration's outputs and the 0-based counter), not declared ports.
      condition: "NOT @test_passed AND @cycle < @in_max_cycles"
      subgraph:
        nodes:
          - {id: "gen", type: "GENERATE", config: {procedure_ref: "procedures.generate_code"}}
          - {id: "rev", type: "GENERATE", config: {procedure_ref: "procedures.review_code"}}
          - {id: "test", type: "SOLVE", config: {procedure_ref: "procedures.test_code"}}
          - {id: "guard", type: "GUARD", config: {policy_ref: "policies.mutation_safety"}}
        edges:
          - {source: "gen.complete", target: "rev.trigger", type: "triggers"}
          - {source: "rev.complete", target: "test.trigger", type: "triggers"}
          - {source: "test.complete", target: "guard.trigger", type: "triggers"}
          - {source: "guard.allow", target: "gen.trigger", type: "triggers"}  # Safe retry
    ports: ["trigger", "loop", "exit", "in_spec", "out_final_code"]

edges:
  - {source: "analyze.complete", target: "spec_gate.trigger", type: "triggers"}
  - {source: "analyze.out_analysis", target: "spec_gate.in_analysis", type: "binds"}
  - {source: "spec_gate.pass", target: "test_gated_loop.trigger", type: "triggers"}
  # ... (full file in cookbook/code_pipeline/)
```

This is the long form, one file with every node. `cookbook_v2/code_pipeline/` is the same recipe **layered**: a short top graph whose steps are composites in subfolders (see below).

**What makes this revolutionary:**
- The `LOOP` node is a **Tier 3 composite** — click it in the UI to see the internal 4-step topology
- The `GUARD` node enforces Cedar policies before allowing a retry
- The closure check (spec → code → spec' → judge) is a clean topological branch, not buried in `if/else`
- The LLM can propose mutations via `MUTATE` nodes, but only those passing Cedar are applied

---

## Layers: a short top graph, composites underneath

A real workflow has too many nodes for one picture. GraphLang lets a step be a **composite** (a *part*: a graph in its own folder, with named inputs, outputs and error exits), so the top graph stays about a page long and each part can be read, checked, reused and tested alone. `graf expand` opens the composites into the flat graph that runs, `graf compact` goes back, `graf group` / `ungroup` turn a selection of steps into a part and back, `graf vis --depth N` and `graf info --depth N` show the workflow N levels deep, and `graf errors` lists the error codes a part may exit with. All 100+ recipes of `cookbook/`, `cookbook_solvers/` and `cookbook_pocketflow/` have a layered twin in the matching `*_v2/` folder, checked against the original on the mock adapter. Design: [graflang-layers.md](docs/DEV/DESIGN/graflang-layers.md), rules: [graflang-semantics.md](docs/DEV/DESIGN/graflang-semantics.md), recipe status: [graflang-recipes.md](docs/DEV/DESIGN/graflang-recipes.md).

**A model that assembles part of its own workflow.** [`cookbook_v2/problem_solver`](cookbook_v2/problem_solver/readme.md): given a problem in words, a model picks one of five deterministic solvers (SymPy, Z3, OR-Tools, portfolio optimisation, SQL) from a catalogue, proposes the inputs, a program checks them, and a `MUTATE` adds the chosen solver to the running graph under a Cedar policy. When no solver fits, or the inputs cannot be bound, a model answers alone and the report says **UNVERIFIED**. The model never writes wiring: it names a part and gives values.

---

## What you can do today

- **Write less.** A compact `steps:` form expands to the full graph (`graf expand`); a bindings file (`--bind`) sets the model, files and limits per environment.
- **Make it dependable.** Per-node retry, timeout, fallback and output schemas; typed ports; `graf validate` finds races, deadlocks and unguarded risky nodes before anything runs.
- **Do more at once.** `--workers` runs parallel branches concurrently, `BATCH` maps a subgraph over a list, `RUN` calls a subprocess, a Python kernel or an http service.
- **Keep it affordable and repeatable.** A run summary with calls, tokens and time; budgets; `--record` / `--replay` of model calls so tests need no model; `--checkpoint` / `--resume` after a failure.
- **Stay in control.** Cedar guards at run time, a workflow policy for which nodes are allowed at all, and a `MUTATE` that can never touch the safety layer or what runs.
- **Build from a sentence, document what exists.** `graf create` drafts an app from a description (or a diagram); `graf describe` writes a recipe as a specification that `graf create --spec` can read back; `graf docs` writes a demo, tutorial or user guide for a folder or repo.
- **Embed it.** The runtime is a library: load a recipe once, run it per input with your own model function and call cap (this is how [work-graph](https://github.com/digital-duck/work-graph) runs its extraction and `ask` recipes, and how app-graph's build pipeline is being moved onto GraphLang). A program inside a recipe can be any language, run as a subprocess, optionally in a Docker container.
- **Come from and go to SPL.** SPL.py's `spl2graph` lifts SPL workflows into graphs (265 of its 274 cookbook workflows validate); `graf compile --lang spl` writes a graph back as SPL.

---

## Relationship to SPL.py

[**SPL.py**](https://github.com/digital-duck/SPL.py) is the declarative workflow language that GraphLang elevates. SPL provides:

- The `GENERATE` / `EVALUATE` (probabilistic) and `SOLVE` / `ASSERT` (deterministic) vocabulary
- The 78-recipe cookbook and its empirical validation
- The neurosymbolic verifier ladder (SymPy → SageMath → Lean 4)

GraphLang takes SPL's proven semantics and gives them a **topological execution model**. SPL workflows are lifted into GraphLang graphs by SPL.py's `spl2graph`; GraphLang itself does not depend on SPL.py (LLM calls go through the shared `dd-llm` package), and can run an `.spl` procedure when you ask it to.

---

## Roadmap

- [x] Core vocabulary design (physics-inspired, pruned from SPL)
- [x] JSON Schema for Graph IR (3-tier composition)
- [x] Cedar integration (`GUARD` and `MUTATE` checks via `cedarpy`)
- [x] Flagship example (`code_pipeline.graph.yaml`)
- [x] Python interpreter (NetworkX-based topological executor)
- [x] `graf vis`: read a workflow as a graph (control flow first, data edges on demand, loops that collapse to one box)
- [x] App: `graf vis --edit` has Create (describe an app in chat), Edit (buttons or chat; validated, comments kept, undoable), Settings (provider, model, API keys) and Import/Export pages, working in `~/.graflang/` or `--src-dir` (`pip install 'graflang[edit]'`). Not yet: drag-to-connect.
- [x] Create from a description (`graf create`), `graf describe`, recipe search (Browse page)
- [ ] Drag-to-connect on the canvas in the app
- [x] SPL recipes as graphs: `spl2graph` (in SPL.py) lifts 265 of 274 cookbook workflows; `graf compile --lang spl` goes back
- [x] The 47 solver recipes of SPL.py migrated and run with a real model (`cookbook_solvers/`)
- [x] Layered form: composites in subfolders, `inherits`, error exits with codes, `graf group` / `expand` / `compact`, `vis --depth`; every cookbook recipe has a `*_v2/` twin
- [x] `problem_solver`: a model chooses and adds a catalogue solver at run time, with an UNVERIFIED fallback
- [ ] Benchmark solvers: a pick-accuracy test set for `problem_solver`
- [ ] `graphlang.run_recipe`: one helper for running a shipped recipe from library code (work-graph and app-graph each have their own today)
- [ ] Paper submission (NeurIPS / ICLR)

---

## License

Apache 2.0. See [LICENSE](./LICENSE).

---

## Citation

```bibtex
@misc{gong2026graflang,
  title={GraphLang: A Physics-Inspired, Topologically Grounded Language for Self-Revising Agentic Workflows},
  author={Gong, Wen},
  year={2026},
  howpublished={\url{https://github.com/digital-duck/graflang}},
  note={Forthcoming paper}
}
```

---

> *"The graph is not a byproduct of the code. The graph **is** the code."*