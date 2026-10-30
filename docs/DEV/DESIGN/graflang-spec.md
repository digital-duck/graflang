# Graph-Lang — Design Spec (draft v0.1)

Derived from `graflang-req-v0.1.md`. Scope narrowed per author direction: Graph-Lang is a **practical upgrade of SPL for agentic workflow orchestration**. Physics, interaction nets and Feynman diagrams remain inspiration only; they impose no requirements.

---

## 1. Goals and Non-Goals

### Goals
1. A workflow is a **typed YAML graph** — the graph file is the source of truth; `.spl` text becomes one projection of it.
2. Nodes are **units of computation**, either **deterministic** (solver, script, program, API call) or **probabilistic** (LLM call, agent).
3. Compute nodes are **language-agnostic**: a node can call a Python library, a JavaScript tool, a Go program, a CLI binary, an HTTP/MCP service, or a math kernel (SymPy/Sage/Lean).
4. **DODA** (Design Once, Deploy Anywhere): the graph is invariant; model, kernel and runtime choices live in separate binding profiles.
5. **LLM-authorable**: a strict schema so an LLM can generate graphs, and validation errors are precise enough to feed back as retry prompts.
6. **Safe by construction** for the practical cases: untrusted data cannot reach dangerous sinks, and nodes only get the capabilities they declare.

### Non-Goals (for v1)
- Not a general-purpose language that replaces Rust/Python. General computation lives *inside* nodes.
- No compile-to-Rust requirement in v1 (see §9).
- No runtime self-modifying graphs in v1 (see §11).
- No visual editor in v1 (graph is viewable via export to Mermaid/Graphviz).

---

## 2. Key Design Decisions (and why)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Graph is the source of truth; SPL is a projection** | Carried over from the notes. Keeps SPL usable as a readable view and migration path. |
| D2 | **Semantic graph, not AST** | Nodes = steps, edges = typed dependencies. |
| D3 | **Node *contract* is separate from node *implementation*** | This is what makes nodes language-agnostic. The graph only sees ports and types; an *executor* runs the body. |
| D4 | **Graph-Lang is orchestration-first, with an interpreter runtime** | Rust codegen conflicts with language-agnostic nodes (a Rust binary would still have to spawn Python/JS/Go). Compile to an orchestrator *runtime*; codegen to LangGraph/Go/TS stays an optional backend as in `splc` today. |
| D5 | **Types = JSON Schema on ports, plus trust labels** | JSON Schema is language-neutral, LLM-friendly, and has validators in every language. Trust labels give the "TrustedSqlString" safety idea without a custom type theory. |
| D6 | **Control flow is a small closed set of node kinds** (branch, loop, fork/join, gate, call) | A closed set is easy for LLMs to generate and for validators to check. No arbitrary cycles outside `loop`. |
| D7 | **Bindings (model/kernel/runtime) are external metadata** | DODA. Same graph runs with `claude-sonnet` or a local model, with `sympy` or `lean`. |
| D8 | **Everything is traced** | Each node run produces a record (inputs hash, outputs, latency, cost, executor). Required for debugging probabilistic nodes. |

---

## 3. Architecture

```
 intent ──► [LLM + schema-constrained decoding] ──► graph.yaml
                                                       │
                          ┌────────────────────────────┤
                          ▼                            │
                 [Validator pipeline]  ◄── error feedback to LLM (retry)
                          │ valid graph
                          ▼
                 [Planner]  (topological order, parallel groups, binding resolution)
                          │
                          ▼
                 [Runtime / Orchestrator]
                    │        │         │          │
              llm executor  python    node(js)   exec/go/cli   solver   http/mcp
                          │
                          ▼
                 [Trace store + checkpoints]
```

Components:
- **Schema** — JSON Schema for the graph format itself (nodes, edges, ports).
- **Validator** — layered checks (§7).
- **Planner** — resolves bindings, computes execution order and parallel groups.
- **Runtime** — executes nodes, handles retries, budgets, checkpoints, tracing.
- **Executors** — pluggable adapters, one per language/tool family (§5).
- **Projections/Backends** — SPL text, Mermaid/Graphviz, LangGraph/Go/TS codegen.

Implementation language for the runtime is open (§12); Go or Rust are both good fits (single static binary, subprocess management, concurrency).

---

## 4. Graph Format

### 4.1 File layout

```yaml
graflang: "0.1"
name: summarize_and_verify
description: Summarize a document, check claims, retry until verified.

inputs:                       # graph-level interface
  doc: {type: string}
outputs:
  summary: {type: string}

nodes: { ... }                # §4.2
edges: [ ... ]                # §4.3  (data edges can be inferred from refs)
subgraphs: { ... }            # optional local reusable graphs
```

Bindings live in a separate file (§6): `summarize_and_verify.bind.yaml`.

### 4.2 Nodes

Every node has: `id`, `kind`, `mode`, ports (`in`/`out`), and kind-specific config.

```yaml
nodes:
  draft:
    kind: generate            # probabilistic
    in:  {doc: string}
    out: {summary: string}
    prompt: |
      Summarize the following in 5 bullets:
      {{ doc }}
    model: $default_llm       # logical name; resolved by binding profile

  check:
    kind: exec                # deterministic, language-agnostic
    in:  {summary: string, doc: string}
    out: {ok: boolean, issues: {type: array, items: string}}
    run:
      executor: python
      entry: tools/check_claims.py:verify     # module:function
```

**Node kinds (v1 closed set):**

| Kind | Mode | Purpose | SPL equivalent |
|---|---|---|---|
| `generate` | probabilistic | LLM call producing typed output | `GENERATE ... INTO` |
| `agent` | probabilistic | LLM with tool loop, bounded steps/budget | (new) |
| `evaluate` | probabilistic | LLM classifies/judges → selects a branch label | `EVALUATE ... WHEN` |
| `exec` | deterministic | Run external code via an executor (§5) | `SOLVE` (generalized) |
| `solve` | deterministic | Math/logic kernel (sympy/sage/lean) — sugar over `exec` with kernel executor | `SOLVE` |
| `assert` | deterministic | Boolean check; pass/fail edges | `ASSERT ... OTHERWISE` |
| `branch` | deterministic | Route on a value/predicate | `EVALUATE` (deterministic form) |
| `loop` | control | Repeat a body subgraph until condition or `max_iterations` | `WHILE` |
| `fork` / `join` | control | Parallel branches, then merge | `CALL PARALLEL` |
| `call` | control | Invoke a subgraph/workflow | `CALL ... INTO` |
| `input` / `output` | — | Graph interface | — |

`mode` is derived from `kind` but exposed on every node so tooling can color/filter by deterministic vs probabilistic.

### 4.3 Edges

Two classes, kept explicit:

```yaml
edges:
  - {from: draft.summary, to: check.summary, type: data}      # data_flow
  - {from: check, to: draft, type: control, when: "!ok"}      # control_flow with condition
```

- **`data`** edges connect an *output port* to an *input port*; the type must be assignable (§7). These replace SPL `@variable` bindings. For brevity, a node may reference `{{ other_node.port }}` and the loader will synthesize the data edge.
- **`control`** edges express ordering/conditions that carry no data. Optional `when` is a predicate over ports.
- Special-purpose forms (`verify_gate`, `back_edge`, `subgraph_ref`) are *not* separate edge types in v1; they are expressed by `assert`, `loop` and `call` node kinds. This keeps the edge vocabulary to two entries and moves richer semantics into node kinds, which are easier to validate and generate.

### 4.4 Loops, parallelism, subgraphs

```yaml
  refine:
    kind: loop
    body: refine_body                 # subgraph id
    until: "check.ok == true"
    max_iterations: 5                 # REQUIRED; no unbounded loops
    carry: {summary: draft.summary}   # values threaded between iterations
    on_exhausted: fail                # fail | continue | goto:<node>

  gather:
    kind: fork
    branches: [fetch_a, fetch_b, fetch_c]
    join: {strategy: all, timeout_s: 60}   # all | any | quorum:N
```

Subgraphs are ordinary graphs with declared `inputs`/`outputs`; a `call` node exposes only those ports. Recursion is allowed only through `call` with a depth limit.

---

## 5. Compute Nodes: the Executor Model

This is the core of "language-agnostic". A compute node declares *what* it needs (typed ports, capabilities); an **executor** decides *how* to run it.

### 5.1 Executor types (v1)

| Executor | Runs | Notes |
|---|---|---|
| `python` | module:function or script | In a managed venv or container |
| `node` | JS/TS module:function | |
| `go` / `binary` | prebuilt executable | Any language that produces a CLI |
| `shell` | command line | Always `risky`; allowlist required |
| `http` | REST/JSON endpoint | |
| `mcp` | MCP tool on an MCP server | Reuses the existing tool ecosystem |
| `kernel` | sympy / sage / lean / z3 | Used by `solve` |
| `wasm` | WASM module | Strong sandbox option |
| `llm` | model call | Used by `generate`/`evaluate`/`agent` |

### 5.2 Invocation protocol

One protocol for all executors so adding a language is just writing an adapter:

- **Input**: a single JSON object matching the node's `in` ports.
- **Output**: a single JSON object matching the node's `out` ports.
- **Transport**: stdin/stdout JSON for processes; HTTP body for `http`; native protocol for `mcp`.
- **Errors**: structured `{error: {code, message, retryable}}`; non-zero exit or schema-invalid output is a node failure.
- **Side channels**: stderr captured to trace; large artifacts passed by file reference (`{"$file": "path"}`) rather than inline.

The runtime validates the output against the `out` schema **before** any downstream node sees it, so a bad Python tool or a hallucinating LLM is caught at the same boundary.

### 5.3 Example: same contract, different implementations

```yaml
  parse_table:
    kind: exec
    in:  {html: string}
    out: {rows: {type: array}}
    run:
      executor: $table_parser         # logical name, resolved in bindings
```

```yaml
# bindings: dev
executors:
  table_parser: {executor: python, entry: tools/parse.py:parse}
# bindings: prod
executors:
  table_parser: {executor: binary, path: ./bin/tableparser-go}
```

The graph is identical; the implementation (and language) is swapped per environment.

### 5.4 Per-node runtime policy

```yaml
    policy:
      timeout_s: 30
      retries: {max: 2, backoff: exponential, on: [retryable]}
      cache: {key: [html], ttl_s: 3600}       # deterministic nodes only by default
      budget: {max_tokens: 4000, max_cost_usd: 0.05}   # probabilistic nodes
      idempotent: true
```

---

## 6. Bindings (DODA)

Separate file(s) selected at invocation: `graflang run flow.yaml --bind prod`.

```yaml
# prod.bind.yaml
models:
  default_llm: {provider: anthropic, model: claude-sonnet-5-5, temperature: 0.2}
  judge_llm:   {provider: local, model: llama3, temperature: 0}
executors:
  table_parser: {executor: binary, path: ./bin/tableparser-go}
kernels:
  default: sympy
secrets:                    # references only, never values
  api_key: env:SERVICE_KEY
limits:
  max_total_cost_usd: 1.00
  max_wall_time_s: 600
```

Rule: **nothing environment-specific (model names, paths, keys, kernel choice) appears in the graph file.**

---

## 7. Type System and Validation

### 7.1 Types
- Port types are **JSON Schema** (with shorthand: `string`, `number`, `boolean`, `{type: array, items: ...}`).
- Optional **trust labels** on types, e.g. `string!untrusted`, `string!sql_safe`, `string!html_escaped`.
- Edge assignability: output type must satisfy the input type; trust labels only *narrow* (untrusted → sanitized via an explicit sanitizer node), never silently widen.

### 7.2 Validator pipeline (each stage emits localized, LLM-readable errors)

1. **Syntax** — valid YAML.
2. **Schema** — conforms to Graph-Lang meta-schema (required fields, known `kind`s).
3. **Structure** — unique ids, all edge endpoints exist, no dangling ports, graph connected, cycles only via `loop`, every `loop` has `max_iterations`, `fork` has matching `join`.
4. **Types** — every data edge type-compatible; every required input is fed.
5. **Safety** — trust-label flow, risky-node allowlist, capability grants (§8).
6. **Bindings** — every logical name (`$default_llm`, `$table_parser`) resolves in the selected profile.
7. **Dry-run (optional)** — execute with stubs/mocks to check shapes end to end.

Error format (for retry prompts):

```yaml
- code: TYPE_MISMATCH
  at: edges[3]            # draft.summary -> check.score
  message: "draft.summary is string; check.score expects number"
  suggestions: ["add a node of kind exec that converts string→number",
                "connect draft.summary to check.summary instead"]
```

### 7.3 LLM authoring loop
`intent → LLM(schema-constrained decoding or JSON-schema tool call) → validate → on error, send structured errors back → retry (max N)`. Constrained decoding (Outlines/guidance, or provider structured output) eliminates stage 1–2 failures; stages 3–6 are what the feedback loop is for. This addresses the SPL finding that `solver_error` (structural) dominates: with typed ports, a malformed `expr|op` shape fails at stage 4, not at kernel run time.

---

## 8. Safety Model (practical subset)

1. **Risky nodes** — kinds/executors flagged risky in the meta-schema: `shell`, `http` to non-allowlisted hosts, filesystem write, DB write, any `exec` with network access. Using one requires an entry in an **allowlist file** reviewed by humans (the `unsafe`-block analogue). CI check: application graphs may not contain un-allowlisted risky nodes.
2. **Capabilities** — each node declares `needs: [net:api.example.com, fs:read:./data]`. The runtime grants *only* those (container flags, seccomp/WASM, network policy). Undeclared access fails at runtime; over-broad declarations fail review.
3. **Trust labels** — data from users, web, or LLM output is `untrusted` by default; sinks (SQL, shell, file path, HTML) declare the label they require; the validator rejects a path from an untrusted source to a sink unless a sanitizer node intervenes. Covers the `TrustedSqlString` idea concretely.
4. **LLM-output containment** — probabilistic node output is always schema-validated and labeled untrusted; it can never directly become a `shell` command or file path without a sanitizer.
5. **Budgets** — token/cost/time/iteration limits at node and graph level to bound runaway agents.
6. **Secrets** — referenced, never inlined; masked in traces.

---

## 9. Execution Targets

| Target | Status | Purpose |
|---|---|---|
| **Graph-Lang runtime (interpreter)** | v1 primary | Executes graphs directly; multi-language executors; tracing; checkpoints |
| **LangGraph / Go / TypeScript codegen** | v1 (carry over from `splc`) | Reuse existing backends; migration path |
| **Standalone Rust binary** | later, optional | Only for graphs whose nodes are all native/WASM; "compile" = embed the plan + runtime. Not a v1 goal. |
| **SPL text** | v1 projection | `graflang export --spl`, readable view and backward compat |
| **Mermaid/Graphviz** | v1 projection | Visualize; color deterministic vs probabilistic |

Rationale for deferring Rust-binary output: the safety guarantees come from schema validation and capability enforcement, not from the host language; and language-agnostic nodes mean a "compiled binary" still has to orchestrate external processes.

---

## 10. SPL → Graph-Lang Mapping

| SPL | Graph-Lang |
|---|---|
| `GENERATE ... INTO @v` | `generate` node, out port `v` |
| `EVALUATE @v WHEN ... THEN` | `evaluate` (probabilistic) or `branch` (deterministic) |
| `SOLVE @v KERNEL := expr` | `solve` node (kernel executor) |
| `ASSERT ... OTHERWISE` | `assert` node with `on_fail` edge |
| `CALL wf INTO @v` | `call` node |
| `CALL PARALLEL ... END` | `fork` + `join` |
| `WHILE cond DO ... END` | `loop` node + body subgraph, `max_iterations` required |
| `@var` | data edge |
| model/kernel in invocation | bindings file |

Migration tooling: `graflang import-spl flow.spl > flow.yaml` (mechanical, lossless for supported constructs); `graflang export --spl flow.yaml` (best-effort projection). Round-trip tests over the 70+ cookbook recipes are the acceptance gate for Phase 1.

---

## 11. Deferred / Future

- **Self-revising graphs** (runtime graph mutation by an LLM). Defer until the validator, allowlist and capability model are proven. When added, every mutation passes the full validator pipeline and cannot add capabilities absent from the parent's grants (the layered mitigations in the original notes still apply).
- **Interaction-net-style rewriting** as an optimization/analysis layer — only if a concrete need appears.
- **Ownership/linear edge types** (Rust-like) for resource handles.
- **Long-running/durable execution** (Temporal-style): v1 has checkpoints; full durability later.
- **Visual editor** and live trace viewer.

---

## 12. Open Questions

1. **Runtime language**: Go vs Rust? (Go: faster iteration, matches existing `splc` Go backend. Rust: matches original vision, better WASM story.)
2. **Data edges inferred or explicit?** Inference (`{{ node.port }}`) is friendlier for LLMs; explicit edges are friendlier for tooling. Proposal: both, normalized to explicit on load.
3. **Large data**: file/object-store references vs inline JSON — threshold and format.
4. **Streaming** outputs between nodes (token streams, large iterators) — v1 batch-only?
5. **Agent nodes**: how much autonomy inside a node vs expressing the loop in the graph? Proposal: prefer graph-level loops; `agent` node is bounded and traced as a black box.
6. **Where does `zinet` fit?** Likely as the shared library for graph load/validate/export — confirm scope against the existing codebase.
7. **Trust labels**: fixed built-in set or user-defined taxonomy?
8. **Determinism for probabilistic nodes**: record/replay of LLM calls for tests (cassette-style) — include in v1 tracing?

---

## 13. Roadmap

**Phase 0 — Spec & schema (2–3 wks)**
Meta-schema (JSON Schema) for graph + bindings; error-code catalog; Mermaid export; example graphs (3–5 hand-written).

**Phase 1 — SPL parity**
Importer (`.spl` → YAML); validator stages 1–6; runtime with `generate`/`solve`/`assert`/`evaluate`/`loop`/`fork`/`call`; executors: `llm`, `kernel`, `python`; LangGraph/Go/TS codegen from graph (replaces `.spl` parser in `splc`); `spl3 vibe` emits YAML. Gate: all cookbook recipes round-trip and pass.

**Phase 2 — Language-agnostic compute & authoring**
Executors: `node`, `binary`/`go`, `http`, `mcp`, `shell`; bindings profiles; policies (retry/cache/budget); tracing + replay; constrained decoding + structured retry loop; `agent` node.

**Phase 3 — Safety**
Risky-node allowlist + CI conformance check; trust labels and sanitizer nodes; capability enforcement (containers/WASM/seccomp); secrets handling.

**Phase 4 — Advanced**
Durable execution, optional Rust/WASM packaging, controlled self-revision.

---

## 14. Worked Example

```yaml
graflang: "0.1"
name: research_brief
inputs:  {topic: string}
outputs: {brief: string}

nodes:
  search:
    kind: exec
    in:  {query: string!untrusted}
    out: {results: {type: array, items: {type: object}}}
    needs: [net:api.search.example.com]
    run: {executor: mcp, tool: web_search}

  draft:
    kind: generate
    in:  {topic: string, results: array}
    out: {brief: string}
    prompt: "Write a brief on {{ topic }} using: {{ results }}"
    model: $default_llm

  facts:
    kind: exec
    in:  {brief: string}
    out: {ok: boolean, issues: {type: array, items: string}}
    run: {executor: python, entry: tools/factcheck.py:check}

  refine:
    kind: loop
    body: draft_and_check
    until: "facts.ok"
    max_iterations: 3
    on_exhausted: fail

edges:
  - {from: input.topic,     to: search.query}
  - {from: search.results,  to: refine.results}
  - {from: refine.brief,    to: output.brief}
```

Flow: web search (deterministic, network-capped) → LLM drafts (probabilistic) → Python fact-check (deterministic) → loop up to 3 times → output. Swap the LLM, the fact-checker's language, or the search tool by editing bindings only.

---

## 15. Summary of Changes vs. the Original Notes

| Original notes | This spec |
|---|---|
| Compile to Rust binary | Interpreter runtime first; Rust/WASM packaging optional later |
| Physics/interaction-net foundations | Inspiration only; no requirements derived from them |
| 5+ edge types (`verify_gate`, `back_edge`, `subgraph_ref`, …) | 2 edge types (`data`, `control`); semantics moved into node kinds |
| Node types: generate/solve/assert/… with fixed kernels | Node *contract* + pluggable *executors* (Python/JS/Go/CLI/HTTP/MCP/kernel/WASM) |
| Self-revising programs in core vision | Deferred; safety substrate comes first |
| Schema constrains LLM | Same, plus layered validator and structured retry loop |
| Safety via risky nodes + edge invariants | Same, made concrete: allowlist, capabilities, trust labels, budgets |
| DODA as a principle | Bindings files as the mechanism |
