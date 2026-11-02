# Recipe 85 — Property-Based Code Verification

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/085_property_based_code_verify` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (4 model calls, 1360 tokens in / 1223 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install hypothesis pytest`

## What this demonstrates

Recipe 79 upgraded recipe 50's LLM-as-tester step into a REAL pytest run, but the LLM still writes a handful of fixed **example** tests (`assert f(2,3) == 5`) — it can only catch bugs on inputs it happened to think of. This recipe goes one rung further: the LLM writes **properties** (invariants that must hold for ALL inputs of a given shape), and Hypothesis auto-generates hundreds of edge-case inputs (empty lists, negative numbers, duplicates, huge values) trying to falsify them.

| Recipe | Tests are... | Catches |
|---|---|---|
| 79 (pytest) | LLM-picked **examples** | Bugs the LLM happened to think to test |
| 85 (Hypothesis) | LLM-written **properties** | Bugs on ANY input matching the property's generator — including inputs no one thought of |

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Generate implementation | **Probabilistic** | LLM (`generate_implementation`) | Code synthesis from the spec |
| Generate properties | **Probabilistic** | LLM (`generate_properties`), independently from the code | Avoids circularity — a test derived from reading the code under test proves nothing |
| Run property-based tests | **Deterministic** | `hypothesis` + `pytest` (subprocess) | Auto-generates inputs, searches for a falsifying example |
| Gate on all-pass | **Deterministic** | `ASSERT all_properties_passed()` | Formal boundary: only continue if NO falsifying example was found |
| Repair test-harness errors | **Probabilistic** | LLM (`repair_properties`) | Only repairs a broken TEST FILE (import/syntax error) — never "fixes" a property to hide a real bug |
| Interpret result | **Probabilistic** | LLM (`interpret_hypothesis_result`) | Plain-English explanation of the verified (or falsified) result |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own narration agrees with whether Hypothesis actually passed or failed |

**Key design choice (inherited from recipe 79):** writing tests from the spec, not from the code, ensures independence. This recipe adds a second discipline on top: a genuine falsifying example (`status = "Failed"`) is treated as the deterministic verdict on the CURRENT implementation and is **not** repaired away — the repair loop only fires on `status = "Error"` (a broken test harness, e.g. a bad import), matching the fail-fast philosophy of recipe 78/79's ASSERT gates. A model cannot talk its way out of a real Hypothesis-found counterexample.

## Setup

```bash
conda activate spl123
pip install hypothesis pytest
```

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM writes the implementation and then self-reviews it by eye, exactly recipe 50's original (unreliable) approach — no test runner at all.
- **`enable_solver=true`** (ARM A, default): the LLM writes the implementation AND the Hypothesis properties (independently, both from the spec); `run_hypothesis()` executes both in a subprocess; `ASSERT all_properties_passed(@result)` gates on Hypothesis finding no falsifying example across its generated inputs; the LLM then narrates the verified result, and `classify_roundtrip()` checks that its narration's pass/fail claim actually agrees with the JSON verdict.

## Run

```bash
# Default spec (merge two sorted lists)
graf run cookbook_solvers/property_based_code_verify/property_based_code_verify.graph.yaml --llm claude_cli

# Custom spec
graf run cookbook_solvers/property_based_code_verify/property_based_code_verify.graph.yaml \
    --llm ollama:gemma3 \
    --param spec="Write a function is_palindrome(s: str) -> bool that ignores case and non-alphanumeric characters."

# Unaided baseline arm
graf run cookbook_solvers/property_based_code_verify/property_based_code_verify.graph.yaml \
    --llm claude_cli --param enable_solver=false
```

## Default spec

> Write a function `merge_sorted(a: list[int], b: list[int]) -> list[int]` that takes two ALREADY-SORTED lists of integers and returns a single sorted list containing all elements of both (duplicates included).

Verified end-to-end (2026-07-17) with `--llm claude_cli`: implementation + 5 independent properties (length, sortedness, element-preservation, commutativity, empty-list identity) generated; first properties draft errored (`status = "Error"`, a harness bug), the repair loop fixed it, and the second attempt passed all 5 properties (`status = "AllPassed"`) — a genuine, observed exercise of both the pass path and the repair path.

## Execution flow

```
GENERATE generate_implementation(@spec)     -- LLM writes the code under test
GENERATE generate_properties(@spec)         -- LLM writes properties, independently
    │
CALL run_hypothesis(@code, @properties)     -- pytest + Hypothesis execute in a subprocess
    │
WHILE @tries < @max_tries
    ├── status = "AllPassed" → exit loop (verified)
    ├── status = "Failed"    → exit loop (genuine falsifying example — do not repair away)
    └── status = "Error"     → repair the TEST HARNESS only, retry
    │
ASSERT all_properties_passed(@result)       -- hard gate: AssertionError unless AllPassed
    │
GENERATE interpret_hypothesis_result(...)    -- LLM explains the verified result
    │
CALL classify_roundtrip(@narrative, @result) -- LLM's pass/fail claim vs actual verdict
    │
CALL format_report(...)                     -- Markdown report
```

## Exception handling

If Hypothesis finds a falsifying example (`status = "Failed"`) or the harness cannot be repaired within `max_tries` (`status = "Error"`), `ASSERT all_properties_passed` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "falsified"` and `roundtrip = "unverifiable"`, embedding the Hypothesis output (including the falsifying example, when present) in the returned report rather than ever claiming success.
