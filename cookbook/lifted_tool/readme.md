# lifted_tool

Upper-case a word and add `!`. No LLM: the whole recipe is one `SOLVE` node. It shows what happens to an SPL workflow that calls a Python tool (`CREATE TOOL_API`): `spl2graph` lifts the call to a `SOLVE` with `backend: kernel` whose `code` carries the tool's source, so the graph runs in graflang's own Python kernel and needs neither SPL.py nor a model.

```
wf_entry -> tool_1 (shout) -> wf_exit
```

| | |
|---|---|
| Input | `word` (TEXT, default `hi`) |
| Output | `loud` (TEXT): the word in capitals plus `!` |
| LLM calls | 0 |
| Needs | the `kernel` extra (`pip install -e ".[kernel]"`: jupyter_client, ipykernel) |

## Run

```bash
graf run cookbook/lifted_tool/lifted_tool.graph.yaml --param word=hello      # HELLO!
graf compile --lang spl cookbook/lifted_tool/lifted_tool.graph.yaml          # back to .spl with CREATE TOOL_API
```

## Things to check

- The tool source sits in `config.code`; `result` names the variable read back. A `MUTATE` delta can never add or change `backend`, `code` or `result`, so a model cannot slip code into a running graph.
- `graf validate` checks the kernel backend's settings without starting a kernel.
