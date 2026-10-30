# GraphLang: Verification Guide

How to check, by hand and by test, every feature built so far (state of 2026-10-30). Each section says what to run, what you should see, and which test file pins it. Commands run from the repo root `graflang/`. Nothing here needs a model unless a step says **[real LLM]**, and those are small and budgeted.

Contents: 0 Setup · 1 The automated suite · 2 The cookbook at a glance · 3 Core commands · 4 Validation rules · 5 Node lifecycle and typed ports · 6 Compact form, parts, elaboration · 7 Bindings, budgets, record and replay, checkpoint · 8 Concurrency, BATCH, RUN, SOLVE backends, containers · 9 Safety: GUARD, MUTATE, policies, PII · 10 The editor · 11 SPL interop and the PocketFlow corpus · 12 Real-LLM checks · 13 Known failures and limits · 14 If something does not behave

---

## 0. Setup

```bash
conda activate graf                    # or use /home/gongai/anaconda3/envs/graf/bin/python and .../bin/graf
pip install -e ".[dev]"                # once; extras: kernel (kernel SOLVE), edit (the editor), grafc (jinja2)
pip install -e ".[kernel]"             # needed by lifted_tool, solver_check, 2 tests
graf --help                            # run, validate, info, expand, export-spl, vis, compile, check
```

- The system `python` lacks `zinet`; use the `graf` env.
- SPL.py must be importable for the SPL interop checks (`pip install -e ../SPL.py`); without it those tests skip, they do not fail.
- Scratch work: use a throwaway folder, e.g. `mkdir -p /tmp/verify && cd /tmp/verify` for the graphs in sections 4, 5 and 7. Outputs of `graf run` go to `<graph folder>/output/` unless you pass `--no-output` or `--output-dir`; logs go to `~/.graflang/logs/` unless `--no-log`.
- **Budget every real-model run** (section 12). A loop that does not exit can make hundreds of billed calls.

## 1. The automated suite

```bash
python -m pytest -q -m "not llm"        # offline: no model
```

Expected (2026-10-30): **729 passed, 4 skipped, 7 failed**, about 45 s. The 7 failures are the known, left-alone ones in the hand-written Cedar compiler: `tests/test_cedar_compiler.py` (6) and `tests/test_policy_slicer.py::test_slice_by_context_keys` (1). Anything else failing is a regression.

Skips: the Streamlit editor tests (no Streamlit in the `graf` env), the real-Docker test (no daemon), and two environment skips.

```bash
python -m pytest -q -m llm              # 8 real-model tests, claude_cli, claude-sonnet-5-5, about 5 min, billed
python -m pytest tests/test_x.py -q     # one file
python -m pytest tests/test_x.py::test_name -q
```

The Streamlit editor tests need Streamlit: `pip install streamlit ruamel.yaml` into a scratch venv (not the `graf` env), then `pytest tests/test_editor_app.py`. They passed (7) when last run that way.

Which file pins which feature:

| Feature | Test files (offline test count) |
|---|---|
| Runtime, output, logging, adapters | `test_grafr_runtime` 13, `test_grafr_output` 12, `test_grafr_logging` 11, `test_grafr_adapters` 8, `test_grafr_llm_flag` 7, `test_cli_alias` 4 |
| Expressions, conditions, `latest()` | `test_grafr_expr` 27 |
| LOOP, back-edges, semantics rules R1 to R10 | `test_grafr_loop` 11, `test_semantics` 12 |
| Validation: race, deadlock, guards, typed ports | `test_topology` 29, `test_ports` 8 |
| Lifecycle, retry, fallback, RECOVER | `test_lifecycle` 30 |
| Compact form (including `loop`, `use`) | `test_compact` 26 |
| Parts and elaboration | `test_parts` 14, `test_elaborate` 16 |
| Bindings, metering, budgets, cassettes, checkpoint | `test_bindings` 12, `test_metering` 10, `test_checkpoint` 5 |
| Concurrency, JOIN, BATCH, RUN | `test_concurrency` 10, `test_batch` 7, `test_run_node` 13 |
| SOLVE backends, subprocess, kernel, container | `test_solve_backends` 47, `test_solver_backend` 15, `test_solver_check_example` 4, `test_container` 15 |
| GUARD, MUTATE (including loop persistence), Cedar | `test_grafr_mutate` 37 |
| Capabilities policy, PII | `test_capabilities` 9, `test_pii` 16 |
| Editor | `test_editor` 38, `test_editor_app` (needs Streamlit) |
| Drawing | `test_grafv` 32, `test_formats` 27 |
| SPL interop | `test_export_spl` 9, `test_lifted_graph` 2, `test_lifted_tool` 1, `test_lifted_loops` 2, `test_pocketflow_corpus` 94 |
| Cookbook recipes | `test_compliance_audit` 20, `test_ts_verify` 11 (needs Node 22.18+), `test_experiment_*` 51 |

In the SPL.py repo: `python -m pytest tests/test_spl2graph.py -q` should give **19 passed**.

## 2. The cookbook at a glance

Every graph validates, and all but the two LLM-only ones run offline with `--adapter mock`.

```bash
for f in cookbook/*/*.graph.yaml cookbook/pocketflow/*.graph.yaml; do
  case $f in */parts/*) continue;; esac
  printf '%-58s' $f; graf validate $f | tail -1
done
```

Expected: every line `✓ Valid GraphLang workflow: <name>`.

| Recipe | Shows | Offline run | Readme |
|---|---|---|---|
| `self_refine` | 3 GENERATE nodes in a line | `graf run cookbook/self_refine/self_refine.graph.yaml --adapter mock --param topic=ducks` | yes |
| `concept_book` | LOOP with `collect` | `graf run cookbook/concept_book/build_concept_book.graph.yaml --adapter mock --param subject=entropy --param num_chapters=2` | yes |
| `code_pipeline` | procedures, guards, MUTATE, RECOVER (needs SPL.py to run `.spl`) | see its readme | yes |
| `compliance_audit` | subprocess SOLVE rules, Cedar release guard | needs a model for extract/redact; tests cover all paths with a stub | yes |
| `solver_check` | kernel and subprocess SOLVE, ASSERT routing | `graf run cookbook/solver_check/solver_check.graph.yaml --adapter mock --param numbers=1,2,3 --param expected=6` | yes |
| `ts_verify` | LLM writes TypeScript, Node and tsc judge it | needs Node 22.18+ and a model | yes |
| `chain_of_thought` | lifted from SPL, cassette | replay (section 7) | yes |
| `lifted_tool` | a Python tool as a kernel SOLVE | `graf run cookbook/lifted_tool/lifted_tool.graph.yaml --param word=hello` | yes |
| `parts_demo` | one part used twice | `graf run cookbook/parts_demo/parts_demo.graph.yaml --adapter mock --param topic=tides` | yes |
| `elaborate_demo` | a template applied to a graph | `graf run cookbook/elaborate_demo/elaborate_demo.graph.yaml --adapter mock --workers 2` | yes |
| `pocketflow` | R1 acceptance samples | section 11 | yes |

## 3. Core commands

```bash
G=cookbook/self_refine/self_refine.graph.yaml
graf info $G                             # name, node and edge counts, inputs, outputs, resources
graf validate $G                         # ✓ Valid GraphLang workflow: self_refine
graf run $G --adapter mock --param topic=ducks --save-nodes --output-dir /tmp/verify/out
```

Check `/tmp/verify/out/self_refine-mock-<time>/`: `essay.md`, `result.json`, `run.json`, `summary.json` (steps 4, 3 calls), and `nodes/` with one file per node output.

```bash
graf run $G --adapter mock --param topic=x --log-level debug --log-format jsonl --log-dir /tmp/verify/logs
ls /tmp/verify/logs                      # a .jsonl with run.start, node events, run.end
graf run $G --adapter mock --param topic=x --no-output --no-log   # prints only to the console
graf run $G --adapter mock                                         # error: required input 'topic' missing (before any node fires)
graf run $G --adapter mock --param nope=1                          # error: unknown workflow input
```

Typed inputs: `graf run cookbook/concept_book/build_concept_book.graph.yaml --adapter mock --param subject=x --param num_chapters=abc` fails at once with `input 'num_chapters' must be INTEGER`.

Other commands:

```bash
graf expand cookbook/parts_demo/parts_demo.graph.yaml        # the long nodes/edges form (compact, parts, elaborate all expand)
graf export-spl cookbook/lifted_tool/lifted_tool.graph.yaml  # SPL text with CREATE TOOL_API shout(...)
graf vis cookbook/elaborate_demo/elaborate_demo.graph.yaml --engine mermaid -o /tmp/verify/e.md --no-open
graf vis cookbook/parts_demo/parts_demo.graph.yaml --no-open # a cytoscape HTML in ~/.graflang/vis/, parts drawn as boxes
```

Engines: `cytoscape` (default), `graphviz`, `pyvis`, `graphify`, `mermaid`. Open the HTML for a LOOP: its body appears as a box. In the parts and elaboration pictures each use of a part is a box labelled `first (polish)`.

Pinned by: `test_grafr_output`, `test_grafr_logging`, `test_grafv`, `test_export_spl`.

## 4. Validation rules

`graf validate` proves properties before anything runs. Make these three small files in a scratch folder and expect each error.

**Race** (two unordered writers of one port):

```yaml
# race.graph.yaml
version: "1.0-graph"
workflow: {name: race, inputs: [], outputs: [{name: out, type: TEXT}]}
nodes:
  - {id: s, type: INPUT, ports: [entry]}
  - {id: f, type: FORK, ports: [trigger, a, b]}
  - {id: x, type: SOLVE, config: {expression: "'x'"}, ports: [trigger, complete, out_v]}
  - {id: y, type: SOLVE, config: {expression: "'y'"}, ports: [trigger, complete, out_v]}
  - {id: o, type: OUTPUT, ports: [trigger, exit, in_out]}
edges:
  - {source: s.entry, target: f.trigger, type: triggers}
  - {source: f.a, target: x.trigger, type: triggers}
  - {source: f.b, target: y.trigger, type: triggers}
  - {source: x.complete, target: o.trigger, type: triggers}
  - {source: x.out_v, target: o.in_out, type: binds}
  - {source: y.out_v, target: o.in_out, type: binds}
```

`graf validate race.graph.yaml` gives `error: race: 'x' and 'y' both write 'o.in_out' and neither runs after the other or excludes it`.

**Unguarded risky node:** an `EMIT` fed straight from `s.entry` (nodes: `s` INPUT with port `entry`, `e` EMIT with ports `trigger`, `complete`; one triggers edge `s.entry -> e.trigger`) gives `error: EMIT 'e' is risky but can run without passing a GUARD's allow port`.

**Type mismatch:** a SOLVE whose `out_n` is declared `INTEGER` (ports as a mapping: `ports: {trigger: control, complete: control, out_n: INTEGER}`) bound to an OUTPUT `in_o: LIST` gives `error: a.out_n -> o.in_o: INTEGER cannot be bound to a LIST port`.

Also checked: a JOIN waiting on two exclusive branches (deadlock), unknown ports and nodes, missing schema fields, unknown LOOP or BATCH settings, `graf validate` on `workflow.policy` (section 9).

Pinned by: `test_topology`, `test_ports`, `test_semantics` (rules R1 to R10 in `graflang-semantics.md`).

## 5. Node lifecycle and typed ports

`config.phases` wraps any node in pre, exec, post.

**Fallback value:**

```yaml
# fb.graph.yaml
version: "1.0-graph"
workflow: {name: fb, inputs: [], outputs: [{name: o, type: TEXT}]}
steps:
  - bad: {solve: "int('abc')", phases: {exec: {fallback: {value: "n/a"}}}}
  - done: {output: bad}
```

`graf run fb.graph.yaml --no-output --no-log` prints `Output: {'o': 'n/a'}`. Remove the `phases` and the run fails with the expression error.

Everything else in the lifecycle is easier to see in tests: `pytest tests/test_lifecycle.py -q` (30) covers `pre.require` and `defaults`, `exec.retry` with `max` and `wait_s` and `on`, `timeout_s`, fallback to a route, `post.out_schema` (GENERATE asks for JSON and re-prompts with the validation error), `post.route`, and `RECOVER` (`halt`, `abort`, `skip`, `retry`). Typed ports and trust labels (`TEXT!sql_safe`): `pytest tests/test_ports.py -q` (8).

**[real LLM]** `pytest tests/test_lifecycle.py -m llm -q` makes one real call asking for JSON that matches a schema.

## 6. Compact form, parts, elaboration

**Compact `steps:`** — `graf expand cookbook/parts_demo/parts_demo.graph.yaml | head -40` shows the long form. Kinds: generate, solve, assert, evaluate, guard, fork, join, output, use, loop, node.

**Compact loop** — save as `loop.graph.yaml` and run with mock:

```yaml
version: "1.0-graph"
workflow:
  name: cl
  inputs: [{name: subject, type: TEXT}, {name: n, type: INTEGER, default: 2}]
  outputs: [{name: book, type: TEXT}]
steps:
  - outline: {generate: "Outline {{in_subject}}", in: {subject: $in.subject}, out: outline}
  - chapters:
      loop: "@in_n"
      index: i
      in: {outline: outline, subject: $in.subject, n: $in.n}
      out: {chapters: {collect: write.chapter}}
      steps:
        - write:  {generate: "Chapter {{in_i}} of {{in_subject}}: {{in_outline}}", in: {outline: $loop.outline, i: $loop.i, subject: $loop.subject}, out: chapter}
        - review: {generate: "Review {{in_chapter}}", in: {chapter: write.chapter}}
  - book: {generate: "Compile {{in_chapters}}", in: {chapters: chapters.chapters}, out: book}
  - done: {output: book}
```

`graf run loop.graph.yaml --adapter mock --param subject=x --no-output --no-log` completes with **6 LLM calls** (outline, two chapters times write and review, compile). With `--param n=3`: 8 calls.

**Parts:**

```bash
graf run cookbook/parts_demo/parts_demo.graph.yaml --adapter mock --param topic=tides --save-nodes --output-dir /tmp/verify/p
graf expand cookbook/parts_demo/parts_demo.graph.yaml | grep -E "id: (first|second)__"   # first__rewrite, second__rewrite
```

The first use is told `formal tone`, the second the part's default `plain tone` (look at the prompts in the saved node files, or run the replay-free test `pytest tests/test_parts.py -q`, 14). Try the errors: in a copy, rename an `in:` key to something the part does not have and `graf validate` names it (`in_mood is not an input`); make the part use itself (`cannot use itself`).

**Elaboration:**

```bash
graf run cookbook/elaborate_demo/elaborate_demo.graph.yaml --adapter mock --workers 2 --no-output --no-log
```

Expected: four explanations keyed `counting`, `probability`, `entropy`, `coding`; the `entropy` prompt contains both prerequisites' texts; `coding` contains `entropy`'s. Run it with `--workers 1` and `--workers 4`: the output is identical. Add an edge `coding -> probability` to `concepts.yaml` (a copy) and validation reports a cycle.

Pinned by: `test_compact`, `test_parts`, `test_elaborate`. **[real LLM]** one test each (`-m llm`).

## 7. Bindings, budgets, record and replay, checkpoint

**Bindings:** a file that changes how a graph runs, not what it is.

```yaml
# b.bind.yaml
params: {max_iterations: 2}
limits: {max_steps: 500}
```

`graf run cookbook/pocketflow/text_transformer.graph.yaml --bind b.bind.yaml --no-output --no-log` runs two rounds instead of 20. Other keys: `llm`, `models` (for `model: $name`), `resources` (replace a prompt or policy), `limits.max_llm_calls`, `max_cost_usd`, `wall_time_s`, `concurrency`. A flag on the command line beats the file, which beats the graph's own hints. `pytest tests/test_bindings.py -q` (12).

**Budgets:** `limits: {max_llm_calls: 2}` stops `self_refine` (3 calls) with `stopped before call 3: limits.max_llm_calls is 2`. `max_cost_usd` needs an adapter that reports cost; with one that does not (`claude_cli`) the run stops at the second call and says so.

**Record and replay:**

```bash
graf run cookbook/chain_of_thought/chain_of_thought.graph.yaml --replay cookbook/chain_of_thought/chain_of_thought.cassette.jsonl --param topic="solar sails" --no-output --no-log
graf run cookbook/pocketflow/majority_vote.graph.yaml --replay cookbook/pocketflow/majority_vote.cassette.jsonl --no-output --no-log   # answer 36, 3 calls
graf run cookbook/pocketflow/debate.graph.yaml --replay cookbook/pocketflow/debate.cassette.jsonl --param max_iterations=2 --no-output --no-log   # a verdict, 11 calls
```

No model is contacted. A different topic is an unrecorded call and fails loudly (`no recording ... for this call`). `--record FILE` writes a cassette from a live run. The cassette is keyed by model, prompt and temperature. `pytest tests/test_metering.py -q` (10).

**Checkpoint and resume:**

```bash
graf run cookbook/pocketflow/text_transformer.graph.yaml --max-steps 12 --checkpoint /tmp/verify/c.json --no-output --no-log   # stops: "stopped after 12 node firings"
graf run cookbook/pocketflow/text_transformer.graph.yaml --resume /tmp/verify/c.json --no-output --no-log                      # ✓ Workflow completed, 79 steps
```

A checkpoint belongs to one graph; resuming against an edited graph is refused. Kernel variables are not restored. `pytest tests/test_checkpoint.py -q` (5).

## 8. Concurrency, BATCH, RUN, SOLVE backends, containers

**Concurrency:** `--workers N` runs nodes released together at the same time; results are applied in token order, so the output must not change:

```bash
for w in 1 4; do graf run cookbook/elaborate_demo/elaborate_demo.graph.yaml --adapter mock --workers $w --no-output --no-log | grep Output | md5sum; done   # two identical hashes
```

`pytest tests/test_concurrency.py -q` (10) checks every shipped graph gives the same result with 4 workers as with 1. **[real LLM]** `test_real_llm_two_branches_overlap` proves two branches really overlap in time.

**JOIN bundling and BATCH:** `pytest tests/test_batch.py tests/test_concurrency.py -q`. A JOIN with `in_*` ports yields one object (`@in_args.name`); BATCH maps a list through a subgraph with `concurrency` and `max_items`.

**SOLVE backends** (deterministic work, no model):

```bash
graf run cookbook/solver_check/solver_check.graph.yaml --adapter mock --param numbers=1,2,3 --param expected=6 --no-output --no-log
#   Output: {'verdict': 'confirmed: 6 (kernel and subprocess agree)'}
graf run cookbook/solver_check/solver_check.graph.yaml --adapter mock --param numbers=1,2,3 --param expected=7 --no-output --no-log
#   Output: {'verdict': 'MISMATCH: kernel 6, subprocess 6, expected 7'}
graf run cookbook/lifted_tool/lifted_tool.graph.yaml --param word=hello --no-output --no-log   # Output: {'loud': 'HELLO!'}
```

`pytest tests/test_solve_backends.py tests/test_solver_backend.py tests/test_run_node.py -q`. The RUN node (`executor: subprocess | python | http`) has one contract (named JSON in, one typed result out); http needs `allow_hosts`, refuses redirects, reads `{result}` or `{error: {code, message, retryable}}`.

**What the executors do not confine** (pinned as `test_KNOWN_*` tests): a subprocess or kernel can read files anywhere you can, and a kernel inherits the runtime's environment. They do limit memory (`memory_mb`), time (`timeout`), and a subprocess's environment (only `PATH` and `env_passthrough`).

**Container option** (a `subprocess` node with `container: {image: python:3.12-slim}`):

```bash
pytest tests/test_container.py -q        # 14 pass with a stub docker; 1 real-daemon test skips
```

To verify for real you need a Docker daemon and `docker pull python:3.12-slim`; then the same command runs `test_real_docker_has_no_network_and_a_read_only_mount` (no network, read-only mount). **This is the one feature not yet verified against a real daemon.** `graf validate` on a node with a bad `container:` names the problem (unknown key, `network: host`, non-positive limits).

## 9. Safety: GUARD, MUTATE, policies, PII

**GUARD and MUTATE** (Cedar via `cedarpy`, fail-closed):

```bash
pytest tests/test_grafr_mutate.py -q     # 37
```

Covers: default deny and forbid-beats-permit; a policy that errors denies; a MUTATE applies a delta only if it parses, matches the schema, keeps the graph well formed, is allowed by Cedar, and is under `max_mutations`; a delta can never remove or edit a `GUARD`/`MUTATE` node, the `risky` flag, or any code key (`backend`, `code`, `result`, `command`, `parse`, `env_passthrough`, `executor`, `url`, `allow_hosts`, `headers`, `method`, `container`); a MUTATE keeps the race, deadlock and guarded-risky invariants.

**Loop persistence:** a MUTATE in a LOOP body changes only that iteration's copy; `persist_mutations: true` on the LOOP carries it to the next iteration (`test_persist_mutations_carries_the_changed_body_to_the_next_iteration`).

**Capabilities policy** (what a workflow may contain): put `policy: policies.capabilities` in the workflow header and list `graphlang/policies/capabilities.cedar` under `resources.policies`. `graf validate` then refuses a node that needs `shell`, an unguarded node with a capability, or an http `RUN` to an unnamed host, and `graf run` refuses it too. `pytest tests/test_capabilities.py -q` (9).

**PII:** `has_pii(@text)` in a condition detects email, phone, US SSN, Luhn-valid card and IBAN shapes; a MUTATE sets `contains_pii` from its delta. `pytest tests/test_pii.py -q` (16). The `compliance_audit` recipe uses rules and a Cedar release guard end to end: `pytest tests/test_compliance_audit.py -q` (20, stub model).

## 10. The editor

Needs Streamlit, which is not in the `graf` env: `pip install 'graflang[edit]'` (or a scratch venv).

```bash
graf vis --edit cookbook/self_refine/self_refine.graph.yaml     # opens a browser tab (alias: graf ui)
```

Check by hand:

1. The picture shows the graph; the sidebar says "saved".
2. **Node tab:** pick `draft`, change `temperature` to `0.2` and press Set. The sidebar says "unsaved changes"; **Problems** still says valid; **Undo** restores it.
3. Add a config key with an invalid value, or remove a port an edge uses: **Problems** lists the error and **Save** is disabled.
4. Fix it and press **Save**: comments such as `# Control flow` are kept in the file and only the edited line changes (`git diff cookbook/self_refine`). Revert with `git checkout cookbook/self_refine`.
5. **Run tab:** fill `topic`, keep `mock`, press Run: you see the step count, the output JSON and a table of nodes fired. Choosing `claude_cli` makes real calls.
6. Open a compact file (`parts_demo`) or an `elaborate:` file: the editor refuses with a message pointing to `graf expand`.

Not in the editor, by decision: dragging edges on the canvas, and editing compact or `elaborate:` files. `pytest tests/test_editor.py -q` (38) always runs; `test_editor_app.py` (7) needs Streamlit.

## 11. SPL interop and the PocketFlow corpus

Needs SPL.py importable.

```bash
graf export-spl cookbook/lifted_tool/lifted_tool.graph.yaml > /tmp/verify/t.spl     # CREATE TOOL_API + WORKFLOW
pytest tests/test_export_spl.py tests/test_lifted_graph.py tests/test_lifted_tool.py tests/test_lifted_loops.py -q
pytest tests/test_pocketflow_corpus.py -q      # 94: all 83 PocketFlow workflows lift and validate, plus the 3 samples run
```

The corpus test finds SPL.py next to this repo or via `SPL_PY_PATH`. Samples in `cookbook/pocketflow/`: `majority_vote` and `debate` replay from cassettes, `text_transformer` runs with no model (its log ends with `[exit] Session ended.`; it opens with one empty round because the source recipe's 1-based `list_get` meets a counter from 0).

Survey of the whole SPL.py corpus (265 files at the start, 266 now of 274 workflows) is a throwaway script, not shipped; to repeat it, loop `spl_to_graph` and `check` over `SPL.py/cookbook` and `cookbook-pocketflow`. The 8 files that do not lift are not lifter faults (see the build status in `graflang-design.md`).

In SPL.py: `python -m pytest tests/test_spl2graph.py -q` gives 19 passed, including the round trip to `.spl` (a fixed point for lifted graphs).

## 12. Real-LLM checks

Always with a budget, always with a timeout, after an offline run. A small bindings file:

```yaml
# budget.bind.yaml
limits: {max_llm_calls: 12, max_steps: 300}
```

```bash
timeout 300 graf run cookbook/self_refine/self_refine.graph.yaml --llm claude_cli:claude-sonnet-5-5 --bind budget.bind.yaml --param topic="why ducks float" --no-output --no-log
timeout 300 graf run cookbook/parts_demo/parts_demo.graph.yaml --llm claude_cli:claude-sonnet-5-5 --bind budget.bind.yaml --param topic=tides --no-output --no-log     # 3 calls
timeout 300 graf run cookbook/pocketflow/majority_vote.graph.yaml --llm claude_cli:claude-sonnet-5-5 --bind budget.bind.yaml --no-output --no-log                     # 3 calls, answer 36
pytest -m llm -q                                                                                                                                                      # the 8 real tests
```

Summary line to expect after a real run: `N steps · M LLM calls, X tokens in / Y out · slowest: <node> <s>s`. `claude_cli` reports tokens but not cost.

Do **not** run `017_judge` from the PocketFlow set unattended: the lifter skips its `RETURN` inside a `WHILE`, so it does not stop on a pass (see section 13).

## 13. Known failures and limits

| Item | What you will see | Status |
|---|---|---|
| 7 Cedar compiler tests | `test_cedar_compiler` (6), `test_policy_slicer` (1) fail | known, `grafc/cedar` left alone |
| `RETURN` inside `WHILE` | the lifter warns `COMMIT inside a WHILE body was skipped`; the lifted loop runs until `max_steps` (`017_judge`) | open lifter gap |
| Container sandbox | stub-tested only; real-daemon test skipped without Docker | verify on a machine with Docker |
| Kernel and plain subprocess confinement | files and network not confined; kernel inherits the environment | by design, pinned as KNOWN tests |
| `max_cost_usd` | stops at the second call with `reports no cost` on `claude_cli` | by design; use `max_llm_calls` |
| Editor | no drag-to-connect; compact and `elaborate:` files are edited as text | by decision |
| `mcp` and WASM executors | not built | out of scope for now |
| `chain_of_thought` from PocketFlow (`014_thinking`) | the model declines the "reveal your reasoning" prompt | not a graflang fault |
| `ts_verify` | needs Node 22.18+; 11 tests skip or pass accordingly | environment |
| README claims | Rust compilation (`graf compile`) is a stub; Cedar compiler is experimental | README is partly aspirational |

## 14. If something does not behave

- `ModuleNotFoundError: zinet` → you are using the system Python; use the `graf` env.
- `kernel` SOLVE hangs or errors → `pip install -e ".[kernel]"`; the first kernel call takes a few seconds.
- A real run seems stuck → it may be a loop; Ctrl-C, then rerun with `--adapter mock` and read the step count, and use a `max_llm_calls` budget.
- `graf run` writes into the repo → results go to `<graph folder>/output/`; pass `--output-dir /tmp/...` or `--no-output`. `cookbook/*/output/` is ignored by git.
- A cassette replay fails with `no recording` → the prompt or model changed; re-record with `--record` (small budget).
- Logs: `~/.graflang/logs/<name>-<adapter>-<time>.log` and `.jsonl`; use `--log-level debug` for every node firing.
- To see what a compact, parts or elaborate file becomes: `graf expand FILE`.
- Design rules that every behaviour above rests on are in `graflang-semantics.md` (R1 to R14); the full feature list and the open items are in `graflang-design.md` (build status and Appendix B); user-level documentation is `docs/GUIDE/USER-GUIDE.md`.
