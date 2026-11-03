# supervisor

A supervisor over an unreliable worker. The worker answers; the supervisor approves it (`APPROVED`) or says what to fix; the worker tries again with that note; at most `max_rounds` times. If nothing was approved the graph **says so** (`status`) instead of passing the last attempt off as good. PocketFlow's `pocketflow-supervisor`, as a graph.

| | |
|---|---|
| Inputs | `question` (TEXT), `max_rounds` (INTEGER, default 3) |
| Outputs | `answer` (TEXT), `status` (TEXT: `approved by the supervisor` or `not approved after N rounds; the last attempt is shown`) |
| Model calls | 2 when the first answer is approved; at most 1 + 2 x `max_rounds` |

```bash
graf run cookbook/supervisor/supervisor.graph.yaml --param question="Why is the sky blue?"
```

Tried with `claude_cli:claude-haiku-5-5`: the first answer was approved (2 calls). The rejection path (the worker sees the supervisor's note and tries again) and the give-up path are covered by `tests/test_patterns_recipes.py` with a scripted model; a real model rarely fails a simple question, so a real run of those paths needs a harder question or a weaker model.

The loop cap is the bound that matters here: a supervisor that never approves cannot run away (`max_rounds`, and `limits.max_llm_calls` in a bind file).
