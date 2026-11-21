# Graph-Lang core semantics (v0, as implemented)

Date: 2026-11-21

What a graph means, independent of how `runtime.py` is written. Each rule R1 to R10 has a test in `tests/test_semantics.py`; the checks S2 and S3 in `graf validate` and `MUTATE` enforce the guarantees in section 3. Rules marked **accident** describe today's behaviour and are pinned so any change is deliberate.

## 1. Model

A workflow is a set of **nodes** with named **ports**, and two kinds of **edges** between ports:

- `triggers`: control. A token travels from a control port (`complete`, `pass`, `exit`, ...) to a `trigger` port.
- `binds`: data. It links an `out_*` port to an `in_*` port. It never causes a node to run.

The edge list is a **set**: its order means nothing. A run starts at the `INPUT` node, which writes the workflow inputs to its `out_*` ports and emits a token; it does not count as a firing.

## 2. Rules

- **R1 Firing.** A node fires when a token reaches its `trigger` port. A node nothing triggers never fires.
- **R2 Emission.** After firing, a node sends a token over the `triggers` edges that leave the control port it chose: `_route` if the executor set one, else every control port for a `FORK`, else the first of `complete`, `exit`, `entry`. A node picks one port per firing unless it is a `FORK`.
- **R3 Routing.** `_route` must be one of the node's ports; otherwise the run fails.
- **R4 Join.** A `JOIN` fires once, when a token has arrived over every one of its incoming `triggers` edges, then resets.
- **R5 Reading.** A firing node reads each `in_*` port as the value most recently written by any `binds` source of that port, by write order (a logical clock), never by edge order.
- **R6 Persistence (accident).** A written value stays on its port until overwritten, so a later reader can see a value from an earlier activation. There is no per-activation versioning.
- **R7 Missing input.** An `in_*` port nothing has written is absent from the node's inputs; it is not an error. Inside a LOOP body an unbound port falls back to the loop's input of that name, then to a loop-state variable.
- **R8 Repetition.** A node may fire many times; a back edge is a loop. `max_steps` bounds the run (`RunLimitExceeded`).
- **R9 LOOP.** The condition (and `max_iterations`) is checked before each iteration, so it can run zero times. A LOOP ends by routing to `exit`.
- **R15 Input map.** A node's `config.phases.pre.map` (`{in_port: expression}`) recomputes those inputs after the defaults and `require` are applied: each expression is the safe expression language over the node's in_* values as they were before any map ran, and its result replaces that port's value. A `map:` written on a `binds` edge (long form, beside `type:`) is moved into the target node's `pre.map` when the graph loads (`edgemap.py`, called from `flatten_parts`, so the runtime, `graf validate` and `graf expand` all see the node form); `graf validate` refuses a map on a `triggers` edge, on a port with several writers (the node cannot tell which edge wrote the value), on a port already mapped, on a name that is not an in_* port, or on a LOOP, BATCH or MUTATE node (they do not run phases). Tests: `tests/test_pre_map.py`.
- **R10a State.** A LOOP's loop-carried values are declared under `state:` (`name: {from: node.out_port | [ports], init: value, type: T}`). A value starts as the LOOP's input `in_<name>` when bound, else `init`, else absent. An iteration that writes it replaces it (with several ports, the one written last); one that does not leaves it. A body `in_<name>` with no `binds` edge reads it, and so does a condition (`@name`). The LOOP's `out_<name>` is the final value. Nothing else crosses from one iteration to the next. `collect` and `fired` outputs are results only: a body cannot read them (`graf validate` refuses it). `outputs: {name: {from: ...}}` still runs, as a state variable, but `graf validate` warns: write it under `state:`.
- **R10 Iteration scope.** Each iteration runs the body in a fresh copy: body values are not visible in the next iteration except through the LOOP's declared `outputs` (`from`, `collect`, `fired`). A `from` output is loop state: it starts as the LOOP's input of the same name, an iteration that writes it on no branch leaves it unchanged, and an unbound body `in_X` reads that state before the LOOP's own `in_X`. `from` may list several ports (a variable set on exclusive branches); the one written last wins.
- **R11 Failure.** An exception in any node ends the run. The only graceful paths are `SOLVE ... on_error: route` and E1's planned error routes.
- **R12 Mutation.** A `MUTATE` applies one delta per firing, only if it passes: parse, schema, well-formedness, the code-key refusal, the safety-layer refusal, the Cedar policy, the mutation budget, and the invariants of section 3. Otherwise it routes to `rejected` and nothing changes.
- **R13 Concurrency (opt-in).** With one worker (the default) nodes fire one at a time in token order, as above. With `--workers N` (or `limits.concurrency`) the tokens waiting together form a wave: GENERATE nodes and slow SOLVE nodes (`subprocess` backend, `procedure_ref`) in it run on a thread pool and read the values from before the wave started; every other node runs in token order on its turn. Results are written and routed strictly in token order, so the outcome does not depend on which call finishes first. A node released in the same wave as the node it reads from, with nothing ordering them, sees the earlier value (R6 again); `graf validate` reports unordered writers of one port as a race.
- **R14 JOIN as fan-in.** A `JOIN` with `in_*` ports and one `out_*` port bundles those inputs into an object keyed by the port names; a reader takes a field with `@in_args.name`.

## 3. Guarantees `graf validate` gives, and mutations must keep

For the loaded graph and for every graph a `MUTATE` produces:

1. **Guarded risky nodes.** A risky node (`EMIT`, `QUERY`, or `risky: true`) is reachable only through a `GUARD`'s `allow` port, and not after a `deny`.
2. **No race.** Two nodes that write the same input port must be ordered (one reaches the other along `triggers` edges) or exclusive (they hang off different control ports of one non-`FORK` node). Otherwise the port holds whichever ran last, which the program does not specify.
3. **No JOIN deadlock.** A `JOIN` is never fed by two sources of which at most one can run.

A delta that adds any error to this list is rejected. The safety layer (`GUARD` and `MUTATE` nodes, the `risky` flag) cannot be removed or edited by a delta.

## 3c. Elaboration

An `expand:` block, like a part use, has no runtime semantics: it is rewritten into SUBGRAPH nodes, a FORK over the roots, a JOIN before each node with several predecessors, and a final JOIN that gathers results. The things' graph must be acyclic. Ordering exists only where the things' graph has an edge (ConceptBook question: a required order is an edge).

## 3b. Persistent self-revision in a LOOP

`persist_mutations: true` on a LOOP: after an iteration whose body was mutated, the mutated body (nodes and edges) replaces the written body for the following iterations. The invariants of section 3 were checked on every delta, so they hold on the carried body. Off by default, which is rule R10.

## 3a. Named subgraphs

A `SUBGRAPH` node (a *use* of a part listed under `resources.parts`) has no runtime semantics of its own: before anything runs, `load_graph` replaces it by a copy of the part's nodes (ids `<use>__<node>`), wiring the part's INPUT and OUTPUT into direct edges. Every rule above therefore applies to the expanded graph, and two uses of one part are two independent copies with separate state.

## 3d. The interface of a composite

What a level sees of a part (`SUBGRAPH` use) is its interface, and nothing else:

- **Ports.** `workflow.inputs` and `workflow.outputs` (name, type, default, description) become the use's `in_*` and `out_*` ports; `trigger` and `complete` are fixed. `workflow.description` is a one-line statement of what it does (`graf parts`, Browse).
- **Error exits.** `workflow.errors: [{name, description}]` declares named ways out other than `complete`. Each is a control port of the use; inside the part an `OUTPUT` node with `config: {exit: name}` ends it, and a token reaching it leaves the use by that port. `complete` fires only from OUTPUT nodes with no `exit`. An error may carry an optional `code` (letters, digits, `_ . -`, starting with a letter) that names one cause: unique within the part and across the different part files of one graph (one part used twice is one meaning; the use path tells the copies apart). Every code must be defined once in the catalogue `graflang.errors.yaml` (`code`, `description`, optional `cause`, `remedy`): the file shipped in the package plus, optionally, one beside the top graph; a code defined in both, or twice, or not at all, is refused. When a token leaves a part by an error exit the run logs `part.error` (use, part, error name, code, and the catalogue's description and remedy); `graf errors [CODE]` prints the entries. `graf validate` refuses a use port that is none of these, an `exit` that is not declared, and a declared error that no OUTPUT ends.
- **Neighbour rule.** An edge in a graph may end at a use's ports, never at a node inside it (`first__rewrite`, the name the node gets once expanded). It is refused before expansion with a message naming the composite; after expansion the node exists and the edge would pass every other check.

## 4. Known gaps, decided in the roadmap

- R6 stale reads and the single-store data model: E5 (explicit fan-in with `JOIN`, merge rules).
- R11 failure as abort: E1 (retry, fallback, error routes).
- FORK branches run one after another unless concurrent mode is on (R13); BATCH over a list is the remaining E5 item.
- Back edges and LOOP bodies behave differently (shared store versus a fresh copy per iteration); their interaction is unspecified beyond R8 and R10.

## 5. Under consideration: the dual view of y = f(x) (an idea, not a rule)

Nothing here is implemented or tested; it is written down so it can be thought through. Recorded 2026-11-21, from the owner's own framing.

**The duality.** Take `y = f(x)`. It can be drawn two ways:

- **f as an edge.** x and y are nodes (values, states), and f is the arrow between them: a relationship, function, mapping.
- **f as a node.** f is a box, and x (the input) and y (the output) are the wires into and out of it.

The owner's words: "if we treat x, y as nodes, then f represents edge/relationship/function/mapping, but f could represent node too, where x is the input, and y is output, I see the duality in f."

**Where GraphLang is today.** It is the second view. Nodes are steps (GENERATE, SOLVE, EVALUATE, ...), and `binds` edges carry values between them (section 1). A composite (section 3d) is an `f` whose body is another graph with the same inputs and outputs, which is the "f is a node" view applied level by level.

**What the other view would be.** Values become the nodes (a workflow input, a port, a context key) and the steps that make one from another become the arrows: `spec --analyze--> analysis --write--> code`. It is the same graph read from the other side, so it needs no new semantics, only a second picture (and perhaps a second listing in `graf describe`).

**Why it might help** (to be tested against real recipes before believing it):

- Scoped context (`graflang-layers.md`, section 4) is about which keys a level can see; the value-centred view shows that directly.
- Troubleshooting: the journey of one value reads separately from the control flow.
- Recursion: `f` appearing inside its own body is easier to say when `f` is also an arrow.

**Open questions.**

1. Is it a view only (a `graf vis` engine or a `--view values` option), or does it change how a graph is written or checked?
2. What is a "value node" when a step has several outputs, or when a value is overwritten (R6: the last writer wins)? Is each write a new node, or the port?
3. Control (`triggers`) has no counterpart in the value view; does it stay as a second kind of arrow, or is it left out?
4. Does a composite appear as one arrow with its interface at its ends, and how does `--depth` open it?

### 5a. Where an edge's f would live (a thought, 2026-11-21)

Today an edge has no transformation (`triggers` move a token, `binds` copy a value); the compute is inside a node, written as code, an
expression or a prompt. In the "f as an edge" view the compute is written on the arrow instead. The owner's observation: the edge's
logic would be **injected into a node**, not make a new kind of thing, and it need not be built right away.

**Built 2026-11-21 (R15, the simple form below):** `phases.pre.map` and the edge `map:` that is moved into it. Not built: a `triggers` map, a label on the arrow in `graf vis`, a line in `graf describe`, compact-form syntax (`in:`), and keeping the edge's map for display after loading. The shape that was decided:

- **Logical form.** An optional pure `map:` on a `binds` edge, evaluated by the safe expression language (`expr.py`, whitelisted functions, no
  side effects): `a.answer -> b.query  map: "strip(@x)"`. It reads as f on the arrow, and with dict-valued data (the kwargs idea) every such
  edge is unary, so one source value in, one target value out.
- **Physical form.** At load the map is injected into the consuming node's `phases.pre` (section 3 of `lifecycle.py`: `pre` today has only
  `require` and `defaults`; a `map: {in_query: "strip(@in_x)"}` key would be the new part). The runtime still sees f inside a node, so R1 to R14
  and the guarantees of section 3 do not change. This is the same logical-to-physical split as parts (`graflang-layers.md`, section 2).
- **Limits.** Injection on the target side needs one writer per mapped port: `pre` runs after R5 has picked the last writer, so it no
  longer knows which edge wrote the value; `graf validate` would refuse a map on a port with two writers. A map must be pure and cheap: a
  model call, a program or an EMIT stays a node (cost, retries, `risky`, Cedar, the race and deadlock checks all attach to nodes). A step with
  several inputs is not an edge (it needs a JOIN, R14).
- **Rejected for now:** inserting a SOLVE node per map (works, but clutters the physical graph and shows up in `--depth` and traces).

Open: whether the map belongs on `binds` only or also on `triggers` (a trigger that carries a condition is already `phases.post.route`);
what `graf vis` shows for it (a label on the arrow); how it appears in `graf describe`.
