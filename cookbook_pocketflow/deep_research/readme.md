# 032 — Deep Research  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/032_deep_research` with `spl3 util spl2graph` (AST-direct, no model involved); source `deep_research.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-deep-research](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-deep-research)
**Difficulty:** ★★☆
**Category:** research

## What it does

Runs a recursive multi-iteration research pipeline: a planner generates three search queries per cycle, `CALL PARALLEL` dispatches all three searches and fact extractions concurrently, a synthesizer decides whether to finalize or continue researching, and accumulated notes carry forward as context into the next planning cycle. A forced fallback terminates the loop gracefully at the iteration cap with a concise report rather than truncating mid-cycle.

## Real-world use cases

- **Literature surveys**: Generate a structured research report on a technical topic by iteratively querying, extracting, and synthesizing until the model self-assesses as sufficiently informed
- **Due diligence research**: Investigate a company, person, or market by running parallel web lookups and accumulating evidence before producing a report
- **Competitive analysis**: Research multiple competitors simultaneously per cycle, building a comprehensive landscape view that grows with each iteration
- **Policy research**: Gather facts, precedents, and stakeholder positions from parallel sources and synthesize them into a structured policy brief

## Key SPL constructs

- `GENERATE planner(@topic, @feedback)` — query planning with accumulated feedback from prior cycles
- `CALL PARALLEL search_web(@query1) INTO @result1, search_web(@query2) INTO @result2, search_web(@query3) INTO @result3 END` — three concurrent web searches
- `CALL PARALLEL extract_facts(@result1) INTO @note1, ... END` — three concurrent fact extractions
- `GENERATE accumulate_notes(@notes, @note1, @note2, @note3)` — merge pass over retrieved notes
- `GENERATE synthesizer(@topic, @notes, @loop_count)` — decides "DECISION: finalize" or returns feedback for the next planning cycle
- `EVALUATE @decision WHEN contains("DECISION: finalize")` — early exit on sufficient evidence
- `CALL write_file(@out, @report, "w")` — writes the final report to disk

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@topic` | TEXT | _(required)_ | The research topic or question |
| `@out` | TEXT | `"report.txt"` | Path to write the final research report |
| `@max_iterations` | INTEGER | 2 | Maximum number of research cycles before forced finalization |

**Output:** `@report TEXT` — the synthesized research report

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/deep_research/deep_research.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Increase `--param max_iterations=5` for thorough research on complex topics where 2 cycles leave gaps
- Use `--adapter momagrid` to dispatch each `CALL PARALLEL` branch to a separate Momagrid worker node for true distributed research
- Add a citation-tracking `CALL append_to_file(@citations_file, @source_url)` inside each search branch for a source-grounded report
- Chain with `021_self_healing` to validate the final report against a structural schema before writing
