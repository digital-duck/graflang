# 057 — TAO (ReAct Tool Agent)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/057_tao` with `spl3 util spl2graph` (AST-direct, no model involved); source `tao.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tao](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tao)
**Difficulty:** —
**Category:** agent

## What it does

A general-purpose ReAct (Reason + Act) agent with a multi-tool dispatch layer: the LLM selects a tool from `search_web`, `run_python`, `calculate`, or `none` at each step, generating a JSON `{thought, tool, args}` response. A single `dispatch_tool` function routes to the appropriate implementation. The loop continues until the LLM selects `none` (or `answer`/`final_answer`) to signal it has enough information to synthesize a final answer.

## Real-world use cases

- **General research agents**: Answer open-ended questions by combining web search for facts, Python for calculations, and reasoning over accumulated results
- **Data analysis assistants**: Run mathematical operations and Python data transformations interleaved with web lookups to answer quantitative research questions
- **Automated problem solvers**: Tackle multi-step problems that require fetching information, computing intermediate values, and synthesizing a conclusion
- **Prototyping tool-augmented agents**: Use TAO's single `dispatch_tool` pattern as a starting template when building domain-specific agents with a custom tool set

## Key SPL constructs

- `CREATE TOOL_API dispatch_tool(action_json)` — routes to `search_web` (DuckDuckGo HTTP), `run_python` (subprocess), `calculate` (safe `eval()`), or returns a final-answer signal
- `CREATE FUNCTION reason_and_act(query, history, tools_available)` — LLM generates JSON: `{thought, tool, args}` for the next action
- `CALL json_get(@action_json, "tool")` — extracts the tool name from the LLM's JSON response
- `WHILE @i < @max_iterations DO` — bounded ReAct loop
- `EVALUATE @tool_name WHEN contains("none")` / `contains("answer")` — exits loop when the LLM is done with tool calls
- History accumulation: `@history := @history + "Thought: " + @thought + "\nTool: ..."` — carries the full reasoning trace forward

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@query` | TEXT | _(required)_ | The question or task to solve |
| `@max_iterations` | INTEGER | 10 | Maximum number of Reason + Act cycles |

**Output:** `@answer TEXT` — the final synthesized answer after tool use

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/tao/tao.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `read_file` and `write_file` tool to `dispatch_tool` to enable filesystem access in the agent loop
- Replace the DuckDuckGo search with SerpAPI (see `062_tool_search`) for higher-quality search results
- Add `CALL write_file(@trace_file, @history, "w")` after the loop to persist the reasoning trace for debugging or fine-tuning
- Extend the tool set with domain-specific tools (database query, API call, email send) to build specialized agents
