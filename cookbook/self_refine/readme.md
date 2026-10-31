# self_refine

Draft an essay, critique it, then rewrite it using the critique. The smallest recipe: three `GENERATE` nodes in a line, no loop, no guard.

```
wf_entry -> draft -> critique -> refine -> wf_exit
              \__________________^   (refine reads both the draft and the critique)
```

| | |
|---|---|
| Input | `topic` (TEXT, required) |
| Output | `essay` (TEXT): the refined essay |
| LLM calls | 3 (about 1 minute with `claude_cli`) |
| Prompts | `prompts/draft.md`, `prompts/critique.md`, `prompts/refine.md` |

## Run

From the repo root:

```bash
# the default: claude_cli with claude-sonnet-5-5
graf run cookbook/self_refine/self_refine.graph.yaml --param topic="why ducks float"

# another model
graf run cookbook/self_refine/self_refine.graph.yaml --llm claude_cli:claude-haiku-5-5 --param topic="why ducks float"
graf run cookbook/self_refine/self_refine.graph.yaml --llm ollama:gemma3 --param topic="why ducks float"
```

Under `claude_cli` the model is `claude-sonnet-5-5` unless you give another with `--llm claude_cli:<model>`. Under `ollama` there is no default: pass `--llm ollama:<model>`, or the nodes' hint `model: ollama/gemma3` applies and the folder name has no model part.

## What you get

- **Console:** the three firings (`draft`, `critique`, `refine`), then `✓ Workflow completed` and the output.
- **Result:** `cookbook/self_refine/output/self_refine-<adapter>[-<model>]-<time>/essay.md` (also `result.json`).
- **Intermediate text:** add `--save-nodes` to also get `nodes/001-draft.out_essay.md`, `002-critique.out_feedback.md` and `003-refine.out_essay.md`, so you can compare the draft with the refined essay.
- **Log:** `~/.graflang/logs/self_refine-<adapter>[-<model>]-<time>.log` and `.jsonl` (no essay text, only sizes and timings).

## Things to check

- `essay.md` differs from `nodes/001-draft.out_essay.md` and responds to the points in `002-critique.out_feedback.md`.
- The log has four `node.done` events (`draft`, `critique`, `refine`, `wf_exit`) and one `run.end` with `steps=4 reached_output=True`.
- Without `--param topic=...` the run stops at once with `missing workflow input(s): ['topic']`.
