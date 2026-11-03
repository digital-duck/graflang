# 055 — Flow (Text Transformer)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/055_flow` with `spl3 util spl2graph` (AST-direct, no model involved); source `text_transformer.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-flow](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-flow)
**Difficulty:** —
**Category:** basics

## What it does

An interactive text transformation tool that processes a pipe-delimited list of `type:input` commands in a WHILE loop, applying the selected transformation (uppercase, lowercase, reverse, collapse whitespace) to each input and accumulating a formatted session log. An "exit" sentinel terminates the loop. All transformations are deterministic — no LLM is involved in the core processing — making this a pure SPL control-flow demonstration.

## Real-world use cases

- **Text preprocessing pipelines**: Normalize a batch of user-supplied strings (case folding, whitespace normalization) as a preprocessing step before embedding or classification
- **Data cleaning workflows**: Apply a sequence of string transformations to raw input fields from a CSV export before loading into a database
- **CLI utilities**: Build a command-loop tool where each user command specifies both the operation and its input, driven by a config file or CLI argument
- **Testing SPL control flow**: Use as a minimal testbed for EVALUATE-branch routing and sentinel-based WHILE loop termination patterns

## Key SPL constructs

- `CREATE TOOL_API collapse_whitespace(text)` — regex-based whitespace normalization (the only non-stdlib transformation)
- `CALL list_get(@commands, @i, "|")` — index into the pipe-delimited command list
- `CALL split_part(@command, ":", "1")` — extracts the transform type from the `type:input` format
- `CALL split_part(@command, ":", "2")` — extracts the input text
- `EVALUATE @is_exit WHEN contains("true")` — sentinel-value exit: sets `@i := @max_iterations`
- Nested `EVALUATE @transform_type WHEN contains(...)` chain — routes to `upper()`, `lower()`, `reverse()`, or `collapse_whitespace()`
- Session log accumulation: `@session_log := @session_log + ...` — builds the output inline

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@commands` | TEXT | `"uppercase:hello world\|lowercase:HELLO\|reverse:abcdef\|exit"` | Pipe-delimited list of `type:input` commands; "exit" terminates |
| `@max_iterations` | INTEGER | 20 | Safety cap on the number of iterations |

**Output:** `@session_log TEXT` — accumulated session log with each command's menu display and transformation result

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/flow/text_transformer.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add an LLM-powered `GENERATE smart_transform(@input_text, @style)` transformation type for open-ended text rewriting
- Replace the pipe-delimited command list with `CALL read_file` + line-by-line iteration to process transformation scripts from files
- Add a `CALL write_file(@output_log, @session_log, "w")` step to persist the session log for audit or replay
- Extend the EVALUATE branch chain with additional transformations (trim, base64 encode, JSON pretty-print) to build a versatile text toolkit
