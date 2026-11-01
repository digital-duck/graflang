# Recipe 101 — Production Sustainability (Multi-objective: profit vs. carbon)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/101_production_sustainability` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `pulp` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

Given a factory producing two products with different profitability and emissions profiles,
find the set of non-dominated production plans that simultaneously maximize profit and minimize
carbon footprint — the Pareto front.

**Benchmark B3** from the multi-objective optimization suite.  
**DODA**: the same `.spl` spec runs on any adapter; only the solver flag changes behavior.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | PuLP weighted-sum scalarization (CBC) | LLM heuristic (x, y) selection |
| Guarantee | Correct Pareto front via LP at each λ | Plausible plan, may not be Pareto-optimal |
| Verification | `ASSERT is_pareto_feasible` (≥2 points) | `verify_production_off` back-substitution |
| Solver class | C2 (Multi-objective LP / scalarization) | — |
| LLM role | Interpret tradeoff, recommend operating points | Propose plan + reasoning |

## Default problem (B3)

Two products, two objectives, two resource constraints:

| Product | Profit ($/unit) | Carbon (kg/unit) | Labor (hr/unit) | Material (kg/unit) |
|---|---|---|---|---|
| A (standard) | $10 | 3.0 kg | 2 hr | 3 kg |
| B (green)    |  $6 | 1.0 kg | 1 hr | 2 kg |

Available resources: **20 labor-hours**, **30 kg material**

Known anchor points:

- **Max-profit only**: x=10, y=0 → profit=$100, carbon=30 kg
- **Min-carbon only**: x=0,  y=15 → profit=$90,  carbon=15 kg

The tension: Product A is more profitable but dirtier; Product B is greener but less profitable.

## Example output

### solver=ON (PuLP scalarization, n_points=10)

```
Pareto Front (3 non-dominated points):
| Profit ($) | Carbon (kg) | Product A (units) | Product B (units) |
|---|---|---|---|
| 100.0 | 30.0 | 10.00 | 0.00 |
|  90.0 | 15.0 |  0.00 | 15.00 |
|   0.0 |  0.0 |  0.00 |  0.00 |
```

**Why 3 points, not 10**: B3 has a triangular feasible region (2 products, 2 constraints intersecting at one vertex). Any λ sweep collapses to the same 3 corner vertices; deduplication correctly removes the redundant λ solutions. For a richer Pareto front, add more products or constraints.

**Why (0,0) appears**: at λ≈0 (minimize carbon only), the scalarizer drives toward the origin. It is technically Pareto-optimal on the carbon axis (0 kg is unbeatable) but operationally irrelevant — a real factory always chooses a production plan. The solver reports it correctly; the LLM interpretation filters it out as "not viable."

**LLM interpretation highlights** (from actual run):
- Switching all-A → all-B: give up **10% of profit** to cut **50% of carbon** — exceptional ratio
- Carbon market equivalent: $667/tonne of avoided emissions (vs. $50–$150 on offset markets)
- Recommendation: run Product B exclusively unless in a cash crisis

### solver=OFF (LLM heuristic)

```
Proposed: x=0, y=15  →  profit=$90, carbon=15 kg
Verification: PASS (all checks passed)
```

The LLM enumerated all 3 corner points, correctly identified (0,20) as infeasible (material constraint violated), and chose the balanced point (0,15) with explicit reasoning. Arithmetic matches to cent/gram precision.

### solver=ON vs. solver=OFF comparison

| | solver=ON | solver=OFF |
|---|---|---|
| Output | Full Pareto front (3 points) | Single recommended point |
| Recommended plan | All-B: (0, 15) | All-B: (0, 15) |
| Profit | $90 | $90 |
| Carbon | 15 kg | 15 kg |
| Verification | ASSERT passed | PASS |
| LLM calls | 2 | 3 |
| Latency | 35s | 56s |

For this clean 2-product B3 problem the LLM heuristic agrees with the solver. The difference emerges at larger scale (more products, tighter constraints) where LLM corner-point enumeration breaks down — use r109 to generate harder variants.

## Run commands

```bash
# solver=ON — PuLP Pareto sweep, claude_cli
graf run ~/.graflang/solvers/production_sustainability/production_sustainability.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param n_points=10

# solver=OFF — LLM heuristic, ollama/gemma3
graf run ~/.graflang/solvers/production_sustainability/production_sustainability.graph.yaml \
  --llm claude_cli \
  --param use_solver=false \
  --param n_points=10

# solver=ON — finer sweep (20 λ steps)
graf run ~/.graflang/solvers/production_sustainability/production_sustainability.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param n_points=20
```

## Optimization formulation

**Scalarized LP** (solved once per λ value):

```
Maximize    λ · (profit / 100) − (1−λ) · (carbon / 30)

Subject to  2x + y  ≤ 20    (labor hours)
            3x + 2y ≤ 30    (kg material)
            x ≥ 0,  y ≥ 0

where  profit = 10x + 6y
       carbon =  3x +  y
       λ swept from 0.0 (minimize carbon only) to 1.0 (maximize profit only)
```

Normalization anchors: max_profit=100 (x=10, y=0); max_carbon=30 (same anchor).  
Dominated points are stripped after the sweep to yield the true Pareto front.

## TOOL_API reference

| Function | Purpose |
|---|---|
| `sweep_pareto_scalarization(problem_json, n_points)` | PuLP LP sweep over λ ∈ [0,1]; returns Pareto front JSON |
| `is_pareto_feasible(front_json)` | ASSERT gate: status==OK and ≥2 non-dominated points |
| `format_pareto_table(front_json)` | Renders Pareto front as markdown table |
| `verify_production_off(problem_json, solution_json)` | Checks feasibility and arithmetic for LLM-proposed plan |
| `format_report_solver_on(...)` | Formats solver=ON report (replaces verbose f-string in .spl) |
| `format_report_solver_off(...)` | Formats solver=OFF report (replaces verbose f-string in .spl) |

## Verification (solver=OFF)

`verify_production_off` checks three things:

1. **Feasibility**: 2x+y ≤ 20, 3x+2y ≤ 30, x ≥ 0, y ≥ 0
2. **Profit arithmetic**: recompute 10x+6y vs. LLM-claimed profit (tolerance ±$0.50)
3. **Carbon arithmetic**: recompute 3x+y vs. LLM-claimed carbon (tolerance ±0.50 kg)

## Output metadata

The `RETURN` statement surfaces:

- `objective` — solver=ON: number of Pareto points found; solver=OFF: claimed profit ($)
- `verify` — solver=ON: N/A; solver=OFF: PASS / FAIL

## Related recipes

- Recipe 78: Single-objective LP/MILP via PuLP (constraint optimization)
- Recipe 99: Markowitz portfolio optimization via cvxpy (convex QP)
- Recipe 100: Supply sourcing (mixed-integer LP)
