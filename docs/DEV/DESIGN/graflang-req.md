# Graph-Based Language Design

# Graph-First Programming Language — Design Notes

---

## Vision in One Sentence

A **semantic-graph programming language** where the program is a typed YAML graph (nodes = computation steps, edges = typed data/control dependencies), authored by LLM under schema constraints, compiled to a Rust binary — addressing entire classes of coding vulnerabilities by construction, not by after-the-fact analysis.

---

## Origin Story

5 personal prototype projects converged on this idea:

| Project | Representation | LLM role | codebase |
|---|---|---|---|
| **SPL** (Structured Prompt Language) | Declarative text DSL `.spl` | Constraint on "vibe coding"; LLM fills structured prompts | ~/projects/digital-duck/SPL.py |
| **Conceptbook** | Concept-based graph `.yaml` | Content generation from graph nodes | ~/projects/digital-duck/conceptbook-demo |
| **graph-code** | graph `.yaml` based blueprint | App generation from graph specification | ~/projects/digital-duck/graph-code |
| **work-graph** | process-level knowledge graph `.yaml` | build knowledge base from repo/product/org/process domain | ~/projects/digital-duck/work-graph | 
| **zinet** | reusable library for graph `.yaml` | - | ~/projects/digital-duck/zinet | 

SPL was the initial attempt to constrain LLM prompting with structure. The conceptbook and code-graph projects revealed the deeper pattern: **the graph is the right primary representation for programs**, not text. The plan is to migrate SPL entirely to `.yaml` semantic graphs.

---

## Core Ideas

### 1. Code ↔ Data Symmetry (Semantic IR)

Traditional compilation: source text → AST (syntactic IR) → machine code.

This approach: intent → **semantic graph** (YAML) → compiled binary.

The key distinction from an AST is that the semantic graph captures *meaning* — computation steps, data dependencies, control flow, module boundaries — not syntactic structure. This makes the representation:
- **Human-legible** (YAML with domain vocabulary)
- **LLM-legible** (patterns, not syntax rules)
- **Compiler-legible** (typed schema, mechanically processable)
- **Round-trippable** in both directions: a program can be serialized to its graph and regenerated

This is **homoiconicity for graphs**: code and data share the same representation, just as Lisp achieves this with S-expressions (trees). Graphs strictly subsume trees, so the representation is more expressive — shared structure, cycles (loops), and subgraph references are all native.

### 2. Node/Edge as Fermion/Boson

From physics: fermions are matter particles (half-integer spin, Pauli exclusion — structural, distinct); bosons are force carriers (integer spin, can overlap — relational, mediating).

- **Node = fermion**: expresses structure, identity, computation
- **Edge = boson**: expresses interaction, relationship, data flow

This is not merely analogy. **Feynman diagrams** are literally a graph-first language for computing particle interaction amplitudes — nodes are interaction vertices, edges are propagators. Physicists have used graph-first computation since the 1940s. The mathematical substrate (monoidal categories / string diagrams) is identical to what categorical quantum mechanics uses for quantum circuits and what interaction nets use for lambda calculus.

### 3. Graphs Are Maximally Expressive

Graphs have only two primitives — nodes and edges — yet:
- Lists, trees, and all other data structures are degenerate graphs
- Recursion is handled natively via **sub-graphs**: a node can reference a sub-graph as its body; back-edges and shared sub-graph references handle recursion and closures without special syntax. A sub-graph is treated as a node — composability is uniform at every scale. This also fulfills **encapsulation and modularity**: a sub-graph exposes only its interface edges to the outer graph, hiding its internal structure — the graph-native equivalent of a module boundary.
- This is precisely how **interaction nets** (Lafont 1990) handle lambda calculus and achieve Turing-completeness via pure graph rewriting

The ergonomics objection ("graphs are awkward to write") dissolves when **LLM is the authoring surface**. The human describes intent; the LLM constructs the graph. The schema constrains what the LLM can generate.

### 4. Human vs. LLM Non-Determinism

Human non-determinism is *uncontrolled*: fatigue, context loss, inconsistent application of rules across a large codebase, differing mental models between developers. This is the systemic root cause Kern (2025) identifies for the persistence of vulnerability classes.

LLM non-determinism is *tunable* (temperature parameter) and *pattern-driven* (the distribution is over learned correct patterns, not random errors). For well-scoped tasks with a clear schema — which is exactly what filling in a typed graph provides — LLM consistency exceeds human consistency on repetitive structured tasks.

The architecture contains LLM non-determinism at the right level:

```
intent → [LLM, constrained by schema] → typed graph YAML
                      ↓
            [deterministic compiler]
                      ↓
                 Rust binary
```

Stochasticity is bounded by schema validation. Code generation is mechanical and verifiable.

### 5. Schema as Vocabulary Grammar

The graph schema defines:
- **Node types** (vocabulary): analogous to keywords in a programming language, but expressed as a domain ontology
- **Edge types** (relationship types): constrained by which node types can connect
- **Type invariants on edges**: analogous to Kern's `TrustedSqlString` — the edge type carries a semantic guarantee

When the LLM generates a YAML graph that fails schema validation, the failure is **localized and diagnosable** (which relationship type was violated, what the valid alternatives are), unlike a cryptic Rust compile error. The schema validation error is fed back to the LLM as a structured retry prompt.

### 6. Safety by Construction (Connection to Safe Coding)

Kern (2025) argues that coding vulnerabilities persist because developers must individually track implicit safety preconditions on "risky operations" — this is unreliable at scale. The solution: encapsulate risky operations in **safe abstractions** whose type invariants, enforced by the type checker, guarantee safety to all callers.

The graph-first language takes this further:
- **Risky nodes** (nodes that perform unsafe operations) must be declared as such in the schema and require explicit allowlisting (analogous to Rust's `unsafe` block)
- **Edge type invariants** encode preconditions structurally — a `TrustedSqlString`-equivalent is just an edge type labeled `safe_sql_fragment`; the schema forbids connecting an untrusted data_flow edge to a SQL-sink node
- **The majority of the graph** (safe nodes + typed edges) is verified by schema validation — the type checker equivalent — without any additional analysis
- Complex safety reasoning is localized to the small set of reviewed risky-node implementations

This makes **coding safety a property of the language schema**, not a property individual developers must reason about.

### 7. Dynamic Coding and Safe Self-Revision

Because the program IS a graph (data), a running program can read, modify, and hot-swap its own sub-graphs at runtime. This is **homoiconicity** fully realized — not just "code can be inspected as data" (Lisp's promise), but "code can rewrite itself as data."

In interaction nets, this is not a special feature: **computation IS graph rewriting**. The program evolves by applying reduction rules to its own graph structure. Self-revision is the native execution model, not an add-on.

Practical implications:
- An LLM can generate a revised sub-graph at runtime, validated against the schema, and hot-swapped into the running program — enabling adaptive, self-improving systems
- SPL's `WHILE` loop already does this implicitly (LLM regenerates output until it passes an EVALUATE gate); explicit graph self-revision generalizes the pattern
- Programs can introspect their own workflow graph, reason about it, and restructure it — a foundation for meta-learning and autonomous agents that improve their own pipelines

**The risk:** a self-revising program could generate a graph that introduces risky nodes not in the allowlist, creates unexpected data flows, or exceeds its granted capabilities.

**Mitigations (layered):**
1. **Schema validation on every graph mutation** — any runtime graph modification that violates the schema is rejected before execution, analogous to a type error
2. **Risky node allowlist checked at instantiation** — a dynamically generated node of a risky type is blocked unless it appears in the expert-reviewed allowlist
3. **Capability edges** — capabilities (network access, filesystem, kernel calls) are encoded as edge types granted by trusted parent nodes; a dynamically generated node cannot acquire capabilities not present in its incoming edges (object-capability model)
4. **Hardened sandbox** — process isolation and OS-level capability restrictions (Rust `no_std`, WASM sandbox, seccomp) form the final enforcement layer; the schema handles structural safety, the sandbox handles behavioral safety

The schema + sandbox combination means the risk surface of self-revision is bounded: the schema catches structural violations, the sandbox catches behavioral ones. Together they make dynamic coding tractable in a safe-coding framework.

---

## SPL → Semantic Graph Conversion

### SPL Today

SPL is a declarative text DSL that composes **deterministic** (SOLVE/ASSERT, dispatched to SymPy/Sage/Lean kernels) and **probabilistic** (GENERATE/EVALUATE, dispatched to LLM) computation in a single `.spl` specification. Key DODA property: the `.spl` file is the invariant; model/kernel selection is deferred to invocation time.

The `splc` compiler already targets multiple backends: LangGraph, Go, TypeScript. The `.spl` text is already "graph-shaped" — it is a linearization of an implicit DAG.

### The Semantic Graph Mapping

| SPL construct | Graph node type | Edge(s) produced |
|---|---|---|
| `GENERATE ... INTO @var` | probabilistic | `data_flow` to consumers of `@var` |
| `EVALUATE @var WHEN...THEN` | branch | `control_flow` (labeled by condition) |
| `SOLVE @var KERNEL := expr` | deterministic | `data_flow` + `kernel_call` |
| `ASSERT ... OTHERWISE` | gate | `verify_gate` (pass) + `control_flow` (fail) |
| `CALL workflow INTO @var` | subgraph_call | `subgraph_ref` + `data_flow` (return) |
| `CALL PARALLEL ... END` | fork + join | parallel `control_flow` edges |
| `WHILE "condition" DO` | loop | `back_edge` from body terminal to loop entry |
| `@variable` binding | — | `data_flow` edge: producer → consumer |

`@variable` bindings become **explicit typed data_flow edges**, making the data dependency graph visible without reading the text. The probabilistic/deterministic mode boundary becomes a **node property**, structurally visible in any graph visualization.

### AST Graph vs. Semantic Graph

**AST graph** (syntactic): preserves the SPL syntax tree. `WHILE` is a node with a `body` child sub-graph. Faithful round-trip back to `.spl` text.

**Semantic graph** (computation): nodes = computation steps; edges = data + control dependencies. `WHILE` is a back-edge from the loop body's terminal to its entry node, with the loop condition as an edge property. Richer for analysis, visualization, and LLM authoring.

**Decision: semantic graph.** The graph IS the program, not a representation of SPL syntax. SPL text becomes one possible *projection* of the graph — a human-readable linearization — not the source of truth.

### YAML Schema Sketch

```yaml
# Node vocabulary
node_types:
  generate:
    mode: probabilistic
    required: [call, output_var, prompt]
    optional: [input_vars, system_role, rag, memory]
  solve:
    mode: deterministic
    required: [output_var, kernel, expression]
    kernel_values: [sympy, sage, lean, python]
  assert:
    mode: deterministic
    required: [condition]
    optional: [otherwise_goto]
  evaluate:
    mode: probabilistic
    required: [input_var, branches]
  call:
    required: [target_workflow, input_vars, output_var]
  fork:
    required: [branches]  # list of call nodes
  loop:
    required: [condition, body_entry_node]
    max_iterations: 5

# Edge vocabulary
edge_types:
  data_flow:
    carries: variable_name
  control_flow:
    carries: condition_label  # optional
  verify_gate:
    carries: [pass_goto, fail_goto]
  subgraph_ref:
    carries: workflow_id
  back_edge:
    carries: loop_condition
```

### Dominant Failure Mode — Resolved at Generation Time

The SPL paper's empirical finding: the dominant failure mode is `solver_error` (kernel-rejected expressions), not format non-compliance. This is a *structural* failure — the LLM doesn't produce the right `expr|op` decomposition shape. A typed graph schema with constrained node interfaces would catch this at **schema validation time** rather than at kernel execution time, shortening the feedback loop dramatically.

---

## Prior Work & References to Study

### Graph Rewriting & Formal Foundations

| Work | Why relevant |
|---|---|
| **Interaction Nets** — Yves Lafont (1990) | Turing-complete graph rewriting system; models lambda calculus via node annihilation; recursion via sub-graph references; the formal basis for graph-first computation |
| **Interaction Combinators** — Lafont (1997) | Minimal basis (3 node types) for interaction nets; optimal lambda reduction |
| **String Diagrams / Monoidal Categories** | Mathematical framework unifying Feynman diagrams, quantum circuits, and interaction nets; the common substrate for graph-first computation across physics and CS |
| **Categorical Quantum Mechanics** — Coecke & Abramsky | Quantum computation as string diagram rewriting; shows graph-first reasoning is rigorous and compositional |
| **Feynman Diagrams** | The original graph-first computation language for physics; nodes = interaction vertices, edges = propagators; computes scattering amplitudes via graph rewriting rules |
| **Penrose Spin Networks / Loop Quantum Gravity** | Graph-based description of spacetime geometry; same mathematical structure |
| **Port Graphs / Attributed Graph Grammars** | Formal language theory for typed graphs with attributed nodes/edges; directly applicable to schema design |
| **GrGen.NET** | Graph rewriting system for code transformation and analysis |
| **Pi-calculus / Kell calculus** | Process calculi modeling concurrent systems as communicating graphs |

### Intermediate Representations

| Work | Why relevant |
|---|---|
| **MLIR** (Multi-Level Intermediate Representation) — Google/LLVM | Compiler IR framework where each level is a typed graph (operations + regions); shows how graph IRs compose across abstraction levels |
| **LLVM IR / SSA form** | Standard compiler IR; programs in SSA form are already data-flow graphs |
| **Cranelift / WebAssembly** | Alternative graph-based IR targets; relevant if targeting WASM instead of Rust |

### Graph-First Programming Systems

| Work | Why relevant |
|---|---|
| **Flow-Based Programming (FBP)** — J. Paul Morrison (1971/1994) | Earliest explicit graph-first programming paradigm; programs as networks of black-box processes connected by data streams; book: *Flow-Based Programming* |
| **Node-RED** | FBP for IoT/automation; graph authored visually, compiled to JavaScript; large ecosystem of node types (vocabulary) |
| **Apache Beam** | Dataflow pipelines as typed graphs of transforms + PCollections; compiles to multiple runners (Dataflow, Spark, Flink); closest industrial analogue |
| **Unreal Engine Blueprints** | Visual graph-first scripting; nodes = functions, edges = data/execution flow; compiled to native code; large-scale real-world use |
| **LabVIEW** | Graph-first language for scientific/engineering computation; dataflow execution model |
| **Temporal / Durable Execution** | Workflow graphs compiled to distributed, durable execution; similar DODA property to SPL |
| **dbt (data build tool)** | SQL transformations as a DAG; graph-first for data pipelines; strong community precedent |
| **Terraform / Pulumi** | Infrastructure-as-code as dependency graphs; graph structure enforces ordering and safety |

### LLM-Constrained Generation

| Work | Why relevant |
|---|---|
| **Outlines** (dottxt-ai) | Constrained LLM decoding via finite-state machines; guarantees syntactically valid JSON/regex output at generation time; applicable to YAML graph schema |
| **guidance** (Microsoft) | Grammar-constrained LLM generation; interleaves generation and computation |
| **LMQL** | SQL-like query language for LLM interaction with constraints |
| **Reflexion** — Shinn et al. (2023) | Verifier→generator feedback loop; LLM uses execution feedback to improve generation; directly relevant to schema-validation feedback |
| **AlphaCode** — DeepMind | Code generation with test-based filtering; validates the verifier-in-the-loop pattern at scale |
| **SHACL** (Shapes Constraint Language) | W3C standard for validating RDF graphs against shape schemas; directly applicable to graph schema validation tooling |
| **OWL / RDF Schema** | Ontology languages for typed knowledge graphs; mature tooling for schema definition and constraint checking |

### Safety & Verification

| Work | Why relevant |
|---|---|
| **Safe Coding** — Christoph Kern (Google TR, Nov 2025; Commun. ACM Mar 2026) | Core argument: shift safety responsibility from developer to language/library via safe abstractions and type invariants. The graph schema IS the type invariant system for graph-first programs. |
| **Developer Ecosystems for Software Safety** — Christoph Kern (Commun. ACM, Jun 2024) | Practitioner version of the above; ecosystem-level enforcement (conformance checks, expert allowlists) maps to graph schema toolchain integration |
| **Error Prone** — Google | Java static analysis framework; `@CompileTimeConstant` annotation enforces the `TrustedSqlString` pattern; shows lightweight static checks for safe abstraction enforcement |
| **Rust ownership/borrow system** | Type-system enforcement of memory-safety invariants; the gold standard for "safety by construction"; graph edge types could encode ownership transfer |

### LLM Orchestration Frameworks (Prior Art to Differentiate From)

| Framework | Limitation addressed by graph-first approach |
|---|---|
| LangGraph | Python-defined graph; graph structure implicit in code, not a first-class artifact |
| AutoGen / CrewAI | Agent roles defined in Python; no formal schema for agent interaction patterns |
| DSPy | Optimizes prompts but workflow structure is still Python code |
| Prefect / Airflow | DAG defined in Python decorators; graph is derived from code, not the source of truth |

---

## The Graph-First Language Roadmap

### Phase 1 — SPL → YAML (Immediate)

- Define the semantic graph schema for SPL's node/edge vocabulary
- Migrate existing SPL recipes (70+ cookbook) to YAML graph format
- Update `splc` to compile YAML graph → LangGraph / Go / TypeScript (replaces `.spl` parser)
- LLM generates YAML graph directly (**`spl3 vibe` now targets YAML, not `.spl` text**) *(highlighted in original)*

### Phase 2 — Typed Graph Language

- Extend schema to handle general computation (not just LLM workflows) *(highlighted in original)*
- Add Rust code generation target to `splc`
- Implement constrained decoding (Outlines/guidance) for YAML generation — eliminate schema validation failures
- Structured feedback loop: schema error → natural language explanation → LLM retry

### Phase 3 — Safety-by-Construction

- Mark risky node types in schema (analogous to Rust `unsafe`) *(`unsafe` highlighted in original)*
- Encode edge type invariants (analogous to `TrustedSqlString`) *(highlighted in original)*
- Conformance checks integrated into CI: application graphs cannot contain bare risky nodes
- Expert allowlist mechanism for reviewed risky-node implementations

---

## Key Design Principles (Summary)

1. **Graph is the source of truth** — text syntax (SPL, Python, Rust) is a projection, not the canonical form *(partly highlighted in original)*
2. **Semantic graph, not AST** — nodes are computation steps, edges are typed dependencies; not a parse tree *(partly highlighted in original)*
3. **Schema = vocabulary grammar** — constrains LLM output at generation or validation time *(partly highlighted in original)*
4. **DODA (Design Once, Deploy Anywhere)** — model/kernel/backend selection is graph-external metadata
5. **Modular safety** — risky operations isolated in reviewed safe-abstraction sub-graphs; the rest verified by schema
6. **LLM non-determinism is an asset** — pattern-driven, tunable, bounded by schema; superior to unbounded human inconsistency at scale for structured tasks
7. **Homoiconicity** — the program graph is first-class data; programs can inspect and modify their own structure *(partly highlighted in original)*

---

*Source: printout of `file:///C:/work/github/CS_AIML/AI-Tools/qlcoder/docs/Safe-Coding/README-graph-lang.html` (8 pages, printed 10/28/26)*
