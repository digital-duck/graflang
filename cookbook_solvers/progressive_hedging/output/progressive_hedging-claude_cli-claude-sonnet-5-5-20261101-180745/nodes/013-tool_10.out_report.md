=== Progressive Hedging — Battery Storage (r125) | solver=ON ===

## Progressive Hedging Report — Battery Storage Investment

**Scenarios:** 30  
**PH iterations:** 1  
**Converged:** Yes ✓  
**Primal residual:** 0.0 MW  
**Solve time:** 0.0s  

### Investment Decision

| | PH (stochastic) | EV (mean scenario) |
|---|---|---|
| Capacity (MW) | **100.0** | 100.0 |
| Capital cost ($/yr) | $800,000.0 | — |
| Annual net value (profit − capital, $) | **$2,252,629.0** | $2,252,629.0 |
| **Value of Stochastic Solution (VSS)** | **$0.0** | baseline |

VSS = RP_profit − EV_profit: the annual dollar gain from solving with
all 30 scenarios vs. optimizing on the mean alone.
Positive VSS means the stochastic solution earns more than the EV policy.

── Analyst Explanation ─────────────────────────────────────
**1. Non-anticipativity.** Capacity is chosen before the scenario is known, so it must be the same in all 30 scenarios. A solution that picks a different capacity per scenario would be using information that doesn't exist yet. The constraint is x₁ = x₂ = … = x₃₀.

**2. PH and ρ.** PH solves each scenario separately, with the added penalty (ρ/2)‖xₛ − x̄‖² plus a multiplier term wₛ·xₛ. After each iteration it averages the scenario capacities to get x̄ and updates wₛ ← wₛ + ρ(xₛ − x̄). As ρ → ∞, deviations from x̄ become prohibitively costly, so the scenarios are forced into agreement quickly. Each one stops optimizing for its own scenario, and convergence can be slow or numerically stiff. Small ρ leaves the scenarios free but converges slowly.

**3. VSS.** VSS = RP − EV, the gain from optimizing over all scenarios rather than over the mean scenario. A positive VSS would mean that modelling price and demand variability changes the investment and pays off. Here VSS is $0, so the stochastic and mean-scenario solutions are identical at 100 MW.

This result is likely degenerate. Capacity sits at its upper bound, and PH converged in one iteration with zero residual. Every scenario probably wants at least 100 MW, so the bound binds and uncertainty has no effect. Raising the cap or checking scenario spread would test whether the VSS is really zero.

**4. PH vs. extensive form.** Use PH when there are many scenarios (thousands), when memory is limited, when the subproblems are expensive (MIP recourse), or when you have parallel hardware. Solve the extensive form directly for a modest number of scenarios, like these 30 with an LP. It gives an exact optimum with no tuning of ρ.