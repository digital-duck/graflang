
## Directory layout

```markdown

graflang/
├── LICENSE                 # Apache 2.0
├── README.md               # The vision, CLI usage (grafr / grafc), and link to the paper
├── pyproject.toml          # Python project config (for the `grafr` dynamic interpreter)
├── graphlang/              # GraphLang source
|   ├── schema/
│   ├── graflang-ir.json    # The tightened JSON Schema we defined
|   └── grafr/                  # The dynamic Python interpreter
│       ├── __init__.py
│       ├── runtime.py          # The NetworkX-based topological executor
│       ├── resolver.py         # The 3-tier resource resolver
│       └── cedar_guard.py      # Integration with the `cedar-policy` Python bindings
|   └── grafc/                  # The static compiler (stubbed for now, Rust target later)
│       └── compiler.py         # Translates Graph IR + Cedar to Rust AST
├── cookbook/
│   └── code_pipeline/
│       ├── code_pipeline.graph.yaml  # The masterpiece file above
│       ├── 00_analyze_spec.spl       # (copied from SPL.py)
│       ├── 01_generate_code.spl      # (copied from SPL.py)
│       ├── 02_review_code.spl        # (copied from SPL.py)
│       ├── 03_improve_code.spl       # (copied from SPL.py)
│       ├── 04_test_code.spl          # (copied from SPL.py)
│       ├── 05_document_code.spl      # (copied from SPL.py)
│       ├── 06_extract_spec.spl       # (copied from SPL.py)
│       ├── 07_spec_judge.spl         # (copied from SPL.py)
│       └── policies/
│           └── mutation_safety.cedar # The Cedar policy file
└── tests/
    └── test_topology.py    # Validates the YAML against the JSON schema

```
---

## Gap tracker (reconcile at the end)

Running list of discrepancies between README.md (Qwen draft), this design doc, and the code as files are populated. Add rows as they are found; mark resolved when fixed.

### Naming decisions (intentional, not gaps)

- Language is **GraphLang**; repo is **graflang** because searching "graphlang" on GitHub mostly returns LangGraph hits.
- `examples/` renamed to `cookbook/` on purpose, matching `SPL.py/cookbook`.
- Import name is `graphlang`; the pip package is named `graflang` (unique on PyPI/GitHub).
- `graphlang/` is the Python package layer; `grafr` = runner, `grafc` = transpiler/compiler, chosen to be unique.

### Decisions on process (Wen)

- Interaction nets are the **foundation, not a strict spec**: the theory is ~30 years old, so GraphLang may depart from it where useful. Gaps #6-#8 should be read as "decide and document the departure", not "conform".
- Final review of the populated codebase uses **rigorous best-practice standards** (correctness, tests, structure, security, packaging), plus a check of code against the documented design.
- Qwen's code is pasted as-is, then corrected in place by Claude where wrong; Wen keeps the originals in chat history.
- Nothing is committed yet; Wen will say when.

### Open items

Note: rows citing "README" refer to the archived Qwen draft `archive/README-qwen-v0.1.md`; apply the fixes to the new README when it is written.

| # | Area | Gap / question | Status |
|---|---|---|---|
| 1 | Paths | README quick start, YAML excerpt and policy paths now point at `cookbook/code_pipeline/` and the shared `graphlang/policies/`; the nonexistent `grafc --policy` flag was removed (policies come from `resources.policies`) | resolved |
| 2 | README | README excerpt now declares `analyze_spec` and notes the full file has 8 procedures (00-07) | resolved |
| 3 | README | README excerpt now explains `@in_max_cycles` (LOOP input), `@test_passed`/`@cycle` (loop state) and `@in_analysis` (own `in_*` port, with the `binds` edge shown) | resolved |
| 4 | README | README roadmap now says Cedar integration is in `grafr` (`GUARD`/`MUTATE` via `cedarpy`); `cedar_guard.py` exists. Rust-side Cedar remains #18 | resolved |
| 5 | README | `MUTATE` is a headline feature but has no schema entry or example; `code_pipeline` does not use it | open |
| 6 | Semantics | README now says confluent for the deterministic core only; LLM-sampling nodes and `LOOP` are not | resolved |
| 7 | Semantics | Node ports (`trigger`/`complete`/`pass`/`fail`) read as dataflow, not interaction-net principal/auxiliary ports with rewrite rules; define how `grafr` realises interaction-net semantics | open |
| 8 | Semantics | Cedar role: `GUARD` checkpoint nodes (README) vs. Cedar gating whether any rewrite fires (see readme-claude.md); pick the primary model | open |
| 9 | Facts | Run and adapter counts removed from the README (SPL.py's README says 15 adapters, the paper draft 14); re-add once the SPL paper numbers are settled | resolved |
| 10 | README | README now says the paper is in preparation, with no draft in this repo | resolved |
| 11 | Tooling | README now marks `grafc`/Rust as planned and a stub (intro table, safety section, section 4, quick start) | resolved |
| 12 | Schema | Define explicit `FORK` (one in, n out, forwards the same value; duplicator-like) and `JOIN` (n in, one out; define the rule, prefer collecting over first-arrival). No implicit fan-out or desugaring (Wen). The archived README's names `FORK`/`JOIN` are kept (Wen prefers shorter names) | open |
| 13 | Paths | Cedar policies live in `graphlang/policies/` (Wen's placement: `graph_safety.cedar`, `mutation_safety.cedar`), not per example. README/yaml `policy_ref` paths and the `resources.policies` entries must match | resolved (placement); paths in yaml to check |
| 14 | Layout | Qwen's code used root-level `grafr/ grafc/ schema/ examples/`; mapped to `graphlang/{grafr,grafc,schema}/` + `cookbook/` (see `qwen-file-map.md`). Correction: I had said the schema path in `runtime.py` breaks after the move; it does not (`graphlang/grafr/runtime.py` finds `graphlang/schema/`). The real fault was the silent skip when the file is missing, now an error | resolved |
| 15 | pyproject | Rewritten: name `graflang`, package `graphlang`, scripts `grafr` + `grafc`, deps (`cedarpy`, `jsonschema`, `networkx`, `ruamel.yaml`, `rich`), extras `spl` (= `spl-llm`, for real adapters and procedures), `grafc` (jinja2), `dev`; schema/policy/template package data | resolved |
| 16 | Schema | `GUARD` added to the node-type enum; `graph_delta.schema.json` rewritten as valid JSON and now enforced by `MUTATE`. Edge types are still only `triggers`/`binds` | resolved |
| 17 | Runtime | Fixed in `runtime.py` (rewritten): `MultiDiGraph`; control tokens, nodes may re-fire (retry wires loop, `max_steps` stops runaway loops); `JOIN` is a barrier, `FORK` emits on all control ports; data keyed by port name; `_route` honoured; INPUT/OUTPUT wired to workflow inputs/outputs; resolver honours the `resources` block; 12 tests. `grafr run` now works end to end on all three cookbook graphs | resolved |
| 18 | Cedar | `grafr` now uses the official Cedar engine (`cedarpy`), fail-closed (any evaluation error denies). Still open: `grafc/cedar/*`, a ~1,500-line hand-written Cedar compiler. Its dataclass error is fixed so it imports, but only 4 of its 14 tests pass (parser defects, e.g. the keyword `action` is read as an identifier). Decide: repair it, or generate Rust that calls the official `cedar-policy` crate | open (decision for Wen) |
| 19 | Paper | Qwen's draft abstract claims 40% fewer hallucination-induced loops and 2x faster audits with no experiment; do not reuse. Citations (Cedar, SymPy, Lean key) need verifying | open |
| 20 | Missing | `tests/test_topology.py` written (static wiring/resource/condition checks over the shipped graphs; `grafr validate` runs the same checker); the eight `.spl` procedures copied from `SPL.py/cookbook/050_code_pipeline` into `cookbook/code_pipeline/` | resolved |
| 21 | Placement | `spl2graph` placed in SPL.py as `spl3/spl2graph.py` (sibling of `spl2mmd.py`), unreviewed Qwen draft: imports now resolve but it crashes on real recipes (`generate_clause.options` does not exist; no WHILE/EVALUATE/LOGGING/assignment support) and needs a rewrite against the real AST once the vocabulary is settled. `graph2spl` placed as `SPL.py/scripts/graph2spl.py`, also an unreviewed draft (handles only Workflow/Generate/Call/Solve/Assert/Commit; emits SPL-like text, not valid SPL) | open |
| 22 | Tests | Cedar-compiler test imports fixed to `graphlang.grafc...`; the `__init__.py` files exist. The tests themselves: 4 pass, 10 fail on parser/compiler defects (see #18) | partly resolved |
| 23 | Runtime | `EVALUATE`/`ASSERT` now evaluate their conditions with a safe evaluator (`grafr/expr.py`, no `eval`; whitelist; tested against injection attempts) and `GENERATE` calls a real LLM through SPL.py's adapters (`--adapter claude_cli --model ...`; default `mock`). Still open: `SOLVE` without an `expression` is a stub (no SymPy/Sage/Lean kernel); LLM-judged (semantic) EVALUATE conditions as in SPL | partly resolved |
| 24 | Runtime | `LOOP` runs its subgraph; `MUTATE` validates (schema, structure, Cedar, budget) and applies deltas to the live graph; `procedure_ref` nodes (GENERATE and SOLVE) run SPL.py workflows through SPL.py's executor. Semantics below | resolved |
| 25 | Runtime | The flagship's `GUARD` and retry now run inside the `LOOP` subgraph; the YAML's policy path was corrected to `graphlang/policies/`. Writing the loop for real exposed missing binds in Qwen's YAML (loop inputs, closure gate, `extract.in_code`, output when the closure check is skipped); fixed. Cedar enforcement itself is still a stub (#18) | resolved (except #18) |
| 26 | Semantics | Execution is token-passing dataflow, not interaction-net rewriting (principal ports, rewrite rules); a documented departure candidate for #7 | open |
| 27 | Adapters | Real LLM calls need SPL.py importable: `pip install -e /path/to/SPL.py`, or set `SPL_PY_PATH`. It is installed in the `spl123` conda env, not in `graf`. `pyproject.toml` declares it as the optional extra `spl` (`spl-llm>=3.4`), so `pip install -e ".[spl]"` works; the `graf` env still lacks it unless installed | resolved |
| 28 | Semantics | LOOP semantics are my design, not Qwen's (its YAML did not define them): condition checked before each iteration; outputs `from`/`collect`/`fired`; unbound body inputs read the loop's inputs, then loop-state variables; body = DAG per iteration, repetition by the loop only. Needs Wen's review (section below) | open |

---

## grafr semantics added so far (Claude's design, for review)

### LOOP
A `LOOP` node runs its `subgraph` once per iteration.

```yaml
config:
  condition: "NOT @test_passed AND NOT @denied AND @cycle < @in_max_cycles"   # checked BEFORE each iteration
  max_iterations: "@in_max_cycles"        # number or expression; default 100
  index_var: chapter_index                # name of the 0-based counter; default `cycle`
  outputs:                                # become the LOOP's out_* ports
    final_code:  {from: "loop_imp.out_improved_code"}   # value from the latest iteration
    chapters:    {collect: "write_chapter.out_chapter"} # list, one per iteration
    test_passed: {fired: "loop_eval.pass"}              # did a token leave that port in the latest iteration?
  subgraph: {nodes: [...], edges: [...]}
```

- One iteration = run the body from its start nodes (nodes nothing triggers) until no tokens are left. The body is a DAG per iteration; **repetition is the loop's job**, not a back-wire inside the body (Qwen's flagship had both, which double-counted).
- The condition and `max_iterations` see: the LOOP's `in_*` values (`@in_max_cycles`), the previous outputs by name (`@test_passed`), and the counter (`@cycle` or `index_var`).
- Inside the body, an `in_X` port with no `binds` edge reads the LOOP's `in_X`, else the loop-state variable `X` (so `in_chapter_index` reads `chapter_index`). Data between body nodes uses ordinary `binds` edges.
- The LOOP then routes to `exit`. Body nodes share the run's step budget (`--max-steps`), LLM, context and resources; a loop that never ends stops with `RunLimitExceeded`.
- Compatible with the fermion/boson picture: the loop body is re-fired, not copied; the wiring (topology) never changes between iterations.

### Conditions
`EVALUATE`, `ASSERT` and `LOOP` conditions use `grafr/expr.py`: `@variables`, literals, `AND/OR/NOT`, comparisons, arithmetic, and a fixed function list (`contains`, `startswith`, `endswith`, `len`, `lower`, `upper`, `strip`, `abs`, `min`, `max`, `int`, `float`, `str`, `bool`, `is_empty`). No `eval`; no attribute access, subscripts, lambdas or `**`; length, node count and repetition are capped. `EVALUATE`/`ASSERT` see their own `in_*` ports. An unknown variable or a bad expression stops the run with the node id in the message.

### Data
Values live on ports. If several `binds` edges feed one port, the **most recently written** source wins. Command-line inputs are coerced to the declared type (`INTEGER`, `FLOAT`, `BOOL`).

### LLM
`grafr run --adapter NAME --model M`: `mock` (default, no LLM) or any SPL.py adapter (`claude_cli` runs the Claude Code CLI on the subscription, with `ANTHROPIC_API_KEY` stripped by SPL.py's adapter). A `model:` in a node is only a hint: used when no `--model` is given and it fits the adapter (`ollama/gemma3` is ignored under `claude_cli`). Verified once live with `claude_cli` and `claude-haiku-5-5` (one short call).
| 29 | Policy | Edited `graphlang/policies/mutation_safety.cedar`: two `x in [..]` on strings (invalid for strings in Cedar; they errored) became `[..].contains(x)`, and a policy 7 `allow_retry` permit was appended for the loop guard. The forbids are otherwise unchanged. Please review the file | open (review) |
| 30 | Policy | `contains_pii` in the Cedar context is always false: PII detection is not implemented, so the data-sovereignty policy cannot trigger | open |
| 31 | Runtime | `SOLVE` with neither `expression` nor `procedure_ref` (kernel-backed SymPy/Sage/Lean) is still a stub that yields True; SPL.py has the kernel (`spl3/kernel.py`) to wire in | open |
| 32 | Runtime | A MUTATE inside a LOOP body changes only that iteration's copy of the body; it does not persist across iterations. Wen: fine for now | accepted (revisit if persistent self-revision inside loops is needed) |
| 33 | Qwen YAML | The topology checker found a dead edge in the flagship (`spec_gate.out_analysis`, a port that does not exist); fixed. The runtime now rejects edges to missing ports instead of ignoring them | resolved |

### GUARD and Cedar
`GUARD` asks Cedar (the real engine, `cedarpy`) whether an action is allowed: `config.policy_ref` (required), `principal`/`action`/`resource` (defaults `Service::"llm-agent"`, `Action::"mutate_graph"`, `Graph::"execution_topology"`), and `context_mapping` `{attribute: "<expression>"}` evaluated over the node's `in_*` values. It routes to `allow` or `deny`.
**Fail closed:** Cedar skips a policy that errors, so a `forbid` that reads a missing context attribute silently stops forbidding (and a catch-all `permit` then allows). The guard therefore treats any evaluation error as a deny, and callers must supply every attribute the policies read. `MUTATE` always does; for `GUARD`, the mapping must.

### MUTATE
`MUTATE` takes a graph delta on `in_delta` (a dict, or JSON text, with or without a code fence) and applies it only if, in order: it parses; it matches `graph_delta.schema.json`; it keeps the graph well formed (known nodes and ports, port kinds right, no duplicates, `INPUT`/`OUTPUT` not removable, `id`/`type`/`ports` not editable); Cedar allows it under `config.policy_ref`; and the mutation count is under `config.max_mutations` (default 3, enforced by policy 3). Deny-by-default: no `policy_ref`, no mutation. It routes to `applied` or `rejected` (both ports required) and writes the reason on `out_reason`. Later tokens follow the mutated wiring. Adding a `MUTATE` node by delta is not allowed.
The Cedar context carries `proposed_delta` (`action`, `node_id`, `node_type`, `source_port`/`target_port` as `TYPE.port`, and `source`/`target` records), `mutation_count`, `max_allowed_mutations`, `human_approval`, `contains_pii`.

### Procedures
A `procedure_ref` on a `GENERATE` or `SOLVE` node runs the SPL.py workflow in that file with SPL.py's own executor (`grafr/procedures.py`, mirroring `spl3 run`): sibling `.spl` files load into a registry, so `IMPORT`/`CALL` work. Parameters come from the node's `in_*` ports (`in_spec` -> `spec`) or from `config.params` `{spl_parameter: in_port}`; only declared inputs are passed; `*model*` parameters get `--model`; `log_dir` goes to `<graph folder>/.grafr/logs` (git-ignored). The result goes on the first `out_*` port. Under `--adapter mock` nothing is run.

### Static checks
`grafr validate FILE` and `tests/test_topology.py` run `grafr/topology.py`: edges to real nodes and ports, triggers vs binds port kinds, resources exist, conditions parse and use only available variables, GUARD/MUTATE/LOOP configs complete. Errors fail; warnings (an input nothing feeds, a node nothing triggers) do not.
