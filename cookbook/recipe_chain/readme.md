# recipe_chain

Three recipes that already existed, used unchanged as parts of one workflow: `guardrail` -> `agent_notes` -> `supervisor`. The text each stage produces becomes the next stage's `question`.

| | |
|---|---|
| Inputs | `question` (TEXT), `max_steps` (INTEGER, default 4), `max_rounds` (INTEGER, default 3) |
| Outputs | `answer`, `status` (TEXT) |
| Model calls | 2 (guardrail) + 1 to 2 (agent) + 2 to 6 (supervisor) |

```bash
graf validate cookbook/recipe_chain/recipe_chain.graph.yaml
graf expand cookbook/recipe_chain/recipe_chain.graph.yaml     # the flat graph: screen__check, notes__agent, review__first ...
graf vis cookbook/recipe_chain/recipe_chain.graph.yaml
```

This is the acceptance test of the part interface (composability step 6), not a useful product: chaining the three makes little sense semantically. What it shows is that nothing in the three recipes had to change: the branching `guardrail` (two exits), the looping and guarded `agent_notes` (a `QUERY` that reads its own `notes/`) and the two-output `supervisor` all plug in through their `workflow.inputs` and `outputs`. If a composite ever needs a recipe edited, that is a defect of the interface, to be fixed in `grafr/parts.py`.

`tests/test_composition.py` runs it with a scripted model (on-topic and refused paths). Run once with `claude_cli:claude-haiku-5-5` (7 calls, completed): the plumbing worked, and the answer showed the chain's flaw. The guardrail's reply (not the user's question) reached the agent, which found nothing in the notes, and the supervisor approved a reply asking for the question again. Each part did its own job; the composition made no sense, as expected.
