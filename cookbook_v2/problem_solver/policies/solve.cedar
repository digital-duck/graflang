// A model may add a part from the catalogue; nothing else is permitted.
permit(principal == Service::"llm-agent", action == Action::"mutate_graph", resource == Graph::"execution_topology")
when { context.proposed_delta.action == "add_part" };
