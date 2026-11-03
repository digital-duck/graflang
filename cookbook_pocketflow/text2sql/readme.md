# 033 — Text-to-SQL  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/033_text2sql` with `spl3 util spl2graph` (AST-direct, no model involved); source `text2sql.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-text2sql](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-text2sql)
**Difficulty:** ★★☆
**Category:** data

## What it does

Converts natural language questions to SQLite queries with automatic self-repair: the LLM generates SQL from the database schema, a deterministic executor runs it against the live database, and if execution fails the LLM receives the exact error message and rewrites the query — repeating until success or the attempt budget is exhausted. Schema introspection is deterministic; only query generation and debugging involve LLM calls.

## Real-world use cases

- **Analyst self-service**: Let business analysts query any SQLite database in plain English without writing SQL, with built-in retry on syntax or schema errors
- **Customer support dashboards**: Enable support agents to ask data questions ("how many tickets were opened last week?") against a live support database without a data engineer
- **Embedded data assistants**: Add natural language query capability to any application that uses SQLite as its storage layer
- **Data exploration tools**: Allow data scientists to prototype queries against unfamiliar schemas by describing intent rather than looking up column names

## Key SPL constructs

- `CREATE TOOL_API read_db_schema(db_path)` — introspects all tables via `sqlite_master` and returns their CREATE TABLE DDL
- `CREATE TOOL_API execute_sql(db_path, sql)` — runs the SQL against SQLite; returns JSON rows or `{"rows_affected": N}` for non-SELECT statements
- `CREATE FUNCTION sql_from_nl(schema, question)` — LLM generates raw SQL from the schema and question (no markdown, no explanation)
- `CREATE FUNCTION debug_sql(sql, error_msg, schema)` — LLM rewrites a failing query given the exact error
- `WHILE @attempts < @max_attempts DO` — self-repair loop
- `EVALUATE @exec_result WHEN contains("error:")` — branches to the debug step vs. early exit on success

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@db_path` | TEXT | `"database.db"` | Path to the SQLite database file |
| `@question` | TEXT | `"How many rows are in each table?"` | Natural language question to answer |
| `@max_attempts` | INTEGER | 3 | Maximum number of generate-execute-debug cycles |

**Output:** `@result TEXT` — JSON result set from the successful query execution

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/text2sql/text2sql.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `GENERATE explain_result(@question, @result)` step after successful execution to produce a human-readable interpretation of the JSON result set
- Extend `read_db_schema` to include sample row values for each table, improving LLM accuracy on unfamiliar schemas
- Replace the SQLite tools with PostgreSQL or DuckDB equivalents — the .spl workflow remains unchanged (DODA)
- Chain with `030_lead_generation` to query a leads database and pass results to the enrichment pipeline
