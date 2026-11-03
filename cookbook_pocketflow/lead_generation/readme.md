# 030 — Lead Generation  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/030_lead_generation` with `spl3 util spl2graph` (AST-direct, no model involved); source `lead_generation.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-lead-generation](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-lead-generation)
**Difficulty:** ★★☆
**Category:** sales

## What it does

Processes a CSV list of sales prospects through a three-stage enrichment and scoring pipeline: web-search-based company research, LLM-based lead qualification scoring, and conditional cold email generation for high-fit leads only. A WHILE loop iterates over each lead, skips empty rows, and writes high-scoring leads to a JSONL output file, separating the scoring and outreach concerns cleanly.

## Real-world use cases

- **B2B sales development**: Automatically enrich, score, and prioritize a CRM export, generating personalized cold outreach only for the highest-fit accounts
- **Partnership outreach**: Screen a list of potential technology partners, surface those with the best strategic alignment, and draft tailored partnership inquiry emails
- **Investor prospect research**: Score a list of target investors against a startup's profile and auto-generate personalized deck-sharing emails for tier-one matches
- **Competitive intelligence**: Enrich a list of competitor customers with public web data, score them as potential switcher prospects, and draft win-back messaging

## Key SPL constructs

- `CREATE TOOL_API parse_leads(raw_csv)` — strips the header row and returns individual lead records
- `CREATE TOOL_API extract_company_name(lead)` — extracts the company field from a CSV row
- `CREATE FUNCTION enrich_lead_context(lead, company_info)` — synthesizes a 3–5 sentence company context profile from web research
- `CREATE FUNCTION score_lead_fit(lead, enrichment)` — scores 0–10 and classifies as high/medium/low fit
- `CREATE FUNCTION classify_fit_score(score_text)` — LLM gate that returns "high", "medium", or "low"
- `CREATE FUNCTION generate_cold_email(lead, enrichment, score_text)` — writes a personalized outreach email for high-fit leads
- `CALL search_web(@company_name)` — web search tool used for company research
- `WHILE @i < @max_leads DO` — lead iteration loop with empty-row early exit via `EVALUATE @is_empty`
- `CALL append_to_file(@output_path, @entry)` — streams results to JSONL as leads are processed

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@lead_list_path` | TEXT | `"leads.csv"` | Path to the input CSV of lead records |
| `@output_path` | TEXT | `"output/scored_leads.jsonl"` | Path to write enriched and scored leads |
| `@max_leads` | INTEGER | 100 | Maximum number of leads to process |

**Output:** `@final_output TEXT` — formatted summary with scored leads and ready-to-send emails

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/lead_generation/lead_generation.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Use `CALL PARALLEL` to enrich and score multiple leads simultaneously, collapsing to sequential only for the file write step
- Add a `GENERATE personalize_subject_line(@lead, @email)` step to vary email subjects across the batch
- Chain with `034_communication` to send approved emails via an email API tool
- Use `--adapter momagrid` to distribute the enrichment + scoring pass across Momagrid worker nodes for large lead lists
