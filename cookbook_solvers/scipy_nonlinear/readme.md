# Recipe 114 — Constrained Nonlinear Optimization (scipy.optimize)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/114_scipy_nonlinear` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

Given a nonlinear profit function (pricing or logistics), find the profit-maximizing
decision using `scipy.optimize` — and verify the result by independent back-substitution.

**DODA**: same `.spl` spec runs on any adapter; only `--param method=` changes the scipy solver.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | scipy.optimize (SLSQP / Nelder-Mead / differential_evolution) | LLM heuristic estimate |
| Guarantee | Locally/globally optimal (method-dependent) | Plausible estimate, unverified |
| Verification | `ASSERT is_optimal` + back-substitution | Back-substitution only |
| Solver class | S028 — constrained nonlinear (SLSQP / global) | — |

## Architecture

The workflow uses three WORKFLOW declarations (same pattern as r116/r117):

```
nonlinear_opt (entry point)
  ├── formulates problem spec via LLM (EVALUATE pricing vs logistics)
  ├── calls solver_enabled() → "run_solver" or "run_llm" (unambiguous gate)
  └── EVALUATE @gate
        WHEN "run_solver" → CALL solver_on_nonlinear
        WHEN "run_llm"    → CALL solver_off_llm_nonlinear
  └── CALL save_report() → writes to @out_dir

solver_on_nonlinear
  ├── CALL solve_nonlinear (scipy) → @solution_json
  ├── ASSERT is_optimal
  ├── CALL verify_solution (back-substitution) → @verify_json
  └── GENERATE interpret_result → @interpretation

solver_off_llm_nonlinear
  ├── GENERATE estimate_optimum (LLM reasoning)
  ├── GENERATE extract_solution_json
  ├── CALL verify_solution
  └── GENERATE interpret_result
```

## Default problems

### Pricing (power demand curve)

```
D(p) = 10000 × p^(−1.5)
Unit cost:   $8
Fixed cost:  $200/period
Price range: [$6, $150]

Analytical optimum (Lerner rule):
  p* = ε × c / (ε − 1) = 1.5 × 8 / 0.5 = $24.00
  profit* = (24 − 8) × 85.05 − 200 ≈ $1,160.83  [SLSQP verified ✓]
```

### Logistics (quadratic revenue / congestion cost)

```
Revenue(x) = 20x − 0.02x²
Cost(x)    = 200 + 8x + 0.05x²
Profit(x)  = 12x − 0.07x² − 200
Volume range: [6, 150] units

Analytical optimum (MR = MC):
  x* = 12 / (2 × 0.07) = 85.71 units
  profit* = 12×85.71 − 0.07×85.71² − 200 ≈ $314.29  [SLSQP verified ✓]
```

## Run commands

```bash
# Pricing — SLSQP (gradient-based, default)
graf run ~/.graflang/solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml \
  --llm claude_cli \
  --param problem_type=pricing \
  --param method=SLSQP

# Pricing — differential_evolution (global search, no gradient needed)
graf run ~/.graflang/solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml \
  --llm claude_cli \
  --param problem_type=pricing \
  --param method=differential_evolution

# Logistics — Nelder-Mead (derivative-free)
graf run ~/.graflang/solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml \
  --llm claude_cli \
  --param problem_type=logistics \
  --param method=Nelder-Mead

# solver=OFF ablation — LLM estimates without scipy
graf run ~/.graflang/solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml \
  --adapter ollama -m gemma3 \
  --param problem_type=pricing \
  --param use_solver=false

# Custom pricing problem (higher elasticity)
graf run ~/.graflang/solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml \
  --llm claude_cli \
  --param problem_type=pricing \
  --param demand_scale=50000 \
  --param elasticity=2.0 \
  --param unit_cost=10 \
  --param x_min=5 --param x_max=200

# Write output to a custom directory
graf run ~/.graflang/solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml \
  --llm claude_cli \
  --param problem_type=pricing \
  --param out_dir=./results/r114
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `problem_type` | `pricing` | `pricing` or `logistics` |
| `method` | `SLSQP` | `SLSQP`, `Nelder-Mead`, `differential_evolution` |
| `max_iterations` | `1000` | Solver iteration budget (100–10000) |
| `use_solver` | `true` | `false` → LLM heuristic only (ablation) |
| `out_dir` | `./cookbook/114_scipy_nonlinear/output` | Directory to write the report file |
| `demand_scale` | `10000` | Pricing: D(p) scale coefficient |
| `elasticity` | `1.5` | Pricing: price elasticity exponent |
| `revenue_scale` | `20` | Logistics: linear revenue coefficient |
| `saturation` | `0.02` | Logistics: quadratic revenue penalty |
| `congestion` | `0.05` | Logistics: quadratic cost penalty |
| `unit_cost` | `8` | Variable cost per unit |
| `fixed_cost` | `200` | Fixed cost per period |
| `x_min` / `x_max` | `6` / `150` | Decision variable bounds |
| `min_demand` | `0` | Minimum demand constraint (0 = none) |

## TOOL_API reference

| Function | Purpose |
|---|---|
| `solve_nonlinear(problem_json, method, max_iterations)` | scipy constrained nonlinear solve |
| `verify_solution(problem_json, solution_json)` | Back-substitution: recomputes objective at x_opt |
| `is_optimal(solution_json)` | Returns True when scipy reports success and finite objective |
| `solver_enabled(use_solver)` | Returns `"run_solver"` or `"run_llm"` — unambiguous gate for EVALUATE |
| `save_report(report, out_dir, filename)` | Writes report text to `out_dir/filename` (creates dir if needed) |

## Optimization formulations

**Pricing:**
```
Maximize    (p − c) × S × p^(−ε) − F
Subject to  p ∈ [x_min, x_max]
            S × p^(−ε) ≥ min_demand   (optional)

Analytical solution: p* = ε × c / (ε − 1)   [only when min_demand = 0]
```

**Logistics:**
```
Maximize    (r × x − α × x²) − (F + c × x + β × x²)
         =  (r − c) × x − (α + β) × x² − F
Subject to  x ∈ [x_min, x_max]
            x ≥ min_demand            (optional)

Analytical solution: x* = (r − c) / (2 × (α + β))   [interior optimum]
```

## Verification gate

`ASSERT is_optimal(@solution_json)` halts the workflow if scipy did not converge.
`verify_solution` then recomputes the objective independently and reports `PASS` / `FAIL` / `SKIP`.

The ASSERT + back-substitution pattern appears in all solver recipes (r78, r98, r99) —
see solver-research-plan.md §2 for the 4-pillar framework.

## Sample output (pricing, solver=ON, SLSQP, claude_cli)

```
=== Nonlinear Optimization (scipy.optimize / pricing) ===

── Solver Result (solver=ON, method=SLSQP) ──────────────
{"success": true, "method": "SLSQP", "problem_type": "pricing",
 "x_opt": 24.0, "objective": 1160.8276, "n_iterations": 13,
 "message": "Optimization terminated successfully"}

── Verification ─────────────────────────────────────────────
{"verdict": "PASS", "x_opt": 24.0, "recomputed_objective": 1160.8276,
 "reported_objective": 1160.8276, "delta": 0.0, "notes": "all checks passed"}

── Business Interpretation ──────────────────────────────────
Set price to $24.00 — this maximizes profit at $1,160.83 per period.

Analytical check: p* = ε × c / (ε − 1) = 1.5 × $8 / 0.5 = $24.00 ✓
Scipy found this in 13 iterations and landed exactly on the closed-form answer.

Sensitivity: raising elasticity from 1.5 → 2.0 drops p* to $16 and
profit collapses ~90% — the single biggest model risk.

LLM calls: 2  (formulation + interpretation)
```

Report saved to: `./cookbook/114_scipy_nonlinear/output/pricing_true_SLSQP.txt`

## Related recipes

- Recipe 78: LP / MILP via PuLP (linear & integer programs)
- Recipe 98: Job-shop scheduling via OR-Tools CP-SAT (constraint programming)
- Recipe 99: Portfolio optimization via cvxpy (convex QP)
- Recipe 109: Synthetic problem catalog (n05 / n10 / n20 scale testing)
