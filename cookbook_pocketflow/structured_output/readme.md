# 002 — Structured Output  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/002_structured_output` with `spl3 util spl2graph` (AST-direct, no model involved); source `structured_output.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-structured-output](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-structured-output)
**Difficulty:** ☆☆☆
**Category:** basics

## What it does

Parses an unstructured plain-text resume into a validated YAML candidate record containing contact info, work history, and matched skills. Three LLM extractions (candidate info, work experience, skill matching) are followed by a deterministic field completeness check, then a YAML generation and validation loop that retries up to three times if the LLM produces malformed output. The result is a normalized, schema-conforming record ready for downstream ATS ingestion or reporting.

## Real-world use cases

- **HR / ATS pipelines**: Bulk-parse thousands of incoming resumes into a normalized schema for candidate ranking and database ingestion
- **Recruiting agencies**: Automatically match candidates against a client-supplied skill list and generate structured profiles for shortlisting
- **Compliance reporting**: Extract structured employment history from document uploads for background-check workflows
- **Talent analytics**: Feed structured candidate records into analytics pipelines to identify skill gaps across an applicant pool

## Key SPL constructs

- `CREATE TOOL_API check_required_fields(...)` — deterministic completeness check before expensive YAML generation
- `CREATE TOOL_API validate_yaml(yaml_doc)` — YAML syntax validation gate
- `GENERATE extract_candidate_info(@resume_text)` — extracts name and email as JSON
- `GENERATE parse_work_experience(@resume_text)` — produces a JSON array of job entries
- `GENERATE match_skills(@resume_text, @work_experience, @skill_list)` — maps resume content to a predefined skill list
- `EVALUATE @fields_check WHEN contains("complete")` — branches on field completeness
- `WHILE @i < @max_yaml_retries DO` — retry loop for YAML self-correction
- `GENERATE fix_yaml_errors(@yaml_doc, @yaml_result)` — LLM fixes its own syntax errors

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@resume_path` | TEXT | `"cookbook-pocketflow/002_structured_output/data/resume.txt"` | Path to the plain-text resume file |
| `@skill_list_path` | TEXT | `"cookbook-pocketflow/002_structured_output/data/skills.txt"` | Path to the newline-delimited skill list |
| `@max_yaml_retries` | INTEGER | 3 | Maximum YAML self-correction attempts |

**Output:** `@output_record TEXT` — validated YAML candidate record, or a missing-fields message

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/structured_output/structured_output.graph.yaml \
    --llm claude_cli:claude-sonnet-5-5
#    --llm ollama:gemma4
```

### ToDO
- try different models and evaluate the match accuracy

## Extend it

- Add `CALL PARALLEL` to process batches of resumes concurrently against the same skill list
- Replace the skill list file with a database lookup via a `CREATE TOOL_API` that queries your ATS
- Add an `EXCEPTION WHEN` block to handle missing resume files gracefully and log failures per item
- Swap `--llm` to compare extraction accuracy across models using the same ground-truth resume
