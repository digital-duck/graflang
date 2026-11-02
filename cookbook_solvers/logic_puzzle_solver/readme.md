# Recipe 82 — Logic Puzzle Solver

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/082_logic_puzzle_solver` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 1167 tokens in / 517 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install python-constraint`

## What this demonstrates

This recipe adds a verifier **class** that didn't exist yet in the cookbook: constraint satisfaction (CSP), distinct from numeric optimization (78's LP/PuLP) and symbolic algebra (67/75/77's SymPy/Sage). Zebra-style logic puzzles are classic CSPs — many candidate house/color/nationality/drink assignments, exactly one of which (if the puzzle is well-posed) satisfies every clue simultaneously.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language clues | **Probabilistic** | LLM (`formulate_csp_code`) | LLMs read prose; CSP solvers don't |
| Generate python-constraint code | **Probabilistic** | LLM | Model each category as CSP variables + constraints |
| Run backtracking solver | **Deterministic** | `python-constraint` | Enumerates ALL solutions exhaustively |
| Gate on uniqueness | **Deterministic** | `ASSERT is_unique()` | Formal boundary: only continue if EXACTLY one solution exists |
| Repair failed/wrong code | **Probabilistic** | LLM (`repair_csp_code`) | LLM sees the actual exception or Ambiguous/NoSolution verdict |
| Interpret result | **Probabilistic** | LLM (`interpret_csp_result`) | Plain-English explanation of the verified answer |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated answer matches the solver's unique solution |

**Key property:** the LLM never solves the puzzle by hand — it only translates clues into a CSP model. `python-constraint`'s exhaustive search is what actually proves the answer, and "Unique" vs "Ambiguous" vs "NoSolution" is a categorical, unambiguous verdict — exactly like PuLP's Optimal/Infeasible in recipe 78.

## Setup

```bash
conda activate spl123
pip install python-constraint
```

### Why python-constraint (not z3-solver)?

The README findings session that proposed this recipe flagged the choice between `python-constraint` and `z3-solver` as a judgment call. This recipe uses **python-constraint**:

- Pure Python, no compiled solver binary — lighter dependency footprint than z3's ~30MB native wheel
- Its `Problem` / `addVariable` / `addConstraint` / `AllDifferentConstraint` vocabulary maps directly onto how zebra-style puzzles are naturally described (one variable per category-value, `AllDifferent` per category, one lambda constraint per clue)
- `getSolutions()` (not just "is it satisfiable") gives an exhaustive solution count for free, which is exactly the "Unique/Ambiguous/NoSolution" gate this recipe needs

**z3-solver is the better choice** if a future puzzle needs richer arithmetic or boolean theories (e.g. mixing integer inequalities with the CSP), which plain finite-domain CSP doesn't reach as naturally.

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM works through the clues in prose, one at a time — no CSP solver at all. This is exactly where LLMs are known to confidently violate an earlier clue while satisfying a later one, without noticing.
- **`enable_solver=true`** (ARM A, default): the LLM writes runnable `python-constraint` code modeling every category and clue; `run_constraint()` executes it; `ASSERT is_unique(@solution)` gates on the solver finding EXACTLY one solution (repair loop up to `max_tries`, fed the real exception or the Ambiguous/NoSolution verdict); the LLM narrates the verified unique solution and restates a `Final answer:` line, cross-checked by `classify_roundtrip()`.

## Run

```bash
# Default puzzle (3-house zebra-lite: who drinks Coffee?)
graf run cookbook_solvers/logic_puzzle_solver/logic_puzzle_solver.graph.yaml --llm claude_cli

# Unaided baseline arm
graf run cookbook_solvers/logic_puzzle_solver/logic_puzzle_solver.graph.yaml \
    --llm claude_cli --param enable_solver=false
```

## Default problem

> There are 3 houses in a row, numbered 1 to 3 from left to right. Each house has a unique color (Red, Green, Blue), is occupied by a person of a unique nationality (Brit, Swede, Dane), and that person drinks a unique beverage (Tea, Coffee, Milk). Clues: (1) The Brit lives in the Red house. (2) The Swede drinks Tea. (3) The Dane lives in house 1. (4) The owner of the Green house drinks Coffee. (5) The Blue house is house 2. Who drinks Coffee?

**Known unique solution** (verifiable by hand): house 1 = Green/Dane/Coffee, house 2 = Blue/Swede/Tea, house 3 = Red/Brit/Milk → **the Dane drinks Coffee**.

Verified end-to-end (2026-07-17) with `--llm claude_cli`: correct python-constraint code on the first attempt, `ASSERT is_unique` passed, round-trip check returned `match`. Local 7B-class models (gemma3, qwen2.5-coder) occasionally mis-model a clue or use an incorrect `addConstraint` call arity and exhaust `max_tries` — the repair loop and graceful failure path both function correctly in that case; it is a model-capability limit, not a defect in the harness (the same effect recipe 78 documents for weaker models against PuLP).

## Execution flow

```
GENERATE formulate_csp_code(@problem)      -- LLM models clues as CSP
    │
CALL run_constraint(@code)                 -- python-constraint solves exhaustively
    │
WHILE @tries < @max_tries                  -- repair loop on Error/Ambiguous/NoSolution
    │
ASSERT is_unique(@solution)                -- hard gate: AssertionError if not Unique
    │
GENERATE interpret_csp_result(...)          -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution)  -- LLM's stated answer vs ground truth
    │
CALL format_report(...)                    -- Markdown report
```

## Exception handling

If the solver cannot reach a Unique solution within `max_tries` (stuck at Error, Ambiguous, or NoSolution), `ASSERT is_unique` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning a guessed answer.
