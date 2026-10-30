# pocketflow

Three recipes from the PocketFlow-derived set in SPL.py (`cookbook-pocketflow`), lifted to graphs by `spl2graph` and kept here as the **R1 acceptance samples** (design E1). They run in graflang with no SPL.py; the two that call a model are replayed from cassettes recorded with `claude_cli` (`claude-sonnet-5-5`).

| Graph | Lifted from | Shows | LLM calls |
|---|---|---|---|
| `majority_vote.graph.yaml` | `056_majority_vote` | `FORK` into three samples, `JOIN`, a vote by a `SOLVE` | 3 |
| `debate.graph.yaml` | `018_debate` | parallel arguments, a judge `LOOP` with `EVALUATE`, a fallback verdict after the loop | 11 with `max_iterations=2` |
| `text_transformer.graph.yaml` | `055_flow` | a command loop with counters and branches, no model | 0 |

## Run

```bash
# replay the recorded answers: no model, no network
graf run cookbook/pocketflow/majority_vote.graph.yaml --replay cookbook/pocketflow/majority_vote.cassette.jsonl
graf run cookbook/pocketflow/debate.graph.yaml --replay cookbook/pocketflow/debate.cassette.jsonl --param max_iterations=2
graf run cookbook/pocketflow/text_transformer.graph.yaml

# a real model; always give a call budget (see below)
graf run cookbook/pocketflow/debate.graph.yaml --llm claude_cli:claude-sonnet-5-5 --bind budget.bind.yaml --param max_iterations=2
```

with `budget.bind.yaml` containing `limits: {max_llm_calls: 12, max_steps: 300}`.

## The acceptance gate

`tests/test_pocketflow_corpus.py` lifts **every** workflow in `SPL.py/cookbook-pocketflow` (83 files; `tools.spl` files are tool definitions, not workflows) and requires `graf validate` to pass. It is skipped when SPL.py or its cookbook is not next to this repo (set `SPL_PY_PATH` if it is elsewhere). The three samples above also run in the suite.

## What lifting these recipes found

Running them, not just validating them, found and closed four gaps:

- `@x := expr` (lifted as `CONTEXT set`) did nothing at run time; it now evaluates its expression.
- A counter in a `WHILE` condition read its starting value forever; a loop variable now starts as the value it had before the loop, an iteration that does not set it leaves it unchanged, and `latest(@in_x, @x)` lets a condition say so.
- A variable set on exclusive branches of a loop body (`@i := @i + 1` in one branch, `@i := @max` in the other) kept only one of them; a loop output's `from` may now list several ports.
- A tool called in a `WHILE` condition runs once before the loop and again at the end of each iteration.

## Known limits

- `017_judge` is not a sample: it ends its loop with `RETURN` from inside the `WHILE`, which the lifter skips (it warns), so the lifted loop does not stop when the judge passes and runs until `max_steps`. With a real model that is hundreds of calls, which is why every real run above is given a budget.
- Recipes that read from the terminal (`001_chat`), need files relative to the SPL.py checkout (`002_structured_output`), need Sage or a tool whose source does not compile (`021_self_healing`), or ask a model to reveal its reasoning (`014_thinking`, declined by the model) do not run unattended here, though they lift and validate.
- `055_flow` runs one empty round first: its `list_get` is 1-based and its counter starts at 0, as in the SPL recipe.
