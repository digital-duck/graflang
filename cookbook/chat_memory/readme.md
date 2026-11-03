# chat_memory

One turn of a chat **with memory**. The memory is a file: `QUERY` reads its last 8 lines (a sliding window, `tail: 8`), the model answers with them in view, and `EMIT` appends the new exchange. Run it again and the next turn remembers this one. PocketFlow's `pocketflow-chat-memory`, with a file in place of a vector store.

| | |
|---|---|
| Inputs | `message` (TEXT), `memory_file` (TEXT, default `output/memory.md`) |
| Output | `reply` (TEXT) |
| Model calls | 1 per turn |

```bash
graf run cookbook/chat_memory/chat_memory.graph.yaml --param message="My name is Wen and I like Go."
graf run cookbook/chat_memory/chat_memory.graph.yaml --param message="What language did I say I like?"
```

Tried with `claude_cli:claude-haiku-5-5`: the second turn answered "You said you like Go." from the file. The file stays inside this folder; `QUERY` and `EMIT` sit behind the Cedar `GUARD` `allowed`.

The window is the last N *lines*, not the last N exchanges, so a long multi-line reply uses more of it (the prompt asks for a one-line reply). Retrieval of older, relevant turns (PocketFlow's memory example adds it) would need an embedding step and is not here.
