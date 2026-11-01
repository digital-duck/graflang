# Recipe 117 — Two-Stage Stochastic Programming (Pyomo + GLPK)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/117_pyomo_stochastic` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

Given a seasonal inventory problem where demand is uncertain, find the order quantity that minimizes **expected total cost** across all demand scenarios — using Pyomo's Extensive Form (EF) to solve the two-stage stochastic LP.

**The key insight**: ordering the expected demand (the naïve heuristic) is suboptimal when shortage costs are asymmetrically higher than holding costs. The stochastic solution orders *above* the mean to hedge against the high-shortage tail.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Pyomo Extensive Form (GLPK / CBC / HiGHS) | LLM heuristic — "order the expected demand" |
| Guarantee | Certified optimal expected cost | Single-point EV baseline; suboptimal under asymmetric costs |
| Verification | `ASSERT` on solver status == optimal | VSS (Value of Stochastic Solution) comparison |
| Solver class | Two-stage stochastic LP/IP | — |

## Default problem (seasonal inventory stocking)

```
A retailer must order promotional merchandise NOW, before knowing seasonal demand.
Order cost: $5/unit  |  Shortage penalty: $15/unit  |  Holding cost: $2/unit
Warehouse capacity: 400 units

Demand scenarios:
  Pessimistic: 100 units  (p = 0.30)
  Nominal:     200 units  (p = 0.50)
  Optimistic:  300 units  (p = 0.20)

Expected demand: 0.30×100 + 0.50×200 + 0.20×300 = 190 units
```

**Plain English**: If you order 190 units (the expected demand), you under-stock in the Optimistic scenario (20% chance of 300-unit demand) and pay \$15/unit in shortage penalty. The asymmetry — shortage costs 7.5× more than holding — means the optimal order is 200, not 190. The Pyomo solver prices all scenarios simultaneously and finds this automatically.

## Example output (2026-09-06, claude-sonnet-4-6)

### solver=ON (Pyomo + GLPK)

| Method | Q | Expected Cost | vs. Q* |
|---|---|---|---|
| **Pyomo stochastic optimum** | **200** | **\$1,360** | — |
| EV baseline (order E[D]=190) | 190 | \$1,409 | +\$49 worse |

**Per-scenario breakdown (Q*=200):**

| Scenario | Demand | Prob | Shortage | Excess | Cost | Weighted |
|---|---|---|---|---|---|---|
| Pessimistic | 100 | 0.30 | 0 | 100 | \$1,200 | \$360 |
| Nominal | 200 | 0.50 | 0 | 0 | \$1,000 | \$500 |
| Optimistic | 300 | 0.20 | 100 | 0 | \$2,500 | \$500 |
| **Expected** | | | | | | **\$1,360** |

**VSS = \$49** — the cost of ignoring uncertainty. Small in absolute terms here; scales dramatically with volume and volatile demand.

### solver=OFF (LLM direct reasoning)

The LLM enumerated all three candidate quantities explicitly:

| Q | Pessimistic cost | Nominal cost | Optimistic cost | Expected cost |
|---|---|---|---|---|
| 190 | \$1,130 | \$1,100 | \$2,600 | **\$1,409** |
| **200** | **\$1,200** | **\$1,000** | **\$2,500** | **\$1,360** |
| 300 | \$1,900 | \$1,700 | \$1,500 | **\$1,720** |

**Conclusion: Order 200.** The LLM correctly applied the asymmetric cost logic ("shortage costs 7.5× more than holding"), rejected the EV heuristic, and computed the correct arithmetic for all three scenarios.

### Comparison

| | solver=ON | solver=OFF |
|---|---|---|
| Q* | 200 | 200 ✓ |
| Expected cost | \$1,360 | \$1,360 ✓ |
| VSS | \$49 | \$49 ✓ (computed explicitly) |
| Per-scenario arithmetic | Tool-computed | LLM-computed — exact match |
| Optimality guarantee | Formal (GLPK proves optimal) | Informal (enumeration over 3 candidates) |
| Tokens in / out | 33 / 0 | 64 / 0 |
| Latency | 16s | 96s |
| LLM calls | ~1 | ~3 |

**Verdict: solver=OFF matched solver=ON on every number** — Q*, expected cost, and VSS are identical. The LLM's reasoning was clear, step-by-step, and arithmetically correct.

**Why solver=OFF works here (and when it won't):**

This problem has a discrete demand structure with exactly 3 scenarios (100/200/300). The LLM can enumerate all 3 candidate order quantities by hand in seconds. With this structure, scenario enumeration and the solver reach the same answer.

Solver advantage emerges when:
- Demand is continuous or has many discrete values (100+ scenarios)
- The feasible Q space is large (enumeration becomes intractable)
- Multiple items or locations couple the decisions (newsvendor with substitution, multi-product stochastic)
- Time pressure makes per-scenario manual arithmetic infeasible

**Contrast with r107:** In the 3-objective workforce problem, the LLM found 1 of 82 Pareto-optimal points by greedy reasoning. Here with 3 scenarios and 1 decision variable, the LLM matches the solver exactly. The complexity threshold for when LLM enumeration breaks down is around 10–20 discrete candidates in the decision space.

**The template note** at the bottom of solver=OFF output says "LLM typically defaults to ordering the expected demand (Q=190)." Claude-sonnet-4-6 did *not* default — it explicitly rejected Q=190 as suboptimal and found Q=200. The note reflects a weaker model assumption; capable LLMs can reason correctly about cost asymmetry in simple newsvendor problems.

Why Q=200 > E[D]=190: critical ratio = c_u / (c_u + c_o) = 15 / (15 + 2) = 15/17 ≈ 0.882. Order enough to cover demand in 88.2% of scenarios. F(200)=0.80 is the closest feasible point below that threshold in the discrete distribution; Q=200 is where adding one more unit crosses from net-benefit to net-cost.

## Run commands

```bash
# solver=ON — Pyomo Extensive Form (auto-selects GLPK / CBC / HiGHS)
graf run ~/.graflang/solvers/pyomo_stochastic/pyomo_stochastic.graph.yaml \
  --llm claude_cli \
  --param use_solver=true

# solver=OFF — LLM EV heuristic baseline
graf run ~/.graflang/solvers/pyomo_stochastic/pyomo_stochastic.graph.yaml \
  --llm claude_cli \
  --param use_solver=false
```

## Install

```bash
pip install pyomo
pip install highspy
```

Pyomo auto-selects the first available solver from: `glpk` → `cbc` → `highs` → `appsi_highs`.

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_problem_setup()` | Return the default newsvendor problem JSON |
| `solve_two_stage_sp(problem_json)` | Pyomo EF → optimal order qty + per-scenario breakdown |
| `compute_ev_baseline(problem_json)` | EV heuristic (order expected demand) |
| `sp_optimal(result_json)` | ASSERT gate: status == "optimal" |
| `format_sp_report(result_json, baseline_json)` | Format comparison report |

## Optimization formulation

```
Stage 1 (here-and-now):
  Q ∈ ℤ⁺,  Q ≤ capacity          (order quantity, decided before demand is known)

Stage 2 (wait-and-see, per scenario s):
  shortage_s ≥ demand_s − Q       (unmet demand, penalized at c_shortage)
  excess_s   ≥ Q − demand_s       (unsold stock, penalized at c_holding)

Objective (Extensive Form):
  min  c_order × Q
     + Σ_s  p_s × (c_shortage × shortage_s  +  c_holding × excess_s)
```

## Related recipes

- Recipe 108: Robust Supply Chain MILP (python-mip, scenario-based capacity decisions)
- Recipe 100: Supply Sourcing Pareto front (PuLP ε-constraint, multi-objective)
- Recipe 119: Demand Forecasting (statsmodels structural time series)
- Recipe 99:  Portfolio Optimization (cvxpy, mean-variance efficient frontier)
