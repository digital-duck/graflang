=== Global MINLP — Reactor Optimization (r122) | solver=ON ===

## Global MINLP Report — Chemical Reactor Yield

**Solver used:** grid_search_fallback  
**Global optimum certified:** No (grid search fallback)  
> Couenne/Bonmin not found — grid search used to show gap. Install: conda install -c conda-forge coinor-couenne pyomo

### Solution Comparison

| | Global Solver | Local Solver (scipy) | Gap |
|---|---|---|---|
| Net yield | **0.0891** | 0.0431 | 0.046 |
| Use catalyst | 1 | 0 | — |
| Temperature (K) | 610 | 300.0 | — |
| Concentration (mol/L) | 2.0 | 2.0 | — |

### Why the Gap Exists

The Arrhenius term `exp(-Ea/RT)` combined with the binary catalyst decision
creates a non-convex surface. scipy started near (T=480, no catalyst) and
converged to the local optimum. Couenne's spatial branch-and-bound builds
convex relaxations of the nonlinear terms, progressively tightening the lower
bound until the global optimum is certified within the specified gap.

── Analyst Explanation ─────────────────────────────────────
**Caveat first:** this report is from the grid-search fallback, not Couenne/Bonmin. Nothing here is certified global. The grid result (catalyst, T=610 K) also differs from the problem's expected optimum (T~680 K), and the local result shows T=300 K, not ~480 K, so treat the numbers as illustrative.

**1. Spatial branch-and-bound.** It splits the variable ranges (T, concentration) into boxes. On each box it replaces nonconvex terms like `exp(-Ea/RT)` with convex underestimators/relaxations, which give a provable bound on the best possible yield in that box. Boxes whose bound cannot beat the best known feasible solution are pruned. When every box is pruned or closed, the incumbent is globally optimal within tolerance. scipy only checks local gradient conditions.

**2. Local trap.** The Arrhenius term rises steeply with T, while other terms (cost, side reactions) penalize it, so yield is non-convex in T. The binary catalyst switch adds a second basin. Started near T=480 K with no catalyst, scipy follows the gradient to the nearest peak and can't jump to the catalyst basin.

**3. Optimality gap.** It is (best upper bound − incumbent)/|incumbent|, the most you could still gain. It's safe to stop when it falls below your tolerance (e.g. 0.01%–1%) given model and data uncertainty. A grid search has no bound, so no gap is meaningful here.

**4. Industrial examples.** Refinery/chemical process design (reactor and heat-exchanger network synthesis), and power grid optimal power flow/unit commitment, where small suboptimality means large cost or safety consequences.