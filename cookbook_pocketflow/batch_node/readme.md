# 012 — Batch Node  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/012_batch_node` with `spl3 util spl2graph` (AST-direct, no model involved); source `batch_node.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-batch-node](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-batch-node)
**Difficulty:** ★☆☆
**Category:** basics

## What it does

Processes arbitrarily large CSV files in fixed-size chunks, computing running totals and averages over a numeric column without loading the entire file into memory. The workflow reads one chunk at a time in a WHILE loop, computes per-chunk statistics via deterministic tool functions, accumulates the running total, and exits when an empty chunk signals end-of-file. This is the foundational pattern for LLM-augmented large-file batch processing in SPL.

## Real-world use cases

- **Financial reporting**: Aggregate sales, revenue, or cost columns from multi-million-row transaction exports without memory overflow
- **Operational analytics**: Compute running metrics (average latency, error rates) over large server log exports for dashboards
- **Data pipeline validation**: Scan a CSV in chunks to detect statistical anomalies (e.g., sudden drop in average) that would be invisible in sampled data
- **ETL preprocessing**: Accumulate per-column statistics over ingested CSVs as part of a data quality gate before downstream loading

## Key SPL constructs

- `CREATE TOOL_API read_csv_chunk(csv_path, chunk_size, offset)` — reads a fixed-size window of rows with header; returns empty string at EOF
- `CREATE TOOL_API compute_chunk_stats(chunk_csv, column)` — computes sum and count for the target column in a chunk
- `CREATE TOOL_API accumulate_totals(running_total, running_count, chunk_sum, chunk_count)` — incremental accumulator
- `CREATE TOOL_API advance_offset(offset, chunk_size)` — moves the read window forward
- `CREATE TOOL_API format_results(total, count)` — formats the final aggregation result
- `WHILE @i < @max_iterations DO` — chunk iteration loop with empty-chunk early exit
- `EVALUATE @chunk_empty WHEN contains("true")` — force-exits loop at EOF

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@csv_path` | TEXT | `"data.csv"` | Path to the CSV file to process |
| `@chunk_size` | TEXT | `"100"` | Number of rows per chunk |
| `@column` | TEXT | `"sales"` | Name of the numeric column to aggregate |
| `@max_iterations` | INTEGER | 10000 | Safety cap on total loop iterations |

**Output:** `@result TEXT` — formatted aggregation result with total, count, and average

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/batch_node/batch_node.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add an LLM step inside the loop to flag anomalous chunks (e.g., unusually high or low values) before accumulating
- Replace `compute_chunk_stats` with a multi-column aggregator to process several metrics in one pass
- Use `--adapter momagrid` to distribute chunk processing across worker nodes for very large files
- Write per-chunk results to a JSONL file with `CALL write_file(..., "a")` for resumable processing
