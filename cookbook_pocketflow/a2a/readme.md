# 050 — A2A (Agent-to-Agent via JSON-RPC)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/050_a2a` with `spl3 util spl2graph` (AST-direct, no model involved); source `a2a.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-a2a](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-a2a)
**Difficulty:** —
**Category:** agent

## What it does

Implements an agent that accepts requests in JSON-RPC 2.0 format and runs a ReAct (Reason + Act) loop to answer them. A `parse_jsonrpc_request` tool extracts the question from the incoming payload, the LLM reasons about what information it needs and may emit a `NEED_MORE_INFO:` directive to trigger a web search, and a `build_jsonrpc_response` tool wraps the final answer back into a valid JSON-RPC response. This pattern makes SPL workflows interoperable as A2A (agent-to-agent) endpoints.

## Real-world use cases

- **Agent orchestration layers**: Wire an SPL workflow as a callable service behind a JSON-RPC endpoint so other agents or orchestrators can invoke it programmatically
- **LLM service proxies**: Build a reasoning agent that accepts structured requests from external systems (CI pipelines, schedulers, dashboards) and returns structured responses
- **Microservice agents**: Deploy specialized SPL agents (fact-checker, calculator, summarizer) as JSON-RPC services in a multi-agent architecture
- **Inter-workflow communication**: Call one SPL workflow from another via JSON-RPC rather than direct CALL — useful when the callee runs on a different Momagrid node

## Key SPL constructs

- `CREATE TOOL_API parse_jsonrpc_request(request_json)` — extracts the question from a JSON-RPC 2.0 params object
- `CREATE TOOL_API extract_search_query(reasoning)` — parses the `NEED_MORE_INFO: <query>` directive from the LLM's reasoning output
- `CREATE TOOL_API parse_search_results(raw_results)` — trims and normalizes web search output
- `CREATE TOOL_API build_jsonrpc_response(request_json, answer)` — wraps the answer in a JSON-RPC 2.0 response with the original request ID
- `CREATE FUNCTION reason(question, context)` — ReAct reasoning step; may return a `NEED_MORE_INFO:` directive or a final answer
- `WHILE @i < @max_iterations DO` — reasoning loop with early exit when the LLM produces a final answer

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@request_json` | TEXT | _(required)_ | JSON-RPC 2.0 request payload |
| `@max_iterations` | INTEGER | 5 | Maximum number of ReAct reasoning steps |

**Output:** `@response TEXT` — JSON-RPC 2.0 response object with the agent's answer

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/a2a/a2a.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Deploy behind a FastAPI endpoint using `uvicorn` to expose the agent as a real HTTP JSON-RPC service
- Register the endpoint with Momagrid Hub so other SPL workflows can discover and `CALL` it via `hub_registry`
- Chain with `041_agent_skills` to route incoming JSON-RPC requests to the most appropriate skill before answering
- Add `EXCEPTION WHEN` handling for malformed JSON-RPC payloads to return standard JSON-RPC error objects
