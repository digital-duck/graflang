# User guide

Reference for running and writing GraphLang workflows. New here? Start with [SETUP.md](SETUP.md) and [TUTORIAL.md](TUTORIAL.md).

A GraphLang program is a YAML file, `*.graph.yaml`. The topology is the program: nodes do work, edges say what fires next and where data flows. `grafr` runs it.

## Commands

```bash
grafr validate FILE      # static checks, nothing executes
grafr info     FILE      # name, node/edge counts, inputs, outputs, resources
grafr run      FILE [options]
grafc check    FILE      # can it be compiled? (compiler is a stub)
grafc compile  FILE [-o DIR] [--target rust] [--optimize]
```

`python -m graphlang.grafr.cli ...` is equivalent to `grafr ...`.

### `grafr run` options

| Option | Meaning |
|---|---|
| `--param key=value` | a workflow input; repeatable. Coerced to the declared type (`INTEGER`, `FLOAT`, `BOOL`). A value without `=` is a usage error |
| `--adapter NAME` | `mock` (default, no LLM) or an SPL.py adapter: `claude_cli`, `ollama`, `openrouter`, ... |
| `--model ID` | model for every `GENERATE` node; overrides `model:` hints in the graph |
| `--max-steps N` | stop after N node firings (default 1000) |

A run ends with the workflow output. If no `OUTPUT` node was reached (a gate routed to a dead end) it says so. Failures print `✗ Run failed: ...` and exit with code 1: bad expression, unknown variable (message names the node), rejected edge to a missing port, or the step limit (`stopped after N node firings`).

### `grafr validate`

Checks edges point to real nodes and ports, `triggers`/`binds` join the right kinds of port, resources exist, conditions parse and use only available variables, and `GUARD`/`MUTATE`/`LOOP` configs are complete. Errors fail the command; warnings (an input nothing feeds, a node nothing triggers) do not.

## File layout

```yaml
version: "1.0-graph"

workflow:
  name: "self_refine"
  inputs:  [{name: "topic", type: "TEXT"}]
  outputs: [{name: "essay", type: "TEXT"}]

resources:                       # external files, paths relative to this YAML
  prompts:    {draft: "./prompts/draft.md"}
  procedures: {generate_code: "./01_generate_code.spl"}
  policies:   {mutation_safety: "../../graphlang/policies/mutation_safety.cedar"}

nodes: [ ... ]
edges: [ ... ]
```

Schema: `graphlang/schema/graflang-ir.json`. Node ids match `[a-zA-Z0-9_]+`.

## Nodes and ports

Each node has `id`, `type`, `ports`, and optional `config`. Port names carry their kind:

- control: `trigger` (input); outputs such as `complete`, `pass`, `fail`, `allow`, `deny`, `applied`, `rejected`, `exit`
- data: `in_<name>` and `out_<name>`

| Node | Role |
|---|---|
| `INPUT` | entry point: an `entry` control port and an `out_<input>` per workflow input |
| `OUTPUT` | exit point: its `in_*` ports become the workflow outputs |
| `GENERATE` | LLM call: `prompt_ref`, `prompt_inline`, or `procedure_ref`. The result goes on the first `out_*` port |
| `EVALUATE` / `ASSERT` | evaluate `config.condition`; route to `pass` or `fail` |
| `SOLVE` | deterministic: `config.expression` or a `procedure_ref` |
| `FORK` | emits on all its control output ports |
| `JOIN` | barrier: fires when every incoming trigger has arrived |
| `LOOP` | repeats a `subgraph` (see below) |
| `GUARD` | asks Cedar whether an action is allowed; routes to `allow` or `deny` |
| `MUTATE` | applies an LLM-proposed graph delta if every check passes; routes to `applied` or `rejected` |

The schema also lists `QUERY`, `RECOVER`, `CONTEXT`, `OBSERVE`, `EMIT`; check the runtime before relying on one.

## Edges and data

```yaml
- {source: "draft.complete",  target: "critique.trigger",  type: "triggers"}   # control
- {source: "draft.out_essay", target: "critique.in_essay", type: "binds"}      # data
```

- `triggers` passes a control token. A node fires when a token reaches `trigger` and may fire again if another arrives, so a retry is a wire back to an earlier node. Execution is token-passing dataflow, not interaction-net rewriting.
- `binds` copies an `out_*` value to an `in_*` port. If several `binds` edges feed one port, the most recently written source wins.
- Edges to nodes or ports that do not exist are rejected.
- In a prompt file, `{{in_topic}}` is replaced by the value on the node's `in_topic` port.

## Conditions

`EVALUATE`, `ASSERT` and `LOOP` conditions are expressions over `@variables`:

```
NOT @test_passed AND @cycle < @in_max_cycles
contains(@in_analysis, '[READY]')
```

Literals, `AND`/`OR`/`NOT`, comparisons, arithmetic, and these functions: `contains`, `startswith`, `endswith`, `len`, `lower`, `upper`, `strip`, `abs`, `min`, `max`, `int`, `float`, `str`, `bool`, `is_empty`. There is no `eval`, attribute access, subscripts, lambdas or `**`; expression length and repetition are capped. `EVALUATE`/`ASSERT` see their own `in_*` ports, so bind what they need. LLM-judged (semantic) conditions are not implemented.

## LOOP

```yaml
- id: "loop"
  type: "LOOP"
  ports: ["trigger", "exit", "in_max_cycles", "out_final_code", "out_test_passed"]
  config:
    condition: "NOT @test_passed AND @cycle < @in_max_cycles"   # checked BEFORE each iteration
    max_iterations: "@in_max_cycles"     # number or expression; default 100
    index_var: cycle                     # 0-based counter name; default `cycle`
    outputs:                             # become the LOOP's out_* ports
      final_code:  {from: "imp.out_code"}       # latest iteration's value
      chapters:    {collect: "write.out_text"}  # list, one entry per iteration
      test_passed: {fired: "eval.pass"}         # did a token leave that port last iteration?
    subgraph: {nodes: [...], edges: [...]}
```

- One iteration runs the body from its start nodes (nodes nothing triggers) until no tokens remain. The body is a DAG; repetition is the loop's job, so no back-edge inside it.
- The condition sees the loop's `in_*` values, the previous iteration's outputs by name, and the counter.
- A body `in_X` port with no `binds` edge reads the loop's `in_X`, else the loop-state variable `X`.
- When the loop ends it routes to `exit`. Body nodes share the run's step budget.

## Resources and composition

1. **Inline**: `prompt_inline`, short `condition`/`expression` strings.
2. **Reference**: `prompt_ref: "prompts.draft"` (a `.md` file), `procedure_ref: "procedures.generate_code"` (an SPL.py `.spl` file), `policy_ref: "policies.mutation_safety"` (a `.cedar` file), each declared under `resources`.
3. **Sub-graph**: a composite node; currently `LOOP`.

A `procedure_ref` on `GENERATE` or `SOLVE` runs the SPL.py workflow in that file with SPL's own executor; sibling `.spl` files load into a registry so `IMPORT`/`CALL` work. Parameters come from the node's `in_*` ports (`in_spec` becomes `spec`) or from `config.params` `{spl_parameter: in_port}`; `*model*` parameters receive `--model`. Not executed under `--adapter mock`.

## Safety: GUARD and MUTATE

Safety is Cedar policy. Policies live in `graphlang/policies/` (`graph_safety.cedar`, `mutation_safety.cedar`) and are referenced via `resources.policies`.

### GUARD

```yaml
- id: "guard"
  type: "GUARD"
  ports: ["trigger", "allow", "deny", "in_test_passed"]
  config:
    policy_ref: "policies.mutation_safety"       # required
    action: 'Action::"allow_retry"'              # defaults: Service::"llm-agent", Action::"mutate_graph", Graph::"execution_topology"
    context_mapping: {test_passed: "@in_test_passed"}
```

`context_mapping` builds the Cedar context from the node's `in_*` values. Cedar must say Allow *and* raise no evaluation error, otherwise the token goes to `deny` (fail closed). Supply every attribute your policies read.

### MUTATE

`in_delta` takes one JSON object (a dict, or text with or without a code fence):

```json
{"action": "add_edge", "payload": {"source": "mut.applied", "target": "rec.trigger", "type": "triggers"}}
```

Actions: `add_node`, `remove_node`, `add_edge`, `remove_edge`, `update_config` (schema: `graphlang/schema/graph_delta.schema.json`). A delta is applied only if it parses, matches the schema, keeps the graph well formed (known nodes and ports, no duplicates, `INPUT`/`OUTPUT` not removable, `id`/`type`/`ports` not editable), Cedar allows it under `config.policy_ref`, and the count is under `config.max_mutations` (default 3). No `policy_ref` means no mutation. The reason goes on `out_reason`. A `MUTATE` inside a `LOOP` body changes only that iteration's copy of the body. A `MUTATE` cannot add another `MUTATE` node.

## Bundled workflows

| Graph | What it does |
|---|---|
| `cookbook/self_refine/` | draft, critique, refine an essay |
| `cookbook/concept_book/` | builds a concept book chapter by chapter in a `LOOP` that collects chapters |
| `cookbook/code_pipeline/` | the flagship: analyse a spec, generate/review/test code in a `LOOP`, Cedar-guarded retries, optional closure check; SPL procedures `00`-`07` sit next to the graph |

## Known limits

- `SOLVE` with neither `expression` nor `procedure_ref` is a stub that returns True.
- `contains_pii` in the Cedar context is always false, so the data-sovereignty policy cannot trigger.
- `grafc compile` does not produce a working Rust project yet.

The full list is the gap table in [`../DEV/readme-design.md`](../DEV/readme-design.md).
