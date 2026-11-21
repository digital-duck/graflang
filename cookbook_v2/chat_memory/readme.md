# chat_memory

A chat that remembers. It recalls the last turns from a memory file, replies to the message, and appends the new exchange to the file. All file access sits behind a Cedar guard.

```
chat_memory     allowed (guard) -> recall -> reply -> remember
  recall/       read the memory file (QUERY)
  reply/        one model call: the earlier turns plus the new message
  remember/     build "You: ... / Assistant: ..." and append it to the file (EMIT)
```

Inputs: `message`, `memory_file` (default `output/memory.md`, inside this folder tree). Output: `reply`. Model calls: 1.

```bash
graf run cookbook_v2/chat_memory/chat_memory.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 --param message="My name is Wen and I like Go."
graf run cookbook_v2/chat_memory/chat_memory.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 --param message="What language did I say I like?"
```

The second answer should come from the file. Delete the memory file to start over. Policy: `policies/memory.cedar`. Original: `cookbook/chat_memory`.
