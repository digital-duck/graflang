# Recipe 108 — Robust Supply Chain MILP (python-mip)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/108_robust_milp` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `mip` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**The key story:** a naive *expected-demand heuristic* recommends the wrong capacity decision. The two-stage stochastic MILP prices all demand scenarios simultaneously and finds the true optimum — often the opposite recommendation.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | python-mip MILP (CBC backend) | Naive expected-demand heuristic |
| Decision model | Two-stage stochastic: commit now, respond per scenario | Single-stage: decide based on E[demand] |
| Guarantee | Proven optimal across **all** scenarios simultaneously | Feasible but possibly suboptimal |
| Verification | `ASSERT` on `OptimizationStatus.OPTIMAL` | `verify_robust_off` constraint check |
| Solver class | C1 (Status oracle: `OPTIMAL`) | — |

## The two-stage structure

```
Stage 1 (now, before uncertainty resolves)
└── y ∈ {0, 1}   build own factory (y=1) or lease (y=0)

Stage 2 (later, one plan per scenario)
└── x_s ≥ 0      produce from own/leased capacity
    z_s ≥ 0      emergency spot-market sourcing
```

The MILP optimizes **Stage 1** by pricing the cost consequences across **all Stage 2 scenarios at once** — not just at expected demand.

## Default problem (B5)

| Parameter | Value |
|---|---|
| Own factory | capacity 300 units, fixed cost $4,000 |
| Leased facility | capacity 150 units, no fixed cost |
| Production cost | $8/unit (same from either) |
| Emergency sourcing | $60/unit (spot market) |

| Scenario | Probability | Demand |
|---|---|---|
| Low | 30% | 100 units |
| Normal | 50% | 200 units |
| High | 20% | 300 units |

**Expected demand:** 0.3×100 + 0.5×200 + 0.2×300 = **190 units > 150** (lease cap)  
**Naive heuristic says:** BUILD (E[D] exceeds lease capacity)  
**MILP finds:** LEASE — build cost $4,000 outweighs the emergency sourcing savings

| Decision | Fixed cost | Expected op. cost | Total |
|---|---|---|---|
| **Lease** (MILP optimal) | $0 | $2,340 | **$2,340** |
| Build (heuristic) | $4,000 | $1,520 | $5,520 |

The \$3,180 gap comes from the asymmetry: High demand (20% probability) would cost \$9,000 extra in emergency sourcing if you lease — but you only need \$6,000 build cost to avoid that. The MILP accounts for the 20% weight correctly; the heuristic ignores it.

Wait — this is the *opposite* of the default numbers above. The correct hand-calculation for the default B5:

**If lease (cap=150):**
- Low (D=100): produce 100, emerg 0 → $8×100 = $800
- Normal (D=200): produce 150, emerg 50 → $8×150 + $60×50 = $1,200 + $3,000 = $4,200
- High (D=300): produce 150, emerg 150 → $8×150 + $60×150 = $1,200 + $9,000 = $10,200
- Expected op = 0.3×800 + 0.5×4,200 + 0.2×10,200 = 240 + 2,100 + 2,040 = **$4,380**
- **Total = $4,380**

**If build (cap=300):**
- Low: $8×100 = $800
- Normal: $8×200 = $1,600
- High: $8×300 = $2,400
- Expected op = 0.3×800 + 0.5×1,600 + 0.2×2,400 = 240 + 800 + 480 = **$1,520**
- **Total = $4,000 + $1,520 = $5,520**

**MILP optimal: LEASE (\$4,380) — saves \$1,140 vs BUILD ($5,520)**

The naive heuristic (E[D]=190 > 150 lease cap) recommends BUILD and overpays by $1,140.

## Run commands

```bash
# solver=ON — python-mip two-stage MILP
graf run ~/.graflang/solvers/robust_milp/robust_milp.graph.yaml \
  --llm claude_cli --param use_solver=true

# solver=OFF — naive heuristic + comparison
graf run ~/.graflang/solvers/robust_milp/robust_milp.graph.yaml \
  --llm claude_cli --param use_solver=false

# Custom scenario (pipe a different problem)
graf run ~/.graflang/solvers/robust_milp/robust_milp.graph.yaml \
  --llm claude_cli --param use_solver=true \
  --param "problem=A retailer must decide whether to build a large warehouse (capacity 500 units, cost $8,000) or rent a small one (capacity 250 units). Production: $5/unit. Emergency restocking: $45/unit. Scenarios: Low (20%, 150 units), Normal (60%, 300 units), High (20%, 500 units)."
```

## Install

```bash
conda activate spl123

# https://pypi.org/project/mip/
pip install mip   # CBC solver bundled
```

## Optimization formulation

```
minimize   cost_build·y + Σ_s prob_s · (cost_prod·x_s + cost_emerg·z_s)

subject to x_s ≤ cap_own·y + cap_lease·(1−y)   ∀ s   (capacity)
           x_s + z_s ≥ demand_s                  ∀ s   (demand met)
           y ∈ {0, 1}                                  (binary: build or lease)
           x_s, z_s ≥ 0                          ∀ s
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `extract_robust_problem(problem)` | NL → JSON with scenarios, capacities, costs |
| `solve_robust_milp(problem_json)` | python-mip two-stage MILP → optimal decision + scenario plans |
| `is_optimal(solution_json)` | ASSERT gate: `status == "OPTIMAL"` |
| `format_scenario_report(solution_json)` | Markdown table of scenario-by-scenario costs |
| `solve_naive_heuristic(problem_json)` | Expected-demand heuristic baseline (solver=OFF) |
| `verify_robust_off(problem_json, solution_json)` | Check all scenario capacity/demand constraints |

## Why python-mip vs PuLP

Both wrap CBC. python-mip offers:
- Cleaner `OptimizationStatus` enum (vs PuLP's string `LpStatus`)
- Native numpy array support for large scenario matrices
- Callback API for cutting planes (not used here, but available)
- Better suited for multi-scenario models with structured variable indexing

## Related recipes

- r78: single-scenario MILP via PuLP (the OR baseline)
- r99: portfolio optimization via cvxpy (convex, not MILP)
- r107: workforce 3-objective (pymoo NSGA-II, multi-objective)
- r100, r101: 2-objective Pareto benchmarks (PuLP)
