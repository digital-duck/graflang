// ============================================================
// mutation_safety.cedar
// Constitutional policies for GraphLang's self-revising topology.
//
// These policies are evaluated by GUARD nodes at runtime (via grafr)
// and compiled to inline Rust match statements at deployment (via grafc).
// ============================================================

// ────────────────────────────────────────────────────────────
// POLICY 1: Structural Integrity — Preserve the verifier ladder
// ────────────────────────────────────────────────────────────
// The LLM must NEVER be allowed to remove ASSERT or SOLVE nodes.
// These are the mathematical guarantees of the neurosymbolic pipeline.
// Removing them would turn a verified system into a hallucination engine.

forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "remove_node" &&
    context.proposed_delta.node_type in ["ASSERT", "SOLVE"]
};

forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "remove_edge" &&
    context.proposed_delta.source_port in ["ASSERT.fail", "SOLVE.complete"]
};

// ────────────────────────────────────────────────────────────
// POLICY 2: Data Sovereignty — Prevent PII leakage to public models
// ────────────────────────────────────────────────────────────
// If the runtime context contains personally identifiable information,
// the LLM must route through a local/private model, never a public API.

forbid(
    principal == Service::"llm-agent",
    action == Action::"generate",
    resource == Model::"public-api"
) when {
    context.contains_pii == true
};

permit(
    principal == Service::"llm-agent",
    action == Action::"generate",
    resource == Model::"local-ollama"
) when {
    context.contains_pii == true
};

// ────────────────────────────────────────────────────────────
// POLICY 3: Bounded Self-Revision — Prevent infinite mutation loops
// ────────────────────────────────────────────────────────────
// The LLM can propose mutations, but only up to a bounded number per
// workflow execution. This prevents runaway self-revision that would
// consume infinite compute or destabilize the graph.

forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.mutation_count >= context.max_allowed_mutations
};

// ────────────────────────────────────────────────────────────
// POLICY 4: Human-in-the-Loop — Require approval for critical mutations
// ────────────────────────────────────────────────────────────
// Certain mutations (adding new GENERATE nodes, changing model routing)
// require explicit human approval. The LLM can propose them, but they
// are held in a "pending" state until a human reviewer signs off.

forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "add_node" &&
    context.proposed_delta.node_type == "GENERATE" &&
    context.human_approval != true
};

// ────────────────────────────────────────────────────────────
// POLICY 5: Safe Internal Mutations — Permit recovery wiring
// ────────────────────────────────────────────────────────────
// The LLM IS allowed to add RECOVER nodes and wire them to ASSERT.fail
// ports. This is the intended self-revision behavior: when a verification
// fails, the LLM proposes a recovery path, which is then evaluated by
// the deterministic solver before being accepted.

permit(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "add_node" &&
    context.proposed_delta.node_type == "RECOVER"
};

permit(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "add_edge" &&
    context.proposed_delta.target_port == "RECOVER.trigger"
};

// ────────────────────────────────────────────────────────────
// POLICY 6: Default Deny — Explicit authorization required
// ────────────────────────────────────────────────────────────
// No implicit permissions. Every mutation must be explicitly permitted
// by one of the rules above. This is the Cedar philosophy: security
// by construction, not by accident.

// (Implicit default-deny is enforced by Cedar's evaluation engine.
//  No `permit(principal, action, resource)` catch-all is needed.)