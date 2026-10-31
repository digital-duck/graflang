# parts_demo

One reusable workflow (a *part*) used twice. `draft` writes two sentences, then the part `polish` rewrites them in a formal tone, then the same part rewrites the result again with its default (plain) tone.

```
draft -> first (polish, tone formal) -> second (polish, default tone) -> done
```

| | |
|---|---|
| Input | `topic` (TEXT, required) |
| Output | `essay` (TEXT) |
| LLM calls | 3 |
| Files | `parts_demo.graph.yaml` (compact form), `parts/polish.graph.yaml` (the part), `parts/prompts/rewrite.md` |

## How a part works

A part is an ordinary workflow file with one `INPUT` and one `OUTPUT` node; its `workflow.inputs` / `outputs` are the interface. The using graph lists it under `resources.parts` and writes `use: parts.polish` with `in:` and `out:`. Before anything runs, each use is expanded in place into its own copy of the part's nodes (`first__rewrite`, `second__rewrite`), so the two uses share no state. Run `graf expand cookbook/parts_demo/parts_demo.graph.yaml` to see the flat graph.

The interface is checked when the file loads (`graf validate`): `in:`/`out:` names must exist in the part, an input without a default must be bound (`tone` has one, `essay` does not), and types must be assignable. A literal in `in:` (`tone: formal`) overrides the part's default.

## Run

```bash
graf run cookbook/parts_demo/parts_demo.graph.yaml --param topic=tides
graf run cookbook/parts_demo/parts_demo.graph.yaml --param topic=tides
```

In the run folder's `nodes/` you get the draft, the formal version and the plain version, to compare.

## Things to check

- A part may use another part; a part may not use itself.
- Prompt files are resolved relative to the part file, not to the using graph.
