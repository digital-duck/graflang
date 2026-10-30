# Graph-Lang core semantics (v0, as implemented)

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
- **R10 Iteration scope.** Each iteration runs the body in a fresh copy: body values are not visible in the next iteration except through the LOOP's declared `outputs` (`from`, `collect`, `fired`).
- **R11 Failure.** An exception in any node ends the run. The only graceful paths are `SOLVE ... on_error: route` and E1's planned error routes.
- **R12 Mutation.** A `MUTATE` applies one delta per firing, only if it passes: parse, schema, well-formedness, the code-key refusal, the safety-layer refusal, the Cedar policy, the mutation budget, and the invariants of section 3. Otherwise it routes to `rejected` and nothing changes.

## 3. Guarantees `graf validate` gives, and mutations must keep

For the loaded graph and for every graph a `MUTATE` produces:

1. **Guarded risky nodes.** A risky node (`EMIT`, `QUERY`, or `risky: true`) is reachable only through a `GUARD`'s `allow` port, and not after a `deny`.
2. **No race.** Two nodes that write the same input port must be ordered (one reaches the other along `triggers` edges) or exclusive (they hang off different control ports of one non-`FORK` node). Otherwise the port holds whichever ran last, which the program does not specify.
3. **No JOIN deadlock.** A `JOIN` is never fed by two sources of which at most one can run.

A delta that adds any error to this list is rejected. The safety layer (`GUARD` and `MUTATE` nodes, the `risky` flag) cannot be removed or edited by a delta.

## 4. Known gaps, decided in the roadmap

- R6 stale reads and the single-store data model: E5 (explicit fan-in with `JOIN`, merge rules).
- R11 failure as abort: E1 (retry, fallback, error routes).
- FORK branches run one after another, not concurrently: E5.
- Back edges and LOOP bodies behave differently (shared store versus a fresh copy per iteration); their interaction is unspecified beyond R8 and R10.
