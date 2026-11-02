# Resource Allocation Report

**Problem:** An IT department must select a portfolio of projects for next quarter. Six candidate projects are available. Project P1 costs $120K and requires 3 developer-months, delivering strategic value 8. Project P2 costs $80K and requires 2 developer-months, delivering value 5. Project P3 costs $200K and requires 5 developer-months, delivering value 10. Project P4 costs $150K and requires 3 developer-months, delivering value 9. Project P5 costs $60K and requires 2 developer-months, delivering value 4. Project P6 costs $90K and requires 2 developer-months, delivering value 6. The total budget is $500K and the team has 10 developer-months available. Each project is either fully funded or not funded — no partial investment. Select which projects to fund to maximize total strategic value.

**Solver status:** `Optimal`
**Maximum portfolio value:** 28

**Selected projects:**
  ✓ y_P1
  ✓ y_P2
  ✓ y_P4
  ✓ y_P6

**Rejected projects:**
  ✗ y_P3
  ✗ y_P5

## Interpretation

**Selected:** P1, P2, P4 and P6, for a total strategic value of 28.

**Resources:** The portfolio costs $440K of the $500K budget, leaving $60K unspent. It uses all 10 of the 10 available developer-months, so there is no headcount slack.

**Left out:** P3 (value 10, the single largest) and P5 (value 4).
- P3 is excluded because of headcount. It needs 5 developer-months, half the team's capacity, and displaces more value than it adds.
- P5 fits the leftover budget exactly, but there is no headcount left for it.

**Strategic observation:** Developer capacity, not money, is the constraint. Extra budget alone would change nothing. Two more developer-months would let the team add P5 (value 4) for $60K, using the unspent budget exactly and lifting value to 32. Hiring or contracting capacity is therefore the better lever than a budget increase.

## Solution Verification

**Cost:** 120 + 80 + 150 + 90 = $440K, which is within the $500K budget.

**Developer-months:** 3 + 2 + 3 + 2 = 10, which equals the 10 available, so the limit is met exactly.

**Value:** 8 + 5 + 9 + 6 = 28.

**Rejected alternatives:**
- Swap P2 for P5: cost is $420K and developer-months are 10, so it is feasible, but value is 8 + 4 + 9 + 6 = 27, which is lower.
- Include P3 with P1 and P4: cost is $470K, but developer-months are 3 + 5 + 3 = 11, which breaks the limit.
- Include P3 with P4 and P6: this is feasible (cost $440K, 10 developer-months), but value is 10 + 9 + 6 = 25, which is lower.

**Match with solver:** The computed value of 28 equals the solver's reported optimum of 28, so the result is confirmed.

## Solver Code (LLM-generated, PuLP)

```python
projects = ["P1", "P2", "P3", "P4", "P5", "P6"]
cost     = {"P1": 120, "P2": 80, "P3": 200, "P4": 150, "P5": 60, "P6": 90}
devmos   = {"P1": 3, "P2": 2, "P3": 5, "P4": 3, "P5": 2, "P6": 2}
value    = {"P1": 8, "P2": 5, "P3": 10, "P4": 9, "P5": 4, "P6": 6}
budget   = 500
capacity = 10

prob = pulp.LpProblem("portfolio", pulp.LpMaximize)
y = {p: pulp.LpVariable(f"y_{p}", cat="Binary") for p in projects}
prob += pulp.lpSum(value[p] * y[p] for p in projects)
prob += (pulp.lpSum(cost[p] * y[p] for p in projects) <= budget)
prob += (pulp.lpSum(devmos[p] * y[p] for p in projects) <= capacity)
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
| Stage 1 — formulation + solve (s) | 4.50 |
| Stage 2 — interpretation (s) | 10.30 |
| Total latency (s) | 14.90 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total tokens | 0 |