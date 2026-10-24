# GraphLang

**A physics-inspired, topologically grounded language for self-revising agentic workflows.**

GraphLang flips the script on agentic AI. Where LangGraph and AutoGen use Python code to *describe* a graph, GraphLang treats the graph as the **primary, executable source of truth**. The topology is the program. The LLM doesn't write code — it mutates the graph.

> **Status:** Early prototype. Private development repository.  
> **Companion:** [SPL.py](https://github.com/digital-duck/SPL.py) — the declarative workflow language that GraphLang elevates.  
> **Paper:** *GraphLang: A Physics-Inspired, Topologically Grounded Language for Self-Revising Agentic Workflows* (in preparation; no draft in this repository yet)

---

## The Paradigm Shift

| | Imperative Frameworks (LangGraph, AutoGen) | GraphLang |
|---|---|---|
| **Source of truth** | Python code that describes a graph | The graph itself |
| **LLM's role** | Generate text/code | Mutate the topology |
| **Parallelism** | `asyncio.gather` + race conditions | Interaction Nets (confluent for the deterministic core; LLM-sampling nodes and `LOOP` are not) |
| **Safety** | Scattered `if/else` guardrails | Declarative Cedar policies, enforced at runtime (Rust compilation planned) |
| **Self-revision** | Rewrite the Python file | Output a validated graph delta |
| **Visualization** | Lossy Mermaid translation | First-class, interactive topology |

---

## Two graph formats, one family

GraphLang workflows live in `*.graph.yaml` and are run, checked, compiled and drawn by the one command `graf`. They are not
[zinet](https://github.com/digital-duck/zinet) graphs: zinet stores a *static* dependency graph (`primitives:`, `concepts:`,
`applications:`), while a workflow is *executable* (typed nodes with ports, `triggers` and `binds` edges, loops and retries,
Cedar policies). Both are plain YAML that persists a graph, and the file name is only a convention, so `graf` tells the files
apart by content (`workflow:` with `nodes:` and `edges:` is a workflow) and says what a zinet or ConceptBook file is instead of
failing on a schema error. The two share graph code: `graf vis` draws through zinet's engines (`zinet.vis`).

## Core Innovations

### 1. Physics-Inspired Execution
GraphLang is grounded in **Lafont's Interaction Nets** — a mathematically proven model for deterministic, concurrent graph rewriting. Computation occurs via local rewrite rules when agents interact:

- **`GENERATE`** — probabilistic agents (LLM calls)
- **`SOLVE` / `ASSERT`** — deterministic agents (SymPy, Lean, Python eval)
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
- Evaluated at runtime by `grafr` (dynamic, hot-reloadable)
- Planned: compiled to zero-cost Rust `match` statements by `grafc` (deployment; `grafc` is still a stub)

The LLM can propose mutations, but only those that pass the Cedar policy check are applied.

### 4. Compilation to Rust (Downstream)
**Planned; `grafc` is currently a stub.** `grafc` is meant to compile the Graph IR + Cedar policies into a memory-safe, high-performance Rust binary. This is a **downstream deployment optimization**, not the core innovation. The innovation is the topological execution model itself.

---

## Quick Start

```bash
# Install the dynamic interpreter (development)
pip install -e ".[dev]"        # `claude_cli`, `ollama`, `openai`, `openrouter` work as is; `.[anthropic]`, `.[gemini]` add SDKs

# Run a workflow (default adapter is `claude_cli`; `--adapter mock` calls no LLM)
graf run cookbook/code_pipeline/code_pipeline.graph.yaml \
    --adapter ollama \
    --param spec="Write a binary search function"

# Compile to Rust (deployment; planned, grafc is a stub)
# Cedar policies are referenced from the graph's `resources.policies` block
# (shared policies live in graphlang/policies/).
graf compile cookbook/code_pipeline/code_pipeline.graph.yaml \
    --target rust \
    -o code_pipeline
```

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
    mutation_safety: "../../graphlang/policies/mutation_safety.cedar"

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

**What makes this revolutionary:**
- The `LOOP` node is a **Tier 3 composite** — click it in the UI to see the internal 4-step topology
- The `GUARD` node enforces Cedar policies before allowing a retry
- The closure check (spec → code → spec' → judge) is a clean topological branch, not buried in `if/else`
- The LLM can propose mutations via `MUTATE` nodes, but only those passing Cedar are applied

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GraphLang Toolchain                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Source              IR              Runtime     Deployment │
│   ──────              ──              ───────     ────────── │
│                                                             │
│   *.graph.yaml ──► grafr ──► NetworkX/Python (dev)          │
│                  │                                          │
│                  └──► grafc ──► Rust binary (prod)          │
│                                                             │
│   *.cedar ─────────┘  (compiled inline to Rust match)       │
│   *.spl ───────────┘  (Tier 2 procedure references)         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Relationship to SPL.py

[**SPL.py**](https://github.com/digital-duck/SPL.py) is the declarative workflow language that GraphLang elevates. SPL provides:

- The `GENERATE` / `EVALUATE` (probabilistic) and `SOLVE` / `ASSERT` (deterministic) vocabulary
- The 78-recipe cookbook and its empirical validation
- The neurosymbolic verifier ladder (SymPy → SageMath → Lean 4)
- The LLM adapters (Ollama, Claude, OpenAI, Momagrid, etc.)

GraphLang takes SPL's proven semantics and gives them a **topological execution model**. SPL workflows can be automatically ported to GraphLang via the `spl2graph` transpiler.

---

## Roadmap

- [x] Core vocabulary design (physics-inspired, pruned from SPL)
- [x] JSON Schema for Graph IR (3-tier composition)
- [x] Cedar integration in `grafr` (`GUARD` and `MUTATE` checks via `cedarpy`)
- [x] Flagship example (`code_pipeline.graph.yaml`)
- [x] `grafr` Python interpreter (NetworkX-based topological executor)
- [ ] `grafc` Rust compiler (Graph IR + Cedar → Rust AST)
- [ ] Interactive Streamlit UI (drill-down visualization of Tier 3 composites)
- [ ] `spl2graph` transpiler (port all 78 SPL recipes)
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