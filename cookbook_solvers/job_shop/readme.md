# Recipe 98 — Job-Shop Scheduling (OR-Tools CP-SAT)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/098_job_shop` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `ortools` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

Classic job-shop scheduling: N jobs × M machines, each job has a fixed sequence of operations.  
OR-Tools CP-SAT finds the optimal schedule (minimum makespan) in milliseconds.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | OR-Tools CP-SAT (constraint programming) | LLM heuristic reasoning |
| Guarantee | Proven optimal or proven infeasible | Plausible schedule, may violate constraints |
| Verification | `ASSERT` on CP-SAT status | `verify_job_shop` back-substitution |
| Solver class | C5 (Constraint propagation / CP-SAT) | — |

## Default problem (n=3 jobs × 3 machines)

```
Job 1: M1(3) → M2(2) → M3(2)   (three operations in sequence)
Job 2: M2(2) → M1(3) → M3(1)
Job 3: M3(2) → M2(1) → M1(2)
Known optimal makespan: 8
```


You have 3 jobs and 3 machines. Each job must visit all 3 machines in a specific order — and each visit takes a certain amount of time. No machine can work on two jobs at once.

- Job 1: First go to M1 (takes 3), then M2 (takes 2), then M3 (takes 2)
- Job 2: First go to M2 (takes 2), then M1 (takes 3), then M3 (takes 1)
- Job 3: First go to M3 (takes 2), then M2 (takes 1), then M1 (takes 2)

The goal is to schedule all the operations so everything finishes as early as possible. The makespan is when the last operation across all jobs finishes — the known optimal answer here is 8 time units.

The challenge: Job 1 needs M1 first, but Job 2 also needs M1 (second step). They can't overlap, so you have to decide who waits. Get the ordering wrong and you waste time; get it right and you hit makespan 8.

## Run commands

```bash
export PROBLEM="3 jobs, 3 machines. Job1: M1(3)→M2(2)→M3(2). Job2: M2(2)→M1(3)→M3(1). Job3: M3(2)→M2(1)→M1(2). Minimize makespan."

# solver=ON, claude_cli
graf run ~/.graflang/solvers/job_shop/job_shop.graph.yaml \
  --llm claude_cli \
  --param use_solver=true \
  --param problem="$PROBLEM"

# solver=OFF
graf run ~/.graflang/solvers/job_shop/job_shop.graph.yaml \
  --llm claude_cli \
  --param use_solver=false \
  --param problem="$PROBLEM"
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `parse_job_shop_problem(problem)` | Normalise LLM-extracted JSON |
| `solve_job_shop(problem_json)` | OR-Tools CP-SAT → `{status, makespan, schedule}` |
| `verify_job_shop(problem_json, solution_json)` | Back-substitute: check no-overlap + precedence |
| `format_gantt(solution_json)` | ASCII Gantt chart |

## Verification (solver=OFF)

`verify_job_shop` checks:
1. **No-overlap**: no two jobs assigned to the same machine at the same time
2. **Precedence**: each job's operations run in the specified order
3. **Makespan consistency**: claimed makespan matches max end-time in schedule

## Example output (solver=ON, 3×3 default problem)

CP-SAT finds the optimal schedule and `format_gantt` renders it as an ASCII timeline.  
Each cell is one time unit; the letter is the **first character of the job name** (all three jobs start with "J" here).

```
Makespan = 8 time units

Machine  |012345678
-------------------
M1       |JJJJJJJJ.
M2       |JJJJJ....
M3       |JJ...JJJ.
```

Reading the chart against the solution schedule:

| Time | M1 | M2 | M3 |
|------|----|----|-----|
| 0–3  | Job1 (op1, dur=3) | Job2 (op1, dur=2) | Job3 (op1, dur=2) |
| 3–5  | Job2 (op2, dur=3, ends t=6) | Job1 (op2, dur=2) | idle |
| 5–7  | …Job2 cont. | idle | Job1 (op3, dur=2) |
| 6–8  | Job3 (op3, dur=2) | idle | Job2 (op3, dur=1, ends t=8) |

All three machines stay busy until t=8 — no slack left; makespan 8 is proven optimal.

## Scale sensitivity

| n | Difficulty | Comment |
|---|---|---|
| 3×3 | Easy | LLM can enumerate feasible schedules |
| 5×5 | Medium | dispatching heuristics degrade |
| 10×10 | Hard | near-optimal solutions require branch-and-bound |

## Related recipes

- Recipe 78: LP / MILP via PuLP (recipe 78a–d ablation study)
- Recipe 99: Portfolio optimization via cvxpy (convex QP)
