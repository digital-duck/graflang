# Recipe 90 — Physics Conservation Check

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/090_compsci_physics` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 551 tokens in / 198 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `numpy` (already a project dependency, no new install)

## What this demonstrates

This recipe opens the **computational-science** application domain (companion recipes: `91_compsci_chemistry`, `92_compsci_materials`) with the richest oracle in that domain: **conservation laws**. On a 1-D collision problem, the LLM's most common failure mode isn't the algebra — it's returning a final state that silently *violates* momentum or (for an elastic collision) kinetic-energy conservation. Every sanity check a physics grad student runs by hand before trusting a result — "does momentum balance? does energy balance?" — becomes a machine-checkable `ASSERT` predicate here.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language collision problem | **Probabilistic** | LLM (`formulate_conservation_code`) | LLMs read prose; conservation checkers don't |
| Generate NumPy code | **Probabilistic** | LLM | Compute final-state velocities |
| Independently recompute invariants | **Deterministic** | `run_conservation_check()` | Never trusts the code's own self-report — recomputes momentum/KE before vs. after from the reported values |
| Gate on conservation | **Deterministic** | `ASSERT is_ok()` | Formal boundary: only continue if momentum (and energy, if elastic) is conserved within 1% |
| Repair failed code | **Probabilistic** | LLM (`repair_conservation_code`) | LLM sees the actual conservation-law violation |
| Interpret result | **Probabilistic** | LLM (`interpret_conservation_result`) | Plain-English explanation of the verified answer |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated final velocity matches the verified value (0.5% tolerance) |

**Key property:** conservation of momentum is never optional — it holds for *every* collision, elastic or not, and is independently recomputed from the code's own reported values rather than trusted. This mirrors recipe 83's `DimensionalityError`: a categorical, hand-checkable physical law standing in for a numeric-fuzzy grader.

## Setup

No new dependency — NumPy is already required by the cookbook.

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM works the collision problem in prose, applying conservation laws "in its head." This is exactly where models are known to report a plausible-looking final velocity that doesn't actually balance momentum.
- **`enable_solver=true`** (ARM A, default): the LLM writes runnable NumPy code reporting masses/velocities in a `_result` dict; `run_conservation_check()` independently recomputes total momentum and kinetic energy before/after; `ASSERT is_ok(@solution)` gates on both being conserved within tolerance (repair loop up to `max_tries`, fed the real violation); the LLM narrates the verified velocity and restates a `Final answer:` line, cross-checked by `classify_roundtrip()`.

## Run

```bash
# Default problem (elastic collision, equal masses: velocities swap)
graf run cookbook_solvers/compsci_physics/physics_conservation.graph.yaml --llm claude_cli

# Custom problem
graf run cookbook_solvers/compsci_physics/physics_conservation.graph.yaml \
    --llm ollama:gemma3 \
    --param problem="A 3 kg cart at 4 m/s collides and sticks to a stationary 1 kg cart. What is their common final velocity, in m/s?"

# Unaided baseline arm
graf run cookbook_solvers/compsci_physics/physics_conservation.graph.yaml \
    --llm claude_cli --param enable_solver=false
```

## Default problem

> A 2 kg ball moving at 5 m/s strikes a stationary 2 kg ball head-on in a perfectly elastic collision. What is the final velocity of the first ball, in m/s?

**Known closed-form answer:** equal masses in an elastic collision exchange velocities — ball 1 stops (**0 m/s**), ball 2 moves off at 5 m/s.

Verified end-to-end (2026-07-19) with `--llm claude_cli`: correct NumPy code on the first attempt using the standard 1-D elastic-collision formulas, `ASSERT is_ok` passed (momentum 10.0→10.0, KE 25.0→25.0), round-trip check returned `match`.

## Execution flow

```
GENERATE formulate_conservation_code(@problem)   -- LLM writes collision code
    │
CALL run_conservation_check(@code)               -- independently recomputes momentum/KE
    │
WHILE @tries < @max_tries                        -- repair loop on conservation violation
    │
ASSERT is_ok(@solution)                          -- hard gate: AssertionError if not OK
    │
GENERATE interpret_conservation_result(...)       -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution)    -- LLM's stated answer vs ground truth
    │
CALL format_report(...)                          -- Markdown report
```

## Exception handling

If momentum (or, for an elastic collision, kinetic energy) cannot be reconciled within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning a physically-inconsistent velocity.

## Why this recipe next

Opens Domain 1 (Computational Science) from the post-TMLR roadmap: conservation laws as correctness oracles are a physicist's-eye-view companion to the η_AI energy-efficiency framing already explored elsewhere in this cookbook — best author fit, and the domain where agentic-workflow research is currently most active (materials discovery, simulation-in-the-loop).
