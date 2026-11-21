// memory.cedar: may the chat_memory workflow read and extend its memory file?
// Denied unless this permit applies; the QUERY and the EMIT sit behind the guard's `allow` port.

permit (
    principal == Service::"chat-memory",
    action == Action::"remember",
    resource
);
