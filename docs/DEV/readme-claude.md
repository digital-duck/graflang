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
