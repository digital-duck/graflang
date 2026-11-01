# Recipe 112 — Optuna Black-Box Strategy Optimization

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/112_optuna_blackbox` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**The key story:** A SaaS team needs to tune (monthly_price, annual_discount_pct, trial_days) to maximize customer LTV. The LTV model is non-convex with no gradient. Optuna TPE (50 trials) finds price≈\$45.7, discount≈3.6%, trial≈30 days → LTV=\$246 — a **+48%** improvement over the naive baseline (\$166). The LLM's recommendation (\$79, 20% discount, 14-day trial) goes in the opposite direction on all three dimensions, reasoning from real-world SaaS heuristics that conflict with the actual objective function's structure.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Optuna TPE (Tree-structured Parzen Estimator) | LLM heuristic reasoning |
| Guarantee | Global optimum approximation over 50 trials | Local intuition, misses parameter interactions |
| Objective | Non-convex black-box (churn + conversion model) | "Lower price = more customers = better LTV" |
| Verification | `ASSERT optimization_improved` (C1) | — |
| Solver class | C1 (improvement verified vs baseline) + C2 (LTV recomputed) | — |

## Background

**Optuna Black-Box Strategy Optimization** addresses the regime where the objective function has no closed form and no gradient — where analytical solvers (PuLP, cvxpy) and gradient descent cannot apply.

**The problem:** A SaaS team tunes three levers — monthly price ($30–$120), annual discount (0–40%), trial length (3–30 days) — to maximize customer lifetime value (LTV). The LTV model is non-convex because of three interacting non-linearities:
- Conversion saturates with trial length (diminishing returns past ~10 days)
- Churn spikes discontinuously when price > $50 or discount > 25%
- The price × discount interaction creates a valley around the "intuitive" naive point

**What Optuna does:** TPE (Tree-structured Parzen Estimator) builds a probabilistic model of where good values occur based on previous trials, then samples new points in promising regions. No gradient required — it treats the objective as a pure black box. After 50 trials it finds price ≈ $43, 28% discount, 7-day trial → LTV ≈ $218, versus the LLM's intuitive guess of $50 / 20% / 14-day → LTV ≈ $172 (21% worse).

**The core insight:** The LLM's reasoning is "lower price = more customers = better LTV" — a monotonic heuristic that ignores the churn/discount interaction. The short trial (7 days vs 14) is counter-intuitive but correct because conversion saturates quickly and longer trials delay first payment without meaningfully improving retention.

**Position in the solver taxonomy:** Optuna sits between scipy.optimize (needs a gradient, non-convex) and Bayesian GP (r113, fewer trials but heavier prior modeling). It's the right tool when the objective is a simulation, A/B test result, or any function you can evaluate but not differentiate.

## Why this objective is hard

The LTV function has three interacting non-linearities:
1. **Conversion**: `1 - exp(-trial_days/10)` — saturates at ~30 days; short trials not catastrophic
2. **Churn penalty**: jumps at `price > 50` and `discount > 25` — high-discount churners are cheap customers
3. **Revenue per customer**: discount × price interaction creates a valley at naive (50, 20%) parameters

No gradient. No closed form. Optuna samples where previous trials showed improvement.

## Default problem parameters

| Parameter | Range | Naive baseline | Optuna Best | LLM solver=OFF |
|---|---|---|---|---|
| monthly_price | \$30–\$120 | \$50 | **\$45.7** | \$79 |
| annual_discount_pct | 0%–40% | 20% | **3.6%** | 20% |
| trial_days | 3–30 | 14 days | **30 days** | 14 days |
| **LTV** | — | **\$166** | **\$246 (+48%)** | ~\$2,570* |

\* LLM computed LTV using its own ARPU/churn formula (revenue ÷ monthly_churn_rate), not the recipe's black-box objective — the numbers are not comparable.

## Run results — solver=ON vs solver=OFF

Both runs: `claude_cli` / `claude-sonnet-4-6`, default SaaS pricing problem.

| Metric | solver=ON | solver=OFF |
|---|---|---|
| Timestamp | 2026-09-07 07:32:48 | 2026-09-07 07:35:26 |
| Tokens in | 391 | 319 |
| Tokens out | 408 | 713 |
| Total tokens | 799 | 1,032 (+29%) |
| Latency | 23.3s | 47.7s (2.0×) |
| Recommendation | \$45.7 / 3.6% / 30 days | \$79 / 20% / 14 days |
| LTV (recipe objective) | **\$246.05** (+48.2% over naive) | not computed |
| ASSERT passed | ✓ (best > naive) | — |
| LLM calls | 2 | 3 |

### Three-way parameter disagreement

Every parameter recommendation is opposite between Optuna and the LLM:

| Parameter | LLM solver=OFF | Optuna solver=ON | Why they diverge |
|---|---|---|---|
| Price | \$79 ("below \$80 psychological barrier") | \$45.7 | LLM avoids "low-price = low-value signal"; objective's churn spikes above \$50 |
| Discount | 20% ("2.4× LTV multiplier via annual plans") | 3.6% | LLM models discount as churn reducer; objective penalizes discount > 25% |
| Trial days | 14 ("urgency deadline, tire-kicker filter") | 30 days | LLM fears tire-kickers; objective's conversion saturates upward with trial length |

### The LLM's reasoning is coherent — but for a different objective

Solver=OFF produced well-argued SaaS pricing advice: lower price attracts bargain hunters, annual discounts reduce churn 3×, 30-day trials attract tire-kickers. These are real-world heuristics backed by industry data. The LLM even computed its own LTV formula: LTV = ARPU ÷ monthly\_churn\_rate, arriving at ~\$2,570 — a plausible number for a \$79/mo product.

The problem: its reasoning is anchored to general SaaS playbook intuition, not the specific black-box function in this recipe. The recipe's LTV model has three structural features the LLM could not know:
- Churn spikes discontinuously at price > \$50 (making \$79 severely penalized)
- Discount > 25% triggers a churn spike (making 20% near the penalty boundary)
- Conversion `1 - exp(-trial_days/10)` saturates positively (making 30 days strictly better than 14)

This is the fundamental case for black-box optimization: when the objective has hidden non-linearities and discontinuities that no heuristic framework can anticipate, you have to evaluate it empirically.

### Key takeaway

solver=ON is 2× faster and finds a 48% improvement the LLM not only missed but argued against. The LLM's counter-argument is internally consistent and would be good advice in the real world — but it is reasoning about a different LTV model than the one being optimized. Optuna makes no assumptions: it evaluates the actual function 50 times and converges on the true optimum.

## Run commands

```bash
# solver=ON — Optuna 50-trial TPE study
graf run ~/.graflang/solvers/optuna_blackbox/optuna_blackbox.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF — LLM heuristic guess
graf run ~/.graflang/solvers/optuna_blackbox/optuna_blackbox.graph.yaml \
    --llm claude_cli --param use_solver=false
```

## Install

```bash
conda activate spl123
pip install optuna
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_problem()` | Returns SaaS pricing problem JSON (params + naive baseline) |
| `run_optuna_study(problem_json)` | Optuna TPE study → best params + top 5 trials |
| `optimization_improved(result_json)` | ASSERT gate: best_value > naive_value |
| `format_optuna_report(result_json)` | Markdown comparison table + top 5 trials |

## When to use Optuna vs analytical optimization

| Situation | Use |
|---|---|
| Objective has gradient, convex | LP/QP solver (r78, r99) |
| Objective has gradient, non-convex | scipy.optimize, gradient descent |
| Objective is a black box (simulation, A/B test) | **Optuna TPE** (r112) |
| Objective + uncertainty (few trials budget) | Bayesian GP (r113) |
| Multiple competing objectives | pymoo NSGA-II (r107) |

## Related recipes

- r113: Ax Bayesian optimization (GP-based, fewer trials needed)
- r107: pymoo NSGA-II (multi-objective Pareto, not single-objective)
- r78: PuLP constraint optimization (analytical LP with gradient)
