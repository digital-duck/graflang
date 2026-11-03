# 016 — MCP (Model Context Protocol)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/016_mcp` with `spl3 util spl2graph` (AST-direct, no model involved); source `mcp.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-mcp](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-mcp)
**Difficulty:** ★☆☆
**Category:** tool-use

## What it does

Demonstrates dynamic tool discovery and invocation via the Model Context Protocol: the workflow first discovers available tools from an MCP server (or falls back to built-in math tools when no server is configured), then asks the LLM to select and call the right tool for a given question, and finally invokes the chosen tool — either via the MCP server or locally. This cleanly separates tool catalog management from tool selection and execution.

## Real-world use cases

- **Dynamic toolsets**: Connect an LLM to an evolving MCP server whose tool list changes over time without changing the .spl file — DODA in action across tool registries
- **Multi-environment deployment**: Run the same workflow against a local math library in development and a production MCP server with broader capabilities, swapping `--param mcp_mode=true`
- **Enterprise tool gateways**: Have the LLM select from company-managed MCP tools (database queries, document search, calendar actions) without hardcoding tool signatures in the workflow
- **Tool capability testing**: Validate that an LLM correctly selects among discovered tools for a range of question types

## Key SPL constructs

- `CREATE TOOL_API discover_tools(mcp_mode, mcp_server_url)` — returns JSON list of available tool specs
- `CREATE TOOL_API call_mcp_tool(tool_name, tool_args, mcp_server_url)` — invokes a tool via MCP HTTP endpoint
- `CREATE TOOL_API call_local_tool(tool_name, tool_args)` — invokes a built-in fallback math tool
- `GENERATE select_tool(@question, @tools_json)` — LLM reads tool catalog and selects the right tool + args
- `EVALUATE @use_mcp WHEN contains("true")` — routes to MCP invocation vs. local invocation

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@question` | TEXT | _(required)_ | The math or factual question to answer |
| `@mcp_mode` | TEXT | `"false"` | `"true"` to use an MCP server, `"false"` for built-in tools |
| `@mcp_server_url` | TEXT | `""` | URL of the MCP server (required when mcp_mode is true) |

**Output:** `@answer TEXT` — the tool's computed result

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/mcp/mcp.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Point `--param mcp_server_url=http://localhost:3000` at a real MCP server to unlock dynamic tool registration
- Add a WHILE retry loop if the LLM selects a tool that returns an error, re-discovering tools on each retry
- Use `CALL PARALLEL` to invoke multiple tools simultaneously and synthesize results for multi-step queries
- Extend `discover_tools` to query multiple MCP servers and merge their tool catalogs for a federated toolbox
