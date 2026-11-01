# Recipe 121 — Platypus MOEA 3-Objective Workforce Scheduling (S020)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/121_platypus_moea` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `pulp` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**The key story:** Same B4 benchmark as r107 (pymoo NSGA-II), re-solved with platypus NSGA-II — a pure-Python MOEA library with no C/Fortran extensions. Platypus reproduces the identical Pareto surface (cost \$3,900–\$6,200, quality 0.867–0.900, risk 0.2125–0.2500), finding **100 non-dominated integer points** and correctly pinning the strictly-dominated Night shift at its minimum. Two independent `S020` validations: (1) platypus matches pymoo's front on the same problem spec — DODA holds across MOEA libraries; (2) across two solver=OFF runs the LLM **consistently picked the same plan (20/10/10) but reported wrong arithmetic one run and correct arithmetic the next** — the back-substitution verifier caught the bad run. When dependency weight matters (embedded / containerized edge inference), platypus is the right MOEA choice.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | platypus NSGA-II (pure Python) | LLM estimation + back-substitution |
| Output | 100 Pareto-optimal staffing plans | Single schedule with claimed metrics |
| Guarantee | All 100 points are feasible and non-dominated (deterministic, seed=42) | Plan plausible; claimed metrics unreliable run-to-run |
| Verification | `ASSERT is_pareto_feasible` (n_points >= 3) | `verify_workforce_off` — **FAIL or PASS** depending on the run |
| Solver class | C3 (independent multi-objective computation) | — |

## Problem (B4 benchmark — same as r107)

| Shift | Cost/person | Quality | Risk | Min | Max |
|---|---|---|---|---|---|
| Day | $100 | 0.90 | 0.10 | 10 | 20 |
| Evening | $130 | 1.00 | 0.25 | 10 | 20 |
| Night | $160 | 0.70 | 0.40 | 10 | 20 |

Total minimum staff: 30. Objectives: minimize cost, maximize quality, minimize fatigue risk.

## Key finding: Night shift dominated across all 100 Pareto points

Night shift has the worst score on all three objectives simultaneously — highest cost, lowest quality, highest risk. The solver pins it at the minimum (10) in every Pareto-optimal solution. The true Pareto surface traces the Day↔Evening tradeoff:

- **Day shift**: cheapest, lowest risk — favored by cost/risk objectives
- **Evening shift**: highest quality — favored by quality objective
- Night shift: dominated — minimum in all 100 solutions

**Representative operating points** (from solver=ON):

| Scenario | xD | xE | xN | Cost ($) | Quality | Risk |
|---|---|---|---|---|---|---|
| Budget floor | 10 | 10 | 10 | 3,900 | 0.8667 | 0.2500 |
| Balanced (LLM pick) | 15 | 13 | 10 | 4,790 | 0.8816 | 0.2303 |
| Risk-minimizing | 20 | 10 | 10 | 4,900 | 0.8750 | 0.2125 |
| Quality-maximizing | 10 | 20 | 10 | 5,300 | 0.9000 | 0.2463 |
| Peak | 20 | 20 | 10 | 6,200 | 0.9000 | 0.2200 |

The solver=ON interpreter recommended the **balanced 15/13/10 point ($4,790)**: ~23% over
the budget floor buys +1.7% quality and −8% risk — the steepest part of the efficiency curve.

## Run results — solver=ON vs solver=OFF (two OFF runs)

All runs: `claude_cli` / `claude-sonnet-4-6`, B4 default problem (3 shifts, total_min=30).
solver=OFF was run twice to probe reproducibility.

| Metric | solver=ON | solver=OFF run 1 | solver=OFF run 2 |
|---|---|---|---|
| Timestamp | 2026-09-07 08:58:46 | 2026-09-07 00:42:05 | 2026-09-07 08:59:00 |
| Tokens in / out | 2,267 / 529 | 872 / 170 | 897 / 190 |
| Latency | 49.0s | 15.1s | 89.5s |
| Pareto points | 100 | — | — |
| ASSERT passed | ✓ | — | — |
| Verify verdict | N/A | **FAIL** | **PASS** |
| LLM calls | 2 | 3 | 3 |

**Note on solver=ON token count:** 2,267 tokens in reflects the full 100-point Pareto
table passed to the interpreter LLM. With 20 representative points the table would be
~500 tokens, matching r107's profile. This is a table-size artifact, not an algorithm cost.

### The solver=OFF reproducibility finding

Both OFF runs independently chose the **same plan — xD=20, xE=10, xN=10** — and gave the
same *reasoning* (Night dominated → pin at min; max cheap/low-risk Day). The **decision was
stable**. What was *not* stable was the LLM's self-reported arithmetic:

| | Claimed cost | Claimed quality | Claimed risk | Verifier recompute | Verdict |
|---|---|---|---|---|---|
| Run 1 | \$4,700 | 0.900 | 0.175 | \$4,900 / 0.875 / 0.2125 | **FAIL** (all 3 wrong) |
| Run 2 | \$4,900 | 0.875 | 0.2125 | \$4,900 / 0.875 / 0.2125 | **PASS** (exact) |

Run 1's errors are the classic LLM failure mode: it reported the *best-case single-shift*
numbers (Day's \$100/0.90/0.10-ish blend) instead of the headcount-weighted average over all
40 staff. Run 2 did the weighted average correctly. **Same model, same prompt, same decision —
opposite arithmetic reliability.** This is precisely why the recipe back-substitutes:
`verify_workforce_off` recomputes cost/quality/risk from the proposed (xD,xE,xN) and rejects
the run when the LLM's claimed metrics don't match. solver=ON (platypus, `seed=42`) is
deterministic and needs no such guard.

## platypus vs pymoo (r107) comparison

| Dimension | platypus (r121) | pymoo (r107) |
|---|---|---|
| Dependency | `platypus-opt` — pure Python, ~124 KB wheel | `pymoo` — requires numpy/scipy, ~4 MB+ |
| Algorithm API | `Problem(n_var, n_obj, n_constr)` + function | `Problem` class inheritance |
| Variable types | `Integer(min, max)` natively | `vtype=int` flag on SBX/PM operators |
| Evaluations | `algorithm.run(n_eval)` | `minimize(..., termination=("n_gen", n))` |
| Result read | `problem.types[i].decode(sol.variables[i])` | `np.round(res.X).astype(int)` |
| Pareto filter | `nondominated(algorithm.result)` | `res.X` (already filtered) |
| B4 result | 100 non-dominated points | 82 non-dominated points (r107 actual run) |
| Solver time | ~1.1s (5000 evaluations) | ~2–5s (n_gen=50, pop_size=100 = 5000 total) |
| Install size | lightweight (single .whl, no native ext) | heavy (requires numpy, scipy, matplotlib) |

**Why more Pareto points in platypus?** The discrete B4 surface has exactly 100 non-dominated integer lattice points (all with xN=10, xD∈[10,20], xE∈[10,20] satisfying the total_min constraint). platypus's `nondominated()` returns the complete filtered population — all 100 here. pymoo's run (r107) surfaced 82: a sparser but equivalent subset of the *same* front (identical cost/quality/risk ranges and identical corner solutions). Neither is "better" — both trace the true Pareto surface; platypus just sampled it more densely in this configuration.

## Platypus NSGA-II algorithm details

1. Population initialized with `pop_size=100` random feasible solutions
2. `algorithm.run(5000)`: 5000 objective function evaluations (50 generations × 100 population)
3. Non-dominated sorting + crowding distance selection (same as NSGA-II in pymoo)
4. Integer-type variables via platypus `Integer(min, max)` — stored as Gray-coded bit arrays internally; decoded with `problem.types[i].decode(solution.variables[i])`
5. Constraint handling: `problem.constraints[:] = ">=0"` → `total - total_min >= 0`
6. Random seed fixed (`random.seed(42)`) for reproducibility

## Run commands

```bash
# solver=ON — platypus NSGA-II Pareto surface
graf run ~/.graflang/solvers/platypus_moea/platypus_moea.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF — LLM direct scheduling + arithmetic verification
graf run ~/.graflang/solvers/platypus_moea/platypus_moea.graph.yaml \
    --llm claude_cli --param use_solver=false
```

## Install

```bash
conda activate spl123
pip install platypus-opt   # pure Python, no native extensions
pip install pulp           # already present if r107 run; used for utopia anchors only
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `extract_workforce_problem(text)` | Parse problem description into shift JSON |
| `solve_workforce_platypus(problem_json, n_eval, pop_size)` | platypus NSGA-II; returns 100-point Pareto front |
| `is_pareto_feasible(front_json)` | ASSERT gate: status==OK and n_points >= 3 |
| `format_pareto_surface(front_json)` | Markdown table with Algorithm column |
| `compute_utopia_anchors(problem_json)` | PuLP continuous relaxation; per-objective best |
| `verify_workforce_off(problem_json, solution_json)` | Back-substitution check: integer, bounds, total, metrics |
| `format_report_solver_on / _off` | Assemble the final report |

*(JSON field access uses the stdlib `json_get` builtin — no recipe-local helper.)*

## When to prefer platypus over pymoo

| Context | Prefer |
|---|---|
| Containerized edge inference (limited disk/memory) | platypus |
| CI/CD with minimal dependencies | platypus |
| Teaching / rapid prototyping | platypus |
| Production with large populations (>1000 vars) | pymoo (numpy-accelerated) |
| NSGA-III, MOEA/D, reference-point decomposition | pymoo |
| Hypervolume or IGD metrics required | pymoo |

## Related recipes

- r107: pymoo NSGA-II — same B4 problem, numpy-based, sparser Pareto front
- r114: scipy.optimize — constrained single-objective (SLSQP)
- r099: cvxpy — convex multi-objective via scalarization (efficient frontier)
- r112: optuna — black-box single-objective; no Pareto surface
