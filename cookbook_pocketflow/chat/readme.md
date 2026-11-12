# 001 — Chat  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/001_chat` with `spl3 util spl2graph` (AST-direct, no model involved); source `chat.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-chat](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-chat)
**Difficulty:** ☆☆☆
**Category:** basics

## What it does

Implements a multi-turn conversational loop that reads user input at the CLI, maintains a sliding-window JSON message history, and generates a contextually aware reply with each turn. The workflow continues until the user sends an exit signal ("exit", "quit", "bye", or "goodbye"), then returns the full conversation history. This is the foundational pattern for any production chatbot built on SPL.

## Real-world use cases

- **Customer support**: Embed as the core interaction loop for a domain-scoped support bot, replacing stateless single-turn calls with full conversation context
- **Internal tooling**: Power interactive CLI assistants for DevOps teams that need to query infrastructure state across multiple turns without re-stating context
- **Education platforms**: Drive conversational tutoring sessions where the assistant tracks what a student has understood across the session
- **Personal productivity**: Build a long-running "thinking partner" CLI that maintains session memory for brainstorming or planning tasks

## Key SPL constructs

- `CREATE TOOL_API read_user_input()` — reads a line from stdin with graceful EOF/interrupt handling
- `CREATE TOOL_API is_exit_command(user_input)` — deterministic keyword check for exit signals
- `CREATE TOOL_API append_turn(history, role, content)` — appends a `{role, content}` pair to the JSON history array
- `WHILE @i < @max_turns DO` — bounded conversation loop with force-exit on exit command
- `EVALUATE @is_exit WHEN contains("true")` — branches to force-exit vs. continue
- `GENERATE chat_reply(@trimmed)` — LLM reply generation over the sliding-window context
- `LOGGING` — echoes the assistant reply to stdout during execution

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@max_turns` | INTEGER | 50 | Maximum conversation turns before auto-exit |
| `@last_n` | TEXT | "10" | Number of most-recent turns to pass as context |

**Output:** `@history TEXT` — full JSON array of all conversation turns

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/chat/chat.graph.yaml \
    --llm claude_cli:claude-sonnet-5-5
```

## Chat in the browser

```bash
conda activate graf
cd ~/projects/digital-duck/graflang
streamlit run cookbook_pocketflow/chat/chat_ui.py
```

Up to three chatbots answer side by side, one column each, so models can be compared on the same questions. In the sidebar:

- **Reset** (the settings back to their defaults; the chats are kept) and **Clear Chats** (every chatbot's conversation; the settings are kept).
- **Number of chatbots** (1 to 3).
- For each chatbot: **Provider** (`anthropic`, through the Claude CLI and billed; or `ollama`, local and free), **Model** (`fable`, `opus`, `sonnet` or `haiku`, the default, for Anthropic; the chat models Ollama has installed, embedding models left out), **Turns it sees**, and **New chat**, which clears only that chatbot.

Type a question at the bottom of the page: every chatbot gets it at the same time, keeps its own conversation, and shows its reply with the model and the seconds it took. A chatbot that fails shows the error in its column; its conversation stays as it was and the others are kept.

The page runs a second graph, `chat_turn.graph.yaml`: **one turn** per run. The history so far and the question go in; the question is appended, the history is trimmed to the last N turns, the model replies (`GENERATE`, one billed call, capped at one per run), and the reply and the new history come out. The page only shows and keeps the conversation, so the chat's logic stays in the graph, and the same graph runs from the command line:

```bash
graf run cookbook_pocketflow/chat/chat_turn.graph.yaml --llm claude_cli:claude-sonnet-5-5 \
    --param question="What is a graph?" --param history='[]'
```

`chat.graph.yaml` (the terminal loop above) reads the keyboard inside a node, which a web page cannot do. Its `trim_turns` also splits on `"\nUser: "` while the history is JSON, so it never trims; `chat_turn.graph.yaml` trims the JSON messages.

## Extend it

- ~~Wrap with `CALL PARALLEL` to run multiple concurrent chatbot personas and compare outputs~~ Done in the browser page: up to three chatbots, each with its own model, answer the same question in parallel (one run of `chat_turn.graph.yaml` each). Next: give each chatbot a persona (a system line in the prompt).
- Replace `read_user_input` with a WebSocket or REST hook to drive web-based chat interfaces
- Add `EXCEPTION WHEN BudgetExceeded` to gracefully close the session when token limits approach
- Swap `--llm` flag at runtime to A/B test different models on the same conversation trace
