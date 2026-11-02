=== Bayesian Optimization (r113) | solver=ON ===

## Bayesian Optimization Report — Web Page Conversion Rate Optimizer

**Budget:** 25 experiment slots  
**Best conversion rate (Bayesian):** 35.00%  
**Best conversion rate (random):** 35.00%  
**True optimum:** 35.00%  
**Improvement over random:** +0.0%  
**Trials to find best:** 14 / 25

### Best Parameters Found

| Parameter | Value |
|---|---|
| headline_score | 1.000 |
| layout_score | 1.000 |
| cta_placement | 0.727 |

### Top 5 Trials

| Rank | headline | layout | cta | Conversion Rate |
|---|---|---|---|---|
| 1 | 1.0 | 1.0 | 0.727 | 35.00% |
| 2 | 0.888 | 1.0 | 0.788 | 35.00% |
| 3 | 1.0 | 0.841 | 0.758 | 35.00% |
| 4 | 1.0 | 0.944 | 0.809 | 35.00% |
| 5 | 0.924 | 0.92 | 0.693 | 35.00% |

── Analyst Explanation ─────────────────────────────────────
**Caveat first:** the report doesn't show Bayesian outperforming random. Both reach 35.00% (+0.0%). The best point (1.0, 1.0, 0.727) also differs from the stated optimum (0.75, 0.85, 0.60), yet scores the same 35.00%. All top-5 trials tie, so the response surface looks flat or capped near the top (or the output is rounded or clipped). The run can't separate the two methods.

1. **Why Bayesian might win:** the GP uses past results to concentrate trials near good regions. Here, 14 trials to reach the best suggests it did little better than chance on a plateau.

2. **Expected Improvement:** the GP predicts a mean and uncertainty at each untested point. EI is the expected amount by which a point beats the current best. It favors high predicted values (exploit) and high uncertainty (explore), and the next trial maximizes it.

3. **Interior optima:** there are diminishing returns and trade-offs. Over-personalization feels creepy, a bare layout loses information, and a CTA that is too aggressive hurts trust. Extremes rarely win.

4. **Choosing:** use a GP for few trials (<~50), continuous low-dimensional spaces, and expensive evaluations. Use TPE for many parameters, categorical or conditional spaces, and larger budgets.