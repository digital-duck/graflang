=== MiniZinc CP — Nurse Scheduling (r126) | solver=ON ===

## CP Schedule Report — Nurse Scheduling

**Backend:** MiniZinc → python_backtracking_fallback  
**Preference score:** 0  
**Night→Morning violations:** 0  
**Coverage shortages:** 0  
**Overwork violations:** 2  

> MiniZinc binary not found — install from https://www.minizinc.org/software.html

### Weekly Schedule

| Nurse | Mon | Tue | Wed | Thu | Fri | Sat | Sun | Days |
|---|---|---|---|---|---|---|---|---|
| N1_senior | M | M | M | M | M | M | M | 7 |
| N2_senior | M | M | M | M | M | M | M | 7 |
| N3 | Off | N | N | A | A | Off | Off | 4 |
| N4 | A | A | A | Off | Off | A | A | 5 |
| N5 | A | Off | Off | N | Off | Off | N | 3 |
| N6 | Off | Off | A | Off | A | A | Off | 3 |
| N7 | N | Off | Off | Off | Off | N | Off | 2 |
| N8 | Off | A | Off | A | N | Off | A | 4 |

── Analyst Explanation ─────────────────────────────────────
**Caveat first:** this isn't an optimized MiniZinc result. The binary was missing, so a backtracking fallback produced the table. Its report also doesn't match the schedule.

- **Overwork:** N1 and N2 work 7 days, which breaks the 5-day cap (the 2 violations).
- **Coverage:** Monday afternoon has only N4, so the "0 shortages" figure is wrong.
- **Night→Morning:** I found no violation, which matches the report's 0. The premise of question 2 doesn't hold for this table.

1. **Propagation vs. LP relaxation:** CP prunes variable domains by inference. If N1 and N2 hit 5 days, their remaining values are removed, and a nurse on Night day D loses Morning on D+1. It stays in discrete, logical space and handles global constraints like `cardinality`. LP relaxes integrality to get a continuous bound and then branches. CP is strong at feasibility, LP at bounds.

2. **Night→Morning:** If a schedule did violate it, that would be a search-complexity or enforcement failure, not a reasoning one. The rule is easy to state, but a heuristic or LLM can't track all the interacting constraints. Here the fallback ignored the 5-day cap, which is that kind of failure.

3. **Model/solver separation:**
   - You can swap solvers (Gecode, Chuffed, OR-Tools, or a commercial one) without rewriting the model when licenses change.
   - You can benchmark several solvers on the same model and avoid vendor lock-in.

4. **Monthly roster, 30+ nurses:** Use `regular` automaton constraints for shift sequences, `global_cardinality` for coverage, and sliding-window sums for weekly caps. Symmetry breaking among interchangeable nurses and decomposition by week help too. CP scales well because these global constraints propagate strongly and handle sequencing rules directly. MILP needs many big-M or linearized constraints that weaken its relaxation.