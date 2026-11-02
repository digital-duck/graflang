# Recipe 92 — Crystal Structure Check

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/092_compsci_materials` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 683 tokens in / 281 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `numpy`/stdlib `math` only — no new pip dependency

## What this demonstrates

Third recipe in the computational-science domain (companion to `90_compsci_physics` and `91_compsci_chemistry`). Given a unit cell's lattice parameters and a claimed crystal system, the LLM's most common failure mode is computing a plausible-looking theoretical density while silently (a) using lattice parameters inconsistent with the claimed system's own symmetry (calling something "cubic" with `a != b`), or (b) botching the Å³ → cm³ unit conversion or Avogadro's-number arithmetic. This recipe layers **two** independent oracles in one `ASSERT`: a categorical symmetry check and a numeric density round-trip — deliberately combining Pattern 1 and Pattern 2 verification (per Appendix I) in a single gate.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse crystallography word problem | **Probabilistic** | LLM (`formulate_materials_code`) | LLMs read prose; symmetry/density checkers don't |
| Generate Python code | **Probabilistic** | LLM | Report lattice parameters + computed density |
| Verify crystal-system symmetry | **Deterministic** | `run_materials_check()` | Checks the claimed system's own constraints (cubic: a=b=c, angles=90; hexagonal: a=b, γ=120; etc.) |
| Recompute volume + density | **Deterministic** | `run_materials_check()` | General triclinic volume formula + `density = Z·M/(N_A·V)`, independently, from the raw lattice parameters |
| Gate on both checks | **Deterministic** | `ASSERT is_ok()` | Formal boundary: only continue if symmetry holds AND density matches within 1% |
| Repair failed code | **Probabilistic** | LLM (`repair_materials_code`) | LLM sees the actual symmetry violation or density mismatch |
| Interpret result | **Probabilistic** | LLM (`interpret_materials_result`) | Plain-English explanation of the verified answer |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated density matches the verified value (1% tolerance) |

**Key property:** the symmetry check is categorical (a crystal system's constraints hold or they don't); the density check is numeric-fuzzy (independently recomputed from first principles, not just re-parsed from the LLM's own arithmetic). Combining both in one `ASSERT` demonstrates that a single verifier ladder rung can stack more than one oracle class.

## Setup

No new dependency — the symmetry and volume/density checks are pure stdlib Python (`math`).

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM works the crystallography problem in prose. This is exactly where models silently drop the Å³→cm³ conversion factor (`1e-24`) or misstate a crystal system's symmetry.
- **`enable_solver=true`** (ARM A, default): the LLM writes Python code reporting the crystal system, lattice parameters, Z, molar mass, and computed density in a `_result` dict; `run_materials_check()` independently checks the system's symmetry constraints and recomputes density from scratch; `ASSERT is_ok(@solution)` gates on both agreeing (repair loop up to `max_tries`, fed the real violation); the LLM narrates the verified density and restates a `Final answer:` line, cross-checked by `classify_roundtrip()`.

## Run

```bash
# Default problem (NaCl, cubic rock-salt structure; known density ~2.165 g/cm^3)
graf run cookbook_solvers/compsci_materials/materials_crystal.graph.yaml \
    --llm claude_cli

# Unaided baseline arm
graf run cookbook_solvers/compsci_materials/materials_crystal.graph.yaml \
    --llm claude_cli \
    --param enable_solver=false

# Custom problem
graf run cookbook_solvers/compsci_materials/materials_crystal.graph.yaml \
    --llm claude_cli \
    --param problem="Silicon has a cubic diamond structure with a = 5.431 Angstrom, Z = 8, molar mass 28.09 g/mol. What is its theoretical density in g/cm^3?"

```

## Default problem

> NaCl crystallizes in a cubic (rock-salt) structure with lattice parameter a = 5.640 Angstrom, all angles 90 degrees, Z = 4 formula units per unit cell, and molar mass 58.44 g/mol. What is its theoretical density, in g/cm^3?

**Known closed-form answer:** V = a³ = 179.406 Å³; density = 4 × 58.44 / (6.02214076e23 × 179.406e-24) ≈ **2.1636 g/cm³** (matches the commonly cited experimental value of ~2.165 g/cm³ within 0.1%).

Verified end-to-end (2026-07-19) with `--llm claude_cli`: correct code on the first attempt, `ASSERT is_ok` passed (symmetry_ok=True, density_ok=True), round-trip check returned `match`.

## Execution flow

```
GENERATE formulate_materials_code(@problem)   -- LLM writes lattice+density code
    │
CALL run_materials_check(@code)               -- independently checks symmetry + recomputes density
    │
WHILE @tries < @max_tries                     -- repair loop on symmetry/density mismatch
    │
ASSERT is_ok(@solution)                       -- hard gate: AssertionError if not OK
    │
GENERATE interpret_materials_result(...)       -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution) -- LLM's stated answer vs ground truth
    │
CALL format_report(...)                       -- Markdown report
```

## Exception handling

If symmetry and density cannot both be reconciled within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning an unverified density.

## Why this recipe next

Closes out Domain 1 (Computational Science) from the post-TMLR roadmap: "crystal structure validity, symmetry groups" from the oracle table, implemented without `pymatgen` — pure math keeps the recipe's dependency footprint at zero-new-installs, same bar as `84_sql_verifier` and `91_compsci_chemistry`.
