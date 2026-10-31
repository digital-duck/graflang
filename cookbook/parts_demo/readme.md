# parts_demo

One reusable workflow (a *part*) used twice. `draft` writes five sentences, then the part `polish` rewrites them in a formal tone, then the same part rewrites the result again with its default (plain) tone.

```
draft -> first (polish, tone formal) -> second (polish, default tone) -> done
```

| | |
|---|---|
| Input | `topic` (TEXT, required) |
| Output | `essay` (TEXT) |
| LLM calls | 3 |
| Files | `parts_demo.graph.yaml` (compact form), `sub_graph/polish.graph.yaml` (the part), `sub_graph/prompts/rewrite.md` |

## Reading `parts_demo.graph.yaml`: steps are shorthand for nodes and edges

The `steps:` list is a compact way to write a graph. It is not a different program: when the file loads, `steps:` is expanded into the `nodes:` and `edges:` the runtime runs, and `graf expand` prints that long form. Each step is one line, `id: {kind: ..., in: ..., out: ...}`:

| Step | What you wrote | What it becomes |
|---|---|---|
| `draft` | `generate: "Write 5 sentences about {{in_topic}}."` | a `GENERATE` node `draft` with that prompt |
| `first` | `use: parts.polish, in: {essay: draft, tone: formal}` | the part's nodes copied in, as `first__rewrite` (`GENERATE`), with `tone` preset to `formal` |
| `second` | `use: parts.polish, in: {essay: first.essay}` | another copy, `second__rewrite`, with the part's default tone `plain` |
| `done` | `output: second.essay` | an `OUTPUT` node `done` that returns `essay` |
| (not written) | | an `INPUT` node `wf_entry`, added for the workflow's `topic` input |

Two kinds of edge are inferred from the steps:

- **Data (`binds`)**: every name in `in:` is a reference. `essay: draft` means "the output of `draft`"; `essay: first.essay` means "the `essay` output of `first`"; `$in.topic` is the workflow input `topic`. Each reference becomes a `binds` edge, for example `draft.out_essay -> first__rewrite.in_essay`.
- **Control (`triggers`)**: each step fires after the one listed before it, and the first step after the workflow entry. Here that gives `wf_entry -> draft -> first__rewrite -> second__rewrite -> done`; no step writes it. A step that should hang elsewhere (a branch of `evaluate`, say) says `on: step.port`.

So the 4 lines expand to 5 nodes (`wf_entry`, `draft`, `first__rewrite`, `second__rewrite`, `done`) and 8 edges, 4 `binds` and 4 `triggers`:

```
wf_entry --> draft --> first__rewrite --> second__rewrite --> done      (triggers, one after another)
   topic ----> draft ... essay ----> first__rewrite ... essay ----> second__rewrite ... essay ----> done   (binds, the data)
```

Run `graf expand cookbook/parts_demo/parts_demo.graph.yaml` to see all of it, and `graf vis cookbook/parts_demo/parts_demo.graph.yaml` to draw it (each `use` as a box). The two forms are interchangeable; use `steps:` for a line of steps and `nodes:`/`edges:` for anything it cannot say (the two may sit in one file, and steps can refer to the hand-written nodes). The full step grammar is in the module docstring of `graphlang/grafr/compact.py` and in the USER-GUIDE.

## How a part works

A part is an ordinary workflow file with one `INPUT` and one `OUTPUT` node; its `workflow.inputs` / `outputs` are the interface. The using graph lists it under `resources.parts` and writes `use: parts.polish` with `in:` and `out:`. Before anything runs, each use is expanded in place into its own copy of the part's nodes (`first__rewrite`, `second__rewrite`), so the two uses share no state. Run `graf expand cookbook/parts_demo/parts_demo.graph.yaml` to see the flat graph.

The interface is checked when the file loads (`graf validate`): `in:`/`out:` names must exist in the part, an input without a default must be bound (`tone` has one, `essay` does not), and types must be assignable. A literal in `in:` (`tone: formal`) overrides the part's default.

## Run

```bash
graf run cookbook/parts_demo/parts_demo.graph.yaml --param topic="AI assisted education"
```

In the run folder's `nodes/` you get the draft, the formal version and the plain version, to compare.

## Things to check

- A part may use another part; a part may not use itself.
- Prompt files are resolved relative to the part file, not to the using graph.
