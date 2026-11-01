# Recipe 83 — Unit / Dimensional Check

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/083_unit_dimensional_check` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `pint` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install pint`

## What this demonstrates

This recipe targets physics/engineering word problems, where the LLM's most common failure mode isn't the underlying arithmetic — it's silently dropping or mismatching **units** (mixing m/s with km/h, forgetting to square time in `s = ½at²`, adding a length to a time). `pint` attaches units to every quantity and raises `DimensionalityError` the instant two incompatible quantities are combined, making it a categorical verifier rather than a numeric-fuzzy one.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language physics problem | **Probabilistic** | LLM (`formulate_pint_code`) | LLMs read prose; unit-checkers don't |
| Generate pint code | **Probabilistic** | LLM | Attach units, compute, convert |
| Run unit-aware calculation | **Deterministic** | `pint` | Tracks units through every operation |
| Gate on dimensional consistency | **Deterministic** | `ASSERT is_ok()` | Formal boundary: only continue if no `DimensionalityError` occurred |
| Repair failed code | **Probabilistic** | LLM (`repair_pint_code`) | LLM sees the actual dimensionality error |
| Interpret result | **Probabilistic** | LLM (`interpret_pint_result`) | Plain-English explanation of the verified answer |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated answer matches pint's computed magnitude (0.5% tolerance) |

**Key property:** a `DimensionalityError` is impossible to talk your way past — pint either lets the operation through (units are consistent) or raises. This mirrors PuLP's Optimal/Infeasible verdict in recipe 78: a categorical, non-negotiable check.

## Setup

```bash
conda activate spl123
pip install pint
```

`pint` bundles its own default unit registry (SI units plus common imperial/US units, `mile`, `hour`, `N`, etc.) — no extra configuration needed.

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM works the physics problem in prose, tracking units "in its head." This is exactly where models are known to silently forget a unit conversion (e.g. reporting m/s where km/h was asked) and never notice.
- **`enable_solver=true`** (ARM A, default): the LLM writes runnable `pint` code with every quantity constructed as `Q_(value, 'unit')`; `run_pint()` executes it; `ASSERT is_ok(@solution)` gates on the calculation running without a `DimensionalityError` (repair loop up to `max_tries`, fed the real pint error); the LLM narrates the verified magnitude and restates a `Final answer:` line, cross-checked by `classify_roundtrip()`.

## Run

```bash
# Default problem (kinematics: final speed after constant acceleration)
graf run ~/.graflang/solvers/unit_dimensional_check/unit_dimensional_check.graph.yaml \
    --llm claude_cli

# Unaided baseline arm
graf run ~/.graflang/solvers/unit_dimensional_check/unit_dimensional_check.graph.yaml \
    --llm claude_cli --param enable_solver=false

# Custom problem
graf run ~/.graflang/solvers/unit_dimensional_check/unit_dimensional_check.graph.yaml \
    --llm claude_cli \
    --param problem="A 500 g mass falls from 3 meters. What is its speed in mph when it hits the ground (g = 9.8 m/s^2)?"

```

## Default problem

> A car accelerates from rest at 2.5 m/s^2 for 12 seconds. What is its final speed, in km/h?

**Known closed-form answer** (verifiable by hand): v = a·t = 2.5 × 12 = 30 m/s = **108 km/h**.

Verified end-to-end (2026-07-17) with `--llm claude_cli`: correct pint code on the first attempt (`v = v0 + a*t`, converted with `.to('km/h')`), `ASSERT is_ok` passed, round-trip check returned `match`.

## Execution flow

```
GENERATE formulate_pint_code(@problem)     -- LLM writes unit-aware code
    │
CALL run_pint(@code)                       -- pint executes with units enforced
    │
WHILE @tries < @max_tries                  -- repair loop on DimensionalityError/Error
    │
ASSERT is_ok(@solution)                    -- hard gate: AssertionError if not OK
    │
GENERATE interpret_pint_result(...)         -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution)  -- LLM's stated answer vs ground truth
    │
CALL format_report(...)                    -- Markdown report
```

## Exception handling

If pint cannot compute a dimensionally-consistent answer within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning a unit-inconsistent number.

## Why this recipe next

Physics word-problems sit close to the η_AI energy-efficiency framing already explored elsewhere in this cookbook — correctly-unit-checked numeric answers are a natural next data point for that scaling-trend argument, per the README review session that proposed this recipe.
