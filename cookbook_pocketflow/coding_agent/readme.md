# 040 — Coding Agent  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/040_coding_agent` with `spl3 util spl2graph` (AST-direct, no model involved); source `coding_web_search_agent.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-coding-agent](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-coding-agent)
**Difficulty:** ★★★
**Category:** agent

## What it does

An autonomous coding agent that implements stub functions in a codebase until a failing test suite passes. The agent runs in a WHILE loop, selecting one action per iteration from a fixed repertoire: inspect a directory, read a file, patch a file with new code, or run the test suite. Each action's result is appended to a history buffer that feeds the next decision step. The loop exits when tests pass or the action budget is exhausted.

## Real-world use cases

- **Automated code completion**: Implement stub functions in a scaffolded project by driving the agent against the project's existing test suite as the ground truth
- **Technical interview practice**: Generate and implement coding challenge stubs, then verify solutions automatically against test cases
- **Codebase modernization**: Have the agent refactor specific function implementations while ensuring the test suite remains green throughout
- **CI fix-bot**: Automatically attempt to fix a failing test suite on a PR branch by reading error output and applying targeted patches

## Key SPL constructs

- `CREATE TOOL_API list_project_files(directory)` — walks the directory tree and returns a structured file listing
- `CREATE TOOL_API run_test_suite(test_dir)` — runs pytest with `--tb=short` and returns captured output
- `CREATE TOOL_API check_tests_pass(test_output)` — deterministic regex check returning "pass" or "fail"
- `CREATE TOOL_API append_history(history, action, result)` — accumulates the action log for LLM context
- `CREATE TOOL_API parse_field(text, field)` — extracts `ACTION:`, `PATH:`, `CONTENT:` fields from the LLM's structured response
- `CREATE FUNCTION select_action(action_history, codebase_structure, skeleton_functions, test_suite)` — LLM selects the next action from `{inspect, read, patch, run_tests}`
- `WHILE @iteration < @max_iterations DO` — bounded agent loop
- `EVALUATE @tests_pass WHEN contains("pass")` — exits loop on green test suite

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@project_dir` | TEXT | `"."` | Root directory of the project to work on |
| `@test_dir` | TEXT | `"tests/"` | Directory containing the test suite |
| `@skeleton_functions` | TEXT | _(required)_ | Description of the stub functions to implement |
| `@max_iterations` | INTEGER | 20 | Maximum number of agent action steps |

**Output:** `@result TEXT` — final test suite output with pass/fail status

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/coding_agent/coding_web_search_agent.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `git commit` tool step triggered automatically when tests first pass, capturing the working implementation
- Use `CALL PARALLEL` to run multiple independent coding agent instances on different stub functions simultaneously
- Add `EXCEPTION WHEN` handling for infinite-loop detection — if the same action is taken three times consecutively without progress, escalate with a different prompt
- Extend the action space with a `search` action that greps for patterns across the codebase to aid discovery
