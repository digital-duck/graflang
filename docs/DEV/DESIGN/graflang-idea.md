# Idea: outcome-driven workflows (the MonteFlow vision)

Status: **placeholder, not built here.** A candidate roadmap item, recorded 2026-11-02 from the owner's earlier plan (`/home/gongai/projects/digital-duck/monteflow`, a package skeleton: "stochastic workflow simulation engine with transition matrices", built on MarkoFlow). The owner has a prototype on another machine; it is not in this repo and is not reviewed here. The plan is to pick this up **once GraphLang is stable**, with that prototype as the starting point. Nothing below is implemented in GraphLang, and no result is claimed.

**The aim in one line:** a workflow whose **set of states is fixed** (the nodes of the graph) while **how it moves between them is probabilistic**: a Markov chain over a known, finite state space. The behaviour is bound because the states are enumerable and nothing outside them can happen; it is unpredictable because which transition is taken on a given run is drawn from a distribution (set by the model's answers), not fixed by the file.

## The idea

A workflow step that calls a model does not have one outcome. An `EVALUATE` or `ASSERT` sends the token to `pass` or `fail`; a `LOOP` exits early or runs to its cap; a `GUARD` allows or denies. Each of these is a choice among a few next nodes, and over many runs it has a frequency. Treat the graph as a **Markov chain** over its nodes: the edges out of a node carry probabilities, estimated from past runs. Then a workflow can be *driven by outcome probability*:

- **Predict before running:** the chance a run reaches each `OUTPUT` (`released`, `escalated`), the expected number of model calls, tokens and cost, and the spread, from the transition matrix, without spending a call.
- **Simulate:** sample paths through the graph with the estimated probabilities (a Monte Carlo run with no model), to size a budget (`max_llm_calls`) or find a retry cap that is rarely hit.
- **Revise the graph from the numbers:** because the workflow is data, a `MUTATE` delta can act on what the chain shows (a retry edge that almost never helps is removed or capped; a branch that fails 60% of the time gets a cheaper first step). This is the part only a graph can do: code cannot be revised from its own statistics in a checkable way.

Bound here means the **state space is closed**: every state is a node you can list, every transition is an edge you can list, and a run cannot enter anything else. Unpredictable means the **transition out of a state is a distribution** (for example `fail` 0.3, `pass` 0.7), so two runs of the same graph on the same input may differ. Together they give a finite chain that can be analysed exactly (reachability, absorbing states such as `released` and `escalated`, expected visits) while the workflow stays free to adapt to what the model says. This is a different bound from the budget limits (`max_steps`, `max_llm_calls`, cost), which cap one run in time and money; those still apply on top.

An analogy from the owner: people all work, play, study, rest and dream (the same small set of states), yet every person is unique, because each moves between those states with different habits (different transition probabilities). In the same way, many agents or runs can share one graph and differ only in their transition weights. The weights are then what characterises a run, a model or a user, and they can be estimated from logs and compared (is `claude-haiku-5-5` more likely than `claude-sonnet-5-5` to take the retry edge on this graph?). This is an analogy for intuition, not a claim about people or models.

Hypotheses from the same analogy (to test, not to assume): a weaker model may settle into a steady state, meaning a retry loop it rarely leaves or an absorbing state such as `escalated`, which shows in the chain as a high self-transition or absorption probability; a stronger model may reach paths the weaker one almost never takes. Two cautions. With the state set fixed, "novel behaviour" can only mean a different distribution over existing paths (rare paths becoming likelier); a genuinely new state needs a `MUTATE` that adds one, which the tension below governs. And a stronger model may look *less* varied, not more, because it passes the gate on the first try and the chain collapses onto the short path. The evolution picture (variation, then selection) maps onto sampling or mutation deltas as the variation and `EVALUATE`/`GUARD` as the selection; whether anything like adaptation over many runs happens is exactly what the estimates would show.

One tension to settle: a `MUTATE` changes the graph, so it changes the state space. Either the chain is re-estimated after each accepted revision, or a mutation is only allowed to keep the state set (rewire or reweight, not add nodes), which would make the fixed-state guarantee hold across revisions too. The second is stricter and may be the safer default.

## Why GraphLang is a good host

| Needed | Already in GraphLang |
|---|---|
| a discrete state space | nodes and ports; token-passing dataflow |
| the observed choices | the `route` of every `node.done` event in the run log (`route=fail`), and per-node firing counts in `summary.json` |
| many recorded runs | `output/<graph>-<model>-<time>/` folders (`run.json`, `summary.json`, `result.json`, `nodes/`), now also written by the editor's Run tab and read back by its Logs tab |
| cheap repeats | record and replay of model answers (`--record`, `--replay`), the `mock` adapter |
| a safe way to change the graph | `MUTATE` deltas, validated (schema, Cedar, budget, invariants on a trial copy) |
| bounds | `--max-steps`, `limits.max_llm_calls`, cost and wall-time limits |

## Sketch

1. **Estimate.** Read the JSONL logs (or run folders) of a graph; count, per node, how often each route was taken; add a prior so unseen routes keep a small probability. Output a transition table: `node.port -> next node: p`, with the count behind each number.
2. **Analyse.** From the table: absorption probabilities at each `OUTPUT`, expected visits per node, expected calls and cost (visits times the measured per-node tokens), and a cap check ("a loop of 3 is exceeded in about p of runs").
3. **Simulate.** Sample N paths; report the distribution of calls, cost and result. No model is called.
4. **Propose.** Suggest (never apply on its own) `MUTATE` deltas from the table, shown as a diff the owner accepts, as the app's chat already does for edits.

A command might read `graf chain GRAPH [--logs DIR]` (the table, the absorption probabilities, an expected cost) and `graf chain GRAPH --simulate N`. Whether it lives in this repo or in `monteflow` (GraphLang reading the table through an optional import, as `procedure_ref` reads SPL.py) is open; the second keeps GraphLang free of the statistics.

## Honest limits

- **The Markov assumption is a model, not a fact.** A node's outcome often depends on more than the node: the content of the draft, the loop counter, the input. The probability of `fail` on the third retry is not the probability on the first. Likely remedy: a state that is the node plus the loop cycle (or a small bucket of the inputs), checked against the data; where it does not fit, the numbers must say so.
- **Estimates need runs, and real runs cost money.** A handful of runs gives wide uncertainty. Report counts and intervals, not bare probabilities; use replay and the mock for the cheap part and keep real-model runs capped, as always.
- **Inputs shift the probabilities.** A table from one kind of document does not carry to another. Keep it per graph and per model (the output folder name already carries both).
- **Revising from the numbers can chase noise.** Any proposed change should be tested by a fresh batch of runs before it is believed; the claim "this change helps" is an experiment, and none exists yet.
- **No claim about accuracy or savings** until such an experiment is run (see the paper draft's list of missing work).

## Roadmap placement

When picked up (after GraphLang is stable, starting from the prototype on the other machine), a small, checkable first step: **estimate and report** (items 1 and 2 above) from logs that already exist, on `code_pipeline` and `compliance_audit`, where the routes are known and the answers can be compared with the raw counts. Simulation (3) follows if the estimates are stable. Proposing graph changes (4) is last, and only after the first three show the table predicts a held-out batch of runs. It connects to the Logs tab (a "chain" view of a graph's past runs) and to the speculative-outlook slide's "safer self-editing agents".

Open questions: whether a revision may add states or only change transitions (above); the state definition (node, node plus cycle, node plus a feature of the input); whether `GENERATE` outcomes that are not routes (the quality of a text) can enter at all, or only the routes of `EVALUATE`, `ASSERT`, `GUARD` and `LOOP`; where the code lives (this repo or `monteflow`); and the MonteFlow naming and its "path" vocabulary, which should be written in plain words (probability of a path) here.

---

# What GraphLang could borrow from PocketFlow

Against the backdrop of "Vibe Coding", Zack Huang's "Agentic Coding" blog at https://pocketflow.substack.com/p/agentic-coding-the-most-fun-way-to is quite good and resonates with me. GraphLang is doing what he preaches. Huang created PocketFlow.

Review of `~/projects/wgong/Pocketflow/PocketFlow` (2026-11-03; the core `pocketflow/__init__.py` is about 100 lines, MIT, no dependencies; 70-odd `cookbook/` examples; `docs/` with the core abstractions, design patterns and an "Agentic Coding" guide). This is a reading of that tree, not a benchmark, and nothing below is built.

## What PocketFlow is, in four ideas

1. **A node has three steps:** `prep(shared)` reads the shared store, `exec(prep_res)` computes (and must not touch `shared`), `post(shared, prep_res, exec_res)` writes back and returns an **action string**. Reading, computing and writing are kept apart on purpose.
2. **A flow is nodes joined by labelled actions:** `a - "approved" >> b`. The graph is built in Python; the next node is chosen by the action `post` returns.
3. **A flow is itself a node,** so flows nest. `BatchNode` / `BatchFlow` run a node or a whole flow once per item or per parameter set; async and parallel variants exist.
4. **Retries are two numbers:** `max_retries` and `wait`, plus an `exec_fallback(prep_res, exc)` hook.

## Where GraphLang already has it

| PocketFlow | GraphLang today |
|---|---|
| `prep` / `exec` / `post`, retries, `exec_fallback` | `config.phases` (`pre -> exec -> post`: timeout, retry, fallback, `out_schema`, routing on the result), `RECOVER` |
| action-labelled edges | ports (`pass` / `fail`, `complete`) and `route` on EVALUATE |
| a flow as a node | parts (`resources.parts`, a `SUBGRAPH`/`use` node flattened by `load_graph`) |
| `BatchNode`, parallel batch | `BATCH`, `FORK`/`JOIN`, `--workers` (opt-in concurrent waves) |
| majority vote, debate, map-reduce, supervisor, judge loop | `cookbook/pocketflow/` (majority_vote, debate lifted from SPL.py's `cookbook-pocketflow`), `LOOP` with `EVALUATE`, `expand:` |

So most of the engine is covered, and in places stricter: GraphLang's edges and data are declared and checked before a run; PocketFlow's wiring is Python and its `shared` dict is untyped.

## What is worth borrowing

Ordered by how cheaply they could be tried. None is a commitment.

1. **The three-step discipline as a documented rule for nodes** ("`exec` must not read or write shared state"). GraphLang's phases already allow it; what PocketFlow adds is the stated reason (separate data access from computation, which makes `exec` safe to retry) and a clear note that retried steps must be idempotent. Cheap: a paragraph in the user guide and a `graf validate` hint for a retried node that has side effects (a `RUN` or `EMIT`).
2. **A pattern catalogue with a "which pattern fits" page.** PocketFlow's `docs/design_pattern/` (agent, map-reduce, RAG, structured output, workflow, multi-agent) is what newcomers read first. GraphLang has recipes but no page that names the patterns and points at one recipe each. Cheap, high value for the talk and the app's Welcome page.
3. **Cookbook patterns GraphLang has no recipe for yet,** each a small acceptance test of the language:
   - **Agent (decide, act, observe loop)** and **TAO (thought, action, observation):** a `LOOP` with an `EVALUATE` on the model's chosen action; the first real use of `QUERY`/`OBSERVE` below.
   - **Supervisor over an unreliable agent,** and **guardrail** (reject off-topic input before the model sees it): a `GUARD` or `ASSERT` at the front; fits the safety story.
   - **Human in the loop** (CLI, web): GraphLang's runtime already reads a `human_approval` flag in the guard path, but there is no node that waits for a person and no recipe. Needs a design (a blocking input node, a timeout, a default on no answer, and the checkpoint/resume mechanism to park a run).
   - **Self-healing** (compile or validate an output, feed the error back, retry): `cookbook/ts_verify` is the same shape; a Mermaid or YAML version would be a second, cheap example.
   - **Chat with memory** (a window of recent turns plus retrieved older ones): uses `CONTEXT`; tests whether state in a long run is expressible.
   - **Heartbeat / always-on monitor:** a run that polls and acts on a schedule. GraphLang's runs are one-shot; a scheduler or a `graf watch` wrapper would be new, and a place where the Markov view (below) would apply.
4. **Observability hooks.** PocketFlow has a tracing cookbook (a decorator that traces `prep`, `exec` and `post` of every node into Langfuse). GraphLang already writes JSONL events per node and per model call; an exporter from that log to OpenTelemetry or Langfuse would give a trace view without changing the runtime, and is the natural first user of an `OBSERVE` node (data out of the run without blocking it).
5. **Streaming and long-running service use** (LLM streaming, FastAPI background tasks, websockets). GraphLang has no streaming path. Only worth doing when an app needs it.
6. **MCP and agent skills as tools.** PocketFlow shows MCP tool calling and "skills" (markdown instruction files routed to at runtime). GraphLang's design already names an `mcp` executor for `RUN` and has prompt resources; a skills recipe would be a small test of routing among prompt files.
7. **The agentic-coding guide** (humans own requirements and the flow, the agent fills in utilities, data and nodes; start small; "if a human can't specify the flow, an agent can't automate it"). This matches how `graf create`, `graf describe` and the Create page are meant to be used; worth quoting as the process behind them, and its step table (requirements, flow, utilities, data, node, implementation, optimisation, reliability) could be a checklist in the Create page's readme.

[WEN] let us build 1-7 except 6
Let us add these 3 new node types - "QUERY, OBSERVE and EMIT", I like them

**Built 2026-11-03 (overnight, offline suite: 1132 passed; the recipes were also tried for real with `claude_cli:claude-haiku-5-5`, about 20 short calls in all, each run capped by `limits.max_llm_calls`):**

| Item | What was built | Where |
|---|---|---|
| New node types | `QUERY` (read a file in the graph's folder: text/JSON/YAML/lines, `tail`, `default`), `EMIT` (file, stdout, webhook, e-mail to fixed recipients; a dry run only reports) and `OBSERVE` (log + `observations.jsonl`, never fails a run). `QUERY` and `EMIT` stay behind a `GUARD`; their path and target keys are `CODE_KEYS`; paths are confined to the graph's folder | `grafr/outside.py`, `grafr/nodes/outside.py`, `tests/test_outside.py` (25 tests); user guide section "QUERY, EMIT and OBSERVE" |
| 1. Three-step rule | documented ("How a node is built: the three steps"); `graf validate` warns when a retried `EMIT` or `RUN` may repeat its effect | user guide; `topology.py` |
| 2. Pattern catalogue | `docs/GUIDE/PATTERNS.md`: which pattern fits, a recipe for each, how to choose | linked from the tutorial and SETUP |
| 3. Recipes | `agent_notes` (decide, act, observe), `guardrail`, `supervisor`, `self_heal`, `notes_digest` (the three new nodes), `chat_memory` (a file as memory). Not built: heartbeat as a recipe (`graf watch` is the tool; a useful heartbeat needs state between runs, which is `chat_memory`'s file trick), human in the loop (design note only, `graflang-hitl.md`) | `cookbook/`, `tests/test_patterns_recipes.py` (15 tests) |
| 4. Observability | `graf trace`: a run's JSONL log as a text timeline or OpenTelemetry OTLP/JSON (works on the existing logs; no runtime change) | `grafr/trace.py`, `tests/test_trace.py` |
| 5. Streaming | `graf run --stream` and the runtime's `on_node` callback (each node's result as it finishes). **Node by node, not token by token:** dd-llm has no streaming API | `runtime.py`, `grafr/cli.py` |
| 5. Long-running | `graf watch`: run a graph every N seconds, one process per run, with a run count and a failure cap | `grafr/cli.py` |
| 6. MCP and skills | skipped, as asked | |
| 7. Agentic-coding checklist | the step table (requirements to reliability) mapped onto `graf create`, `describe`, the editor and the Logs tab | end of `PATTERNS.md` |

Things found on the way: a `LOOP` whose body holds a risky node is itself risky, so the guard must sit in front of the loop, not inside it (`agent_notes`); a literal default on a loop's `in:` is not seen inside the body, so state must be seeded from a step; a loop that hits its cap returns `None` for an output it never wrote, so a recipe should check for that after the loop (`agent_notes`, `supervisor`, `self_heal` do).


## What not to borrow


- **Smallness as a goal.** PocketFlow's appeal is 100 lines and no dependencies; GraphLang's value is the checks, policy and limits, which cost code. Do not trade them for a shorter core.
- **Graph building by operator overloading in Python** (`>>`, `- "action" >>`). It hides the graph in code, the problem GraphLang exists to remove.
- **An untyped shared dict.** Typed ports and declared inputs are the point.

[WEN] agree

## Where to put it

Items 1 and 2 are documentation and a small validate rule, doable any time. Item 3 is a set of recipes that also exercise `QUERY`, `OBSERVE` and `EMIT` before they are built, so it fits next to that roadmap item. Item 4 is a small, separate tool (log to trace). Items 5 and 6 wait for an app that needs them. Human in the loop is the largest and most useful gap, and should get its own design note before any code.

---

# Composability: every recipe a building block

Recorded 2026-11-03 from the owner: *one big benefit of GraphLang could be composability; each recipe we build could become a building block that we later assemble as nodes themselves, like nature self-organising and assembling.* [WEN] pursue this vision.

## The idea

A recipe (a folder: a graph, its prompts, policies and a readme) already has an interface: the typed `workflow.inputs` and `workflow.outputs`. If any recipe can be dropped into another graph as a single node, then the library grows by assembly, not only by writing: a guarded support bot is `guardrail` then `agent_notes` then `supervisor`, each already tried and tested. Because a workflow is data, the assembly can be done by a person, by `graf create`, or, under policy, by a model through `MUTATE`. The picture is cells, tissues and organs: small parts with a clear boundary, combined into larger parts with the same kind of boundary, so the same checks apply at every level.

## What exists

- **Parts** (`grafr/parts.py`): a workflow file with one `INPUT` and one `OUTPUT`, listed under `resources.parts` and used as a `SUBGRAPH` node (compact `use:`). The use is checked against the part's interface (inputs, outputs, types), then **flattened in place** (ids `<use>__<node>`), so `graf validate`, the race check, the safety rules, `graf vis`, checkpoints and concurrency all see one ordinary graph. A part may use parts; cycles are an error; a part used twice is expanded twice.
- **`expand:`** applies one part to every item of a graph of things, and `BATCH` runs a body per item.
- **Recipes are searchable** (Browse, `recipe_index.py`) and already carry what a library entry needs: a readme, typed inputs and outputs, an estimated call count, and "runs programs" flags.

## What a probe found (2026-11-03)

I tried each new recipe as a part inside a one-node wrapper graph:

| Recipe | Result as a part | Why |
|---|---|---|
| `guardrail`, `supervisor`, `self_heal`, `agent_notes` | **refused:** "needs exactly one INPUT and one OUTPUT node, found 1 and 2" | each branch of the recipe ends in its own `OUTPUT` (the idiom for a branching workflow). Four of the six new recipes, and any recipe that branches at the end, cannot be a block |
| `chat_memory`, `notes_digest` | validate, but **paths would be wrong** | a `QUERY` / `EMIT` `file` in a part is read relative to the *using* graph's folder, not the part's (`parts.py` says so for any path in a part's nodes), so `output/memory.md` and `input/notes.md` would point at the wrong place; their `GUARD` and policy do carry over |

So the engine for composition is there, but two gaps stop most recipes from using it. Neither is deep.

## What is missing, in order of how much it blocks

1. **A part with several exits.** Allow more than one `OUTPUT` node when they write the same declared outputs (the runtime already allows several writers to a workflow output, and only one branch fires). On expansion each exit becomes wires to the use node's `out_*` ports, and the use node's `complete` fires from whichever exit was reached. The race check must treat the exits as exclusive when they sit on exclusive branches (it already has the idea of exclusive ports). This unlocks every branching recipe.
2. **Part-relative paths.** Record on each expanded node the folder it came from, and resolve `QUERY` / `EMIT` / `RUN` paths (and `subprocess` commands and parsers) against that folder. Decide what a part may reach: the part's own folder by default; the parent can grant more (`allow_dirs`), and a part can never widen the parent's grant. This is also a security decision, so it needs a Cedar angle: composition must never give a part more reach than its user allowed.
3. **Refer to a recipe by name, not by relative path.** `parts: {guardrail: cookbook:guardrail}` resolved through the work area (`~/.graflang/cookbook`, `solvers`, `apps`), with a "Use as a part" button on the Browse page that writes the `resources.parts` entry and the `SUBGRAPH` node. Pin a version (a content hash, or a `version:` in the workflow header) so a recipe can change without breaking the graphs built on it; `graf validate` reports a part that changed since it was pinned.
4. **Declared capabilities and cost at the boundary.** A recipe's header already implies what it touches (files read and written, programs run, e-mail sent) and roughly what it costs (`graf describe` computes calls). Surface both on the use site and let the *parent's* `workflow.policy` forbid them ("no part may send e-mail", "at most 20 model calls in all"). Budgets compose by addition, and the sum is what the parent's limits must cover.
5. **Typed interfaces that mean something.** Today most ports are `TEXT`, so a composition that validates may still be nonsense. Cheap help: a short `description:` on each input and output (shown in Browse and by `graf describe`), examples in the readme, and optional `out_schema` on outputs so a part can promise a shape (`phases.post.out_schema` exists).
6. **Composites as the acceptance test.** Build two or three composites only from existing recipes (for example `guarded_support`: `guardrail` → `agent_notes` → `supervisor`), run them, and treat anything that needs editing a recipe to fit as a defect in the part interface, not in the recipe.
7. **Assembly by a model.** A `MUTATE` delta that adds a part node, chosen from a catalogue of recipes with declared interfaces, under the same rules as any delta (schema, Cedar, budget, invariants on a trial copy, and never adding a node that holds code keys). This is the "self-organising" end, and it connects to the Markov idea above: with each part a state, the chain over parts says which assemblies a model tends to choose and how they fare.

## Honest limits

- **Composition multiplies cost and failure modes.** Three recipes with three retry loops each are nine loops; the parent's limits must cover the sum, and a failure deep in a part has to be explained at the level the user reads (the trace and Logs tab should show the part as one span with children).
- **Flattening hides the boundary at run time.** That is why checks work (one flat graph), but the editor and the trace need to remember which nodes came from which part (the ids already carry it).
- **Text in, text out is weak typing.** The checker proves the wiring, not that the guardrail's output makes sense to the agent that follows it.
- **A library needs curation.** Search and versioning help; they do not decide which blocks are good. Recipes tried for real (the readmes say which) are the ones to build on.
- No result is claimed: nothing here has been shown to make workflows better or faster to build. The first test is item 6.

## Status (2026-11-04): steps 1 to 7 built

| Step | Built | Where |
|---|---|---|
| 1. A part with several exits | `_interface` takes one INPUT and one or more OUTPUT nodes; on expansion every exit becomes wires to the use node's `out_*` ports and `complete`; two exits that write one output from exclusive branches pass the race check | `grafr/parts.py`, `expand.py` |
| 2. Part-relative paths | a QUERY/EMIT `file` in a part is made absolute against the part's folder and the folder is added to `allow_dirs`, only by the expansion (a graph file cannot name it); an escaping path fails `graf validate`; a path from a port stays the user's | `grafr/parts.py`, `grafr/outside.py` |
| 6. Composites as the acceptance test | `cookbook/recipe_chain`: `guardrail` -> `agent_notes` -> `supervisor`, three parts, no recipe edited; scripted-model tests in `tests/test_composition.py` (and one real haiku run: plumbing worked, chain meaningless) | no interface defect found; the chain is semantically odd, so it proves the plumbing, not usefulness |
| 3. By name, pinned | `cookbook:name[@hash]` in `resources.parts` (`parts.named_part`, `folder_hash`); "Use as a part" on Browse | the hash covers the recipe's text files, not the models it runs against |
| 4. Capabilities and cost at the boundary | `grafr/partinfo.py`, `graf parts`, `workflow.parts_policy` {forbid, max_llm_calls} | cost is an upper bound; loops with an expression bound and procedures count as "n+" |
| 5. Meaningful interfaces | `description:` and `schema:` on workflow inputs/outputs; `schema` becomes `phases.post.out_schema` on the node that makes the output | `schema` is for JSON values; Cedar does not look at it |
| 7. Assembly by a model | MUTATE `add_part` with a `catalogue`; `cookbook/assembler`; `tests/test_assembly.py` | one real haiku run: it chose a recipe, the graph wired it in; it picked the wrong recipe for one of two questions |

All four recipes that were refused (`guardrail`, `supervisor`, `self_heal`, `agent_notes`) and the two with wrong paths (`chat_memory`, `notes_digest`) now work as parts, including a part inside a part (`tests/test_composition.py`, 10 tests; the offline suite is at 1142 passed). Two things surfaced and were fixed: a `LOOP`/`BATCH`/`MUTATE` ignored an input's default (so a part's optional input read by a loop was missing), and the principle for paths: *what ships with the recipe lives in the recipe's folder; what should follow the user (a memory file, an output folder) travels on an input.* The two recipes that held user state were changed to follow it. Not done: subprocess `command` and parser paths in a part are still read relative to the using graph; steps 3 to 7 below.

## Suggested first steps

Items 1 and 2 (a part with several exits; part-relative paths with a confinement rule), because they decide whether the existing recipes can be blocks at all and are small, checkable changes with tests. Then item 6 on the result. Items 3 to 5 follow once real composites show what the interface needs; item 7 waits for the library.
