# Recipe 86 — Financial Calculation Verifier

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/086_financial_calc_verifier` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Category:** reasoning · **Tier:** 2 · **Requires:** stdlib `decimal` only — no new pip dependency

## What this demonstrates

This recipe targets compound-interest and loan-amortization word problems, a business-facing domain close in spirit to the credit-risk/regulatory-audit recipes (48/49) but ties its correctness check to **arithmetic**, not policy language. LLMs are fluent at describing the right formula in prose but routinely drop a term, use the wrong compounding period, or round early and compound the error. The verifier here is the closed-form formula itself, recomputed with stdlib `decimal` — exact, no floating-point drift.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language financial problem | **Probabilistic** | LLM (`formulate_finance_code`) | LLMs read prose; `decimal` doesn't |
| Generate Decimal-arithmetic code | **Probabilistic** | LLM | Implements the correct closed-form formula |
| Run exact arithmetic | **Deterministic** | stdlib `decimal` | Exact fixed-precision arithmetic, no float rounding drift |
| Gate on success | **Deterministic** | `ASSERT is_ok()` | Formal boundary: only continue if the calculation ran without error |
| Repair failed code | **Probabilistic** | LLM (`repair_finance_code`) | LLM sees the actual exception (e.g. mixed Decimal/float) |
| Interpret result | **Probabilistic** | LLM (`interpret_finance_result`) | Plain-English explanation of the verified answer |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated dollar figure matches the Decimal-computed ground truth (1 cent / 0.5% tolerance) |

**Key property:** `Decimal` computed from string literals (never `Decimal(0.06)`, which inherits float imprecision) guarantees the same exact result every run — no floating-point noise to explain away, unlike a numeric-fuzzy comparison against a float computation.

## Setup

No installation needed — `decimal` is part of the Python standard library.

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM does the arithmetic itself in prose — no verifier at all. This is where models often use the annual rate directly instead of dividing by the compounding frequency, or round intermediate values too early.
- **`enable_solver=true`** (ARM A, default): the LLM writes runnable `decimal`-based code implementing the correct formula (compound interest or amortization); `run_finance()` executes it; `ASSERT is_ok(@solution)` gates on clean execution (repair loop up to `max_tries`, fed the real exception); the LLM narrates the verified dollar figure and restates a `Final answer:` line, cross-checked by `classify_roundtrip()`.

## Run

```bash
# Default problem (5-year loan amortization)
graf run ~/.graflang/solvers/financial_calc_verifier/financial_calc_verifier.graph.yaml --llm claude_cli

# Custom problem
graf run ~/.graflang/solvers/financial_calc_verifier/financial_calc_verifier.graph.yaml \
    --llm ollama:gemma4 \
    --param problem="If you invest \$5,000 at 4% annual interest, compounded quarterly, what is it worth after 10 years?"

# Unaided baseline arm
graf run ~/.graflang/solvers/financial_calc_verifier/financial_calc_verifier.graph.yaml \
    --llm claude_cli --param enable_solver=false
```

## Default problem

> A $10,000 loan has a 6% annual interest rate, compounded monthly, and is paid off in equal monthly installments over 5 years (60 months). What is the fixed monthly payment?

**Known reference answer** (standard amortization formula, verifiable against any loan calculator): **$193.33/month** (total paid $11,599.80, total interest $1,599.80).

Verified end-to-end (2026-07-17) with `--llm claude_cli`: correct amortization-formula code on the first attempt, `ASSERT is_ok` passed, computed `$193.33` exactly matching the reference value, round-trip check returned `match`.

## Execution flow

```
GENERATE formulate_finance_code(@problem)   -- LLM writes exact Decimal code
    │
CALL run_finance(@code)                     -- decimal module computes exactly
    │
WHILE @tries < @max_tries                   -- repair loop on Error
    │
ASSERT is_ok(@solution)                     -- hard gate: AssertionError if not OK
    │
GENERATE interpret_finance_result(...)        -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution)  -- LLM's stated answer vs ground truth
    │
CALL format_report(...)                     -- Markdown report
```

## Exception handling

If the Decimal calculation cannot complete cleanly within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning a hallucinated dollar figure.
