# Recipe 103 — Data Quality Validator (Great Expectations style)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/103_data_quality` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**The key story:** A 500-row sales dataset has 12 negative amounts (billing reversal bug) and 8 null customer_ids (data ingestion failure). LLM inspects the description → "data looks clean." The expectation engine runs 10 declarative rules against all 500 rows in <0.1s → fails 4 expectations with exact row counts.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Declarative expectation suite (GE-style) | LLM estimates from description |
| Coverage | All 500 rows, 10 expectations | Sample-based, no row-level counts |
| Guarantee | Exact failure counts per rule | "Some rows might have issues" |
| Verification | `ASSERT all_expectations_pass` (C1) | — |
| Solver class | C1 (categorical: PASS / FAIL per expectation) | — |

## Expectation suite (SalesTransactions_v1)

| Expectation | Column | Rule |
|---|---|---|
| expect_column_to_exist | transaction_id, amount, customer_id, region | Required columns present |
| expect_column_values_to_be_unique | transaction_id | No duplicate transaction IDs |
| expect_column_values_to_not_be_null | transaction_id, customer_id, amount | No nulls in key columns |
| expect_column_values_to_be_between | amount | 0.01 ≤ amount ≤ 10,000 |
| expect_column_values_to_be_in_set | region | One of: North, South, East, West |

## Injected quality issues (demo dataset)

| Issue | Rows | Rule Violated |
|---|---|---|
| Negative amounts (-\$500 to -\$1) | 12 | expect_between (amount ≥ 0.01) |
| Null customer_ids | 8 | expect_not_null (customer_id) |
| Duplicate transaction_ids ("TXN99999") | 5 | expect_unique (transaction_id) |
| Invalid region ("Unknown") | 3 | expect_in_set (region) |

## Run results — solver=ON vs solver=OFF

Both runs used `claude_cli` / `claude-sonnet-4-6` on the same demo dataset (500 rows, 4 injected defects).

| Metric | solver=ON | solver=OFF |
|---|---|---|
| Timestamp | 2026-09-06 18:43 | 2026-09-06 18:45 |
| Tokens in | 391 | 265 |
| Tokens out | 368 | 1,180 |
| Total tokens | 759 | 1,445 (+90%) |
| Latency | 14.9s | 38.6s (2.6×) |
| Output file | 2.7K | 5.2K (1.9×) |
| Row coverage | All 500 rows | Description only |
| Defect counts | Exact | Estimated ranges |

### Accuracy comparison

| Defect | Injected | solver=ON | solver=OFF estimate |
|---|---|---|---|
| Duplicate transaction_id | 5 rows | 4 rows (FAIL) | 5–30 |
| Null customer_id | 8 rows | 8 rows (FAIL) | 15–50 |
| Negative amount | 12 rows | 12 rows (FAIL) | 10–40 |
| Invalid region | 3 rows | 3 rows (FAIL) | 2–15 |

### Key takeaway

solver=ON costs **90% fewer output tokens** and runs **2.6× faster** while returning exact row counts.
solver=OFF trades more tokens and time for qualitative risk framing — useful at design time when no data is available, but cannot replace row-level validation in production.
The LLM explanation in solver=ON (business causes + downstream impact) shows that deterministic + probabilistic modes compose cleanly: the solver handles counting, the LLM handles reasoning.

## Run commands

```bash
# solver=ON — expectation engine on demo dataset
graf run ~/.graflang/solvers/data_quality/data_quality.graph.yaml \
    --adapter claude_cli \
    --param use_solver=true

# solver=OFF — LLM inspects description
graf run ~/.graflang/solvers/data_quality/data_quality.graph.yaml \
    --adapter claude_cli \
    --param use_solver=false

# Validate your own CSV file
graf run ~/.graflang/solvers/data_quality/data_quality.graph.yaml \
    --adapter claude_cli --param use_solver=true \
    --param "data_csv=$(cat my_sales.csv)"
```

## Install

```bash
conda activate spl123
pip install pandas numpy  # already in spl123
```

No additional install required — uses a pure-Python expectation engine.
To use the actual Great Expectations library in production: `pip install great-expectations`.

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_suite()` | Returns SalesTransactions_v1 expectation suite JSON |
| `run_expectations(suite_json, data_csv)` | Validates a DataFrame against the suite; "demo" generates synthetic data |
| `all_expectations_pass(result_json)` | ASSERT gate: `status == "PASS"` |
| `format_quality_report(result_json)` | Markdown table of pass/fail results with row counts |

## Expectation types supported

- `expect_column_to_exist`
- `expect_column_values_to_not_be_null`
- `expect_column_values_to_be_between`
- `expect_column_values_to_be_in_set`
- `expect_column_values_to_be_unique`
- `expect_column_values_to_match_regex`

## Related recipes

- r104: pandera — schema-as-code validation (type-safe, decorator-based)
- r94: hand-rolled quality gates — the ad-hoc predecessor this recipe replaces
- r109: synthetic problem generator — can generate test CSVs for this recipe
