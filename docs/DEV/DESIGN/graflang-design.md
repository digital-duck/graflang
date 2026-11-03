# Graph-Lang — Design Review: Current Implementation vs. Spec

Companion to `graflang-spec.md` (clean-room spec, written **before** looking at the code) and `graflang-req.md` (requirements).
This document reviews the existing prototype at `~/projects/digital-duck/graflang` against that spec, lists strengths, weaknesses and gaps, and proposes enhancements.

**Status, 2026-11-01.** Sections 1 to 9 are the review of 2026-10-30 and are kept as written (the numbers in them are from that day). Everything they ask for has since been built or decided: §5a says, gap by gap, what became of each; §10 is the build log; §14 describes the editor app and §15 the migration of the solver recipes, both done after the review. Appendix B is the current to-do list. The basic functionality of GraphLang is in place: write or generate a graph, validate it, run it with a real model under a budget, edit it in the app, and bring SPL recipes over with `spl2graph`.

**Method and limits**
- Read: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, the IR schema, `grafr/runtime.py` (key parts), `nodes/generate.py`, `nodes/evaluate.py`, `nodes/__init__.py`, head of `solve_backend.py`, the `self_refine` cookbook graph, and the gap tracker `zinets/docs/graph-vision/claude/readme-design.md`.
- Ran: `pytest` in conda env `graf` → **355 passed, 8 failed, 2 skipped** (25 s). Failures: 6 in `test_cedar_compiler.py`, 1 in `test_policy_slicer.py`, 1 in `test_experiment_end_to_end.py[spl]` (hardcoded absolute path, a portability bug; the hardcoded SPL.py paths in `experiments/` are since fixed via `SPL_PY_PATH`).
- **Not read in depth**: `grafc/` internals, `grafv/`, `procedures.py`, `kernel.py`, `solver.py`, `mutate`/`loop` implementations, the other five cookbook graphs, `docs/GUIDE`. Sibling repos `graph-driven-workflow`, `sdlc-graph`, `pocoflow`, `markoflow`, `monteflow` were not examined. Statements below are marked *(verified)* when checked in code or tests, *(inferred)* otherwise.

---

## 1. Snapshot of the Implementation

| Area | State |
|---|---|
| Package | `graflang` (PyPI) / `graphlang` (import); CLI `graf run\|validate\|info\|expand\|describe\|create\|compile\|vis` (`vis --edit` opens the app); 1065 offline tests pass (7 known `grafc/cedar` failures) *(2026-11-01)* |
| Runtime `grafr` | Token-passing dataflow over a `networkx.MultiDiGraph`; node types GENERATE, EVALUATE, SOLVE, ASSERT, LOOP, BATCH, FORK/JOIN, GUARD, MUTATE, CONTEXT, RUN, RECOVER, INPUT/OUTPUT (QUERY, EMIT and OBSERVE became real on 2026-11-03: `grafr/outside.py`) |
| Edges | Two types: `triggers` (control tokens between named ports) and `binds` (data, keyed by port name) |
| LLM | `mock` (tests only) plus adapters through shared `dd-llm` (`claude_cli`, `ollama`, `openai`, ...); default `claude_cli` with `claude-sonnet-5-5` |
| Deterministic compute | `SOLVE` via `expression`, `procedure_ref` (SPL workflow), `backend: kernel` (persistent Python kernel, any installed Jupyter kernel through `kernel_name` / `--kernel-name`, e.g. `sagemath`) or `backend: subprocess` (any program, optionally in a container); `RUN` for subprocess, python and http executors |
| Safety | Cedar (`cedarpy`) for GUARD/MUTATE, fail-closed; safe expression evaluator (with f-strings); MUTATE cannot add code-bearing keys (`CODE_KEYS`); `graf validate` also rejects a prompt whose `{{in_x}}` nothing fills |
| Compiler `grafc` | `graf compile --lang spl` works; Rust is a stub; the ~1,500-line hand-written Cedar compiler is left alone |
| Viz and app | `graf vis` via `zinet.vis` engines; `graf vis --edit`, a Streamlit app with Welcome, Create, Edit, Browse, Import/Export and Settings pages (§14) |
| Cookbook | `cookbook/` (`code_pipeline`, `self_refine`, `your_book`, `compliance_audit`, `solver_check`, `ts_verify`, `stock_analysis`, `pocketflow`, ...) and `cookbook_solvers/`, 47 solver recipes migrated from SPL.py (§15) |
| Process | Gap tracker with 48 numbered items; 59 test files |

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
- **Declared but unimplemented node types** *(as of 2026-10-30; `RECOVER` and, on 2026-11-03, `QUERY`, `OBSERVE` and `EMIT` have since been built)*: `QUERY`, `RECOVER`, `OBSERVE`, `EMIT` were registered to the pass-through base executor *(verified)*. `RECOVER` is the natural home for error handling and it does nothing.
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
- A MUTATE inside a LOOP changes only that iteration's copy by default (#32); `persist_mutations: true` on the LOOP carries the changed body into the next iteration.
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

### 5a. What became of each gap (2026-11-01)

| ID | Status | Where |
|---|---|---|
| G1 SPL conversion | **Resolved.** `spl2graph` (in SPL.py) lifts 265 of 274 cookbook workflows; the 47 solver recipes were migrated and run with a real model | §10 R2, §15 |
| G2 lifecycle | **Resolved** (`config.phases`) | E1, §10 R1 |
| G3 typed ports | **Resolved** | E2, §10 R1 |
| G4 parallelism | **Resolved**, opt-in (`--workers`, `BATCH`) | E5, §10 R3 |
| G5 authoring | **Resolved**: compact `steps:` form, `graf expand`, and the app's Create page that writes a graph from a description | E3, §14 |
| G6 executors | **Resolved** for subprocess, python and http (`RUN`); `mcp` and `wasm` are out for now | E4 |
| G7 stub node types | **Closed 2026-11-03.** `RECOVER`, `QUERY`, `EMIT` and `OBSERVE` are real (`grafr/outside.py`) | Appendix B |
| G8 bindings | **Resolved** (`--bind`) | E6 |
| G9 `grafc/cedar` | **Decided: leave it alone**; its 7 test failures stay known | §12 decision 3 |
| G10 portability | **Resolved** | §10 R0 |
| G11 data semantics | **Resolved**: written semantics, race and deadlock checks | `graflang-semantics.md` |
| G12 overstated docs | **Resolved** | §10 |
| G13 PII | **Resolved** (`has_pii`) | tracker #30 |
| G14 MUTATE in LOOP | **Resolved** (`persist_mutations`) | tracker #32 |
| G15 cost accounting | **Resolved** (run summary, `limits`) | §10 R4 |
| G16 checkpoint and replay | **Resolved** | §10 R4 |
| G17 four dialects | **Deferred** until graflang is stable | `graflang-dialects.md` §8 |
| G18 sandboxing | **Partly.** Memory, environment and time limits, and an opt-in Docker container (verified); filesystem and network limits for kernel nodes are not enforced, no WASM sandbox | §10 R4 |

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

*All of R0 to R4 is done and part of R5 (§10 is the log).*

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
- **Build status (R0 to R4 done; the editor, parts and elaboration done; R5 under way).** By phase, newest first. Run tests with the `graf` conda env (`~/anaconda3/envs/graf/bin/python -m pytest`); the only known failures are the 7 in `grafc/cedar` (left alone).
  - **After the review, 2026-11-01.**
    - *Editor app (§14):* six pages (Welcome, Create, Edit, Browse, Import/Export, Settings), `graf create` and `graf describe` on the command line, recipe search by meaning and words, three work-area roots (`apps`, `cookbook`, `solvers`), a security review with every finding fixed (`graflang-UI.md`).
    - *Solver recipes (§15):* 47 SPL.py recipes migrated, run with `claude_cli` / `claude-sonnet-5-5`, and `cookbook_solvers/` kept as the reviewed copy.
    - *Language and runtime:* f-strings in expressions; a `procedure_ref` into an `.spl` with several workflows runs the right one; `kernel_name` / `graf run --kernel-name` picks the Jupyter kernel of kernel SOLVE nodes (one kernel per name); `graf validate` errors on a prompt whose `{{in_x}}` has no port or no feeding edge.
    - *`spl2graph` (in SPL.py):* ports and placeholders named after the variable passed in, tool types from the return annotation, `SOLVE` statements as kernel nodes with `--kernel-name`, `run_python` in the shared kernel, runtime counters, numeric comparisons of text results, a warning for each file the graph needs, one output file per `--workflow`.
  - **Later items (13.3).**
    - *Abstraction (item 1):* named subgraphs (`grafr/parts.py`). A workflow file listed under `resources.parts` is used as a `SUBGRAPH` node (compact `use`), checked against its interface (ports, types, defaults) and expanded in place; nesting works, a part using itself is refused; `graf vis` draws each use as a box. Example: `cookbook/parts_demo`.
    - *Elaboration (item 2):* `grafr/elaborate.py`. An `elaborate:` block applies a part to every node of a graph of things; edges become ordering (FORK at the roots, JOIN where edges meet) and optionally data (`pass`). The keyword `elaborate` is provisional (the owner's call). Example: `cookbook/elaborate_demo`. Not yet used to rewrite the two ConceptBook driver scripts.
    - *Loop semantics (item 7, gap #32):* a LOOP with `persist_mutations: true` carries a MUTATE's changes into the next iteration; the default is unchanged.
  - **Editor (decision 5).** `graf vis --edit FILE` (`graf ui` hidden alias) opens a Streamlit app (`grafv/app.py`, extra `edit`) on `GraphEditor` (`grafv/editor.py`): ruamel round trip that keeps comments, edits validated by `graf validate` before Save, undo, atomic write, and a Run tab that runs the graph as currently edited (`mock` by default, `claude_cli` optional). Tested with Streamlit's AppTest and the engine's own tests. Not in it, by decision: drag-to-connect on the canvas (edges are chosen from lists) and editing compact `steps:` / `elaborate:` files (edited as text).
  - **R4 (done).**
    - E9 run summary (`grafr/metering.py`): calls, tokens and cost as the adapter reports them, per-node firings and time, `summary.json` in the run folder.
    - Budgets: `limits.max_llm_calls`, and `limits.max_cost_usd`, which fails loudly (at the second call) when the adapter reports no cost, as `claude_cli` does.
    - Cassettes: `graf run --record FILE` / `--replay FILE`, keyed by model, prompt and temperature; an unrecorded call fails loudly; `cookbook/chain_of_thought` ships one recorded with `claude_cli`.
    - E8: `has_pii` (email, phone, US SSN, Luhn card, IBAN) for guards, and MUTATE sets `contains_pii` from the delta; `workflow.policy` (`grafr/capabilities.py`), a Cedar policy about the nodes a workflow may contain, enforced by `graf validate` and refused at `graf run`.
    - Sandbox: memory limit and environment scrubbing are tested; a `subprocess` node may add `container: {image, ...}` (`docker run`: no network, read-only root, capabilities dropped, graph folder mounted read-only, caps on memory, CPU and processes, a timeout kills the container; `container` is a code key a MUTATE can never set). Verified against a real Docker Desktop daemon (2026-10-30: no network, read-only mount and root, timeout removes the container, `cookbook/container_demo` end to end) as well as a stub `docker`. Docker Desktop shares only the home directory, and mounting any other folder hangs rather than failing, so `check_mount_shared` refuses it up front (`GRAF_DOCKER_SHARED` lists extra shared folders). Kernel nodes and plain subprocess nodes still run with the user's privileges (pinned as KNOWN tests).
    - E9 checkpoint/resume: `--checkpoint FILE` before every top-level step, `--resume FILE`; JOIN progress and MUTATE changes included; a LOOP or BATCH is one step; kernel variables are not restored.
    - Not yet: a WASM sandbox.
  - **R3 (done).**
    - E5: `JOIN` with `in_*` ports bundles them into an object (`@in_args.name`; expressions also take `@list[i]`); opt-in concurrency (`--workers N` / `limits.concurrency`; waves of released nodes, results applied in token order; every shipped graph gives the same result with 4 workers as with 1); the `BATCH` node (a subgraph over a list, `collect`, `concurrency`, `max_items`).
    - E4: the `RUN` node (`grafr/run_node.py`), `executor: subprocess | python | http`, one contract (named JSON in, one typed result out, `on_error`, timeout); http requires `allow_hosts`, refuses redirects, reads `{result}` or `{error: {code, message, retryable}}`, and a retryable error is a transient failure for `phases.exec.retry`; `executor`, `url`, `allow_hosts`, `headers`, `method` are code keys a MUTATE can never set.
    - Not yet: the `mcp` and `wasm` executors, and a thin-adapter kit for new languages.
  - **R2 (done).**
    - E7: **`spl2graph` stays in SPL.py**, not graflang (owner rule: graflang does not depend on SPL.py, except that it may emit `.spl` and run `.spl` through `procedure_ref`, as `cookbook/code_pipeline` does). Of 274 workflow files in the SPL.py cookbooks, 265 lift and pass `graf validate` (197 before the fixes). A CREATE FUNCTION body becomes the GENERATE prompt; a Python tool call (`CREATE TOOL_API`, a sibling `tools.py`, or a built-in) becomes a `kernel` SOLVE carrying the tool's source (1435 tool calls carry their source, 158 stay name-only). Examples: `cookbook/chain_of_thought`, `cookbook/lifted_tool`. Of the 9 files that still do not lift (survey of 2026-10-30), none is a lifter fault: 3 are directories named `.spl`, 2 are rejected by SPL.py's own parser, 1 is a rendering copy whose branches name procedures that exist nowhere, 1 reads a Sage kernel's hidden `_spl_solve_result`, and the WHILE-with-tool case is now lifted (266 of 274 workflows pass).
    - E3 compact form (`steps:`, `grafr/compact.py`, expanded inside `load_graph`; `graf expand FILE` prints the long form): kinds generate, solve, assert, evaluate, guard, fork, join, output, use and `node` as the escape hatch; control inferred from order and `on:`; literals become input defaults. A `loop` step carries its own `steps:` body (`$loop.<name>` reads the loop's inputs and state; loops nest; done 2026-10-30).
    - E6 bindings (`--bind FILE`, `grafr/bindings.py`): `llm`, `llms` for `llm: $name`, default `params`, `resources` replacement, `limits`; flags beat the file; a node's own `llm: adapter[:model]` beats the run's `--llm`, which beats the adapter default.
    - `graf compile --lang spl` (was `graf export-spl`; `graphlang/grafe/`, graflang's own emitter, no SPL.py import): a lifted graph comes back with its CREATE FUNCTION / CREATE TOOL_API and lifts to the same graph again; a hand-written GENERATE becomes a function named after its node; lifecycle phases are dropped with a warning. Limitation: SPL variables are named after out ports, so two nodes writing one port name can alias.
  - **R1 (done).**
    - E1 lifecycle (`grafr/lifecycle.py`, `config.phases`): `pre` require/defaults, `exec` retry/wait/fallback (route or value) and `timeout_s`, `post` `out_schema` with JSON parsing (GENERATE asks for JSON matching the schema and re-prompts with the validation error) and `post.route`.
    - E2 typed ports (`grafr/ports.py`): types `ANY TEXT INTEGER FLOAT BOOL LIST JSON control`, `{type: JSON, schema: ...}`; `graf validate` rejects a `binds` edge whose types are not assignable; a run checks each typed value as it is written; trust labels (`TEXT!sql_safe`); `workflow.inputs` types type the INPUT node's ports.
    - `RECOVER` as a real node (`action: halt|abort|skip|retry`, `max_retries`, `then`).
    - Acceptance corpus (done 2026-10-30): every one of the 83 PocketFlow workflows lifts and validates (`tests/test_pocketflow_corpus.py`), and three lifted samples (`cookbook/pocketflow`: `majority_vote`, `debate`, `text_transformer`) run, the first two replayed from `claude_cli` cassettes. Running them closed four gaps: lifted assignments (`CONTEXT set`) now execute, a loop variable starts as its pre-loop value and keeps its last written one, `from` may list several ports, and a tool called in a `WHILE` condition runs before the loop and at the end of each iteration; `latest(@in_x, @x)` joined the expression functions. Open: `RETURN` inside a `WHILE` body is skipped by the lifter, so `017_judge` does not stop on PASS (it is why recorded runs carry a call budget). One real-LLM test (`--mode llm`, `claude_cli`, `claude-sonnet-5-5`) per feature area passes; the `llm` marker is registered in `pyproject.toml`.
  - **R0 and R0.5 (done).** Suite green on a clean checkout apart from the known `grafc/cedar` failures; the `spl` experiment arm no longer depends on `spl3` being on `PATH`. S1 `graflang-semantics.md`; S2 race and JOIN-deadlock checks in `graf validate` (`topology.py`); S3 `MUTATE` re-checks the guarantees on a trial copy and refuses to touch `GUARD`/`MUTATE` nodes or the `risky` flag (`runtime.py`); S4 `tests/test_semantics.py` pins the rules.

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
| 4 | Real-LLM test gating | A small default set; the rest behind `--mode llm` (plain `pytest` is offline); recorded replays (E9) for CI | Register the `llm` marker in `pyproject.toml`; tests call `claude_cli:claude-sonnet-5-5` |
| 5 | IDE target | Left to me: **Streamlit**, behind `graf vis` (read-only by default, `--edit` for the IDE; `graf ui` is a hidden alias) | See below |
| 6 | zinet prerequisite | zinet is not released while graflang is developed, so both codebases may change together | M1–M4 no longer gate R1; change zinet in step with graflang, and take the `zinet` dependency as an editable install |

**IDE (decision 5).** No new command. `graf vis` is the viewer and stays the one entry point; `graf ui` is a hidden alias for it, the same way `graf viz` already is. Plan: `graf vis <graph.yaml>` is read-only by default (today's view, plus click-to-inspect); `graf vis --edit <graph.yaml>` enables the IDE mode (update, add, connect and delete nodes, ports and edges), validated through `graf validate` before every write, with round-trip YAML so comments survive, as in graph-ide's writer. The edit mode reuses the `MUTATE` delta validation (schema, structure, `CODE_KEYS`), so a hand edit and a model edit pass the same checks. Streamlit over Vite because it needs no Node toolchain, matches the README roadmap, and the repo is Python-only; the current engines (cytoscape and others) remain for read-only output, and `--edit` opens the Streamlit app. If a richer canvas is needed later, embed the zinet cytoscape view. *(Built; see §14.)*

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

## 14. The Editor App (`graf vis --edit`)

Decision 5 (§12) chose Streamlit behind `graf vis`. It is built, and it is the way most people will meet GraphLang: nobody has to write YAML.

**Pages** (`graphlang/grafv/pages/`, ordered by the file number; `app.py` is only the navigation):

| Page | What it does |
|---|---|
| Welcome | What GraphLang is, what each page offers, what the work area holds, the command line. `graf vis --edit FILE` opens straight on Edit |
| Create | Describe an app in a chat; the model writes the graph, its prompts and a readme (`grafc/create.py`, same engine as `graf create`). The reply is checked like `graf validate` plus a dry run, problems go back to the model for another round, and nothing is written until **Save**. Later messages revise the draft; *Undo* steps back. Similar recipes from the work area go into the prompt as examples; attachments (documents as material to read, screenshots to a provider that takes images) are accepted |
| Edit | The picture, and tabs: **Source** (the whole file as text in a code editor), Node, Edges, Problems, Run. Buttons or chat change the graph; every change is validated, keeps comments (ruamel round trip), can be undone, and is written atomically only on Save. Sidebar: Browse files (filterable by folder), Clone, Back |
| Browse | Search the recipes by what they do, in your own words: meaning (dd-embed) plus BM25 words, one card per recipe, *Open* / *Use in Create* |
| Import/Export | Zip a recipe out or in; import never overwrites, refuses unsafe paths and runs nothing |
| Settings | Provider, model, embedding model, picture height, API keys (`~/.graflang/settings.json`, mode 0600); *Test* sends one real message |

**Pieces.** `GraphEditor` (`editor.py`) is the one place that changes a file, by buttons and by chat alike. `chat_ops.py` turns the model's JSON list of operations into `GraphEditor` calls, all or none. `ui.py` holds the shared helpers, `attachments.py` reads uploads, `graphlang/workspace.py` is the work area (`~/.graflang/apps` writable; `cookbook` and `solvers` read-only; or `--src-dir`), `recipe_index.py` and `embedding.py` are the search. `graf describe` writes the specification of a graph or a recipe folder (`FILE.spec.md`, or an LLM-written one with `--llm`); its text is what `graf create --spec @FILE` takes, which closes the round trip graph to specification to graph.

**Security decisions** (reviewed in `graflang-UI.md`): the app has no login and holds API keys, so it listens on `127.0.0.1` only (`--host` changes it, with a warning); generated code and external programs need the *Allow app to call external programs* switch; the Run tab lists the nodes that run programs and wants an acknowledgement; the model may not add code (the same `CODE_KEYS` rule as `MUTATE`); chat writes to prompt files are limited to `prompts/*.md|txt`; attached documents are marked as material, not instructions.

**Tests.** Streamlit's `AppTest` drives the pages (`test_app_pages.py`, `test_editor_app.py`), the engine has its own tests (`test_editor*.py`, `test_chat_ops.py`, `test_workspace.py`, `test_describe.py`, `test_create.py`), and plain `pytest` stays offline.

**Not in it, by decision:** drag-to-connect on the canvas (edges come from lists), editing compact `steps:` / `elaborate:` files other than as text, and a login.

## 15. Migration of the Solver Recipes (SPL.py `cookbook-solver`)

**What.** The 47 recipes (55 graphs) of SPL.py's `cookbook-solver` were lifted with `spl3 util spl2graph` and live in `cookbook_solvers/` (the app's `solvers` root). The rule that graflang does not depend on SPL.py held: the lift runs in SPL.py, graflang runs the graphs, and only `procedure_ref` needs SPL.py importable (`symbolic_math`, `neurosymbolic`, `code_pytest`).

**Test.** Every graph was run once with `claude_cli` / `claude-sonnet-5-5`, solver on, under `--bind` limits (20 model calls, 500 steps, 800 s). All complete, including the two SageMath graphs (`sage_math`, `neurosymbolic` default rung, with the Sage kernel) and `lean_proof` (a Lean kernel check). `global_minlp` and `minizinc_cp` run their Python fallbacks (the binaries are not installed); Lean claims over `ℝ` need Mathlib, which is not installed (instructions are in `cookbook_solvers/README.md`). The output of each run is in the recipe's `output/` folder.

**What the run found** (details and the per-recipe table are in `cookbook_solvers/README.md`):

| In | Problem | Fix |
|---|---|---|
| graflang | f-strings, `procedure_ref` into a multi-workflow `.spl`, no choice of Jupyter kernel, a prompt placeholder nothing fills went unnoticed | f-strings; the right workflow; `kernel_name` / `--kernel-name`; the `graf validate` check |
| `spl2graph` | ports named after function parameters (never fed inside a loop), tool types defaulting to TEXT, bare Sage statements, `run_python` as a subprocess, SPL runtime counters, text compared with numbers, files not copied | all fixed in SPL.py with tests; lifting again gives graphs equal to the hand-patched ones (the 12 graphs that needed fixes were run again and match) |
| the graphs | a handful of recipe-specific fixes (a data path, a helper module path, the default dataset of `demand_forecast`) | kept by hand in `cookbook_solvers/`, which stays the reviewed copy |

**Lesson.** A smoke test with the placeholder model proved little: recipes that "ran end to end" still had empty prompts or dead steps. A lifted recipe is checked by `graf validate` first, then by a run with a real model.

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

---

## Appendix B: To-Do List (updated 2026-11-01)

The basic functionality is in place (see the status note at the top). This list replaces the one of 2026-10-30; what was on it and is done is marked done, so nothing is lost. Anything not listed here is not planned.

### Done since the list of 2026-10-30

- Owner's picks #2 to #4: loops as compact steps; the remaining SPL lifting cases; the R1 acceptance corpus (all 83 PocketFlow workflows lift and validate, three samples run). #5 real Docker test: done, with a guard for mounts outside the home directory.
- The editor app (§14) and `graf create` / `graf describe`.
- Migration and real-model run of the 47 solver recipes (§15), with the fixes in graflang and in `spl2graph`.
- Language and runtime: f-strings, `kernel_name` / `--kernel-name`, the named-workflow `procedure_ref`, the unfed-prompt check in `graf validate`.

### Owner decisions (answered 2026-11-01; the answers and what followed are under each item)

1. **Elaboration keyword.** `elaborate` was provisional; 13.3 left `ELABORATE`, `EXPAND` or `INSTANTIATE` to the owner.

[WEN] use "expand"

*Done 2026-11-01:* the block is `expand:` (`grafr/expand.py`, `cookbook/expand_demo`, `tests/test_expand.py`); a file that says `elaborate:` is still read. Sections 13.3 and 10 above keep the old name as history.

2. **ConceptBook section order (13.4 Q1).** If the sequential order is deliberate it must become an edge before elaboration runs sections in parallel.

[WEN] deliberate

*Recorded:* the section order is a real dependency, so each section must wait for the one before it (an edge, or `pass` in `expand:`); it is not a candidate for parallel sections. Nothing to build until the ConceptBook drivers are rewritten (item 9).

3. **13.4 Q2, Q3, Q5.** Declared independence, merge policies, and where the rule language lives.

[WEN] go with your suggestions

*Adopted:* (Q2) declared independence waits until a real app needs it; the race check of S2 already catches an undeclared one. (Q3) the merge policy of a port with several writers stays "error" (a race is reported); `collect` is the one policy to add, when needed, and `JOIN` already bundles. (Q5) the rule language starts inside graflang's `graf validate` and moves to zinet when a second tool needs it.

4. **`review_chapter` verdict.** Nothing reads it today; wiring it to a revision pass changes the recipe's behaviour.

[WEN] yes

*Already so in graflang:* `cookbook/your_book` reads the `review_chapter` verdict (`needs_revision` sends `REVISION_NEEDED` chapters to `revise_chapter`; the loop collects whichever wrote last). The ConceptBook driver scripts are your project and were not touched; the same wiring applies when they are rewritten (item 9).

5. **`OBSERVE`, `QUERY`, `EMIT`.** Built 2026-11-03 (`grafr/outside.py`; owner: "I like them"): `QUERY` reads a file inside the graph's folder, `EMIT` writes a file, prints, posts to a webhook or e-mails fixed recipients, `OBSERVE` records without ever failing a run; `QUERY` and `EMIT` stay behind a `GUARD` and their path/target keys are `CODE_KEYS`. See `graflang-idea.md`.

[WEN] build when needed 

*Noted:* they stay pass-through, and are listed as "not built" in the user guide.

6. **Recipe-level questions in `cookbook_solvers/`:** `portfolio_comparison` finds Markowitz and CVaR infeasible at its default target return (as the SPL demo does); `z3_compliance` shows an empty policy text in its explanation prompt (as the SPL original does). Fix the defaults, or keep them faithful to SPL.

[WEN] fix them as you see fit

*Done 2026-11-01:* `portfolio_comparison` and `portfolio_optimization` default to target return 0.08 and weight cap 0.25 (five stocks under a 20% cap are forced to equal weights, so 12% was out of reach); a run gives OPTIMAL for all six algorithms. `z3_compliance` passes the checked policy (JSON) to the explanation prompt instead of the empty `policy_text` of the default demo; the run shows the explanation reading the rules. Both are noted in the recipe readmes.

### Open, small, no decision needed

7. **`RETURN` inside a `WHILE` body** was skipped by `spl2graph`, so `017_judge` did not stop on PASS (recorded runs carry a call budget).

[WEN] ok

*Done 2026-11-01 (SPL.py `spl2graph`):* a RETURN anywhere inside a WHILE (in a branch, a DO block, or a nested WHILE) sets a flag and a value; the loop condition adds `AND @flag = FALSE` (a comparison, because SPL's WHILE condition drops anything else after AND); after the loop an EVALUATE returns the value or goes on, and in a nested loop it returns from the outer loop in turn. `graph2spl` turns the graph back into valid SPL with the same meaning. `017_judge` now stops on PASS (4 model calls in the run, not 6). The round trip of a graph with such a RETURN is equivalent, not identical, so `self_refine` has its own test. The new `graf validate` check also shows that 10 older quickstart recipes using SPL's `WITH ... SELECT ... INTO` form are skipped by the lift and leave prompts unfilled: they were passing `graf validate` before, wrongly.

8. **Environment, not code:** Mathlib for the Lean rung (`setup_lean.sh --with-mathlib`, ~5 GB; instructions in `cookbook_solvers/README.md`), and the Couenne/Bonmin and MiniZinc binaries that `global_minlp` and `minizinc_cp` fall back from.

[WEN] later

9. **Rewrite the ConceptBook driver scripts with elaboration** (13.3 item 2). Not scheduled by the owner; it is the real test of `elaborate:`.

[WEN] later

10. **Paper.** A first draft exists (below); the README roadmap line stays open until submission.

[WEN] go ahead with draft

*Draft written 2026-11-01:* `docs/paper/graflang-paper.draft.md`, from what exists (design, tests, the solver-recipe migration and the code_pipeline experiment). It claims nothing that was not measured; see the list of what is missing at its end.

### Later items (13.3, not started)

11. Shared rule language in zinet (item 3).
12. Provenance on deltas: origin, confidence and lineage, so Cedar can require human approval for an LLM-origin delta (item 4).
13. Human nodes and durable runs, on top of checkpointing (item 5).
14. Step debugger and a graph-level test harness, on top of replay (item 6).
15. Dialect mapping work (G17) for graph-code, work-graph and ConceptBook, after graflang is stable.

### Deliberately out for now

16. The `mcp` and WASM executors, and a thin-adapter kit for new languages.
17. Editor: drag-to-connect on the canvas; editing compact `steps:` and `elaborate:` files (they are edited as text); a login (the app is local-only by design).
18. A price table for `max_cost_usd` (adapters that report no cost make the budget fail loudly instead).
19. The hand-written Cedar compiler (`grafc/cedar`): its 7 known test failures stay. Filesystem and network limits for kernel nodes, and a WASM sandbox.

### Owner's take

[WEN] (2026-10-30) implement #2 - #4 from "Ready to build" sub-section; no action on all other items. *Done.*
