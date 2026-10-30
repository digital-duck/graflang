// An example organisation policy for `workflow: {policy: policies.capabilities}`. Cedar is deny by default; each rule below is one
// thing this organisation allows or forbids a workflow to contain. Copy it and change it.

// Nodes in general are fine ...
permit(principal, action == Action::"run_node", resource);

// ... except that a node which needs a capability must be marked `risky: true`, which puts it behind a GUARD.
forbid(principal, action == Action::"run_node", resource)
when { context.needs.contains("network") && !context.risky };
forbid(principal, action == Action::"run_node", resource)
when { context.needs.contains("fs_write") && !context.risky };

// Nothing may run a shell.
forbid(principal, action == Action::"run_node", resource)
when { context.needs.contains("shell") };

// An http RUN may only call these hosts.
forbid(principal, action == Action::"run_node", resource)
when { context.executor == "http" && context.host != "api.example.com" && context.host != "localhost" };
