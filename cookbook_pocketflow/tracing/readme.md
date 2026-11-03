# 063 — Tracing (Langfuse Integration)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/063_tracing` with `spl3 util spl2graph` (AST-direct, no model involved); source `tracing.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tracing](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tracing)
**Difficulty:** —
**Category:** observability

## What it does

Demonstrates structured observability for an SPL workflow using Langfuse: a trace decorator generates a distributed `trace_id`, and then a WHILE loop runs each node through three phases (prep → exec → post) — logging each phase to Langfuse as a named span with timing and I/O. Error handling in each phase short-circuits the loop and records exceptions to Langfuse. This pattern enables production-grade LLM observability without changing workflow business logic.

## Real-world use cases

- **Production LLM monitoring**: Track every node's prep/exec/post timing and I/O in Langfuse for latency analysis, cost tracking, and error detection on live workflows
- **Debug tracing**: Reproduce a failing run by replaying the exact inputs at each phase using the Langfuse trace history
- **Compliance auditing**: Maintain an immutable audit trail of every LLM call and tool invocation for regulatory review
- **Performance optimization**: Identify bottleneck nodes by comparing per-phase timing across multiple workflow runs in the Langfuse dashboard

## Key SPL constructs

- `CREATE TOOL_API apply_trace_decorator(flow_name)` — generates a millisecond-precision `trace_id` for the run
- `CREATE TOOL_API run_prep(node_name, inputs)` / `run_exec(node_name, prep_result)` / `run_post(node_name, exec_result)` — simulated node phases with timing metadata
- `CREATE TOOL_API langfuse_log(node_name, phase, payload_json)` — logs a phase as a Langfuse span with input, output, and timing
- `CREATE TOOL_API langfuse_record_exception(node_name, phase, payload_json)` — records a Langfuse exception event on phase failure
- `WHILE @i < @max_nodes DO` — node iteration loop with blank-entry sentinel exit
- `EVALUATE @phase_status WHEN contains("error")` — short-circuits the loop and records the exception on any phase failure

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@flow_name` | TEXT | `"pocketflow"` | Name of the workflow for the Langfuse trace |
| `@node_list` | TEXT | `"node_a,node_b,node_c"` | Comma-delimited list of node names to trace |
| `@flow_inputs` | TEXT | `"{}"` | JSON inputs to pass to the first node |
| `@max_nodes` | INTEGER | 10 | Safety cap on the number of nodes to process |

**Output:** `@trace_summary TEXT` — accumulated summary of all traced phases and any errors encountered

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/tracing/tracing.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` environment variables to enable real Langfuse logging (the tool falls back gracefully when not configured)
- Add `CALL PARALLEL` to run independent node subtrees simultaneously while still logging each branch's spans to Langfuse
- Extend `run_exec` to call the actual LLM GENERATE steps and log the real prompt/response pairs as Langfuse generation spans
- Use the `trace_id` output with Langfuse's session-linking API to group multiple related workflow runs into a single session view
