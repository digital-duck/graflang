=== Synthetic Problem Generator (r109) ===

Domain      : LP
n_size      : 5 decision variables per problem
Requested   : 5 variants
Generated   : 5 valid variants
Solved      : 5/5 optimally
Repair loops: 0
Saved to    : /home/gongai/projects/digital-duck/graflang/cookbook-solver/109_synthetic_problems/output/lp_2026-11-01_18-11-01.json

── Test Suite ──────────────────────────────────────────────
**5/5 variants solved optimally**

| ID | Domain | Status | Optimal | Problem (excerpt) |
|---|---|---|---|---|
| v001 | lp | OPTIMAL | 550.0 | A workshop makes five products P1 to P5 per day. Profit per unit is $10 for P1, … |
| v002 | lp | OPTIMAL | 200.0 | A factory produces five products A to E per day. Profit per unit is $12 for A, $… |
| v003 | lp | OPTIMAL | 352.0 | A bakery makes five goods per day: bread, rolls, cakes, pies and cookies, with p… |
| v004 | lp | OPTIMAL | 705.0 | A plant produces five chemicals C1 to C5 per day with profits per tonne of $20, … |
| v005 | lp | OPTIMAL | 720.0 | A small manufacturer builds five gadgets G1 to G5 per week with profits per unit… |

── Difficulty Analysis ─────────────────────────────────────
**Analysis (n_size=5, 5 LP variants)**

1. **Solve rate:** 5/5 (100%) optimal. No failures, so there is no evidence of infeasible formulations, unboundedness, or solver errors. The generator and solver pipeline are sound at this size, but a clean sweep gives no failure-mode signal.

2. **Difficulty:** n=5 is too easy to discriminate. Five variables, a handful of constraints, and clean integer-like optima (550, 200, 352, 705, 720) are well within what a modern LLM can formulate and even solve by reasoning. For solver=OFF I'd predict high correctness here, roughly 80-100%, with errors mostly arithmetic slips rather than structural misformulation. The ablation signal should appear at n10/n20, where manual solving breaks down and constraint-mapping errors compound.

3. **Best stress test:** v003 (bakery). It uses named goods (bread, rolls, cakes, pies, cookies) instead of indexed P1..P5 or A..E, so the model must build its own variable mapping from prose. The non-integer optimum (352) also suggests less trivial constraint interactions than the round-number cases. Caveat: I only see excerpts, so this choice rests on the naming style and the objective value, not on the full constraint text. Check the full problem statements before committing to it.

4. **Next n_size:** Scale up, to n10 then n20, which is where the r78 ablation expects separation. Optionally, add a small side batch at n=5 with tighter or more coupled constraints (shared resources, ratio or minimum-demand constraints) to see whether difficulty can come from structure rather than size.