# Graph-Lang — Design Review: Current Implementation vs. Spec

Companion to `graflang-spec.md` (clean-room spec, written **before** looking at the code) and `graflang-req.md` (requirements).
This document reviews the existing prototype at `~/projects/digital-duck/graflang` against that spec, lists strengths, weaknesses and gaps, and proposes enhancements.

**Method and limits**
- Read: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, the IR schema, `grafr/runtime.py` (key parts), `nodes/generate.py`, `nodes/evaluate.py`, `nodes/__init__.py`, head of `solve_backend.py`, the `self_refine` cookbook graph, and the gap tracker `zinets/docs/graph-vision/claude/readme-design.md`.
- Ran: `pytest` in conda env `graf` → **355 passed, 8 failed, 2 skipped** (25 s). Failures: 6 in `test_cedar_compiler.py`, 1 in `test_policy_slicer.py`, 1 in `test_experiment_end_to_end.py[spl]` (hardcoded absolute path, a portability bug; the hardcoded SPL.py paths in `experiments/` are since fixed via `SPL_PY_PATH`).
- **Not read in depth**: `grafc/` internals, `grafv/`, `procedures.py`, `kernel.py`, `solver.py`, `mutate`/`loop` implementations, the other five cookbook graphs, `docs/GUIDE`. Sibling repos `graph-driven-workflow`, `sdlc-graph`, `pocoflow`, `markoflow`, `monteflow` were not examined. Statements below are marked *(verified)* when checked in code or tests, *(inferred)* otherwise.

---

## 1. Snapshot of the Implementation

| Area | State |
|---|---|
| Package | `graflang` (PyPI) / `graphlang` (import); CLI `graf run\|validate\|info\|check\|compile\|vis`; ~5.4k lines of Python |
| Runtime `grafr` | Token-passing dataflow over a `networkx.MultiDiGraph`; node types GENERATE, EVALUATE, SOLVE, ASSERT, LOOP, FORK/JOIN, GUARD, MUTATE, CONTEXT, INPUT/OUTPUT |
| Edges | Two types: `triggers` (control tokens between named ports) and `binds` (data, keyed by port name) |
| LLM | `mock` plus adapters through shared `dd-llm` (`claude_cli`, `ollama`, `openai`, ...) |
| Deterministic compute | `SOLVE` via `expression`, `procedure_ref` (SPL workflow), `backend: kernel` (persistent Python kernel) or `backend: subprocess` (any program, stdin JSON → stdout parser) |
| Safety | Cedar (`cedarpy`) for GUARD/MUTATE, fail-closed; safe expression evaluator; MUTATE cannot add code-bearing keys (`CODE_KEYS`) |
| Compiler `grafc` | Mostly stub; ~1,500-line hand-written Cedar compiler; Rust codegen stub |
| Viz | `graf vis` via `zinet.vis` engines: cytoscape (default), graphviz, mermaid, ascii |
| Cookbook | `code_pipeline`, `self_refine`, `concept_book`, `compliance_audit`, `solver_check`, `ts_verify` |
| Process | Gap tracker with 35 numbered items; ~30 test files |

---

## 2. Strengths

1. **The core model works end to end.** Graphs run, loops run, mutation runs, with real LLM adapters; 355 tests pass *(verified)*. This is far past "idea" stage.
2. **Safety thinking is ahead of most frameworks, and concrete.**
   - Cedar evaluation is **fail-closed** (any evaluation error denies).
   - `expr.py` is a whitelist expression evaluator, no `eval`, tested against injection.
   - MUTATE deltas can never add or change code-bearing keys (`backend`, `code`, `command`, `parse`, `env_passthrough`), checked by a deep scan **before** any policy is consulted, so no policy can grant it (gap #35). This is the right trust boundary: *code comes only from the graph file, never from a model.*
   - A missing schema is an error, not a silent skip; runtime rejects edges to nonexistent ports.
3. **Language-agnostic deterministic compute already exists in embryo.** `SOLVE backend: subprocess` runs any program (stdin JSON, declared output parser, timeout, memory cap, `on_error: route`); `backend: kernel` gives a persistent Python kernel. This is the executor idea in the spec, working.
4. **SPL bridge exists.** `procedure_ref` runs an SPL.py workflow as a node, so SPL assets are reusable during migration.
5. **Three-tier composition** (inline / referenced `.spl`/`.md`/`.cedar` / subgraph) keeps topology readable.
6. **Good engineering hygiene around the tool**: structured JSONL logging (`node.fire/done/error`, `llm.call`, `guard.decision`), per-node output saving, static topology checker (`graf validate`, e.g. found a dead edge in the flagship graph), explicit run budget (`--max-steps`, `RunLimitExceeded`).
7. **Shared libraries instead of copies**: `dd-llm`, `dd-logging`, `zinet` (drawing, logging, format detection). Content-based detection of zinet vs. graflang files avoids confusing errors.
8. **Honest process.** The gap tracker separates resolved/open/accepted, flags Qwen-origin code as unreviewed, and records departures from theory as decisions.

---

## 3. Weaknesses

### 3.1 Authoring ergonomics (biggest practical problem for an LLM-authored language)
- A 3-step linear chain (`self_refine`) takes **58 lines**: every node lists port names as free strings, every step needs a `triggers` edge **and** `binds` edges for data. Control flow mostly duplicates what data dependencies already imply.
- Ports are untyped string lists (`ports: ["trigger","complete","in_topic","out_essay"]`). Only workflow-level inputs/outputs carry types. Nothing checks that `out_essay` (text) feeds an `in_*` expecting a number *(verified in schema; inferred for runtime)*.
- Prompt templating is `str.replace("{{in_x}}", ...)` *(verified)*: no escaping, no missing-variable error, no structured values.

### 3.2 Node execution contract is thin
- **GENERATE** returns the raw LLM string on the first `out_*` port *(verified)*: no output schema, no structured output, no validation, no retry, no timeout, no token/cost accounting.
- **No retry/fallback/timeout** outside SOLVE backends *(verified by grep)*. Any node exception aborts the whole run (`node.error` then re-raise). The only graceful path is `SOLVE on_error: route`.
- **Declared but unimplemented node types:** `QUERY`, `RECOVER`, `OBSERVE`, `EMIT` are registered to the pass-through base executor *(verified)*. `RECOVER` is the natural home for error handling and it does nothing.
- Data semantics: "if several `binds` edges feed one port, the most recently written source wins" *(verified)*. Order-dependent; hard to reason about under FORK/JOIN.

### 3.3 No real concurrency
- The scheduler is a single-threaded `deque` loop *(verified: no asyncio/threads in `runtime.py`; the only threading is a shim in `procedures.py`)*. FORK branches therefore run **sequentially**. README says parallelism "without race conditions"; today it is sequencing without parallelism. For LLM-heavy fan-out, this is a large latency cost (PocketFlow's own parallel batch demos claim 3x–8x).

### 3.4 Claims exceed implementation
- README: "grounded in Lafont's Interaction Nets", "confluent", Rust compilation, "mutate the topology" as a headline. Reality per the tracker: token-passing dataflow, not rewriting (#26, #7); `grafc` stub (#11); MUTATE had no schema/example for a long time (#5); `contains_pii` is always false so the data-sovereignty policy cannot fire (#30).
- Naming overload: `graflang` / `graphlang` / `grafr` / `grafc` / `grafv` / `graf` plus the GitHub name collision workaround. `grafr`/`grafc`/`grafv`/`graphlang` are internal module organization and must not be exposed to end users (the README no longer mentions them); users see the product name and the `graf` command only.

### 3.5 Sunk cost in `grafc/cedar`
- ~1,500 lines of hand-written Cedar lexer/parser/type checker/compiler with **6 of 14 compiler tests failing** in the current run *(verified)* plus 1 slicer failure; parser defects (e.g. keyword `action` read as identifier). The runtime already uses the official engine (`cedarpy`), so this is parallel, buggy infrastructure serving a stub target.

### 3.6 SPL migration, the stated mission, is the least finished piece
- `spl2graph` and `graph2spl` are unreviewed Qwen drafts that **crash on real recipes** (gap #21): no WHILE/EVALUATE/LOGGING/assignment support. With 70+ cookbook recipes (and 40+ PocketFlow-derived ones in `SPL.py/cookbook-pocketflow`) this is the main adoption blocker.

### 3.7 Portability and environment
- Hardcoded `/home/papagame/...` paths in tests and docs; a clean checkout cannot pass its own suite *(verified: 1 failure)*.
- Core depends on sibling editable installs (`dd-llm`, `dd-logging`, `zinet`, optionally SPL.py). Fine for a monorepo workflow, fragile for anyone else.

### 3.8 Other
- A MUTATE inside a LOOP changes only that iteration's copy (accepted limitation, #32): self-revision cannot persist across iterations.
- Executor extension point (`register_executor`) is in-process Python only. No out-of-process executor protocol, so JS/Go tools must be wrapped as SOLVE subprocesses, and only for deterministic nodes.
- No bindings layer: model choice is a node `model:` hint plus CLI flags; kernel/executor choice lives inside the graph, which weakens DODA.

---

## 4. Spec vs. Implementation

| Topic | Clean-room spec | Current implementation | Verdict |
|---|---|---|---|
| Graph is source of truth | Yes | Yes | **Aligned** |
| Edge vocabulary | `data`, `control` | `binds`, `triggers` | **Aligned in substance; keep existing names** |
| Node kinds | generate/agent/evaluate/exec/solve/assert/branch/loop/fork-join/call | GENERATE/EVALUATE/SOLVE/ASSERT/LOOP/FORK/JOIN/GUARD/MUTATE/CONTEXT (+4 stubs); no `call`/subgraph-call, no `agent`, no generic `exec` | **Gaps: `exec`, `call`, `agent`** |
| Typed ports | JSON Schema on ports + trust labels | Port names only; types at workflow boundary only | **Major gap** |
| Language-agnostic compute | `exec` with executor adapters (python/node/go/http/mcp/kernel/wasm) | SOLVE `subprocess` + `kernel`; in-process Python executors | **Partial** |
| Node lifecycle (prep/exec/post) | pre → exec (retried) → post (validate, route) | Single `execute()` per node; `_route` for routing | **Gap (enhancement E1)** |
| Error model | retry, fallback, error edge, budgets | abort run; `SOLVE on_error: route` only | **Major gap** |
| Concurrency | fork/join parallel | sequential queue | **Gap** |
| Safety | allowlist + capabilities + trust labels | Cedar GUARD/MUTATE + `CODE_KEYS` + safe expr + risky-type flag (`EMIT`,`QUERY`, `risky: true`) | **Implementation is better on policy; spec's trust labels/capabilities still missing. Adopt Cedar, drop spec's allowlist file** |
| Bindings (DODA) | external bindings file | CLI flags + `model:` hint | **Gap** |
| Validation pipeline | 7 stages | JSON Schema + topology checker + runtime port check | **Partial** |
| Targets | interpreter first; codegen later | interpreter; `grafc` stub | **Aligned** (parking Rust is consistent with both) |
| Interaction nets | inspiration only | claimed as foundation, implemented as dataflow | **Align docs to reality (matches the author's stated direction)** |
| Self-revision | deferred | MUTATE implemented with strong guards | **Implementation ahead; keep, treat as advanced** |
| Observability | trace record per node | JSONL events, node output saving | **Mostly aligned; add cost/latency rollups, replay** |
| SPL migration | importer + round-trip gate | drafts that crash | **Major gap** |

---

## 5. Gap List (prioritized)

Priority: **P0** blocks the mission (SPL upgrade, practical orchestration), **P1** high leverage, **P2** later. "Tracker #" = item in `readme-design.md`.

| ID | Gap | Pri | Tracker # |
|---|---|---|---|
| G1 | SPL ⇄ graph conversion crashes on real recipes; no round-trip acceptance suite | P0 | #21 |
| G2 | No node lifecycle: no input prep/validation, output validation, retry, fallback, timeout for generic nodes | P0 | new |
| G3 | Ports untyped; no edge type checking; GENERATE has no output schema | P0 | new |
| G4 | No real parallelism for FORK; LLM fan-out is serial | P1 | new |
| G5 | Authoring verbosity: control edges duplicate data deps; free-string port lists | P1 | new |
| G6 | No language-agnostic executor protocol outside SOLVE; no `exec` node; no http/mcp/js/go adapters as first-class | P1 | partly #31 |
| G7 | `RECOVER`/`OBSERVE`/`QUERY`/`EMIT` registered but no-ops | P1 | new |
| G8 | No bindings/profile layer (DODA) | P1 | new |
| G9 | `grafc/cedar` hand-written compiler failing 6+1 tests; decision pending | P1 (decision) | #18, #22 |
| G10 | Portability: hardcoded absolute paths, sibling-repo installs | P1 | new |
| G11 | Data semantics (last-writer-wins) undefined under fork/join; no explicit state scope | P1 | new |
| G12 | Docs overstate (interaction nets, confluence, Rust) | P1 | #7, #26, #11 |
| G13 | PII detection stubbed → one Cedar policy inert | P2 | #30 |
| G14 | MUTATE inside LOOP not persistent | P2 | #32 |
| G15 | No cost/token accounting or budgets at node/graph level | P2 | new |
| G16 | No checkpoint/resume or LLM record/replay for tests | P2 | new |
| G17 | Four graph dialects (conceptbook / graph-code Duality / work-graph / graflang) | P2 | partly in zinet README |
| G18 | Resource sandboxing for subprocess/kernel beyond timeout and memory (network, filesystem) not verified | P2 | new |

---

## 6. Enhancement Design

### E1. Node lifecycle: pre → exec → post (PocketFlow-inspired)  *(closes G2, G3, G7)*

PocketFlow separates `prep(shared)` (read and shape input), `exec(prep_res)` (the only retried step, no access to shared state) and `post(shared, prep_res, exec_res)` (write results, return an action string for routing), with `max_retries`, `wait` and `exec_fallback`. Graph-Lang should adopt the **discipline**, not the Python hooks.

**Where it plugs in:** `runtime._execute_node` currently calls `executor.execute(...)` once. Wrap that in a template method on `NodeExecutor`:

```
run(node, in_data):
    payload = pre(node, in_data)             # resolve ports, apply defaults/mapping, validate in-types
    result  = retry(exec)(node, payload)     # existing executors' `execute()` becomes `exec`; retry/timeout/cache live here
        on failure after retries -> fallback (default value | alternate executor | route to `error` port | fail)
    return post(node, result)                # validate out-types, normalize, choose `_route`
```

`_route` already exists and `_emit` already honors it, so `post` produces what PocketFlow calls the action string. SOLVE's existing `on_error: route` becomes one case of the general fallback.

**YAML (additive, all optional, defaults = today's behavior):**

```yaml
- id: draft
  type: GENERATE
  config:
    prompt_ref: prompts.draft
    phases:
      pre:  {require: [in_topic], defaults: {in_style: "concise"}}
      exec: {timeout_s: 60, retry: {max: 3, wait_s: 2, on: [transient, invalid_output]},
             fallback: {route: error}}   # or {value: ""} or {executor: ...}
      post: {out_schema: {type: object, required: [summary]}, route: {ok: complete, empty: retry}}
```

The three names live under `config.phases`, the same shape as graph-code's workflow profile (`graflang-dialects.md` §5). Retry, timeout and fallback belong to `exec`. Not to be confused with the planned `RUN` node type (E4): `exec` here is a lifecycle phase every node has.

Rules:
- `pre` and `post` are **declarative** (schema checks, mappings, routing predicates via the existing `expr.py`). An optional escape hatch may point at an executor, but arbitrary host-language hooks are **not** allowed: they would hide logic from validation, Cedar and sandboxing.
- **Only `exec` is retried.** `pre`/`post` must be side-effect free (this is PocketFlow's reason for the split).
- Error classes: `transient` (timeout, 5xx, rate limit: retry as is), `invalid_output` (schema fail: for probabilistic nodes re-prompt with the structured validation error appended; for deterministic nodes fail fast), `permanent` (no retry).
- A fallback result flows through `post` like a normal result, so downstream nodes see one uniform shape.
- Implement `RECOVER` as a graph-level construct that receives `error` routes (message, node id, class) and decides retry/skip/abort, rather than leaving it a no-op.

**Acceptance corpus:** the 40+ migrated PocketFlow recipes in `SPL.py/cookbook-pocketflow` (batch, parallel, agent, guardrail, self-healing, judge, text2sql).

### E2. Typed ports and edge checking  *(closes G3, G5)*

- Keep port names as today but allow an object form: `ports: {in_topic: text, out_essay: text, complete: control}` (list form remains valid; types default to `any`). Reuse the type names already used in `workflow.inputs` (`TEXT`, `INTEGER`, `FLOAT`, `BOOL`) and add `JSON`/`LIST` with an optional JSON Schema.
- `graf validate` gains a type pass: every `binds` edge must be assignable; unknown/missing required inputs reported with the node id.
- Optional trust label on a type (`TEXT!untrusted`, `TEXT!sql_safe`) checked statically; sinks declare what they accept. Cedar remains the runtime policy layer; labels give early, localized, LLM-readable errors.
- GENERATE gains `out_schema` for structured output (feeds E1 `post`).

### E3. Authoring sugar that compiles to today's format  *(closes G5)*

Add a **compact form** that desugars to the existing nodes/edges, keeping the runtime and schema unchanged:

```yaml
steps:
  - draft:    {generate: prompts.draft,    in: {topic: $in.topic}}
  - critique: {generate: prompts.critique, in: {essay: draft.essay}}
  - refine:   {generate: prompts.refine,   in: {essay: draft.essay, feedback: critique.feedback}}
  - out:      {output: refine.essay}
```

Control edges are inferred from data dependencies and listed order; explicit `triggers` only for routing (EVALUATE/ASSERT/GUARD branches, loops). `graf expand` prints the long form for review. This is the single biggest win for LLM authoring reliability and token cost.

### E4. Generic `exec` node and executor protocol  *(closes G6)*

- Add `RUN` (deterministic; renamed from `EXEC` to keep `exec` free for the lifecycle phase) that generalizes `SOLVE backend: subprocess`: same one contract (named JSON in, one typed out, `on_error`, timeout, memory), different **executors**: `subprocess` (any binary: Go, Rust, Node script), `python` (kernel), `http` (REST/JSON), `mcp` (tool on an MCP server), later `wasm`. Keep `SOLVE` for math/kernel semantics, implemented as `RUN` plus a kernel executor.
- Define the out-of-process protocol once (JSON in/out, structured error `{code, message, retryable}`), so a new language needs only a thin adapter script, not changes to `grafr`.
- Executors that reach outside (shell, http to non-allowlisted hosts, fs write) are `risky` by default; the existing `risky: true` flag and Cedar GUARD apply.

### E5. Real concurrency  *(closes G4, G11)*

- Run FORK branches concurrently. Because LLM and subprocess calls are I/O-bound, a thread pool (or asyncio) at the node-fire level is enough; keep the deterministic **token ordering** contract at JOIN barriers.
- Define data semantics explicitly (corrected after the Next-Level review, §13): a port holds the value of its latest writer *in causal order*, not queue order. Several `binds` into one port are legal only if every pair of writers is ordered by `triggers` paths (happens-before) or sits on mutually exclusive branches (`pass`/`fail`); otherwise `graf validate` reports a race, unless the port declares a merge policy. Real fan-in uses an explicit node: `JOIN` gathers named inputs into one JSON object on its output port (the counterpart of Python's `**kwargs`), and a downstream node reads its fields (`@in_args.topic`); an unpack step splits an object or list back out. The first rule keeps the cookbook valid (4 of 6 graphs have multi-writer ports, all ordered or exclusive).
- Add `BATCH`/map semantics (PocketFlow's BatchNode/ParallelBatch): fan a list through a subgraph with a concurrency limit and a collect output. `LOOP.collect` partially covers the sequential case today.

### E6. Bindings (DODA)  *(closes G8)*

`graf run flow.graph.yaml --bind prod.bind.yaml` where the bindings file maps logical names (`$default_llm`, `$table_parser`, kernel choice) to concrete adapters/executors/paths, plus global limits (max cost, wall time). Graph files then contain no environment-specific model names or paths; the current `model:` hint remains as a fallback.

### E7. SPL migration track  *(closes G1)*

- **Decide the interim split:** keep the interpreter as the system of record; make `spl2graph` the priority.
- Rewrite `spl3/spl2graph.py` against the real SPL AST with full coverage of WHILE/EVALUATE/LOGGING/assignment/CALL/CALL PARALLEL.
- Acceptance gate: every recipe in `Cookbook-of-SPL-Recipes` and `cookbook-pocketflow` converts and validates, and a sample runs with `claude_cli`; for a sample, outputs match the SPL run semantically. `graph2spl` is best-effort projection, lower priority.
- The spec's mapping table (`GENERATE→generate`, `ASSERT→assert`, `WHILE→LOOP` with required `max_iterations`, `CALL PARALLEL→FORK/JOIN`) already matches the implementation's node set.

### E8. Safety consolidation  *(closes G9, G13, G18)*

- **Use Cedar for policy; keep the existing guards.** Remove from the spec: allowlist file and capability list as separate mechanisms. Instead express risky-node allowlisting and capability grants as Cedar policies over node attributes (`type`, `risky`, `needs`), evaluated by `graf validate` (static) and GUARD (runtime).
- **`grafc/cedar`: park or delete.** Recommendation: stop investing in the hand-written Cedar compiler. If a Rust target is ever built, generate code that calls the official `cedar-policy` crate. This removes ~1,500 lines and 7 failing tests, and a large maintenance risk.
- Verify and document sandbox limits for `subprocess`/`kernel` (network, filesystem, env). If absent, add opt-in container/WASM execution for risky executors.
- Either implement `contains_pii` or remove the policy that depends on it.

### E9. Observability and testing  *(closes G15, G16)*

- Roll up per-node latency, tokens, cost into the run summary; enforce optional graph/node budgets from bindings.
- Record/replay of LLM calls (cassette style) so tests and CI never need a real model; the `mock` adapter covers shape, replay covers behavior.
- Checkpoint per node so a failed long run can resume.

### E10. Hygiene  *(closes G10, G12, G17)*

- Replace absolute paths with env/config (`$SPL_PY_PATH`, repo-relative fixtures); skip, don't fail, when optional siblings are absent. Goal: `pip install -e ".[dev]" && pytest` green on a clean machine.
- Rewrite README claims to what exists: "token-passing dataflow; Cedar-guarded; Rust compile planned/optional". Move interaction-net material to a "Background/Inspiration" page, consistent with the author's stated direction.
- Publish a short **"two layers"** doc: `zinet` = static knowledge/blueprint graphs (book, KB, app blueprint), `graflang` = executable workflows; graflang workflows read and write zinet graphs. Freeze new dialects until `graph-code`'s Duality schema and zinet's three-layer format have a written mapping.

---

## 7. Is Graph-Lang the Right Move?

For orchestration upgrades over SPL, yes. The evidence is the working runtime, the passing tests, and the strong safety design. The risks are scope and discipline, not concept:

- **Scope:** keep Graph-Lang to *executable workflows*. Books, knowledge bases and app blueprints are *static* graphs (zinet family) that workflows build and consume. Efficiency for books/apps/KBs comes from shared validate/diff/slice/render plus workflows that generate content from those graphs, not from one language covering everything.
- **Discipline:** the biggest threats are documentation outrunning code, four diverging graph dialects, and polishing exotic parts (Cedar compiler, Rust target, interaction-net theory) before the everyday path (typed nodes, retries, parallel fan-out, SPL migration) is solid.

---

## 8. Revised Roadmap

**R0 — Clean base (≈1 week)**
G10 portability, G12 README honesty, decide G9 (park `grafc/cedar`), get a clean-machine green suite.

**R0.5 — Semantics and soundness (before R1; see §13)**
S1 written core semantics (two pages, followed by tests); S2 happens-before race check and `JOIN`-after-exclusive-branch deadlock check in `graf validate`; S3 `MUTATE` re-runs `graf validate` on the resulting graph and the safety layer (guards, policies, `risky`) becomes immutable to deltas; S4 scheduler characterization tests (the current behaviour pinned down, accidents named).

**R1 — Node contract (core of the upgrade)**
E1 lifecycle (pre/exec/post, retry, fallback, `RECOVER`), E2 typed ports and validator pass, GENERATE `out_schema`. Acceptance: PocketFlow cookbook set run with `claude_cli` (`claude-sonnet-5-5`) and recorded for replay.

**R2 — SPL parity and ergonomics**
E7 `spl2graph` rewrite and round-trip gate; E3 compact authoring form; E6 bindings.

**R3 — Language-agnostic compute and speed**
E4 `RUN` + executor protocol (subprocess, http, mcp); E5 concurrent FORK/BATCH and explicit merge rules.

**R4 — Safety and operations**
E8 Cedar-based allowlist/capabilities, sandbox verification; E9 cost accounting, replay, checkpoints.

**R5 — Advanced**
Persistent MUTATE across loop iterations (G14), optional Rust/WASM packaging, zinet↔graflang read/write nodes for book/KB/app generation.

---

## 9. Decisions Needed from Wen

1. **Lifecycle form:** declarative-only `pre`/`post` (recommended), or also allow executor-backed hooks as an escape hatch?
[WEN] declarative-only

2. **Edge names and control inference:** keep `triggers`/`binds` and add compact form E3 (recommended), or redesign?
[WEN] no redesign

3. **`grafc/cedar`:** park/delete (recommended) vs. repair.
[WEN] your recommend

4. **Concurrency model:** threads vs. asyncio for FORK/BATCH. Threads are simplest with the current sync runtime and subprocess/LLM-CLI calls.
[WEN] simple for now, will enhance in future

5. **Typing depth:** simple scalar types plus optional JSON Schema (recommended) vs. full schema everywhere.
[WEN] your recommend

6. **Where compact form and new executors live:** extend `graflang` in place, or incubate in a branch until R1 acceptance passes.
[WEN] extend in place

7. **Dialects:** write a zinet ⇄ graph-code ⇄ graflang mapping now, or defer.
[WEN] now

### Resolution summary (Claude's reading of the answers above)

| # | Decision | Consequence |
|---|---|---|
| 1 | `pre`/`post` are declarative only | No executor-backed hooks; `pre`/`post` hold schema checks, mappings and routing predicates (E1) |
| 2 | No redesign of edges | Keep `triggers`/`binds`; add compact authoring form (E3) as sugar that expands to today's format |
| 3 | Park/delete `grafc/cedar` | Stop the hand-written Cedar compiler; runtime keeps `cedarpy`; any future Rust target calls the official `cedar-policy` crate |
| 4 | Concurrency: simple for now | Stay sequential until R3, then a thread pool for FORK/BATCH; no asyncio rewrite |
| 5 | Typing: scalar types + optional JSON Schema | As recommended in E2 |
| 6 | Extend `graflang` in place | No incubation branch; ship E1–E3 behind defaults that preserve today's behavior |
| 7 | Dialect mapping now | Done as `graflang-dialects.md`; its work items M1–M8 feed R1/R2 |

**Added after the dialect review:** the shared graph model lives in **zinet** (`zinet.model`), decided now rather than starting in graflang and migrating later; graph-code is still in development, which is when the move is cheapest. See `graflang-dialects.md` §3.1 and work items M1–M4. Roadmap effect (revised, §12 decision 6): zinet is not released during graflang development, so M1–M4 no longer gate R1; zinet and graflang change together.

**Follow-up from the dialect review:** graph-code's `workflow` profile defines `node.phases: {pre, execute, post}` and action-routed `function.transitions`. E1 uses the short names `phases: {pre, exec, post}` (owner decision); graph-code's `execute` maps to `exec` in the dialect mapping. See `graflang-dialects.md` §5.

**Scope after the dialect answers (`graflang-dialects.md` §8):** build graflang first. graph-code, work-graph and ConceptBook are refactored later, once graflang is stable (ConceptBook also after its paper is out), so the dialect work in this release is zinet plus graflang only; G17 is deferred. graph-code's `ide` module is to be reviewed and migrated into graflang (see §10).

---

## 10. Build and Test Policy

- **Real LLM, not mock.** The `mock` adapter stays in the code and in this design, but from the start of the build, new tests, examples and acceptance runs use `claude_cli` with the default model `claude-sonnet-5-5` (`--llm claude_cli:claude-sonnet-5-5`). Keep calls small: short prompts, few cases per test.
- **Status of R0 items:** G12 README honesty is done (interaction nets, "confluent" and Rust compilation removed; internal module names no longer shown); G10 hardcoded `/home/papagame/` paths are removed from code (recorded run outputs under `experiments/` keep them as history); decide G9 remains.
- **Build status (R0, R0.5, R1, R2 done; R3 under way):** R3 part 1 (E5): `JOIN` with `in_*` ports bundles them into an object (`@in_args.name` reads a field; expressions also take `@list[i]`); opt-in concurrent mode (`--workers N` / `limits.concurrency`; waves of released nodes, GENERATE and slow SOLVE on a thread pool, results applied in token order; every shipped graph gives the same result with 4 workers as with 1); `BATCH` node (a subgraph over a list, `collect` outputs, `concurrency`, `max_items`). R3 part 2 (E4): `RUN` node (`grafr/run_node.py`): `executor: subprocess | python | http`, one contract (named JSON in, one typed result out, `on_error`, timeout); subprocess and python are the SOLVE backends under the new name, http posts `{inputs}` to `url` and requires an `allow_hosts` list, refuses redirects, reads `{result}` or `{error: {code, message, retryable}}`, and a retryable error is a transient failure for `phases.exec.retry`; `executor`, `url`, `allow_hosts`, `headers`, `method` are code keys a MUTATE delta can never set. Not yet: the `mcp` and `wasm` executors, and a thin-adapter kit for new languages. R2 was:  R2 part 5: `graf export-spl` (`graphlang/grafe/`, graflang's own graph-to-`.spl` emitter; no SPL.py import): a lifted graph comes back with its CREATE FUNCTION / CREATE TOOL_API and lifts to the same graph again (checked when SPL.py is installed), a hand-written GENERATE becomes a function named after its node; lifecycle phases are dropped with a warning. Limitation: SPL variables are named after out ports, so two nodes writing one port name and a reader of the earlier one can alias. R2 part 4: E6 bindings (`--bind FILE` on `graf run`, `grafr/bindings.py`: `llm`, `models` for `model: $name`, default `params`, `resources` replacement, `limits.max_steps` and `wall_time_s`; flags beat the file beats the graph's hints; `max_cost` is refused because adapters report no cost). R2 part 3: E3 compact form (`steps:` in `grafr/compact.py`, expanded inside `load_graph`, so run, validate, vis and the rest all accept it; `graf expand FILE` prints the long form; kinds generate, solve, assert, evaluate, guard, fork, join, output and `node` as the escape hatch; control inferred from order and `on:`, literals become input defaults). Not in the compact form yet: loops written as steps (a `node: LOOP` carries its `subgraph` in long form).  R2 part 1 (E7): **`spl2graph` stays in SPL.py**, not graflang (owner rule: graflang must not depend on SPL.py, except that it may emit `.spl` and may run `.spl` through `procedure_ref`, as `cookbook/code_pipeline` does). SPL.py depends only on the graph file format. Gap #21 (\"crashes on real recipes\") was stale: of 274 workflow files in `SPL.py/cookbook` and `cookbook-pocketflow`, 265 lift and pass `graf validate` (before the fixes: 197). Fixes (in SPL.py's `spl3/spl2graph.py`, `graph2spl.py` updated to keep the round-trip gate): a CREATE FUNCTION body is the GENERATE prompt (`{param}` becomes `{{in_param}}`, `config.params` lists the parameters, a literal argument becomes a port default under `phases.pre.defaults`), tool calls in ASSERT become a SOLVE that runs first, `IN` conditions, CALL PARALLEL branches that are functions or tools, unquoted input defaults. `cookbook/chain_of_thought` is a lifted graph kept as an example and run with `claude_cli`. R2 part 2: a Python tool call (`CREATE TOOL_API` in the file or an IMPORTed one, a sibling `tools.py`, or a built-in such as `write_file`) is lifted to a `kernel` SOLVE whose `code` is the tool's source plus the call, so the graph runs in graflang's own kernel with no SPL.py (`cookbook/lifted_tool`, run offline); across the SPL.py cookbooks 1435 tool calls carry their source and 158 remain name-only (callee defined elsewhere, or source that does not compile, which gets a warning); `graph2spl` writes the `CREATE TOOL_API` back. Still open: the remaining invalid files (a tool call in a WHILE condition, parallel branches naming workflows that exist nowhere), `graph2spl` as a graflang-owned `.spl` emitter (SPL.py's copy exists meanwhile), E3 compact form, E6 bindings. Earlier: R1 was: R1 part 1: E1 lifecycle in `grafr/lifecycle.py` (`config.phases`: `pre` require/defaults, `exec` retry/wait/fallback route or value, `post` `out_schema` with JSON parsing; GENERATE asks for JSON matching the schema and re-prompts with the validation error; `graf validate` checks the block). R1 part 2: E2 typed ports in `grafr/ports.py` (`ports` may be a name-to-type mapping, types `ANY TEXT INTEGER FLOAT BOOL LIST JSON control`, `{type: JSON, schema: ...}`; `graf validate` rejects a `binds` edge whose types are not assignable and unknown or misplaced types; a run checks each typed value as it is written). R1 part 3 (R1 complete): `exec.timeout_s` (worker thread; a timed-out call may keep running in the background), `post.route` (control port chosen by a condition over the in_/out_ values), `RECOVER` as a real node (`action: halt|abort|skip|retry`, `max_retries`, `then`; `retry` port wires back to the failed node; `halt` ends that branch quietly, as the code_pipeline `abort_vague` node already assumed), trust labels (`TEXT!sql_safe`: a sink's labels must all be on the source) and `workflow.inputs` types typing the INPUT node's ports. Not done: R1's acceptance corpus (the PocketFlow recipes, needs the R2 `spl2graph` rewrite). One real-LLM test (`-m llm`, `claude_cli`, `claude-sonnet-5-5`) passes; the `llm` marker is registered in `pyproject.toml`. Earlier: R0: suite green on a clean checkout apart from the known `grafc/cedar` failures (left alone); the `spl` experiment arm no longer depends on `spl3` being on `PATH`. R0.5: S1 `graflang-semantics.md`; S2 race and JOIN-deadlock checks in `graf validate` (`topology.py`); S3 `MUTATE` re-checks the guarantees on a trial copy and refuses to touch `GUARD`/`MUTATE` nodes or the `risky` flag (`runtime.py`); S4 `tests/test_semantics.py` pins rules R1 to R10. Run tests with the `graf` conda env (`~/anaconda3/envs/graf/bin/python -m pytest`).

## 11. graph-code `ide` Review (input to the migration)

- **What it is:** `graph-ide`, a ~3.3k-line browser viewer/editor for graph-code blueprints: FastAPI backend (`api/`, ~600 lines) plus a Vite and vanilla-JS frontend with a hand-written SVG renderer (`GraphView.js`, 371 lines), detail panel, settings modal, and pages for graph, drift and build. Launched by `grafcode ide`.
- **Maturity: early.** Ported on 2026-08-14 from another tool; last touched 2026-10-24. Working: app discovery, merged multi-file graph view, click-to-highlight dependency path, drag-to-rearrange, and UPDATE of existing nodes' prose fields (`defines`, `docs`, `spec.*`, `verification.*`). Not built: create or delete nodes and edges, editing structure (`composed_of`, `depends_on`, `needs`), running a build, cloning, comparing, LLM assistance (the Settings LLM section is stored but unused). No tests reference it. Its README lists those gaps as unscheduled ideas.
- **Worth migrating (ideas and small pieces):** the `ruamel.yaml` round-trip writer that keeps comments and formatting and validates a trial write before touching the real file (`graph_writer.py`, 161 lines); content-based graph discovery; node click/highlight/detail interaction; the editable-fields whitelist as a safety pattern.
- **Not reusable as is:** it is bound to graph-code's schema (`graph_code.loader`, `validate_full`, `form.nodes` kinds), so every backend call must be rewritten against the graflang IR (`triggers`/`binds`, ports, LOOP subgraphs). The layout is a tiered DAG for dependency graphs, not a port-level workflow with loops. A workflow IDE needs more than the prose-only edit mode: add/connect nodes and ports, edit config, validate while editing. That is the README's "Visual IDE" roadmap item.
- **Verdict:** treat it as a reference prototype, not a base to fork. Reuse the writer pattern and the interaction design; build the workflow-specific parts new, on top of `graf validate` and the zinet drawing engines. Spec Held Up

## 12. Build Decisions (open questions, answered)

| # | Question | Decision | Consequence |
|---|---|---|---|
| 1 | `exec` phase vs `EXEC` node | Node type is **`RUN`** | E4 and the roadmap use `RUN`; `exec` stays the lifecycle phase |
| 2 | Several `binds` into one port | **Explicit nodes** split and join for real fan-in; ordered or exclusive writers stay legal | `JOIN` bundles named inputs into one JSON object (the `kwargs` counterpart), with an unpack step to split. Unordered writers are a race reported by `graf validate` (happens-before rule, E5 and §13). Replaces the earlier "one source per port" wording, which would have broken the cookbook |
| 3 | `grafc/cedar` | **Leave it alone** | No deletion or move; its 7 failing tests stay known failures (gap #18). Not on the build path |
| 4 | Real-LLM test gating | A small default set; the rest behind `-m llm`; recorded replays (E9) for CI | Register the `llm` marker in `pyproject.toml`; tests call `claude_cli:claude-sonnet-5-5` |
| 5 | IDE target | Left to me: **Streamlit**, behind `graf vis` (read-only by default, `--edit` for the IDE; `graf ui` is a hidden alias) | See below |
| 6 | zinet prerequisite | zinet is not released while graflang is developed, so both codebases may change together | M1–M4 no longer gate R1; change zinet in step with graflang, and take the `zinet` dependency as an editable install |

**IDE (decision 5).** No new command. `graf vis` is the viewer and stays the one entry point; `graf ui` is a hidden alias for it, the same way `graf viz` already is. Plan: `graf vis <graph.yaml>` is read-only by default (today's view, plus click-to-inspect); `graf vis --edit <graph.yaml>` enables the IDE mode (update, add, connect and delete nodes, ports and edges), validated through `graf validate` before every write, with round-trip YAML so comments survive, as in graph-ide's writer. The edit mode reuses the `MUTATE` delta validation (schema, structure, `CODE_KEYS`), so a hand edit and a model edit pass the same checks. Streamlit over Vite because it needs no Node toolchain, matches the README roadmap, and the repo is Python-only; the current engines (cytoscape and others) remain for read-only output, and `--edit` opens the Streamlit app. If a richer canvas is needed later, embed the zinet cytoscape view.

---

## 13. Review Findings from the Next-Level Notes

Source: five notes in `zinets/docs/graph-vision/Next-Level/` (`opus-5-5-review.md`, `review-2-lineage.md`, `brainstorm-1-explicit-order.md`, `brainstorm-2-semantic-ir.md`, `chat-history-1.md`). **Stance: practical.** The goal is working code that builds real apps. Graph-Lang stays a coordination language for LLM workflows; the general-purpose ambition, and the theory it would need, is dropped.

### 13.1 Adopted into the build (new roadmap step R0.5, plus changes to E5)

| Id | Item | Why it matters for real apps |
|---|---|---|
| S1 | **Written core semantics**: when a node fires, what it reads, how a port with several writers resolves, what a LOOP iteration sees, what failure means. Two pages, then make the runtime follow them and turn each rule into a test. | Today the meaning of a graph is whatever `runtime.py` does. Front-ends (SPL conversion, compact form E3, the IDE, model deltas) can build the same graph and read it differently. |
| S2 | **Race and deadlock checks** in `graf validate`. Race: two writers to one port that are neither ordered by `triggers` paths (happens-before) nor on exclusive branches. Deadlock: a `JOIN` fed by branches of which only one can fire (`pass`/`fail`). Both are token counting on the control graph. | Both fail silently at run time (wrong value, or a run that hangs). Needed before FORK runs concurrently (E5). |
| S3 | **`MUTATE` keeps the graph valid**: re-run `graf validate` on the result of every accepted delta and reject it if it fails. Protect the safety layer: a delta may not change `policy_ref`, `risky`, a guard's wiring or any `GUARD` node. Deltas become transactions (several edits, validated as a whole). | Today the checks are not re-run after a delta, so an `add_edge` can route around a guard, and `update_config` can change a guard's `policy_ref`. Closes the gap between the safety claim and the code. |
| S4 | **Characterization tests for the scheduler**, in zinet's method: pin down current behaviour, name each accident, then decide keep or fix. | Stops silent drift while E1–E5 change the runtime. |
| E5 fix | Multi-writer ports: happens-before rule instead of "one source per port" (see E5, §12 decision 2). | The cookbook relies on multi-writer ports (`code_pipeline`, `compliance_audit`, `solver_check`), all ordered or exclusive. |

Also adopted, already in the plan: typed ports (E2), error model (E1), real concurrency (E5), README honesty (done).

### 13.2 Findings I did not adopt

- **A separate textual surface syntax.** The review proposed one; the later note treats the YAML as an IR reached through front-ends (compact form E3, `graf vis --edit`, SPL conversion, model deltas). Keep E3 small and skip a new language.
- **Effect system and a formal soundness story** (pure / stochastic / external effects typed through the graph). Good paper material, not on the build path. The existing risky-node guard check already gives most of the practical value.
- **Petri-net/Kahn proofs and an interaction-net research track.** Use the ideas (token counting, single causal writer) where they give a check (S2); no theory work.
- **General-purpose features**: recursion, higher-order graphs, user-defined node types beyond `RUN`.

### 13.3 Later items, kept for when the base is stable

1. **Abstraction: named, parameterised subgraphs** with typed ports, imported from other files, with `LOOP` becoming one use of it. Reuse graph-code's import/export/contract model. Needed once real apps pass a few dozen nodes (the point where graph languages become unreadable). Candidate for R3, after E1–E3.
2. **Elaboration**: map a knowledge graph through a template into a workflow graph (one node becomes one template instance, edges become wires by a declared rule). The best real-app experiment: rewrite the two hand-written driver scripts (`build_concept_book.spl`, `build_component.spl`) as one template applied to two graphs, and measure lines, dependency errors caught by `graf validate`, and wall-clock time with parallel sections. Depends on abstraction and on concurrency. Keyword (`ELABORATE`, `EXPAND` or `INSTANTIATE`) is the owner's call.
3. **Shared rule language** in zinet for graph constraints (reachability, "every requirement has a verifier"), with today's validator checks as its first rules; GraphLang's `graf validate` rules would then be data. Start inside graflang's validator, move to zinet once two tools need it.
4. **Provenance on deltas**: `origin` (llm / human), confidence and lineage on a `MUTATE` delta, so Cedar can require human approval for an LLM-origin delta that adds a risky node.
5. **Human nodes and durable runs** (a step that waits for a person; a run that survives restarts), for work-graph style processes. Builds on checkpointing (E9).
6. **Step debugger and a graph-level test harness** (fixtures for model outputs, assertions on routes and values), built on the existing logs and the replay of E9.
7. **Loop semantics**: back-edge retry wires and `LOOP` bodies behave differently (shared store vs a fresh copy per iteration); specify and test their interaction as part of S1, and fix stale reads across iterations.

### 13.4 Open questions raised by the review

1. **ConceptBook ordering.** Is the sequential section order deliberate (style consistency)? If so it is a real dependency and should be an edge. Matters when elaboration makes sections parallel.
2. **Declared independence.** Should an author be able to claim "these must not be ordered" and have the checker verify it? Needed for safe parallelism; defer until S2 exists.
3. **Merge policies.** Which policies should a port declare (`collect`, `priority`, others), and should the default be "error"? Decide with S2.
4. **Re-validation scope.** Re-run `graf validate` on every `MUTATE`, or only on deltas touching control or data edges? Start with every delta; it is cheap.
5. **Where the rule language lives** (zinet from the start, or graflang first).

---

## Appendix: How the Clean-Room Spec Held Up

**Independent design choices that turned out to match the implementation:**
- Graph as source of truth
- Two edge classes
- Closed node-kind set
- Loops must be bounded
- SOLVE-style subprocess executors with one JSON contract
- Schema errors as structured feedback
- Deferring Rust
- Keeping self-revision behind validation

**Where the spec was weaker:**
- It invented an allowlist/capability layer where Cedar already exists
- It assumed greenfield node kinds where most already exist

**Where the implementation is weaker than the spec** (sections 3 and 6):
- Typed ports
- Error handling
- Concurrency
- Bindings
- Authoring ergonomics
