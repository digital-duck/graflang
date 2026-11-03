# 017 — Judge (Evaluator-Optimizer)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/017_judge` with `spl3 util spl2graph` (AST-direct, no model involved); source `judge.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-judge](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-judge)
**Difficulty:** ★☆☆
**Category:** quality-control

## What it does

Implements the evaluator-optimizer loop: an LLM generates a draft, a second LLM judge scores it against rubric criteria and returns a structured VERDICT, and the workflow retries with the judge's feedback until the draft passes or the retry cap is reached. Early return via `RETURN WITH status="pass"` exits the loop immediately on acceptance — no wasted iterations.

## Real-world use cases

- **Marketing copy review**: Automatically iterate on product descriptions, taglines, or ad copy until they meet a quality bar defined by rubric criteria
- **Technical documentation generation**: Generate and judge API documentation for clarity, completeness, and accuracy until a quality threshold is reached
- **Creative writing assistance**: Iteratively refine poems, story openings, or pitch paragraphs against defined aesthetic criteria without manual review at each step
- **LLM benchmark generation**: Produce questions or problem statements that pass a difficulty and unambiguity judge before being added to an eval dataset

## Key SPL constructs

- `GENERATE generate_draft(@task, @feedback)` — initial generation and subsequent retries incorporating judge feedback
- `GENERATE evaluate_draft(@task, @draft)` — judge returning a structured `VERDICT: PASS` or `VERDICT: FAIL` with critique
- `EVALUATE @judgment WHEN contains("VERDICT: PASS")` — exits loop via `RETURN WITH status="pass"` immediately on acceptance
- `WHILE @attempts < 3` — bounded retry budget
- `RETURN WITH status="pass"` / `status="max_attempts"` — named outcome signaling for caller workflows

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@task` | TEXT | _(required)_ | The generation task description or topic |
| `@max_retries` | INTEGER | 3 | Maximum number of generate-judge cycles |

**Output:** `@final_description TEXT` — the first draft that passed the judge, or the best attempt after max retries

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/judge/judge.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Use a stronger model (e.g., `claude-opus-4-6`) as the judge and a faster model for generation to optimize cost-per-pass
- Parameterize the rubric criteria so the same workflow applies to technical, creative, or regulatory text with a `--param rubric_file=` override
- Accumulate all judge feedback across retries with `CALL list_append` and use the full history as context for each new generation
- Chain multiple judge workflows in sequence, each checking a different quality dimension (accuracy, tone, length)
