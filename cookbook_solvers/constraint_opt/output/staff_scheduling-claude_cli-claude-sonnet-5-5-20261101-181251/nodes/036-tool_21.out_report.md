# Staff Scheduling Report

**Problem:** A clinic needs to staff one day with 3 shifts: Morning, Afternoon, and Night. Minimum nurse coverage required: Morning needs at least 2 nurses, Afternoon needs at least 2 nurses, Night needs at least 1 nurse. Five nurses are available (Nurse1 through Nurse5). Each nurse can work at most 1 shift today. Wage per nurse-shift: Morning costs $200, Afternoon costs $180, Night costs $320. Assign nurses to shifts to meet all minimum coverage requirements at minimum total wage cost.

**Solver status:** `Optimal`
**Minimum total wage cost:** $1080.00

**Schedule (assigned shifts):**
  - x_Nurse1_Morning: assigned
  - x_Nurse2_Morning: assigned
  - x_Nurse3_Afternoon: assigned
  - x_Nurse4_Afternoon: assigned
  - x_Nurse5_Night: assigned

## Interpretation

The minimum total wage cost for this plan is $1,080. Nurse1 and Nurse2 work the Morning shift, Nurse3 and Nurse4 work the Afternoon shift, and Nurse5 works the Night shift. Coverage is met exactly in every shift: 2 of 2 in Morning, 2 of 2 in Afternoon, and 1 of 1 at Night. No shift has extra staff, so there is no buffer if someone calls in sick.

Practical suggestion: all five nurses are used and each works one shift, so nobody is left as backup. Arrange an on-call arrangement or cross-train a nurse who can cover Night or Morning, since a single absence would leave a shift below its minimum.

## Solution Verification

**Coverage by shift**
- Morning: Nurse1 + Nurse2 = 2 nurses. Minimum is 2, so 2 ≥ 2 holds.
- Afternoon: Nurse3 + Nurse4 = 2 nurses. Minimum is 2, so 2 ≥ 2 holds.
- Night: Nurse5 = 1 nurse. Minimum is 1, so 1 ≥ 1 holds.

**Shifts per nurse (limit of 1)**
- Nurse1: 1 shift (Morning). Fine.
- Nurse2: 1 shift (Morning). Fine.
- Nurse3: 1 shift (Afternoon). Fine.
- Nurse4: 1 shift (Afternoon). Fine.
- Nurse5: 1 shift (Night). Fine.

Total assignments are 5, matching the five nurses available.

**Wage cost**
- Morning: 2 nurses × $200 = $400
- Afternoon: 2 nurses × $180 = $360
- Night: 1 nurse × $320 = $320
- Total: $400 + $360 + $320 = $1,080

**Match with solver**
The computed cost of $1,080 equals the solver's reported objective of 1080.0, and the status is Optimal.

The result is also sensible: the minimum required headcount is 2 + 2 + 1 = 5, which equals the number of nurses, so every nurse must be assigned and the only freedom is who goes where. Since every nurse costs the same in a given shift, the cost is fixed once the required headcount per shift is filled, and $1,080 is the only possible total.

## Solver Code (LLM-generated, PuLP)

```python
nurses = ["Nurse1", "Nurse2", "Nurse3", "Nurse4", "Nurse5"]
shifts = ["Morning", "Afternoon", "Night"]
wage         = {"Morning": 200, "Afternoon": 180, "Night": 320}
min_coverage = {"Morning": 2, "Afternoon": 2, "Night": 1}
max_per_nurse = 1

prob = pulp.LpProblem("scheduling", pulp.LpMinimize)

x = {n: {s: pulp.LpVariable(f"x_{n}_{s}", cat="Binary")
         for s in shifts}
     for n in nurses}

prob += pulp.lpSum(wage[s] * x[n][s] for n in nurses for s in shifts)

for s in shifts:
    prob += pulp.lpSum(x[n][s] for n in nurses) >= min_coverage[s]

for n in nurses:
    prob += pulp.lpSum(x[n][s] for s in shifts) <= max_per_nurse

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
| Stage 2 — interpretation (s) | 6.80 |
| Total latency (s) | 11.30 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total tokens | 0 |