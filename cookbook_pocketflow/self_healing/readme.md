# 021 — Self Healing (Mermaid Generator)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/021_self_healing` with `spl3 util spl2graph` (AST-direct, no model involved); source `self_healing.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-self-healing-mermaid](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-self-healing-mermaid)
**Difficulty:** ★☆☆
**Category:** self-correction

## What it does

Generates a syntactically valid Mermaid diagram from a natural language description, with automatic self-repair on syntax errors. The LLM first produces a Mermaid definition, a deterministic validator checks it for parse errors, and if validation fails the LLM receives the error message and attempts a targeted fix — repeating up to the retry cap. This pattern generalizes to any code or structured-output generation task where a fast deterministic validator provides precise error feedback.

## Real-world use cases

- **Architecture documentation**: Auto-generate flowcharts, sequence diagrams, or entity-relationship diagrams from prose descriptions and guarantee they render in Mermaid without a human syntax-checking pass
- **API documentation pipelines**: Generate and validate sequence diagrams for API call flows as part of a CI step, rejecting invalid diagrams before they reach the documentation site
- **Educational diagram generation**: Let students describe a process in plain language and receive a syntactically correct Mermaid diagram they can refine, without needing to learn Mermaid syntax
- **Workflow visualization**: Automatically generate workflow diagrams from .spl files' Workflow I/O descriptions for README illustration

## Key SPL constructs

- `GENERATE generate_mermaid(@description)` — LLM produces an initial Mermaid diagram definition
- `CREATE TOOL_API validate_mermaid(mermaid_code)` — deterministic syntax checker; returns `"valid"` or an error message
- `CREATE TOOL_API fix_mermaid(mermaid_code, error_message)` — calls the LLM to produce a targeted fix given the exact error
- `WHILE @valid = "false" AND @retries < @max_retries DO` — self-repair loop
- `EVALUATE @validation WHEN contains("valid")` — exits loop on successful validation

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@description` | TEXT | _(required)_ | Natural language description of the diagram to generate |
| `@max_retries` | INTEGER | 3 | Maximum number of self-repair attempts |

**Output:** `@output TEXT` — the validated Mermaid diagram source

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/self_healing/self_healing.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Replace the Mermaid validator with a JSON schema validator, SQL parser, or Python linter to apply the same self-repair loop to different output types
- Add `CALL write_file` to save each intermediate attempt for debugging validator–LLM interactions
- After successful validation, add a `GENERATE describe_diagram(@mermaid_output)` step to produce human-readable alt text for accessibility
- Chain with `032_deep_research` to auto-generate process diagrams from research output
