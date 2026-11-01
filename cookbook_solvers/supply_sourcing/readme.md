# Recipe 100 — Supply Sourcing (Multi-objective: cost vs. fill rate)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/100_supply_sourcing` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `pulp` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

Given a set of suppliers with different cost, fill rate, and capacity profiles,
find allocations that trade off total cost against blended fill rate — using the
PuLP ε-constraint method to trace the full Pareto front.

**Benchmark B1** from the multi-objective benchmark suite.
**DODA**: same `.spl` spec runs on any adapter (ollama for exploration, claude_cli for production).

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | PuLP ε-constraint sweep | LLM heuristic allocation |
| Guarantee | Provably Pareto-optimal front | Single plausible point, may violate constraints |
| Verification | `ASSERT` on front feasibility | `verify_sourcing_off` back-substitution |
| Solver class | C2 (LP, multi-objective) | — |

## Default problem (B1)

```
Demand: 1000 units

Supplier  Cost/unit  Fill rate  Capacity
S1        $10        95%        400 units   (premium)
S2        $ 7        80%        500 units   (standard)
S3        $ 5        60%        400 units   (budget)

Objectives: minimize total cost AND maximize blended fill rate
```

Known anchor points:
- Min-cost: x1=100, x2=500, x3=400 → cost=\$6,500, fill=73.5%
- Max-fill: x1=400, x2=500, x3=100 → cost=\$8,000, fill=84.0%

**Plain English**: You need 1,000 units. S1 is the most reliable supplier (95% fill) but the most expensive (\$10/unit). S3 is the cheapest (\$5/unit) but least reliable (60% fill). The solver finds every Pareto-optimal split across the three suppliers — no single allocation can simultaneously be cheaper and have a higher fill rate than any point on the front. A procurement manager picks the row that matches their risk appetite.

## Example output (solver=ON, B1 default)

```
| Cost ($)  | Fill rate (%) | S1  |  S2  |  S3 |
|---|---|---|---|---|
| 6,500.00  | 73.5          | 100 |  500 | 400 |
| 6,714.30  | 75.0          | 143 |  500 | 357 |
| 6,928.55  | 76.5          | 186 |  500 | 314 |
| 7,142.85  | 78.0          | 229 |  500 | 271 |
| 7,357.15  | 79.5          | 271 |  500 | 228 |
| 7,571.45  | 81.0          | 314 |  500 | 185 |
| 7,785.70  | 82.5          | 357 |  500 | 142 |
| 8,000.00  | 84.0          | 400 |  500 | 100 |
```

Reading the table:
- **Row 1** ($6,500 / 73.5%) — pure cost minimization: load S2 and S3 to capacity, top up with just 100 units from S1.
- **Row 8** ($8,000 / 84.0%) — maximum fill rate: saturate S1 and S2, cut S3 to 100 units.
- **Rows 2–7** — the trade-off band: every $214 you spend above the floor buys 1.5 percentage points of fill rate. S2 stays at 500 in every row (always optimal to fill the mid-tier supplier first); the solver only swaps units between S1 and S3.

S2 maxes out in every solution because it dominates — it is strictly better than S3 on both cost and fill rate, and cheaper than S1.

## Run commands

```bash
# solver=ON — PuLP ε-constraint sweep (default 8 Pareto points)
graf run ~/.graflang/solvers/supply_sourcing/supply_sourcing.graph.yaml \
  --llm claude_cli \
  --param use_solver=true

# solver=OFF — LLM heuristic allocation with back-substitution check
graf run ~/.graflang/solvers/supply_sourcing/supply_sourcing.graph.yaml \
  --llm claude_cli \
  --param use_solver=false

# solver=ON — custom n_points
graf run ~/.graflang/solvers/supply_sourcing/supply_sourcing.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param n_points=12

# n_points controls how many evenly-spaced points the ε-constraint sweep generates along the Pareto front.
# More points = finer coverage of the tradeoff curve, at the cost of more LP solves 

# Custom problem
graf run ~/.graflang/solvers/supply_sourcing/supply_sourcing.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param problem="A factory needs 2000 units. SupA: $12/unit, 98% fill rate, capacity 800. SupB: $8/unit, 75% fill rate, capacity 1200. SupC: $6/unit, 55% fill rate, capacity 900."
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `sweep_pareto_front(problem_json, n_points)` | PuLP ε-constraint sweep → Pareto front JSON |
| `is_pareto_feasible(front_json)` | ASSERT gate: status==OK and n_points >= 2 |
| `format_pareto_table(front_json)` | Pareto front → markdown table |
| `verify_sourcing_off(problem_json, solution_json)` | Arithmetic back-check for solver=OFF path |

## Optimization formulation

```
For each fill-rate threshold ε_k ∈ [ε_min, ε_max]:

  Minimize    sum_i  cost_i * x_i
  Subject to  sum_i  x_i  = demand
              sum_i  fill_i * x_i  >=  ε_k * demand
              0  <=  x_i  <=  capacity_i   for each supplier i

Dominated points are removed; the result is the Pareto front.
```

## Verification (solver=OFF)

`verify_sourcing_off` checks:
1. **Demand balance**: sum(allocation) == demand (tolerance ±1 unit)
2. **Capacity**: each allocation <= supplier capacity
3. **Cost**: recompute from allocation; compare to claimed (tolerance ±$10)
4. **Fill rate**: recompute blended fill; compare to claimed (tolerance ±2 pp)

## Output metadata

The `RETURN` statement surfaces:
- `objective = @fill_rate_str` — number of Pareto points (solver=ON) or blended fill rate (solver=OFF)
- `verify = @verify_status` — PASS / FAIL / N/A

## Related recipes

- Recipe 78: LP / MILP via PuLP (single-objective constraint optimization)
- Recipe 99: Portfolio optimization via cvxpy (Markowitz mean-variance)
- Recipe 101: Multi-depot vehicle routing (coming soon)
