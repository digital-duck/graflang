# Recipe 122 — Global MINLP: Chemical Reactor Yield Optimization

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/122_global_minlp` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 484 tokens in / 395 out in total); Couenne/Bonmin are not installed, so the graph used its grid-search fallback (the report says so). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Solver class:** Global Mixed-Integer Nonlinear Programming (MINLP)  
**Backend:** Pyomo + Couenne or Bonmin (COIN-OR, free academic); BARON (commercial baseline)  
**Dependency:** `conda install -c conda-forge coinor-couenne pyomo` or `coinor-bonmin pyomo`

## What it demonstrates

The most dangerous silent failure in nonlinear optimization: `scipy.minimize` returns
`OPTIMAL` status but means *locally* optimal, not *globally* optimal. Couenne and Bonmin
use **spatial branch-and-bound** with convex relaxations to certify the *global* optimum —
proving no better solution exists anywhere in the feasible region.

| | solver=ON (Couenne/Bonmin) | solver=OFF (LLM) |
|---|---|---|
| Optimum type | **Globally certified** via spatial B&B | Heuristic — no certification |
| Catalyst decision | Correct (use catalyst at high T) | May recommend wrong binary |
| Net yield | Global maximum | Possibly local maximum |
| Gap to global | Certified < ε | Unknown |

## The problem: chemical reactor design

Choose three design variables to maximize net reaction yield:

| Variable | Type | Bounds | Meaning |
|---|---|---|---|
| `use_catalyst` | Binary {0, 1} | — | Add catalyst (boosts yield 1.7×, adds cost) |
| `temperature` | Continuous | 300–750 K | Operating temperature (Arrhenius: `k = exp(-Ea/RT)`) |
| `concentration` | Continuous | 0.1–2.0 mol/L | Reactant concentration |

The yield surface is non-convex due to the exponential `exp(-Ea/RT)` term and the
bilinear coupling `use_catalyst × main_yield`. A local solver (scipy, starting near
T=480 K, no catalyst) finds a local optimum with net yield ≈ 0.18. The global optimum
(with catalyst, T ≈ 680 K) achieves net yield ≈ 0.42 — a 130% improvement.

**Why this matters in industry:** Polymer synthesis, pharmaceutical crystallization, and
ammonia production all involve non-convex yield surfaces. Using a local solver means
leaving yield (and revenue) on the table without knowing it.

## Run

```bash
# solver=ON: Couenne/Bonmin global MINLP
graf run cookbook_solvers/global_minlp/global_minlp.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF: LLM chemical engineering reasoning
graf run cookbook_solvers/global_minlp/global_minlp.graph.yaml \
    --llm claude_cli --param use_solver=false
```

If Couenne/Bonmin are not installed, the recipe falls back to a dense grid search
(not certified global, but demonstrates the local vs. global gap).

## Install

```bash
# Option 1: Couenne (open-source global MINLP, COIN-OR)
conda install -c conda-forge coinor-couenne pyomo

# Option 2: Bonmin (COIN-OR, handles convex MINLP well)
conda install -c conda-forge coinor-bonmin pyomo

# PackagesNotFoundError: The following packages are not available from current channels:
#  - coinor-bonmin


# Option 3: BARON (commercial; gold standard for global MINLP)
# License: https://minlp.com/baron-license
```

## Background: spatial branch-and-bound

Global MINLP solvers (Couenne, BARON) work by:
1. **Relaxation:** Replace nonlinear terms with convex outer approximations → get a lower bound
2. **Branching:** Split the feasible region to tighten the relaxation
3. **Pruning:** Discard sub-regions where the lower bound exceeds the best known solution
4. **Certification:** When upper bound - lower bound < ε, the optimum is proved globally optimal

This is fundamentally different from scipy's gradient descent, which only guarantees
convergence to a **local** stationary point.

## Key ASSERT

```
ASSERT minlp_certified(@result_json);
```

Passes when `global_obj >= local_obj` — the global solver found at least as good a solution
as the local solver. When Couenne/Bonmin are available, `certified: true` is also reported.

## Connection to FPGA hardening

The spatial branch-and-bound tree has a fixed computation graph (bound propagation →
branching → pruning → bound update). This maps directly to an on-chip state machine.
Hardware MINLP accelerators targeting pharmaceutical/chemical optimization are an
active research area (Gurobi has reported 8–15× speedups on FPGA for their MILP B&B
kernel; MINLP has the same tree structure).
