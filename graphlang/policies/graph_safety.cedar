// Policy 1: Prevent PII from being sent to external/public models
forbid(
    principal == Service::"llm-agent",
    action == Action::"generate",
    resource == Model::"public-api"
) when {
    context.contains_pii == true
};

// Policy 2: Prevent the LLM from mutating the graph to bypass ASSERT nodes
forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "remove_edge" &&
    context.proposed_delta.source.type == "ASSERT"
};

// Default permit for safe, internal operations
permit(
    principal,
    action,
    resource
);