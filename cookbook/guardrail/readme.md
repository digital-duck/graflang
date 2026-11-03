# guardrail

A check in front of a model: a cheap prompt decides whether a question is on topic **before** the answering prompt ever sees it. An off-topic question gets a short polite refusal instead. This is the guardrail pattern from PocketFlow (`pocketflow-chat-guardrail`), as a graph.

| | |
|---|---|
| Input | `question` (TEXT) |
| Output | `reply` (TEXT): the advice, or the refusal |
| Model calls | 2 (check, then answer or refuse) |

```bash
graf run cookbook/guardrail/guardrail.graph.yaml --param question="What should I pack for a week in Iceland in March?"
graf run cookbook/guardrail/guardrail.graph.yaml --param question="How do I reverse a linked list in Python?"
```

Tried with `claude_cli:claude-haiku-5-5`: the Iceland question went to the advisor (2 calls); the linked-list question was declined (2 calls). `tests/test_patterns_recipes.py` walks both branches with a scripted model and checks that the answering prompt never runs on a declined question.

The check is a model, so it can be wrong. For a hard rule (a banned word, a length limit) replace the `on_topic` step with a plain `evaluate` condition over the input: no model, no mistakes.
