// watch.cedar: may the heartbeat read its inbox and state, and write its state and alerts?
permit (
    principal == Service::"heartbeat",
    action == Action::"watch",
    resource
);
