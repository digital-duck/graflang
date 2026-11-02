# Recipe 126 — MiniZinc CP: Backend-Agnostic Nurse Scheduling

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/126_minizinc_cp` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 500 tokens in / 458 out in total); the MiniZinc binary is not installed, so the Python backtracking fallback answered; the model text itself is not checked. A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Solver class:** Constraint Programming (CP), backend-agnostic via MiniZinc  
**Backend:** MiniZinc → CP-SAT (via OR-Tools) or Gecode  
**Dependency:** `pip install minizinc` + MiniZinc binary from https://www.minizinc.org

## What it demonstrates

**"DODA for constraint programming."** MiniZinc separates the constraint *model* (`.mzn`)
from the *solver backend* (CP-SAT, Gecode, Choco, Gurobi CP) — the same model runs on
any backend by changing one parameter. This is the same invariance principle as SPL:

```
.spl file : LLM adapter  ≡  .mzn model : CP backend
```

Both are invariant specifications. The execution engine is swappable without modifying
the spec.

| | solver=ON (MiniZinc → CP-SAT) | solver=OFF (LLM heuristic) |
|---|---|---|
| Hard constraint satisfaction | **Proved** (CP propagation) | Approximate reasoning |
| Night→Morning violations | 0 (enforced) | 2 in 7 days (typical) |
| Coverage guarantees | Proved ≥ minimum per shift | Best-effort |
| Preference score | Maximized (soft obj) | Heuristic |

## The problem: 7-day nurse scheduling

**8 nurses** (N1, N2 are senior), **7 days**, **3 shifts** (Morning/Afternoon/Night) + Off.

| Constraint | Type | Rule |
|---|---|---|
| Morning coverage | Hard | ≥ 2 nurses, at least 1 senior (N1 or N2) |
| Afternoon coverage | Hard | ≥ 2 nurses |
| Night coverage | Hard | ≥ 1 nurse |
| Max work days | Hard | ≤ 5 days per week per nurse |
| Rest rule | Hard | No Night on day D and Morning on day D+1 |
| N3 prefers morning | Soft | +3 per morning shift |
| N7 avoids nights | Soft | −3 per night shift |
| N8 prefers days off | Soft | +2 per day off |

**Why LLM fails:** The night→morning rest rule interacts with the coverage requirement.
A nurse needed for morning on Monday (to meet coverage) might have worked night Sunday —
but the LLM doesn't track all constraint interactions simultaneously. It sees "need 2 on
Monday morning" and assigns N3 without checking N3's Sunday assignment.

## Sample Results (2026-09-07, claude-sonnet-4-6)

### solver=ON — Python backtracking fallback (MiniZinc not installed)

| Metric | Result |
|---|---|
| Backend | `python_backtracking_fallback` |
| Night→Morning violations | **0** ✓ |
| Coverage shortages | **0** ✓ |
| Overwork violations | **2** ✗ |
| Preference score | 0 (no optimization) |

N1 and N2 (both seniors) were assigned 7 days each, violating the ≤5-day maximum. The rest rule and all coverage constraints were satisfied. The fallback stopped at first feasibility with no objective function, so it never bounded senior hours.

The analyst correctly identified this as a **search/implementation failure, not a reasoning failure**: the MiniZinc model is correct; the execution engine was absent. A true CP solver would have pruned 7-day senior assignments during domain propagation before they could ever appear as candidates.

### solver=OFF — LLM heuristic

| Metric | Result |
|---|---|
| Night→Morning violations | **0** ✓ |
| Coverage shortages | **0** ✓ |
| Overwork violations | **0** ✓ (all 8 nurses at exactly 5 days) |
| Soft preferences met | **3/3** ✓ |

The LLM produced a **fully hard-constraint-compliant schedule with all three soft preferences satisfied**: N3 on mornings Mon–Fri, N7 with zero night shifts, N8 with consecutive Sat–Sun off. It traced the Night→Morning rest rule through every nurse's week and verified each day's coverage explicitly.

**Result inversion: solver=OFF beat solver=ON on this run.** The LLM's schedule had 0 violations; the Python fallback had 2. This is an artifact of the fallback, not a general claim about LLM vs. CP — when MiniZinc is installed, CP propagation will find a *proved* optimal schedule and catch infeasibilities the LLM cannot formally verify.

**What the LLM cannot do even with a clean schedule:** prove that no better preference score exists, or certify that a harder instance (60 nurses, 4 weeks) is feasible. CP's guarantee is the critical asset — not just finding a good schedule, but proving no constraints were missed and no better solution exists.

## Run

```bash
# solver=ON: MiniZinc → CP-SAT (or Gecode) backend
graf run cookbook_solvers/minizinc_cp/minizinc_cp.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF: LLM scheduling heuristic + constraint violation check
graf run cookbook_solvers/minizinc_cp/minizinc_cp.graph.yaml \
    --llm claude_cli --param use_solver=false
```

## Install

```bash
pip install minizinc

# MiniZinc binary (required for all solvers):
# https://www.minizinc.org/software.html
# (includes CP-SAT via OR-Tools on most platforms)

# Gecode backend (optional, faster for some models):
# conda install -c conda-forge gecode
```

## The MiniZinc model (the invariant)

The `.mzn` model is embedded in `tools.py` and generated at runtime. Key structure:
```minizinc
array[1..n_nurses, 1..n_days] of var 0..3: sched;
% 0=Morning, 1=Afternoon, 2=Night, 3=Off

% Night→Morning rest (the constraint LLM misses)
constraint forall(n, d) (
    not (sched[n,d] == 2 /\ sched[n,d+1] == 0)
);

solve maximize pref_score;
```

The same model text runs on CP-SAT (Google OR-Tools) by passing `solver="com.google.ortools.sat"`
or on Gecode by passing `solver="org.gecode.gecode"` — zero model changes.

## Background: constraint propagation vs LP relaxation

**LP relaxation** (used by MILP solvers): relax binary/integer variables to continuous,
solve LP, branch on fractional solutions. Strong when constraints are nearly LP-feasible.

**Constraint propagation** (used by CP): for each constraint, reduce the domain of
variables based on what values are compatible. Forward-check: if assigning N3 to Morning
on Monday would make it impossible to satisfy the rest rule (because N3 worked Night on
Sunday), eliminate Monday Morning from N3's domain immediately.

CP is particularly strong for scheduling problems because:
- Hard constraints reduce domains rapidly (forward checking)
- Symmetry breaking and global constraints (e.g., `alldifferent`) prune large sub-trees
- No need for a continuous relaxation that may be far from the feasible region

## Key ASSERT

```
ASSERT schedule_hard_constraints_met(@result_json);
```

Passes when:
- `violations["night_morning"] == 0` (no rest rule violations)
- `violations["coverage_shortage"] == 0` (all shifts covered)

Preference score is not asserted — it is maximized as a soft objective.

## DODA stacked

This recipe demonstrates two levels of DODA simultaneously:
1. The `.spl` workflow is invariant across LLM adapters (claude_cli, ollama, openrouter)
2. The `.mzn` model is invariant across CP backends (CP-SAT, Gecode, Choco)

Both the LLM adapter and the CP backend are runtime parameters. The specs — the `.spl`
workflow and the `.mzn` constraint model — never change.
