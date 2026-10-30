# User guide

Reference for running and writing GraphLang workflows. New here? Start with [SETUP.md](SETUP.md) and [TUTORIAL.md](TUTORIAL.md).

A GraphLang program is a YAML file, `*.graph.yaml`. The topology is the program: nodes do work, edges say what fires next and where data flows. `graf` runs it, checks it, compiles it and draws it.

## Commands

```bash
graf validate FILE      # static checks, nothing executes
graf info     FILE      # name, node/edge counts, inputs, outputs, resources
graf run      FILE [options]
graf check    FILE      # can it be compiled? (compiler is a stub)
graf compile  FILE [-o DIR] [--target rust] [--optimize]
graf vis      FILE [--engine cytoscape|graphviz|pyvis|graphify|mermaid] [-o OUT] [--no-open]
```

`python -m graphlang ...` is equivalent to `graf ...`.

### `graf vis`

Draws the workflow and opens it. Nodes are coloured by type (`GENERATE`, `EVALUATE`, `LOOP`, ...), control edges (`triggers`) are solid, data edges (`binds`) are dashed and labelled with the port, and a `LOOP` is drawn as a box around its body.

| Option | Meaning |
|---|---|
| `--engine cytoscape` (default) | one interactive HTML file that works offline: search a node, zoom, switch layout, click a node for its config and links |
| `--engine graphviz` | a static SVG through `dot`, good for docs; DOT text is written if `dot` is not installed |
| `--engine pyvis` | interactive HTML through pyvis, laid out left to right; loop-body nodes have a dashed border. Needs `pip install "graflang[vis]"` |
| `--engine graphify` | graphify's HTML export, coloured by community. It is undirected, so it shows structure only (no edge types). Needs `pip install "graflang[graphify]"` |
| `--engine ascii` | a plain-text outline by depth (tier 0 has no dependencies), for a terminal or a diff. Nothing is opened |
| `--engine mermaid` | a Mermaid flowchart as text (`.mmd`; `-o FILE.md` wraps it in a fenced block) to paste into GitHub, mkdocs or `mermaid.live`. Nothing is opened |
| `-o FILE` | output file (default `~/.graflang/vis/<graph>-<engine>.<html\|svg\|mmd>`) |
| `--no-open` | write the file without opening it |
| `--list-engines` | show the engines and whether each is ready |

On the interactive page the first view is the control flow: the data edges are hidden behind a "show data edges" checkbox (they always show for the node you hover or select, with everything else faded) and a `LOOP` starts as one box. Click a collapsed loop to open it, double-click an open one to close it, or use "Collapse groups" / "Expand groups". Click a node for its config and links.

If Graphviz (`dot`) is installed, the interactive page also uses it to lay the nodes out (it keeps a loop's body together and picks a left-to-right or top-to-bottom shape that fits the screen); without it the page falls back to Cytoscape's own layouts.

### Installing Graphviz (optional)

Graphviz is a system program (`dot`), not a pip package, so `pip install` cannot add it. Without it, `--engine graphviz` writes the DOT text instead of an image, and the interactive page uses Cytoscape's own layouts.

| System | Command |
|---|---|
| Ubuntu / Debian | `sudo apt install graphviz` |
| Fedora | `sudo dnf install graphviz` |
| macOS (Homebrew) | `brew install graphviz` |
| Windows | `winget install Graphviz.Graphviz`, or `choco install graphviz`; then open a new terminal so `dot` is on the PATH |
| conda | `conda install -c conda-forge graphviz` |

Check with `dot -V` (it prints the version), then `graf vis --list-engines`: the `graphviz` line should say `ok`.

### `graf run` options

| Option | Meaning |
|---|---|
| `--param key=value` | a workflow input; repeatable. Coerced to the declared type (`INTEGER`, `FLOAT`, `BOOL`). A value without `=` is a usage error |
| `--llm ADAPTER[:MODEL]` | `--adapter` and `--model` in one value, e.g. `claude_cli:claude-haiku-5-5`, `ollama:gemma3:12b`, `mock`. Only the first `:` splits, so model ids with `:` or `/` work. Wins over `--adapter`/`--model` |
| `--adapter NAME` | `claude_cli` (default), `mock` (no LLM, placeholder text), or another dd-llm adapter: `ollama`, `openrouter`, `openai`, `anthropic`, ... |
| `--model ID` | model for every `GENERATE` node; overrides `model:` hints in the graph. Default: `claude-sonnet-5-5` for `claude_cli`; none for other adapters (`ollama`, ...), where the graph's hints apply |
| `--max-steps N` | stop after N node firings (default 1000) |
| `--output-dir DIR` | where results go (default `<graph folder>/output`); see [Results](#results-the-output-folder) |
| `--save-nodes` | also save every node's output, LLM responses included |
| `--no-output` | write no result files |
| `--log-level LEVEL` | `debug`, `info` (default), `warning`, `error`; see [Logging](#logging) |
| `--log-format FORMAT` | `both` (default), `text`, `jsonl` |
| `--log-dir DIR` | where log files go (default `~/.graflang/logs`) |
| `--no-log` | write no log file |

A run ends with the workflow output. If no `OUTPUT` node was reached (a gate routed to a dead end) it says so. Failures print `✗ Run failed: ...` and exit with code 1: bad expression, unknown variable (message names the node), rejected edge to a missing port, or the step limit (`stopped after N node firings`).

### Results: the output folder

Each run writes its results to a new folder, `<graph folder>/output/<graph>-<adapter>[-<model>]-<timestamp>/`. For `graf run cookbook/self_refine/self_refine.graph.yaml --llm ollama:gemma3 ...` that is `cookbook/self_refine/output/self_refine-ollama-gemma3-20261024-111347/`:

```
run.json                          what produced it: graph, adapter, model, parameters, start time
result.json                       the workflow outputs (what the run prints as Output)
essay.md                          one file per text output; other values are written as .json
nodes/001-draft.out_essay.md      only with --save-nodes
```

- With `--save-nodes`, every node's output ports are saved under `nodes/`, numbered in firing order (`001-`, `002-`, ...). Nodes that fire again in a `LOOP` get a new number each time. This is where intermediate LLM responses go. Prompts are not saved.
- The model part is the one you asked for with `--llm` or `--model` (characters other than letters, digits, `.`, `_`, `-` become `-`, so `gemma3:12b` shows as `gemma3-12b`); log files use the same naming. Without one the name still carries the default (`claude-sonnet-5-5` under `claude_cli`). Only adapters with no default (`ollama`, ...) give a folder without a model part and `"model": null` in `run.json`; the nodes then use the model hints in the graph.
- `--output-dir DIR` replaces `<graph folder>/output`. Each run still gets its own subfolder, so runs never overwrite each other.
- `--no-output` writes nothing. A run that fails, or ends without reaching an `OUTPUT` node, writes no result files.
- `output/` is in `.gitignore`.

LLM text is kept out of the log on purpose: it is a result of the run, not a diagnostic. The log records the folder and file names instead.

### Logging

Every run writes a log of what happened: which nodes fired, how long each took, what the guards and mutations decided, and which files were written. By default a run produces two files in `~/.graflang/logs/`, named `<graph>-<adapter>-<timestamp>`:

- `.log`: one line per event, for reading
- `.jsonl`: one JSON object per line, for tools such as `jq`

```
08:21:20  INFO  graflang.grafr.runtime  run.start workflow=self_refine nodes=5 inputs=['topic'] adapter=claude_cli model=None
08:21:41  INFO  graflang.grafr.nodes.generate  llm.call node=draft adapter=claude_cli model=None prompt_chars=186 response_chars=4846 ms=21459
08:22:25  INFO  graflang.grafr.runtime  run.end workflow=self_refine steps=4 outputs=['essay'] reached_output=True mutations=0 ms=64944
```

The path of the log file is printed at the end of the run, also when it fails.

**Settings**

| What | Option | Environment variable | Default |
|---|---|---|---|
| level | `--log-level` | `DD_LOG_LEVEL` | `info` |
| format | `--log-format` | `DD_LOG_FORMAT` | `both` |
| folder | `--log-dir` | `DD_LOG_DIR` | `~/.graflang/logs` |
| off | `--no-log` | | |

An option beats the environment variable, which beats the default. `--log-dir .` puts the files in the current folder.

**Events** (the `event` field in the `.jsonl`)

| Event | Level | Fields |
|---|---|---|
| `run.start`, `run.end` | info | workflow, adapter, model; steps, outputs, mutations, ms |
| `run.fail` | error | error, steps, ms |
| `node.fire` | debug | node, type, n (times fired), depth (loop nesting), inputs |
| `node.done` | info | node, type, route, outputs, ms |
| `node.error` | error | node, error |
| `loop.iteration`, `loop.end` | debug, info | node, cycle; iterations |
| `llm.call` | info | node, adapter, model, prompt_chars, response_chars, ms |
| `llm.text` | debug | a 200-character preview of the prompt and the response |
| `guard.decision` | info, warning when denied | node, policy, allowed, reason, context |
| `mutate.applied`, `mutate.rejected` | info, warning | node, reason, mutations |
| `procedure.start`, `procedure.end`, `procedure.fail` | info, error | procedure, adapter, ms |
| `node.saved`, `run.output` | info | file, chars; dir, files |

Examples:

```bash
jq -c 'select(.event=="node.done") | {node, ms}' ~/.graflang/logs/self_refine-*.jsonl     # time per node
jq -c 'select(.level=="WARNING" or .level=="ERROR")' ~/.graflang/logs/*.jsonl             # denials and failures
graf run FILE --log-level debug                                                          # every firing, plus previews
```

A `procedure_ref` node runs an SPL.py workflow. When logging is on, SPL.py writes its own log for that procedure (`spl-<procedure>-<timestamp>`) into the same folder, with the same level and format. A `tools.py` in the same folder as the procedure is loaded too, so its `CALL` statements can use your `@spl_tool` functions.

Used as a Python library (`GraphLangRuntime(...).execute(...)`), the runtime logs nothing until `graphlang.logging_config.setup_logging(...)` is called; the CLI calls it for you.

### `graf validate`

Checks edges point to real nodes and ports, `triggers`/`binds` join the right kinds of port, resources exist, conditions parse and use only available variables, and `GUARD`/`MUTATE`/`LOOP` configs are complete. Errors fail the command; warnings (an input nothing feeds, a node nothing triggers) do not.

It also checks that **every risky node is behind a `GUARD`**. A node is risky if its type is `EMIT` or `QUERY` (they reach outside the workflow) or you mark it with `config: {risky: true}`; mark an `OUTPUT` that releases data, or a `procedure_ref` node that acts on the world. A `LOOP` whose body holds a risky node counts as risky itself. The check follows `triggers` edges from the `INPUT` node with every edge that leaves a `GUARD` removed. A risky node still reached has a path around the guard, which is an error; a risky node reachable from a guard's `deny` port is an error too. Limits: `binds` (data) edges are ignored, guards inside a `LOOP` body are not credited, and a node you forget to mark is not checked, so the check is only as complete as your marking.

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

## Compact form: `steps:`

A short way to write a workflow. `steps:` replaces `nodes:` and `edges:`; `graf expand FILE` prints the long form that runs.

```yaml
steps:
  - draft:    {generate: prompts.draft,    in: {topic: $in.topic}, out: essay}
  - critique: {generate: prompts.critique, in: {essay: draft}, out: feedback}
  - refine:   {generate: prompts.refine,   in: {essay: draft, feedback: critique, tone: plain}, out: essay}
  - done:     {output: refine}
```

- A step is `id: {kind: argument, ...}`. Kinds: `generate` (a `prompts.name` or prompt text), `solve` (an expression), `assert` and `evaluate` (a condition), `guard` (a policy), `fork` (branch names), `join` (the steps it waits for), `output`, and `node` (any other node type, with its `config`).
- `in` maps an input to a value. `$in.topic` is a workflow input, `draft` or `draft.essay` is another step's result, and anything else is a literal that becomes the input's default. Wrap a literal that looks like a reference as `{value: draft}`.
- `out` names the result port(s); the default is `result`, and a bare step name means the first one.
- Control is inferred from the order you list the steps. A step with `on: gate.fail` (or a list) hangs there instead, which is how you write the branches of `assert`, `evaluate`, `guard` and `fork`.
- Other keys (`model`, `phases`, `temperature`, ...) go into the node's `config`. `nodes:` and `edges:` may sit beside `steps:` for anything the compact form cannot say.

## Bindings: `--bind`

A graph says what to do; a bindings file says which model, which files and how much, so the same graph runs in different places.

```yaml
# prod.bind.yaml
llm: claude_cli:claude-sonnet-5-5       # adapter[:model], like --llm
models: {fast: claude-haiku-5-5}        # what `model: $fast` in a node means
params: {topic: tides}                  # default parameters; --param wins
resources:                              # replaces named prompts / procedures / policies; paths relative to this file
  prompts: {draft: ./prod/draft.md}
limits: {max_steps: 200, wall_time_s: 300}
```

`graf run flow.graph.yaml --bind prod.bind.yaml`. A flag on the command line beats the bindings file, which beats the graph's own `model:` hint. A `model: $name` with no binding uses the run's default model (with a warning). `limits.max_cost` is not supported: adapters do not report cost.

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
| `SOLVE` | deterministic: `config.expression`, a `procedure_ref`, or a `backend` (`kernel` or `subprocess`; see "SOLVE backends") |
| `FORK` | emits on all its control output ports |
| `JOIN` | barrier: fires when every incoming trigger has arrived |
| `LOOP` | repeats a `subgraph` (see below) |
| `GUARD` | asks Cedar whether an action is allowed; routes to `allow` or `deny` |
| `MUTATE` | applies an LLM-proposed graph delta if every check passes; routes to `applied` or `rejected` |

The schema also lists `QUERY`, `RECOVER`, `CONTEXT`, `OBSERVE`, `EMIT`; check the runtime before relying on one.

## SOLVE backends

A `SOLVE` can run real code. `backend: kernel` runs Python in a persistent Jupyter kernel (`pip install 'graflang[kernel]'`);
`backend: subprocess` runs any program as a black box (SymPy, Z3, Lean, a Rust binary). Both follow one contract: each `in_<name>`
port is a named JSON value, the node's one `out_*` port (besides `out_error`) gets a value of `out_type` (`BOOL`, `INTEGER`,
`REAL`, `TEXT` or `JSON`, default `JSON`), and an exception, a timeout or a bad output fails the node. `cookbook/solver_check/` uses both.

```yaml
- id: "sum_kernel"
  type: "SOLVE"
  config:
    backend: "kernel"
    code: |                      # trusted: it is in the graph file, reviewed like code
      total = sum(values)        # in_values arrives as the variable `values`
    result: "total"              # an expression; its JSON value goes to out_total
    out_type: "INTEGER"
    timeout: 30                  # seconds
    scope: "run"                 # "run": one kernel for the whole run (default); "node": a fresh kernel for every firing
  ports: ["trigger", "complete", "in_values", "out_total"]

- id: "solve_sat"
  type: "SOLVE"
  config:
    backend: "subprocess"
    command: ["python3", "-I", "solvers/sat_check.py"]    # relative paths start in the graph's folder
    parse: {tool: "solvers/parsers.py:sat"}               # how to read stdout, see below
    out_type: "BOOL"
    timeout: 60
    memory_mb: 2048
    on_error: "route"            # a failure goes to the `error` port, with the message on out_error, instead of ending the run
    env_passthrough: ["HOME", "NODE_PATH"]   # host variables the program may see (see below); default: none
  ports: ["trigger", "complete", "error", "in_formula", "out_result", "out_error"]
```

- **Inputs are data, never code.** Values are passed as JSON (stdin for a subprocess, a string literal bound to variables for the kernel), so a value that looks like Python is still just a value.
- **`parse` (subprocess)** reads the solver's stdout; nothing is guessed. Built in: `last_json` (default; the last JSON object or fenced block), `first_line` (optionally `{first_line: [sat, unsat]}`), `{regex: "result: (?P<value>\\d+)"}` (text only), or `{tool: "file.py:function"}`, a function you write next to the graph that returns the value. A value of the wrong type, or no match, fails the node with the raw stdout and stderr in the log.
- **Environment (subprocess).** The program sees only `PATH` and the variables named in `env_passthrough`; the rest of your environment (API keys, `HOME`, proxies) does not reach it. The value is taken from the environment the run started in, so the graph file holds names, never secrets, and the run log records names, never values. A named variable that is not set fails the node (it is a declaration of need); `graf validate` only warns, because the machine that validates may not be the one that runs. It cannot be used with `backend: kernel`, which inherits the runtime's whole environment.
- **The kernel** starts on the first kernel node and is shut down when the run ends, Ctrl-C included. A timeout restarts it (its variables are gone). `seed` seeds `random` (and numpy, if installed) when the kernel starts. It talks over a Unix socket, not TCP.
- **Not a sandbox.** Code runs with your privileges. It may come only from the graph file: a MUTATE delta that adds or changes `backend`, `code`, `result`, `command`, `parse` or `env_passthrough` (a variable such as `NODE_OPTIONS` changes what runs), at any depth, is refused before any policy is consulted.
- **`graf validate`** reports as errors what graflang cannot run (a syntax error, a missing `result`, an unknown backend, parser or type, two result ports, `on_error: route` without an `error` port, a SOLVE that computes nothing) and as warnings what the machine running the graph may supply (a command or `requirements` item not found, a parser file that is missing or does not define the function, an input the code never uses). It never runs your code or your parser.
- **Logging:** each firing logs `solve.kernel.exec` or `solve.subprocess.exec` with the node, a hash of the code or of the input and output, the duration and the outcome.

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

Literals, `AND`/`OR`/`NOT`, comparisons, arithmetic, and these functions: `contains`, `startswith`, `endswith`, `len`, `lower`, `upper`, `strip`, `abs`, `min`, `max`, `int`, `float`, `str`, `bool`, `is_empty`, and `json_get(value, "a.b.0", default)`, which reads a typed field out of JSON text (for example a procedure's verdict; a JSON `true` stays a boolean). There is no `eval`, attribute access, subscripts, lambdas or `**`; expression length and repetition are capped. `EVALUATE`/`ASSERT` see their own `in_*` ports, so bind what they need. LLM-judged (semantic) conditions are not implemented.

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
| `cookbook/solver_check/` | both SOLVE backends, no LLM: a Python kernel and a subprocess compute the same sum, an `ASSERT` compares them with the expected value, and a failing solver routes to an error report |
| `cookbook/ts_verify/` | a polyglot loop: an LLM writes a TypeScript function, the TypeScript compiler and Node (run as subprocess tools) judge it, their errors drive the retry, and a Python tool builds the report. Needs Node 22.18+ (`npm install` there adds type checking) |

## Known limits

- A `SOLVE` with no `expression`, `procedure_ref` or `backend` computes nothing: `graf validate` and the runtime both report it.
- `contains_pii` in the Cedar context is always false, so the data-sovereignty policy cannot trigger.
- `graf compile` does not produce a working Rust project yet.

The full list is the gap table in the maintainer's design notes (see [`../DEV/readme.md`](../DEV/readme.md)).
