# Recipe 84 — SQL Verifier (Text-to-SQL)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/084_sql_verifier` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Category:** reasoning · **Tier:** 2 · **Requires:** stdlib `sqlite3` only — no new pip dependency

## What this demonstrates

This recipe's verifier has a different shape from the other rungs: instead of comparing the LLM's *prose* answer against a solver's output, it runs the LLM's own generated SQL against a real SQLite database and does a **row-level, order-insensitive diff** against an independently-authored ground-truth query over the identically-seeded data. "Run it and check the rows" is about as legible a round-trip story as this pattern gets.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language question | **Probabilistic** | LLM (`formulate_sql`) | LLMs read prose; SQLite doesn't |
| Generate SQL | **Probabilistic** | LLM | Query synthesis from intent |
| Execute SQL | **Deterministic** | `sqlite3` (stdlib) | Real execution against a seeded in-memory database |
| Gate on execution success | **Deterministic** | `ASSERT is_ok()` | Formal boundary: only continue if the LLM's SQL ran without error |
| Repair failed SQL | **Probabilistic** | LLM (`repair_sql`) | LLM sees the actual SQLite exception |
| Row-level diff | **Deterministic** | `classify_roundtrip()` | Order-insensitive, float-tolerant diff of the LLM's rows vs ground-truth rows |
| Interpret result | **Probabilistic** | LLM (`interpret_sql_result`) | Plain-English explanation of the verified rows |

**Key property:** the ground-truth SQL is written by the recipe author, never by the LLM — there is no circularity in what the diff is checked against. Both the LLM's SQL and the ground-truth SQL run against byte-identical seed data in the same call, so any row mismatch is attributable to the LLM's query logic, not data drift.

## Setup

No installation needed — `sqlite3` is part of the Python standard library.

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM is shown the schema and all rows as plain text and must answer the question by reasoning over them directly — no SQL is written or executed. This is where LLMs silently miscount rows or misapply a filter/aggregate in their head.
- **`enable_solver=true`** (ARM A, default): the LLM writes a SQL `SELECT` from the schema; `run_sql()` executes it against a freshly-seeded in-memory database; `ASSERT is_ok(@llm_result)` gates on clean execution (repair loop up to `max_tries`, fed the real SQLite error); `ground_truth_result()` runs the author-written reference query against the same seed data; `classify_roundtrip()` diffs the two row sets; the LLM then narrates the verified rows.

## Run

```bash
# Default question (average Engineering salary)
graf run ~/.graflang/solvers/sql_verifier/sql_verifier.graph.yaml \
    --llm claude_cli

# Unaided baseline arm
graf run ~/.graflang/solvers/sql_verifier/sql_verifier.graph.yaml \
    --llm claude_cli --param enable_solver=false

# Custom question (also update the ground-truth SQL to match!)
graf run ~/.graflang/solvers/sql_verifier/sql_verifier.graph.yaml \
    --llm claude_cli \
    --param question="How many employees were hired before 2020?" \
    --param ground_truth_sql="SELECT COUNT(*) FROM employees WHERE hire_year < 2020;"

```

## Default problem

> **Schema:** `employees(id, name, department, salary, hire_year)`, 6 seeded rows across Engineering/Sales/Marketing.
> **Question:** What is the average salary in the Engineering department?

**Known ground truth** (verifiable by hand): (95000 + 87000 + 110000) / 3 = **$97,333.33**.

Verified end-to-end (2026-07-17) with `--llm claude_cli`: `SELECT AVG(salary) FROM employees WHERE department = 'Engineering';` executed cleanly on the first attempt, row diff against the ground-truth query returned `match`.

## Execution flow

```
GENERATE formulate_sql(@question, @schema)  -- LLM writes SQL
    │
CALL run_sql(@llm_sql)                      -- SQLite executes against seeded DB
    │
WHILE @tries < @max_tries                   -- repair loop on SQL error
    │
ASSERT is_ok(@llm_result)                   -- hard gate: AssertionError if not OK
    │
CALL ground_truth_result(@ground_truth_sql) -- author's reference query, same seed data
    │
CALL classify_roundtrip(@llm_result, @truth_result)  -- row-level diff
    │
GENERATE interpret_sql_result(...)           -- LLM explains the verified rows
    │
CALL format_report(...)                     -- Markdown report
```

## Exception handling

If the LLM's SQL cannot execute cleanly within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning rows from a broken query.
