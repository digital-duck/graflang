# assembler

A model **assembles** the workflow it runs. It reads a question and a short catalogue, and proposes a graph change: add one recipe (`guardrail` or `agent_notes`) between the `pick` node and the exit. The `MUTATE` node checks the proposal like any other delta (schema, Cedar policy, budget, the graph's invariants on a trial copy) and also the workflow's `parts_policy`; only then is the recipe wired in and run.

| | |
|---|---|
| Input | `question` (TEXT) |
| Outputs | `reply` (TEXT, from the recipe it chose), `why` (TEXT, what the graph did with the proposal) |
| Model calls | 1 to choose, then what the chosen recipe makes (at most 6 in all, by `parts_policy`) |

```bash
graf run cookbook/assembler/assembler.graph.yaml --param question="What should I pack for Iceland in March?"
graf run cookbook/assembler/assembler.graph.yaml --param question="How much is the Team plan per user?"
```

What the model cannot do: pick a recipe outside `catalogue` (that list is graph-file text, and a delta cannot change it), name a path, or add a part that sends e-mail, posts to a webhook, runs a program or writes a file (`parts_policy.forbid`). The catalogue text in `prompts/choose.md` is written by hand, so it can drift from the recipes; `graf parts` shows what each recipe really takes and touches. An `add_part` is one delta, so with `max_mutations: 1` the model adds one recipe.

Tried once with `claude_cli:claude-haiku-5-5` (3 calls each): for the Iceland question it chose `guardrail` and the recipe answered; for the pricing question it also chose `guardrail`, which declined (wrong pick; the catalogue text was clear, so this is the model, not the graph: the graph did what it was told and the guardrail did its job).

Part names are resolved through the work area (`cookbook:guardrail`), so install the cookbook first (`~/.graflang/cookbook`) or run from a checkout.
