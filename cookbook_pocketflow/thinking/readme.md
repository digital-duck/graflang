# 014 — Thinking (Chain-of-Thought)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/014_thinking` with `spl3 util spl2graph` (AST-direct, no model involved); source `chain_of_thought.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).
> Caveats: `tools.spl` sits next to the graph; the SPL procedures it holds are needed at run time.

**Source:** [pocketflow-thinking](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-thinking)
**Difficulty:** ★☆☆
**Category:** reasoning

## What it does

Solves complex reasoning problems through multi-step chain-of-thought where each thought step is validated as YAML before being accepted. An outer loop continues as long as the LLM indicates more reasoning is needed; an inner loop retries up to three times if the LLM produces malformed YAML. Each accepted thought is appended to a trace file and to the thought history that feeds the next step. An `EXCEPTION WHEN BudgetExceeded` handler ensures graceful degradation under token limits.

## Real-world use cases

- **Multi-step mathematical reasoning**: Solve arithmetic, algebra, or combinatorics problems with verifiable intermediate steps rather than direct single-shot answers
- **Logical deduction and puzzles**: Work through constraint-satisfaction problems (who owns the zebra, etc.) with explicit reasoning trace
- **Debugging and root-cause analysis**: Step through a system failure scenario logically, updating the hypothesis at each step
- **Structured problem decomposition**: Generate and refine a solution plan for software architecture or business strategy decisions

## Key SPL constructs

- `CREATE FUNCTION ChainOfThoughtStep(@problem, @thoughts_text, @last_plan, @thought_number)` — single reasoning step returning YAML with `current_thinking`, `next_action_plan`, `next_thought_needed`
- Outer `WHILE @next_thought_needed = "true" AND @iteration < @max_iterations DO` — reasoning loop
- Inner `WHILE @yaml_valid = "false" AND @retry_count < 3 DO` — structured output validation retry
- `CALL validate_yaml_fields(@thought_data)` — checks required YAML fields are present
- `CALL write_file(@trace_file, ..., "a")` — appends each step to a trace file for debugging
- `EXCEPTION WHEN BudgetExceeded THEN RETURN @current_thinking WITH status = "budget_limit"` — graceful budget handling

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@problem` | TEXT | _(required)_ | The reasoning problem to solve |
| `@max_iterations` | INT | 5 | Maximum number of reasoning steps |
| `@trace_file` | TEXT | `"chain_of_thought_trace.md"` | Path to write the step-by-step reasoning trace |

**Output:** `@solution TEXT` — the final `current_thinking` content from the last reasoning step

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/thinking/chain_of_thought.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Use a stronger reasoning model (e.g., `--llm claude_cli:claude-opus-4-6`) for the outer loop and a faster model for YAML validation retries
- Add `CALL PARALLEL` to generate multiple independent reasoning chains, then synthesize the best answer
- Replace the YAML validation retry with `EXCEPTION WHEN StructuredOutputError` once SPL supports typed exceptions for malformed outputs
- Feed the trace file into a downstream analysis workflow to evaluate reasoning quality across problems
