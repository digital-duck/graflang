# Tutorial: your first GraphLang workflow

You will run a bundled workflow, read its anatomy, then write a small one of your own with a retry loop. About 15 minutes. Every `graf run` here uses the default model (`claude_cli` with `claude-sonnet-5-5`), so the `claude` command-line tool must work; each run makes a handful of short calls, and the one deliberately endless retry in section 4 is capped at 10. Install first: [SETUP.md](SETUP.md).

## 1. Run a workflow

```bash
graf info cookbook/self_refine/self_refine.graph.yaml
graf run  cookbook/self_refine/self_refine.graph.yaml --param topic="rain"
```

`info` shows the workflow's name, size, inputs, outputs and resources. `run` executes it and prints each node as it fires (`⚡ GENERATE draft (#1)` and so on), then the output and a `log:` line with the path of this run's log file (section 5).

## 2. Read the graph

To see it first, run `graf vis cookbook/self_refine/self_refine.graph.yaml`: it opens a picture of the workflow in your browser (click a node to see its config and links). The rest of this section reads the same thing in the YAML.

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
graf validate haiku.graph.yaml
graf run haiku.graph.yaml --param topic="rain"
```

What you built: `write` generates; `gate` (`EVALUATE`) tests a condition on the poem and sends the token to `pass` or `fail`; `fail` is wired back to `write.trigger`, so a bad result tries again. A node may fire more than once, so a retry is simply a wire back to an earlier node.

Notice that `gate` reads `@in_poem`, one of its *own* `in_*` ports. Conditions see only the node's inputs, which is why `write.out_poem` is bound to both `gate.in_poem` and `done.in_result`.

## 4. Break it on purpose

Make the condition impossible and give it a retry that never succeeds:

```yaml
config: {condition: "len(@in_poem) > 100000"}
```

```bash
graf run haiku.graph.yaml --param topic="rain" --max-steps 20
```

The run fails with `✗ Run failed: stopped after 20 node firings` (naming the nodes that fired most). `--max-steps` bounds the number of node firings, which is your safety net for endless retry wires. A better design is to let `LOOP` own the repetition (next section).

Now introduce a typo: change `@in_poem` to `@poem`. `graf validate` reports that the condition uses a variable that is not available, before anything runs. Run `validate` after every edit.

## 5. Read the run log

Every `graf run` also writes a log file that records what happened, whether or not the run succeeded. The terminal shows the last line, `log: <path>`. By default the files go to `~/.graflang/logs/` (created on first use), one pair per run, named `<graph>-<adapter>[-<model>]-<timestamp>` (the model appears when you pass `--model` or `--llm ADAPTER:MODEL`, with `:` and `/` turned into `-`). Use `--log-dir .` to put them in the current folder instead:

```
~/.graflang/logs/haiku-claude_cli-claude-sonnet-5-5-20261024-081302.log      # for people
~/.graflang/logs/haiku-claude_cli-claude-sonnet-5-5-20261024-081302.jsonl    # for tools (one JSON object per line)
```

Run the failing graph from section 4 and open the `.log`:

```
08:13:02  INFO   graflang.grafr.runtime  node.done node=write type=GENERATE n=10 depth=0 route=None outputs=['out_poem'] ms=0
08:13:02  INFO   graflang.grafr.runtime  node.done node=gate type=EVALUATE n=10 depth=0 route=fail outputs=[] ms=0
08:13:02  ERROR  graflang.grafr.runtime  run.fail workflow=haiku_check steps=21 error="RunLimitExceeded: stopped after 20 node firings; most fired: [('write', 10), ('gate', 10)]" ms=9
```

`n=10` is how many times that node has fired, and `route=fail` shows which port `gate` sent the token to: the retry loop is visible as `write` and `gate` alternating until the cap. Each line starts with an event name:

| Event | Level | Meaning |
|---|---|---|
| `run.start`, `run.end`, `run.fail` | info / error | one run; `run.fail` carries the error |
| `node.done`, `node.error` | info / error | a node finished or raised, with its `route` and `ms` |
| `llm.call` | info | a GENERATE call: adapter, model, prompt and response sizes, `ms` |
| `loop.end`, `guard.decision`, `mutate.applied`, `mutate.rejected` | info / warning | LOOP exit, Cedar allow or deny, MUTATE outcome |
| `node.fire`, `loop.iteration`, `llm.text` | debug | every firing, every iteration, and previews of the prompt and response text |

The default level is `info`. Add `--log-level debug` to see the debug events, for example to check exactly what prompt a node sent:

```bash
graf run haiku.graph.yaml --param topic="rain" --max-steps 20 --log-level debug
```

The `.jsonl` has the same events with their fields as keys, so you can query it:

```bash
jq -r 'select(.event=="llm.call") | [.node, .model, .prompt_chars, .response_chars, .ms] | @tsv' ~/.graflang/logs/*.jsonl
jq -r 'select(.level=="ERROR") | .msg' ~/.graflang/logs/*.jsonl
```

Options on `graf run` (each also has an environment variable):

| Option | Env var | Default |
|---|---|---|
| `--log-level debug\|info\|warning\|error` | `DD_LOG_LEVEL` | `info` |
| `--log-format text\|jsonl\|both` | `DD_LOG_FORMAT` | `both` |
| `--log-dir DIR` | `DD_LOG_DIR` | `~/.graflang/logs` |
| `--no-log` | | off (log files are written) |

Logging is off when you use the runtime as a library (`GraphLangRuntime(...)` from Python): nothing is written until you call `graphlang.logging_config.setup_logging(run_name, ...)`. For `procedure_ref` nodes, a SPL.py new enough to have `spl3.logging_config` writes its own `spl-<procedure>-…` log into the same directory; older versions just skip it.

## 6. Let a LOOP own the repetition

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

## 7. Another model

Pick an adapter and model when you run, not in the graph. The default is `--adapter claude_cli --model claude-sonnet-5-5` (the `claude` command-line tool, so no API key). The adapter and model are part of the log file name (`haiku-claude_cli-claude-haiku-5-5-<timestamp>.log`), so runs with different LLMs are easy to tell apart:

```bash
graf run haiku.graph.yaml --llm claude_cli:claude-haiku-5-5 --param topic="rain"
```

`--llm ADAPTER:MODEL` is shorthand for `--adapter ADAPTER --model MODEL` (and wins if you give both). Leave the model off (`--llm claude_cli`) to use the adapter's default. See [SETUP.md](SETUP.md) for adapter setup.

## 8. A real example: PII compliance audit

`cookbook/compliance_audit/` mixes everything above: an LLM for the fuzzy part, fixed rules for the decision, a retry path and a Cedar guard. An LLM reads a document and lists the **types** of personal data in it (never the values). Boolean rules then decide, with no LLM, whether the document may go to a destination. A failing document is redacted, read again and re-checked once. A Cedar `GUARD` has the last word, and anything that cannot be shown compliant ends at the `escalated` output.

The rule check is a small Python program that a `SOLVE` node runs as a subprocess (`backend: subprocess`), so it needs no extra install. Run it:

```bash
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --param document="Customer John Doe, SSN 123-45-6789, asks to update his address." \
    --param destination=external_api --param engine=stdlib --param rules_file=
```

With `claude-sonnet-5-5` the run reads the document, finds an SSN, fails rule R2 ("a social security number never leaves externally, even masked"), redacts it, reads the redacted text again, passes, and the guard releases it. The output folder has `safe_document.md` (the redacted text) and `audit.md` (for example `released to external_api (stdlib engine)`).

The result depends on the model, and the graph fails closed. With `claude-haiku-5-5` the same command ended at `escalated` (`Violated: ['R1']`): the first read found a name and an SSN, the redaction removed both, but the second read reported an unmasked `ADDRESS` (it took the word "address" in the text for personal data), so rule R1 failed and nothing was released. That is a false alarm, not a leak, and it is the intended behaviour when the model's reading cannot be shown compliant. Add `--save-nodes` to keep each node's output under `output/.../nodes/` and see where a run went. Try `--param destination=internal_db` and the same document passes the first check untouched.

Things to look at:

- `graf vis cookbook/compliance_audit/compliance_audit.graph.yaml` draws the two paths (first pass, and redact then re-check).
- `engine` picks how the rules are checked: `stdlib` (no extra install), `sympy` or `z3`. All three must give the same answer.
- The rules are in `cookbook/compliance_audit/procedures/rules.json`. Copy it, edit a rule, and run again with `--param rules_file=my_rules.json`. Check a file first with `python cookbook/compliance_audit/procedures/tools.py my_rules.json`. A missing or invalid rules file stops the run; it is never replaced by the defaults.
- The `released` output is marked `risky: true`, and `graf validate` proves it can only be reached through the guard's `allow` port. Add an edge from `compliant_first.pass` straight to `released` and validate again to see it refuse.
- No LLM needed to see every path: `pytest tests/test_compliance_audit.py` runs the graph with a stub model.

The default rules are an illustration, not legal advice and not a real GDPR or PCI rule set. The full explanation is in `cookbook/compliance_audit/readme.md`.

## Where next

- [USER-GUIDE.md](USER-GUIDE.md): every command, node type, port convention, `GUARD` and `MUTATE`.
- `cookbook/compliance_audit/`: deterministic rules, redact and re-check, and a Cedar release guard (section 8).
- `cookbook/code_pipeline/`: the flagship, with a test-gated `LOOP`, a Cedar `GUARD` on retries, and SPL procedures.
- [contributor-guide.md](contributor-guide.md): how the runtime is built and how to extend it.
