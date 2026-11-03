# 008 — Chat Guardrail  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/008_chat_guardrail` with `spl3 util spl2graph` (AST-direct, no model involved); source `chat_guardrail.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-chat-guardrail](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-chat-guardrail)
**Difficulty:** ☆☆☆
**Category:** safety

## What it does

Adds a two-tier safety classifier layer to a multi-turn chat loop: a fast deterministic keyword filter runs first, and only messages that pass it are forwarded to an LLM topic classifier before reaching the actual response generator. Off-topic or harmful messages receive a polite rejection instead of a substantive answer. This pattern decouples safety policy from response logic, making both independently testable and swappable.

## Real-world use cases

- **Vertical chatbots**: Enforce domain scope in specialized assistants (travel, legal, medical) so users cannot redirect the bot into unrelated or harmful territory
- **Enterprise copilots**: Block queries that violate corporate information security policies before they reach a model with access to sensitive data
- **Children's platforms**: Implement age-appropriate content filtering at the input layer before any LLM processing occurs
- **Regulated industries**: Maintain an audit log of blocked messages for compliance reporting while still providing a helpful redirect response

## Key SPL constructs

- `CREATE TOOL_API heuristic_travel_check(message)` — fast keyword-based pre-filter (travel domain); zero LLM cost
- `CREATE FUNCTION validate_travel_topic(message)` — LLM classifier, single-token output ("travel" / "not_travel")
- `CREATE FUNCTION reject_off_topic(message)` — generates a polite redirection response
- `CREATE FUNCTION generate_travel_advice(message)` — the actual domain response generator
- `WHILE @i < @max_turns DO` — processes each message in the input list sequentially
- Nested `EVALUATE` blocks — heuristic gate → LLM gate → response dispatch
- `CALL list_get(@user_messages, @i, "\n")` — iterates over newline-delimited message list

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@user_messages` | TEXT | _(required)_ | Newline-delimited list of user messages to process |
| `@max_turns` | INTEGER | 10 | Maximum number of messages to process |

**Output:** `@conversation_log TEXT` — full transcript with User/Assistant turns, including rejected messages

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/chat_guardrail/chat_guardrail.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6 \
    --param 'user_messages="help me plan a trip to Wuhu, Anhui, China"'
```

## Extend it

- Replace the heuristic keyword list with a `CREATE TOOL_API` that calls a dedicated toxicity/topic classifier API for higher accuracy
- Add a third tier: an LLM-based intent classifier that catches prompt injection attempts before the domain check
- Log rejected messages to a file via `CALL write_file(@log_file, @entry, "a")` for compliance audit trails
- Parameterize the domain topic so the same workflow serves as a general-purpose scoped-assistant guardrail
