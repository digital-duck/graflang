# Constraint Optimization Report

**Problem:** A bakery produces artisan bread and croissants. Each loaf of bread requires 3 hours of labor and 2 kg of flour, earning $12 profit. Each batch of croissants requires 1 hour of labor and 3 kg of flour, earning $8 profit. The bakery has 12 hours of labor and 15 kg of flour available each day. Both products must have non-negative quantities. Maximize daily profit.

**Solver status:** `Optimal`
**Optimal objective value:** 60

**Decision variables:**
  - bread = 3
  - croissants = 3

## Interpretation

Bake **3 loaves of bread** and **3 batches of croissants** each day. This earns the maximum daily profit of **$60**. Both constraints are binding: all 12 labor hours and all 15 kg of flour are used, so neither resource has any spare capacity. Since both are fully used, extra labor or flour would let you earn more, but only if you add both together. The recommendation is to keep this 3-and-3 production plan, and if you want to grow profit, look at adding labor and flour capacity together.

## Solution Verification

**Labor constraint:** 3·(bread) + 1·(croissants) ≤ 12
- 3 × 3 + 1 × 3 = 9 + 3 = 12 hours
- 12 ≤ 12 is satisfied and **binding** (no slack).

**Flour constraint:** 2·(bread) + 3·(croissants) ≤ 15
- 2 × 3 + 3 × 3 = 6 + 9 = 15 kg
- 15 ≤ 15 is satisfied and **binding** (no slack).

**Non-negativity:**
- bread = 3 ≥ 0 and croissants = 3 ≥ 0, so both are satisfied. They are slack, since both are strictly positive.

**Objective:**
- 3 × $12 + 3 × $8 = $36 + $24 = **$60**

The computed profit of $60 matches the solver's reported objective of 60.0.

**Optimality check:** Two constraints are binding in two variables, so this point is a corner of the feasible region. The other corners give less profit:
- Bread only: limited by flour at 7.5 loaves, but labor allows only 4, so 4 loaves give $48.
- Croissants only: limited by flour at 5 batches, giving $40.
- Origin: $0.

The corner at (3, 3) gives $60, the highest, which confirms the solver's result.

## Solver Code (LLM-generated, PuLP)

```python
prob = pulp.LpProblem("bakery_profit", pulp.LpMaximize)

bread = pulp.LpVariable("bread", lowBound=0)
croissants = pulp.LpVariable("croissants", lowBound=0)

prob += 12 * bread + 8 * croissants, "daily_profit"

prob += 3 * bread + 1 * croissants <= 12, "labor_hours"
prob += 2 * bread + 3 * croissants <= 15, "flour_kg"

prob.solve(pulp.PULP_CBC_CMD(msg=0))

_result = {
    "status": pulp.LpStatus[prob.status],
    "objective": pulp.value(prob.objective),
    "variables": {v.name: pulp.value(v) for v in prob.variables()}
}
```

## Run Metrics

| Metric | Value |
|---|---|
| Mode | solver=ON  (PuLP/CBC + ASSERT gate) |
| LLM calls | 2 |
| Stage 1 — formulation + solve (s) | 3.10 |
| Stage 2 — interpretation (s) | 5.70 |
| Total latency (s) | 8.90 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total tokens | 0 |