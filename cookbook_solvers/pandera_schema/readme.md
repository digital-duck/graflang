# Recipe 104 — pandera Schema Validator

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/104_pandera_schema` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 202 tokens in / 226 out in total); reports three failed column checks on the sample data. A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The key story:** A 200-row employee payroll CSV has 6 rows with `salary=0` (data entry error) and 4 rows with `department="Temp"` (non-standard value). pandera validates all 200 rows against a typed schema in <0.1s and returns exact violation counts. LLM inspects a sample and misses both issues.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | pandera DataFrameSchema | LLM schema reasoning from description |
| Coverage | All 200 rows, all columns | Sample-based, no row-level counts |
| Contract | Typed columns, range checks, categoricals, uniqueness | "Should be positive salary, standard departments" |
| Verification | `ASSERT schema_passes` (C1) | — |
| Solver class | C1 (categorical: PASS / FAIL per column check) | — |

## Default schema (EmployeePayroll_v1)

| Column | Type | Checks |
|---|---|---|
| employee_id | int64 | unique, not null, > 999 |
| name | object | not null |
| department | object | isin [Engineering, Sales, HR, Finance, Operations] |
| salary | float64 | not null, > 0, < 500,000 |
| hire_year | int64 | not null, 2000 ≤ x ≤ 2026 |

## Injected violations (demo dataset)

| Violation | Rows | Check Failed |
|---|---|---|
| `salary = 0.0` | 6 | `salary > 0` |
| `department = "Temp"` | 4 | `isin [Engineering, Sales, HR, Finance, Operations]` |
| `name = None` | 3 | `name not null` |

## Run results — solver=ON (fixed) vs solver=OFF

All runs used `claude_cli` / `claude-sonnet-4-6` on the same demo dataset (200 rows, 3 injected violation types).

### Performance

| Metric | solver=ON (broken) | solver=ON (fixed) | solver=OFF |
|---|---|---|---|
| Timestamp | 2026-09-06 18:52:05 | 2026-09-06 19:02:01 | 2026-09-06 18:52:16 |
| Tokens in | 164 | 232 | 279 |
| Tokens out | 201 | 216 | 1,197 |
| Total tokens | 365 | 448 | 1,476 (+230%) |
| Latency | 14.4s | 12.9s | 57.7s (4.5×) |
| Row coverage | All 200 rows | All 200 rows | Description + schema only |
| Violations surfaced | 0 (bug) | 3 (correct) | 0 exact / fabricated samples |

### Accuracy comparison

| Violation | Injected | solver=ON broken | solver=ON fixed | solver=OFF |
|---|---|---|---|---|
| `salary = 0.0` | 6 rows | Not surfaced | **6 rows ✓** | Predicted (plausible) |
| `department = "Temp"` | 4 rows | Not surfaced | **4 rows ✓** | Predicted ("Marketing", wrong value) |
| `name = None` | 3 rows | Not surfaced | **3 rows ✓** | Not predicted |

### Bug and fix

**Before:** `format_schema_report` silently swallowed `ERROR` status — displayed `Status: FAIL / 0 violations / All column checks passed`, hiding the actual engine error. NaN null-samples were serialized as `NaN` (invalid JSON per spec).

**After two fixes in `tools.py`:**
- `validate_schema`: `groupby(..., dropna=False)` captures DataFrame-level checks; NaN samples replaced with `None` before `json.dumps` (valid JSON)
- `format_schema_report`: detects `status == "ERROR"` early and surfaces the error message instead of rendering a misleading empty-violation report; null samples display as `(null)` in the table

### Key takeaway

solver=ON (fixed) is **4.5× faster** and uses **70% fewer output tokens** than solver=OFF, while returning exact row counts the LLM cannot fabricate. solver=OFF correctly risk-ranked columns (`department` > `salary`) but invented specific failing records that don't exist in the data — useful for design-time reasoning, not for production validation. The LLM explanation in solver=ON (fixed) is concise and actionable because it reasons from real counts, not hypotheticals.

## Run commands

```bash
# solver=ON — pandera validates all 200 rows
graf run cookbook_solvers/pandera_schema/pandera_schema.graph.yaml \
    --llm claude_cli \
    --param use_solver=true

# solver=OFF — LLM reasons from schema description
graf run cookbook_solvers/pandera_schema/pandera_schema.graph.yaml \
    --llm claude_cli \
    --param use_solver=false

# Validate your own CSV
graf run cookbook_solvers/pandera_schema/pandera_schema.graph.yaml \
    --llm claude_cli \
    --param use_solver=true \
    --param data_csv="$(cat employees.csv)"
```

## Install

```bash
conda activate spl123
pip install pandera
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_schema()` | Returns EmployeePayroll_v1 schema JSON |
| `validate_schema(schema_json, data_csv)` | pandera validation; "demo" generates synthetic data |
| `schema_passes(result_json)` | ASSERT gate: `status == "PASS"` |
| `format_schema_report(result_json)` | Markdown table of violations with sample values |

## pandera vs Great Expectations (r103)

| | r103 (GE-style) | r104 (pandera) |
|---|---|---|
| API style | Rule suite JSON → validator | Schema class → `schema.validate(df)` |
| Integration | Standalone quality gate | Decorator on functions (`@pa.check_input`) |
| Best for | Production pipelines, CI checks | Library code, API input validation |
| Scale | Configurable (GE has data docs) | Lightweight, zero config |

## Related recipes

- r103: GE-style data quality validator (expectation suites)
- r78: constraint optimization — pandera can validate solver inputs
- r109: synthetic problem generator — generates test datasets for schema testing
