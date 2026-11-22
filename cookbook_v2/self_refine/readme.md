# self_refine

Draft an essay, critique it, then rewrite it using the critique. The smallest recipe: three model calls in a line, each on its own model (the graph names them: `ollama:gemma3`, then haiku, then sonnet). Ported from `cookbook/self_refine` into the compact `steps:` form; the expanded graph is the original's.

| | |
|---|---|
| Input | `topic` (TEXT, required) |
| Output | `essay` (TEXT): the refined essay |
| LLM calls | 3 |

```bash
# the draft needs a running Ollama with gemma3; the bind file sets the call cap (5) and a default topic
graf run cookbook_v2/self_refine/self_refine.graph.yaml --param topic="why ducks float" --bind cookbook_v2/self_refine/self_refine.bind.yaml
graf expand cookbook_v2/self_refine/self_refine.graph.yaml     # the long form
```

A node's `llm:` beats `--llm`. To run all three on one model, delete the `llm:` keys, then `--llm claude_cli:claude-haiku-5-5`.
Intermediate texts are in `.graf/outputs/<run>/nodes/`.
