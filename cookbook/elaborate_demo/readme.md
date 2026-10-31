# elaborate_demo

One template applied to a graph of things. `concepts.yaml` is a small knowledge graph (an edge `a -> b` means a is a prerequisite of b); the part `parts/explain.graph.yaml` explains one concept. The `elaborate:` block in `elaborate_demo.graph.yaml` makes one use of the part per concept and turns the edges into order and data.

```
probability --\                 
               >-- entropy --> coding         (each box is a use of `explain`)
counting ------/
```

| | |
|---|---|
| Input | `audience` (TEXT, default `curious beginners`), passed to every concept |
| Output | `explanations` (JSON): one explanation per concept id |
| LLM calls | 1 per concept (4) |
| Files | `elaborate_demo.graph.yaml`, `concepts.yaml`, `parts/explain.graph.yaml`, `parts/prompts/explain.md` |

## What elaboration does

- `probability` and `counting` have no prerequisite, so they start together (a `FORK`).
- `entropy` has two, so it waits for both (a `JOIN`) and its `context` input receives `{probability: ..., counting: ...}`, the texts they wrote (`pass: {from: text, to: context}`).
- `coding` has one prerequisite, so it follows `entropy` and receives `{entropy: ...}`.
- When every concept is done, the results are gathered into one object, the workflow output.

`graf expand cookbook/elaborate_demo/elaborate_demo.graph.yaml` prints the ordinary nodes and edges this stands for; `graf vis` draws them, one box per use.

## Run

```bash
graf run cookbook/elaborate_demo/elaborate_demo.graph.yaml --workers 2
graf run cookbook/elaborate_demo/elaborate_demo.graph.yaml --param audience="high-school students" --workers 2 --save-nodes
```

With `--workers 2` the two roots run at the same time; the result is the same as with one worker.

## Things to check

- Adding a concept or an edge to `concepts.yaml` needs no change to the workflow. An edge that closes a cycle is refused, naming the cycle.
- A concept without a `title` attribute is refused (the part's `concept` input has no default).
- Reading order is only what the edges say. If chapters must be written in a fixed order for consistent style, that order has to be an edge.
