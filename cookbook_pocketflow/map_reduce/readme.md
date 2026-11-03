# 006 — Map Reduce  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/006_map_reduce` with `spl3 util spl2graph` (AST-direct, no model involved); source `map_reduce.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-map-reduce](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-map-reduce)
**Difficulty:** ☆☆☆
**Category:** basics

## What it does

Screens a directory of resumes against a set of criteria by mapping an LLM scoring function over each resume in parallel batches of three, then reducing the scored results into a ranked, filtered executive summary report. The map phase uses `CALL PARALLEL` to process three resumes concurrently per loop iteration; the reduce phase aggregates scores, ranks candidates, partitions them into qualified/rejected lists, and generates an executive-ready report.

## Real-world use cases

- **High-volume recruiting**: Process hundreds of applicant resumes against a job's evaluation criteria within minutes, producing a ranked shortlist with scoring rationale
- **Grant program management**: Score applications against funding criteria at scale, surfacing the highest-fit candidates for human review
- **Vendor selection**: Evaluate RFP responses from multiple suppliers against weighted criteria and produce a comparative ranking report
- **Academic admissions**: Screen applicant portfolios against program requirements and generate a triage report for admissions committees

## Key SPL constructs

- `CREATE TOOL_API list_resume_files(directory)` — scans a directory for resume files (.txt, .pdf, .docx, .md, .rtf)
- `CREATE TOOL_API aggregate_scores(all_evaluations)` — extracts numeric scores and computes summary statistics
- `CREATE TOOL_API rank_candidates(all_evaluations)` — sorts candidates by score descending
- `CREATE TOOL_API filter_candidates(ranked, threshold, filter_type)` — partitions into qualified/rejected
- `CALL PARALLEL evaluate_single_resume(@path1, @criteria) INTO @eval1, ... END` — 3 concurrent LLM evaluations per loop
- `WHILE @i < @max_iterations DO` — outer loop over resume batches
- `GENERATE generate_summary_report(...)` — executive-level synthesis of all results

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@resume_dir` | TEXT | `"./resumes"` | Directory containing resume files |
| `@criteria` | TEXT | `"relevant work experience, technical skills, educational background, communication clarity"` | Comma-separated evaluation criteria |
| `@threshold` | TEXT | `"7"` | Minimum score (0–10) to classify as qualified |
| `@max_iterations` | INTEGER | 20 | Maximum batch iterations (covers up to 60 resumes) |

**Output:** `@report TEXT` — executive summary with ranked candidates, score statistics, and recommended next steps

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/map_reduce/map_reduce.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Deploy to Momagrid with `--adapter momagrid` to distribute each `evaluate_single_resume` call across different worker nodes for true parallel execution
- Increase batch size from 3 to larger values by extending the `CALL PARALLEL` block
- Add `EXCEPTION WHEN` handling to skip corrupt or unreadable resume files without aborting the pipeline
- Pipe the output JSONL into a downstream `033_text2sql` workflow to query results via natural language
