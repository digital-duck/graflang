# graflang: Claude's working notes

Early-stage thoughts from the first design conversation. Nothing here is decided; these are proposals and open questions. Items marked **(user)** came from the repo owner, the rest are Claude's interpretation.

## Premise

- **(user)** graflang is a physics-inspired, graph-first, declarative, semantic, safe language, evolving from SPL.py (Structured Prompt Language, arXiv 2607.07727).
- **(user)** Theoretical foundation: **interaction nets** (Lafont, 1989-90).
- **(user)** Safety layer: **AWS Cedar** (authorization policy language).
- **(user)** Physics inspiration: fermion/boson parallels node/edge in graphs.
- **(user)** Implementation evolves from SPL.py.

## Background

### Interaction nets
- An agent of arity n has 1 principal port and n auxiliary ports.
- Computation happens only at **active pairs**: two agents joined at principal ports.
- At most one rewrite rule per agent pair. The RHS net has the same free-port interface as the LHS.
- One-step confluent, so redexes can fire in parallel without interference. Linear: each port has exactly one wire.
- Normal form = no active pairs.

### Cedar
- Policy = `permit`/`forbid` + scope (principal, action, resource) + optional condition.
- Default deny; explicit `forbid` beats `permit`; policy order is irrelevant.
- Supports RBAC and ABAC; formally verified implementation.

### SPL (prior work, paper read through the language and verifier-ladder sections only)
- Probabilistic verbs: `GENERATE`, `EVALUATE`, `WHILE`, `EXCEPTION` (LLM adapter).
- Deterministic verbs: `SOLVE`, `ASSERT` (out-of-process IPython kernel: SymPy/Sage/Lean, or `TOOL_API`).
- Single `@variable` store; `{@name}` interpolation is the "formalization boundary" where LLM text becomes a typed expression.
- `ASSERT ... OTHERWISE` gates progress; failure returns a status, retries or escalates up the verifier ladder (R1 SymPy, R2 Sage, R3 Lean).
- Model, adapter and kernel are invocation-time flags, never in the spec (DODA).
- The paper itself says SQL-style algebraic rewrites don't apply to `GENERATE`, so optimization must be workflow-level (principle P5, "optimizable IR").
- Not yet read: evaluation sections and appendices.

## Proposed mapping: SPL to interaction nets

| SPL | graflang (proposal) |
|---|---|
| `GENERATE` / `EVALUATE` | probabilistic agent; fires once on its active pair, sampled result bound to the output wire |
| `SOLVE` | deterministic agent (kernel call) |
| `ASSERT ... OTHERWISE` | gate agent with pass/fail output wires; the escalation ladder is a chain of gates |
| `{@var}` seam | typed wire between agents of different families; checkable at compile time instead of runtime |
| `CALL PARALLEL` | independent redexes; isolation comes from linearity instead of per-branch namespace copies |
| `WHILE` | needs an explicit termination rule or budget, since cycles in a net don't terminate by construction |
| `--adapter/--model/--kernel` | invocation-time binding of agent implementations (keeps DODA) |

Key idea: once a probabilistic agent has fired, its output is an ordinary value, so downstream reduction stays confluent given that value.

## Cedar integration (proposal)

- A redex fires only if Cedar permits it. Principal = user/agent identity, action = the rewrite rule or agent kind being applied, resource = the wires/data/tools involved.
- Possible policies: an LLM output may not reach a tool-call agent without an `ASSERT` gate in between; tool agents need explicit grants; budget limits as `forbid` conditions.
- Replaces SPL's `exec()`-in-restricted-namespace isolation for `CREATE TOOL_API` with explicit, auditable authorization.

## Fermion/boson analogy (interpretation, needs the owner's input)

- Fermions (Pauli exclusion) ~ nodes/agents: each port connects to exactly one wire, so ports are exclusive.
- Bosons (force carriers) ~ edges/wires: carry the interaction.
- Active pair = collision of two particles that transforms into new ones, with the interface conserved.
- Open: does the deterministic/probabilistic split follow the node/edge split, or cut across it? A conserved quantity on wires (budget, provenance flag) could make the analogy load-bearing.

## Open questions

1. Surface syntax: keep SPL verb names (`GENERATE`, `SOLVE`, `ASSERT`) or go graph-native?
2. How are effectful probabilistic agents modelled so reduction stays well-defined (fire-once, record the sample on the wire)?
3. Termination and cycles: iteration caps, budgets, or Cedar `forbid` limits?
4. Cedar entity model: what are principals and resources in a net?
5. Which interaction-net implementation strategy: a Python reducer evolved from SPL.py, or an existing runtime (e.g. HVM-style) as a backend?
6. What exactly is conserved, to give the physics inspiration teeth?

## Sources

- Interaction nets: <https://en.wikipedia.org/wiki/Interaction_nets>, <https://arxiv.org/pdf/1211.4102>, <https://ar5iv.labs.arxiv.org/html/1505.07164>
- Cedar: <https://aws.amazon.com/blogs/opensource/using-open-source-cedar-to-write-and-enforce-custom-authorization-policies/>, <https://onecloudplease.com/blog/cedar-a-new-policy-language>
- SPL: <https://arxiv.org/abs/2607.07727>; local draft `zinets/docs/publication/TMLR/SPL-for-Agentic-Workflow/paper-draft-v3.0.tex`

## Claude's take on Qwen

Feedback on the Qwen-drafted `README.md`, given before the Qwen-generated files were populated. Mirrors the gap tracker in `readme-design.md`. The README is a vision draft, so these are things to settle, not defects.

### 1. The interaction-net claim is the biggest risk
- The README names Lafont's interaction nets as the foundation, but the design shown is a state-machine/dataflow graph: typed nodes, `trigger`/`complete`/`pass`/`fail` ports, `LOOP` and `FORK`/`JOIN`. There are no agents with principal ports and no rewrite rules.
- "Strongly confluent" and "no race conditions" are properties of the formalism. A NetworkX executor gives neither by itself.
- Choose one framing:
  - (a) Interaction nets are the semantics: `grafr` is a real rewrite engine and `GENERATE`, `SOLVE`, etc. are agent types with rules.
  - (b) Interaction nets are inspiration: the language is a typed workflow graph and the confluence claims are dropped.
- Study interaction nets first (owner's plan), and hold the README's theory claims until then.

[WEN] will revisit after studying "Interaction Nets"

[CLAUDE] Agreed. Parked as gap #7; no README theory claims until then. When you are ready, the concrete question to answer is: what is the agent/rule table for `GENERATE`, `SOLVE`, `ASSERT`, `GUARD`, `MUTATE`?

### 2. Confluence versus LLM nodes
- `GENERATE` samples, `LOOP` is cyclic, `MUTATE` rewrites the graph at runtime. Confluence can hold for the deterministic core only; each of these needs a stated rule.
- For `MUTATE`: a graph delta should itself be a rewrite, applied only if Cedar permits it. This is the likely novel contribution and the README only gestures at it.

[WEN] will revisit after studying "Interaction Nets"

[CLAUDE] Agreed, parked with #1 (gap #6).

### 3. Tone
- "Revolutionary", "flips the script" and "the LLM doesn't write code" will cost credibility with NeurIPS/ICLR reviewers. The LangGraph vs. GraphLang table is strong enough alone.
- `.spl` files and prompts are still code someone writes, so the "no code" framing overstates it.

[WEN] tone down as you see fit

[CLAUDE] Will apply when the new README is written: drop "revolutionary"/"flips the script"/"the LLM doesn't write code", keep the comparison table, state claims as design goals not achievements. Not editing the archived v0.1.

### 4. Claims without backing
- "Compiled to zero-cost Rust `match` statements": `grafc` is a roadmap item.
- Roadmap ticks "Cedar integration" with no `cedar_guard.py` yet.
- No example shows a mutation rejected by a policy; that would be the best demo of the safety story.

[WEN] they will be built

[CLAUDE] Fine. Suggest the README roadmap mark these as planned (unticked) until they exist, so the claims and the repo state match. Gap #4 stays open until then.

### 5. Cedar fit
- Plausible for authorizing graph mutations, but needs an entity schema (nodes, edges, deltas) and a decision on who the principal is.
- Cedar cannot express graph-structure properties (e.g. "no cycle without a budget"); a separate validator is needed, with Cedar covering authorization only.

[WEN] we will extend Cedar for GraphLang if necessary, I visited UPenn and that is how I became aware of Cedar by Professor Mike 

[CLAUDE] Good, that makes the Cedar-extension path credible. Worth recording in the design doc which extensions you anticipate (graph-structure predicates, delta entities) so the Cedar schema is designed with them in mind. Gap #8 stays open.

### 6. Smaller points
- YAML example is incomplete (undeclared `@test_passed`, `@cycle`, `@in_analysis`).
- Fermion/boson, the stated deep physics inspiration, is absent from the README. It is the main differentiator and deserves a section, even a speculative one.
- "Superposition and entanglement" for `FORK`/`JOIN` is a quantum metaphor that does not match fermion/boson; pick one.
- "Physics-inspired" and "topologically grounded" are never defined; one concrete, checkable invariant would do.

[WEN] keep Fermion/boson metaphor, drop quantum metaphor, show me how you will clarify on "Physics-inspired" and "topologically grounded" 

[CLAUDE] Done: quantum wording is dropped (`FORK`/`JOIN` will be described as split/merge, no superposition/entanglement). Proposed definitions follow. They are my proposal; the fermion/boson mapping in particular needs your judgement.

#### Proposed definitions

**Physics-inspired** means the language adopts physical principles as checkable rules, not as decoration (three principles: exclusion, carrier, locality):

| Principle | Physics | GraphLang rule | How it is checked |
|---|---|---|---|
| Exclusion | Fermions cannot share a state | **Nodes are fermion-like**: a port binds to exactly one edge; an agent is consumed by its rewrite (no cloning without an explicit `DUP` agent) | schema/validator: every port has degree exactly 1 |
| Carrier | Bosons mediate interactions and may share a state | **Edges are boson-like** (Wen): shareable carriers. Parallel same-type edges between the same nodes are allowed and indistinguishable; one output may reach many downstream nodes via an explicit `FORK` (see below); `JOIN` is symmetric in its inputs | edge type is the only thing semantics may depend on, not edge identity |
| Locality | Interactions are local | A rewrite touches only the active pair and its adjacent ports; a `MUTATE` delta must name the affected subgraph and leave the rest untouched | delta validator |
| ~~Conservation~~ | ~~Conserved quantities~~ | **Dropped (Wen).** Information can be copied and erased, so a conservation law does not hold. Interface preservation of a rewrite stays as an interaction-net property, not a physics claim. A budget remains a Cedar policy matter, not a conservation law | n/a |

**Topologically grounded** means behaviour is a function of connectivity alone:

- Renaming node ids, or any graph isomorphism, must not change the result for the deterministic core. This is a testable property (`tests/`: shuffle ids, same output).
- Structural properties (degree, connectedness, cycles only inside `LOOP`) are validated on the graph, not inferred from code.
- Tier-3 sub-graphs are contracted nodes: expanding or collapsing one preserves the outer topology's behaviour.

Resolved by Wen: conservation dropped; edges are boson-like shareable carriers; parallel edges allowed; an output port may feed multiple downstream nodes.

#### Fan-out and fan-in: explicit `FORK` and `JOIN` (formerly splitter/merger)

Wen's picture: an output port wired to several downstream nodes through an intermediate splitter, like an optical prism. This reconciles with fermion-like ports:

- The output port still binds **exactly one** edge, to a `FORK` node. Exclusion on ports is preserved.
- `FORK` is a first-class node with one input and n outputs (n >= 2) that forwards the same value to each output. The fan-out lives in the node, not in the port.
- This matches interaction nets, which are linear (each wire has two ends) and handle sharing with explicit duplicator agents (Lafont's duplicator, as in HVM-style runtimes). So `FORK` is the duplicator; the idea of the prism and the net-theoretic mechanism coincide. To confirm when studying interaction nets.
- Value semantics: copies are of an immutable value (e.g. one `GENERATE` output), so duplicating it does not re-sample the LLM. Downstream consumers see identical data.
- `JOIN` is the converse (n inputs, one output) and symmetric in its inputs, per the carrier rule.
- **Decision (Wen): be explicit.** No desugaring and no implicit fan-out: an author who wants one output to reach several nodes writes a `FORK` node, and fan-in is a `JOIN` node. Each port binds exactly one edge in the YAML as well as in the IR. This avoids extending interaction nets beyond what the theory already provides.
- Still to define when studying interaction nets: the `JOIN` rule (what does it emit: a collected set/list of inputs, or the first arrival?). A symmetric n-to-1 agent is not a standard interaction-net agent unless its rewrite rule is spelled out, and for LLM outputs 'first arrival' is non-deterministic, so prefer a collecting rule.
- Gap tracker: row #12 covers defining `FORK`/`JOIN` in the schema.

### Suggested stance
Keep the README as a vision draft, mark theory sections provisional, track the rest in the gap tracker. Protect the unique name, the SPL lineage and the idea of Cedar-gated graph mutation.

[WEN] I have archived /home/papagame/projects/digital-duck/graflang/README.md to /home/papagame/projects/digital-duck/graflang/archive/README-qwen-v0.1.md, please revise accordingly

[CLAUDE] Revised: points above refer to the archived `archive/README-qwen-v0.1.md`, which I will not edit. The gap-tracker rows that cite "README" mean that archived draft and are to be applied to the new README when written.

## work-graph vs GraphLang

Wen's clarification (the two are related tools, not the same thing):

- **work-graph** is about how things work *together*: it organizes and manages context and knowledge. A graph describes what exists; edges are references and relationships (`belongs_to`, `satisfies`); layers are resolutions for navigating without loading everything.
- **GraphLang** is about how things are *built and how they behave*: a language to express a program. The graph is the program, executable; edges are data/control flow with rewrite semantics; composite nodes define sub-programs with interfaces.

| | work-graph | GraphLang |
|---|---|---|
| Purpose | organize and retrieve context and knowledge | express how a program is built and behaves |
| Graph is | a description of what exists | the program itself |
| Edge means | reference or relationship | something that happens (flow, rewrite) |
| Layers / composition | resolution levels for navigation | abstraction of behavior (Tier-3 sub-graphs) |
| Correctness | consistent references, gaps, rename hints | typing, Cedar safety, confluence where it holds |
| LLM's role | extract and search knowledge | propose graph changes that run |

They share a *shape* (a subgraph collapsed into one node) and tooling (the Cytoscape canvas), but the meaning differs, so they are separate designs. An earlier remark here that work-graph layers and GraphLang Tier-3 composites are "the same idea" was wrong and has been dropped.

Possible later links, neither required:
- use work-graph to organize programs that are built with GraphLang (index them like code today);
- re-implement work-graph using GraphLang (Wen: maybe unnecessary).

