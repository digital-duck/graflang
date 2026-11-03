# 053 — CLI HITL (Human-in-the-Loop)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/053_cli_hitl` with `spl3 util spl2graph` (AST-direct, no model involved); source `cli_hitl.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-cli-hitl](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-cli-hitl)
**Difficulty:** —
**Category:** human-in-the-loop

## What it does

Demonstrates the human-in-the-loop pattern via CLI: the workflow prompts the user for a topic interactively, generates a joke about it, displays the joke and asks for approval at the terminal, and loops generating new jokes (with rejection history to avoid repeats) until the user approves one or the iteration cap is reached. The `ask_user_approval` and `ask_topic` tools wrap `input()` calls, making human decisions a first-class part of the workflow.

## Real-world use cases

- **Content approval pipelines**: Generate candidate marketing copy, blog headlines, or social posts and interactively approve or reject them before publication
- **Interactive form generation**: Generate form templates or contract clauses and collect human approval at each step in a CLI-based workflow
- **Code review assistance**: Generate code refactoring suggestions and collect developer approval before applying each change
- **Data labeling workflows**: Generate candidate labels for ambiguous data items and collect human confirmation before committing them to a dataset

## Key SPL constructs

- `CREATE TOOL_API ask_topic()` — reads a topic from `stdin` via `input()`; returns a default if empty
- `CREATE TOOL_API ask_user_approval(joke)` — displays the joke and reads `yes`/`no` approval from `stdin`
- `CREATE FUNCTION generate_joke(topic, rejected_jokes)` — generates a new joke that avoids previously rejected jokes
- `WHILE @i < @max_iterations DO` — approval loop
- `EVALUATE @approval WHEN contains("yes")` — exits loop immediately on human approval
- Rejection accumulation: `@rejected_jokes := @rejected_jokes + "- " + @joke + "\n"` — builds prior-rejection context

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@max_iterations` | INTEGER | 10 | Maximum number of generate-approve cycles |

**Output:** `@joke TEXT` — the joke that received human approval (or the last generated joke if the cap was reached)

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/cli_hitl/cli_hitl.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Replace `ask_user_approval` with a webhook-based approval tool to run the HITL loop in an async web context rather than a blocking CLI
- Add a `CALL write_file(@approved_file, @joke, "a")` step to log all approved outputs across sessions
- Use `EVALUATE @approval WHEN contains("edit")` to collect inline edits from the human and feed the corrected version as the next generation seed
- Chain with `017_judge` to add an LLM pre-screen before presenting to the human, reducing the approval burden for obvious rejects
