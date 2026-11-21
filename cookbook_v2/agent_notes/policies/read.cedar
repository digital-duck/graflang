// read.cedar: may the agent read a note? The guard asks for Action::"read_note"; this one permit lets the agent_notes workflow do it.
// Which notes are readable is decided in the graph (a fixed list), not here.

permit (
    principal == Service::"agent-notes",
    action == Action::"read_note",
    resource
);
