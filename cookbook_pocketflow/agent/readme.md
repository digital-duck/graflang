# 004 — Agent  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/004_agent` with `spl3 util spl2graph` (AST-direct, no model involved); source `web_search_agent.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).
> Caveats: `tools.spl` sits next to the graph; the SPL procedures it holds are needed at run time.

**Source:** [pocketflow-agent](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-agent)
**Difficulty:** ☆☆☆
**Category:** agentic

## What it does

Implements a ReAct (Reason + Act) web-research agent that iterates decide → search → accumulate until it has enough context to answer a question. The LLM decides the next action via structured YAML output; the workflow dispatches to a `search_web` tool or terminates. A nested `EVALUATE` block handles YAML parse errors with a retry, making the structured-output loop robust to formatting failures.

## Real-world use cases

- **Competitive intelligence**: Autonomously research a competitor's product, pricing, and recent news across multiple searches before summarizing
- **Legal and compliance**: Gather regulatory information on a topic from multiple authoritative sources before generating a summary brief
- **Financial research**: Iteratively search for earnings data, analyst ratings, and news for a given company before producing a synthesis
- **Customer FAQs**: Power a self-service bot that can search internal knowledge bases until it has enough context to answer a customer question

## Key SPL constructs

- `CREATE FUNCTION decide_action(@question, @context)` — LLM produces a YAML action decision (`search` or `answer`)
- `CREATE FUNCTION answer_question(@question, @context)` — LLM synthesizes a final answer from accumulated context
- `WHILE @done != 'true' AND @iteration < 10 DO` — bounded ReAct loop
- `CALL parse_yaml(@raw_response)` — YAML parsing tool
- `EVALUATE @parse_result WHEN contains('parse_error')` — nested retry for malformed YAML
- `EVALUATE @decision WHEN contains('action: search')` — dispatches to `search_web` vs. final answer
- `CALL search_web(@search_query)` — external tool invocation accumulating context

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@question` | TEXT | _(required)_ | The research question to answer |

**Output:** `@answer TEXT` — synthesized prose answer grounded in accumulated search results

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/agent/web_search_agent.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add `EXCEPTION WHEN BudgetExceeded` to cap search costs and return a partial answer gracefully
- Replace the single `search_web` tool with a `CALL PARALLEL` block that queries multiple search providers simultaneously
- Chain this workflow as a sub-step of `032_deep_research` to parallelize multi-topic research
- Wrap with a supervisor workflow (`CALL react_agent INTO @answer; EVALUATE quality`) to validate answer before returning
