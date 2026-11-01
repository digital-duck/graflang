# Recipe 125 — Progressive Hedging: Battery Storage Investment

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/125_progressive_hedging` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Solver class:** Parallel Stochastic Programming (Two-Stage SP, Scenario Decomposition)  
**Backend:** Progressive Hedging (custom Python PH loop over Pyomo/HiGHS subproblems)  
**Dependency:** `pip install pyomo highspy`

## What it demonstrates

Extends r117 (3-scenario monolithic stochastic LP) to **30-scenario** two-stage stochastic
programming via **Progressive Hedging (PH)** decomposition. PH solves each scenario as
an independent subproblem and enforces non-anticipativity via a quadratic penalty term.
This is how real stochastic programs scale: not by building a giant monolithic model,
but by decomposing by scenario and coordinating with a penalty.

| | r117 (3 scenarios) | r125 (30 scenarios) |
|---|---|---|
| Method | Monolithic extensive form | Progressive Hedging decomposition |
| Stage 1 vars | 1 (capacity) | 1 (capacity) |
| Stage 2 vars | 3×24 = 72 | 30×24 = 720 |
| Memory | Scales with scenarios | Bounded (one subproblem at a time) |
| Parallelism | None (monolithic) | Each scenario independent |
| Convergence | Immediate (LP) | PH iterations until residual < 0.5 MW |

## The problem: battery storage investment

**Stage 1 (here-and-now):** Choose `capacity_MW ∈ [0, 100]` before knowing which demand
scenario will occur. Capital cost: $150,000/MW.

**Stage 2 (recourse):** Given the realized scenario (demand + price profile), choose hourly
`charge[t]` and `discharge[t]` to maximize arbitrage revenue.

**30 scenarios:** Random demand scaling factors (0.7×–1.4×) and correlated electricity
prices. Each scenario has a 24-hour demand/price profile.

**Non-anticipativity:** All scenarios must use the *same* Stage 1 decision. You cannot
invest differently in different scenarios — you commit to one capacity before the scenario
is revealed. PH enforces this by penalizing scenario-specific capacity decisions that
deviate from the consensus.

## Sample Results (2026-09-07, claude-sonnet-4-6)

### solver=ON — Progressive Hedging (30 scenarios)

| Metric | PH (stochastic) | EV (mean scenario) |
|---|---|---|
| Optimal capacity | **100 MW** (at bound) | **100 MW** (at bound) |
| Capital cost ($/yr) | $800,000 | — |
| Annual net value (profit − capital) | **$2,252,629** | $2,252,629 |
| **VSS** | **$0** | baseline |
| PH iterations to convergence | 1 | — |
| Solve time | 0.0s | — |

**VSS = $0 — corner-pinned result.** Both PH and EV land on the same 100 MW upper-bound decision. When the optimal solution is at a constraint boundary across every scenario, scenario-decomposition adds no value: EV already finds the global optimum. PH converged in a single iteration with zero primal residual.

This is a valid and pedagogically useful outcome: it demonstrates when stochastic programming is *not* worth the complexity overhead. The condition for VSS > 0 is that different scenarios would prefer different Stage 1 decisions — here, the arbitrage revenue model is steep enough that 100 MW dominates under every scenario realization.

**Annual economics:** arbitrage revenue of ~$3.05M/year against $800K annualized capital yields a $2.25M net annual value — a 2.8× return. The revenue model heavily favors full capacity utilization.

### solver=OFF — LLM stochastic reasoning

The LLM applied sound qualitative logic — Jensen's Inequality, asymmetric upside/downside risk, right-skewed payoff structure — but arrived at numerically wrong conclusions:

| | LLM estimate | Actual (solver) |
|---|---|---|
| EV optimal capacity | ~60 MW | 100 MW |
| Stochastic optimal | ~72–78 MW | 100 MW |
| VSS | ~$70K–$110K (15–23%) | $0 |

The LLM correctly reasoned that high-demand scenarios create superlinear payoffs and that EV underweights tail upside — but it assumed a **diminishing-returns revenue curve** (marginal revenue declining beyond 60 MW) that doesn't exist in the actual model. The actual revenue function is linear in capacity, so the optimum is always at the corner (100 MW). The LLM's economic heuristics are reasonable for real-world storage markets with market-depth limits; they just don't match the synthetic model's price structure.

**Finding:** The LLM's qualitative framework for stochastic programming (Jensen's Inequality, asymmetric risk, right-skewed distributions) is correct and well-articulated. Its numerical failure stems from assuming a concave revenue-capacity relationship rather than querying the actual objective. This is the core limitation solver=OFF cannot escape: qualitative structure is learnable from text; problem-instance-specific curvature is not.

## Run

```bash
# solver=ON: Progressive Hedging across 30 scenarios
graf run ~/.graflang/solvers/progressive_hedging/progressive_hedging.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF: deterministic EV (mean scenario) + LLM reasoning
graf run ~/.graflang/solvers/progressive_hedging/progressive_hedging.graph.yaml \
    --llm claude_cli --param use_solver=false

# More scenarios (slower, better convergence demo)
graf run ~/.graflang/solvers/progressive_hedging/progressive_hedging.graph.yaml \
    --llm claude_cli --param use_solver=true --param n_scenarios=50

```

## Install

```bash
pip install pyomo highspy
# HiGHS is the LP/MIP solver used for each scenario subproblem.
# For MPI-based PH at scale: pip install mpi4py mpi-sppy
```

## Background: Progressive Hedging algorithm

Given scenarios S with probabilities p_s and shared first-stage variable x:

```
1. Initialize: solve each scenario independently → x_s^0
2. Compute consensus: x̄ = Σ p_s · x_s
3. Update multipliers: w_s += ρ · (x_s - x̄)
4. Re-solve each scenario with augmented cost: min c(x,y) + w_s·x + (ρ/2)·‖x - x̄‖²
5. Repeat from 2 until max|x_s - x̄| < tolerance
```

The penalty ρ pulls scenario solutions toward the consensus. As ρ → ∞, all scenarios
converge to the same x (perfect non-anticipativity). The algorithm is guaranteed to
converge for convex problems.

## Value of Stochastic Solution (VSS)

```
VSS = EV_cost − RP_cost
```

- **RP (Recourse Problem):** optimal cost when solving with all 30 scenarios (PH result)
- **EV (Expected Value):** cost when solving with the mean scenario and applying that
  decision to all actual scenarios
- **VSS > 0** means knowing the scenario distribution is worth something — risk-averse
  investors should solve with scenarios, not with means

Typical VSS for storage investment: 3–12% of total cost, representing $45K–$180K/MW
in avoided over/under-investment.

## Key ASSERT

```
ASSERT ph_converged(@result_json);
```

Passes when `rp_cost ≤ ev_cost` (stochastic solution is no worse than EV). In practice,
VSS should be positive; the ASSERT allows tie (within numerical tolerance).

## Connection to Momagrid

PH's scenario subproblems are embarrassingly parallel — each scenario is fully
independent within each iteration. On Momagrid, 30 scenario subproblems would
route to 30 different nodes, completing in parallel. The coordinator (PH multiplier
update) runs centrally. This is the natural distributed pattern for large SP problems
and is a direct application of DODA: the `.spl` workflow is identical whether running
locally (ThreadPoolExecutor) or on Momagrid (node dispatch).
