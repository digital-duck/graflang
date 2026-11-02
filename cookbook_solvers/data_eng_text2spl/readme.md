# Recipe 94 — Text-to-SQL with Data-Quality Gates

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/094_data_eng_text2spl` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 466 tokens in / 215 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** stdlib `sqlite3` only — no new pip dependency

## What this demonstrates

Opens Domain 3 (Data Engineering) from the post-TMLR roadmap — Wen's professional home turf and SPL's largest practitioner audience. Recipe 84 already showed "run it and check the rows" for a single text-to-SQL query; this recipe extends that into the **data-quality gates** that make text-to-SQL enterprise-viable. It isn't enough that the LLM's SQL executes and returns rows — those rows must also survive the same invariant checks a data-governance team runs before trusting a number: referential integrity, non-empty results, and the classic Great-Expectations-style trick of **computing the same statistic two structurally independent ways and asserting they agree**.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language question | **Probabilistic** | LLM (`formulate_sql`) | LLMs read prose questions; quality gates don't |
| Generate SQL | **Probabilistic** | LLM | A single SELECT statement |
| Referential integrity gate | **Deterministic** | `run_quality_gated_sql()` | Every `orders.customer_id` must exist in `customers.id` |
| Two-independent-ways gate | **Deterministic** | `run_quality_gated_sql()` | `AVG(amount)` vs `SUM(amount)/COUNT(*)` over the same filter must agree within 1e-6 |
| Non-empty-result gate | **Deterministic** | `run_quality_gated_sql()` | The LLM's query must return at least one row |
| Execute LLM's SQL | **Deterministic** | stdlib `sqlite3` | Runs against a seeded in-memory database |
| Gate on all of the above | **Deterministic** | `ASSERT is_ok()` | Formal boundary: only continue if execution is clean AND every quality gate passed |
| Repair failed SQL | **Probabilistic** | LLM (`repair_sql`) | LLM sees the actual error or which gate failed |
| Row-diff round-trip | **Deterministic** | `classify_roundtrip()` | Order-insensitive, float-tolerant diff against an independently-authored ground-truth query |
| Interpret result | **Probabilistic** | LLM (`interpret_sql_result`) | Plain-English explanation of the verified, quality-gated answer |

**Key property:** the two-independent-ways check is the recipe's centerpiece — it's the same discipline as recipe 77's round-trip verification (Pattern 2 per Appendix I) applied to SQL aggregates instead of symbolic math: a number computed one way is not trusted until a structurally different computation confirms it.

## Setup

No new dependency — schema, seed data, and all quality gates are pure stdlib Python (`sqlite3`).

## Seeded schema

```
customers(id, name, segment)          -- Enterprise / SMB / Consumer
orders(id, customer_id, amount, order_date)
```

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM reads the printed schema and rows, then answers in prose with no SQL execution and no quality gates at all — exactly where models silently miscount rows or misread a JOIN in their head.
- **`enable_solver=true`** (ARM A, default): the LLM writes SQL; `run_quality_gated_sql()` checks referential integrity and two-way stat agreement (both independent of the LLM's query — properties of the seeded data itself), executes the LLM's SQL, requires a non-empty result, and row-diffs it against an independently-authored ground-truth query; `ASSERT is_ok(@solution)` gates on everything passing (repair loop up to `max_tries`, fed the real error/gate failure); the LLM narrates the verified, quality-gated answer.

## Run

```bash
# Default question (average Enterprise-segment order amount; known ground truth: $6,000.00)
graf run cookbook_solvers/data_eng_text2spl/text2sql_quality.graph.yaml \
    --llm claude_cli

# Unaided baseline arm
graf run cookbook_solvers/data_eng_text2spl/text2sql_quality.graph.yaml \
    --llm claude_cli \
    --param enable_solver=false

# Custom question (must also update ground_truth_sql / stat_sql_a / stat_sql_b to match)
graf run cookbook_solvers/data_eng_text2spl/text2sql_quality.graph.yaml \
    --llm ollama:gemma3 \
    --param question="What is the total order amount for the SMB segment?" \
    --param ground_truth_sql="SELECT SUM(o.amount) FROM orders o JOIN customers c ON o.customer_id=c.id WHERE c.segment='SMB'" \
    --param stat_sql_a="SELECT SUM(o.amount) FROM orders o JOIN customers c ON o.customer_id=c.id WHERE c.segment='SMB'" \
    --param stat_sql_b="SELECT COUNT(*) * AVG(o.amount) FROM orders o JOIN customers c ON o.customer_id=c.id WHERE c.segment='SMB'"

```

## Default question

> What is the average order amount for customers in the Enterprise segment?

**Known ground truth:** (5000 + 7000 + 6000) / 3 = **$6,000.00**.

Verified end-to-end (2026-07-19) with `--llm claude_cli`: correct SQL on the first attempt, all three quality gates passed (referential_ok=True, two_way_ok=True with AVG=SUM/COUNT=6000.0), row-diff round-trip returned `match`.

## Execution flow

```
GENERATE formulate_sql(@schema, @question)              -- LLM writes SQL
    │
CALL run_quality_gated_sql(@sql, @ground_truth_sql,      -- referential integrity + two-way
                            @stat_sql_a, @stat_sql_b)       stat agreement + execute + row-diff
    │
WHILE @tries < @max_tries                                -- repair loop on any gate failure
    │
ASSERT is_ok(@solution)                                  -- hard gate: AssertionError if not OK
    │
CALL classify_roundtrip(@solution)                       -- row-diff vs ground truth
    │
GENERATE interpret_sql_result(...)                        -- LLM explains the verified result
    │
CALL format_report(...)                                  -- Markdown report
```

## Exception handling

If the SQL cannot pass execution and all quality gates within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning an ungated number.

## Why this recipe next

Data-governance teams require exactly this: row-count sanity, referential integrity, and independent-recomputation cross-checks as `ASSERT` targets, with the zero-egress local-deployment story (Appendix G.6) already covering the compliance angle. Seeds exist — text-to-SQL is among the 42 migrated PocketFlow recipes — and this is the largest-practitioner-audience, most natural-enterprise-adoption-path domain of the three from the roadmap.
