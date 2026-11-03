# 062 — Tool Search (SerpAPI Briefer)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/062_tool_search` with `spl3 util spl2graph` (AST-direct, no model involved); source `tool_search.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tool-search](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tool-search)
**Difficulty:** —
**Category:** tool-use

## What it does

Executes a Google search via the SerpAPI and synthesizes the results into a structured research briefing with a summary, key facts, and follow-up queries. A deterministic `call_serpapi` tool handles the HTTP request and parses organic results; the LLM receives the top-10 results and produces the structured briefing. An `EVALUATE` branch handles `NO_RESULTS` and API error paths without requiring a WHILE loop.

## Real-world use cases

- **Research briefing generation**: Produce a structured briefing on any topic from live Google search results in a single workflow run
- **News monitoring**: Schedule the workflow to run on key topics and accumulate daily briefings for stakeholders
- **Competitive intelligence**: Search for competitor names, product launches, or press mentions and synthesize them into analyst-style reports
- **Sales research automation**: Search for a prospect company before a call and produce a briefing with key facts and follow-up questions

## Key SPL constructs

- `CREATE TOOL_API call_serpapi(query)` — HTTP GET to SerpAPI with `SERPAPI_KEY` from environment; returns JSON of top-10 organic results or `NO_RESULTS`/`ERROR:` strings
- `CREATE FUNCTION synthesize_briefing(query, search_results)` — LLM produces a three-section briefing: Summary, Key Facts, Follow-up Queries
- `EVALUATE @raw_results WHEN contains("NO_RESULTS")` — routes to a "no results" message without calling the LLM
- `EVALUATE @raw_results WHEN contains("ERROR:")` — propagates API errors directly to output
- Clean error routing pattern with no WHILE loop: success, empty, and error paths in a single EVALUATE chain

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@query` | TEXT | _(required)_ | The search query to run |

**Output:** `@briefing TEXT` — structured research briefing with Summary, Key Facts, and Follow-up Queries sections

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

export SERPAPI_KEY=your_serpapi_key
graf run cookbook_pocketflow/tool_search/tool_search.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Wrap in a WHILE loop driven by the follow-up queries output to perform iterative deep research (similar to `032_deep_research`)
- Chain multiple `tool_search` calls in `CALL PARALLEL` to cover multiple search angles simultaneously
- Add `CALL write_file(@output_file, @briefing, "a")` to accumulate daily briefings on a topic into a single log file
- Replace `call_serpapi` with a different search provider tool (Brave Search, Bing, DuckDuckGo API) — the .spl workflow remains unchanged
