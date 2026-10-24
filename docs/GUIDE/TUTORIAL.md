# Tutorial: your first GraphLang workflow

You will run a bundled workflow, read its anatomy, then write a small one of your own with a retry loop. About 15 minutes. Everything here runs with the default `mock` adapter, so no LLM or network is needed. Install first: [SETUP.md](SETUP.md).

## 1. Run a workflow

```bash
grafr info cookbook/self_refine/self_refine.graph.yaml
grafr run  cookbook/self_refine/self_refine.graph.yaml --param topic="rain" --adapter claude_cli
```

`info` shows the workflow's name, size, inputs, outputs and resources. `run` executes it and prints each node as it fires (`⚡ GENERATE draft (#1)` and so on), then the output. With `mock` the text is a placeholder that echoes the prompt: it proves the wiring works, not that the essay is good.

## 2. Read the graph

Open `cookbook/self_refine/self_refine.graph.yaml`. In GraphLang the graph *is* the program, so there is no code to read: you read nodes and edges.

Four nodes: `wf_entry` (`INPUT`), three `GENERATE` nodes (`draft`, `critique`, `refine`) and `wf_exit` (`OUTPUT`). Each node lists its ports. Ports named `trigger`, `complete`, `entry`, `exit` carry **control**; ports named `in_<x>` and `out_<x>` carry **data**.

Edges come in two kinds:

```yaml
# control: who fires next
- {source: "draft.complete", target: "critique.trigger", type: "triggers"}
# data: where a value flows
- {source: "draft.out_essay", target: "critique.in_essay", type: "binds"}
```

So the control chain is `entry -> draft -> critique -> refine -> exit`, and the data wires carry the essay and the feedback to wherever they are needed. A node fires when a control token reaches its `trigger`; it reads its `in_*` ports and writes its `out_*` ports.

The prompts are files under `prompts/`, declared in `resources.prompts` and referenced as `prompt_ref: "prompts.draft"`. Inside a prompt, `{{in_topic}}` is replaced with the value on the node's `in_topic` port.

## 3. Write your own

Make a folder with a prompt and a graph.

`prompts/haiku.md`:

```
Write a haiku about: {{in_topic}}
```

`haiku.graph.yaml`:

```yaml
version: "1.0-graph"

workflow:
  name: "haiku_check"
  inputs:
    - {name: "topic", type: "TEXT"}
  outputs:
    - {name: "poem", type: "TEXT"}

resources:
  prompts:
    haiku: "./prompts/haiku.md"

nodes:
  - id: "start"
    type: "INPUT"
    ports: ["entry", "out_topic"]

  - id: "write"
    type: "GENERATE"
    config: {prompt_ref: "prompts.haiku"}
    ports: ["trigger", "complete", "in_topic", "out_poem"]

  - id: "gate"
    type: "EVALUATE"
    config: {condition: "len(@in_poem) > 10"}
    ports: ["trigger", "pass", "fail", "in_poem"]

  - id: "done"
    type: "OUTPUT"
    ports: ["trigger", "exit", "in_result"]

edges:
  - {source: "start.entry",    target: "write.trigger", type: "triggers"}
  - {source: "write.complete", target: "gate.trigger",  type: "triggers"}
  - {source: "gate.pass",      target: "done.trigger",  type: "triggers"}
  - {source: "gate.fail",      target: "write.trigger", type: "triggers"}   # retry

  - {source: "start.out_topic", target: "write.in_topic", type: "binds"}
  - {source: "write.out_poem",  target: "gate.in_poem",   type: "binds"}
  - {source: "write.out_poem",  target: "done.in_result", type: "binds"}
```

Check and run it:

```bash
grafr validate haiku.graph.yaml
grafr run haiku.graph.yaml --param topic="rain"
```

What you built: `write` generates; `gate` (`EVALUATE`) tests a condition on the poem and sends the token to `pass` or `fail`; `fail` is wired back to `write.trigger`, so a bad result tries again. A node may fire more than once, so a retry is simply a wire back to an earlier node.

Notice that `gate` reads `@in_poem`, one of its *own* `in_*` ports. Conditions see only the node's inputs, which is why `write.out_poem` is bound to both `gate.in_poem` and `done.in_result`.

## 4. Break it on purpose

Make the condition impossible and give it a retry that never succeeds:

```yaml
config: {condition: "len(@in_poem) > 100000"}
```

```bash
grafr run haiku.graph.yaml --param topic="rain" --max-steps 20
```

The run fails with `✗ Run failed: stopped after 20 node firings` (naming the nodes that fired most). `--max-steps` bounds the number of node firings, which is your safety net for endless retry wires. A better design is to let `LOOP` own the repetition (next section).

Now introduce a typo: change `@in_poem` to `@poem`. `grafr validate` reports that the condition uses a variable that is not available, before anything runs. Run `validate` after every edit.

## 5. Let a LOOP own the repetition

A `LOOP` node runs a sub-graph repeatedly while a condition holds, and has a built-in counter and iteration cap. Its body is a plain sequence (no back-edge inside it); the loop supplies the repetition:

```yaml
- id: "retry"
  type: "LOOP"
  ports: ["trigger", "exit", "in_topic", "out_poem", "out_ok"]
  config:
    condition: "NOT @ok AND @cycle < 3"          # checked BEFORE each iteration
    outputs:
      poem: {from: "write.out_poem"}            # latest iteration's value
      ok:   {fired: "gate.pass"}                # did gate.pass fire last iteration?
    subgraph:
      nodes:
        - {id: "write", type: "GENERATE", config: {prompt_ref: "prompts.haiku"}, ports: ["trigger", "complete", "in_topic", "out_poem"]}
        - {id: "gate",  type: "EVALUATE", config: {condition: "len(@in_poem) > 10"}, ports: ["trigger", "pass", "fail", "in_poem"]}
      edges:
        - {source: "write.complete", target: "gate.trigger", type: "triggers"}
        - {source: "write.out_poem", target: "gate.in_poem", type: "binds"}
```

`@cycle` is the 0-based counter. `@ok` is the previous iteration's output named `ok`. Because the condition is checked before each iteration, `NOT @ok` is true on the first pass (nothing has fired yet). In the body, `write.in_topic` has no `binds` edge, so it reads the loop's own `in_topic`, which you bind from `start.out_topic`. Replace `write`/`gate` in your graph with this node, wire `start.entry -> retry.trigger`, `retry.exit -> done.trigger` and `retry.out_poem -> done.in_result`, then `validate` and `run`. For a complete example see `cookbook/concept_book/` (collects one chapter per iteration) and `cookbook/code_pipeline/`.

## 6. Go real

Pick an adapter and model when you run, not in the graph:

```bash
grafr run haiku.graph.yaml --adapter claude_cli --model claude-haiku-5-5 --param topic="rain"
```

See [SETUP.md](SETUP.md) for adapter setup.

## Where next

- [USER-GUIDE.md](USER-GUIDE.md): every command, node type, port convention, `GUARD` and `MUTATE`.
- `cookbook/code_pipeline/`: the flagship, with a test-gated `LOOP`, a Cedar `GUARD` on retries, and SPL procedures.
- [contributor-guide.md](contributor-guide.md): how the runtime is built and how to extend it.
