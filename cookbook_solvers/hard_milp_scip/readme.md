# Recipe 123 — Hard MILP: Power Grid Unit Commitment (SCIP)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/123_hard_milp_scip` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Solver class:** Hard Mixed-Integer Linear Programming (MILP)  
**Backend:** SCIP via `pyscipopt` (primary); HiGHS (comparison baseline)  
**Dependency:** `pip install pyscipopt` + SCIP binary from https://www.scipopt.org

## What it demonstrates

Not all MILP solvers are equal on hard instances. HiGHS is excellent for LP and
easy MILP. On **hard MILP** — tight ramp constraints, startup costs, minimum up/down
times — SCIP's cutting planes and branch-and-cut heuristics close the optimality gap
significantly faster. Motivated by the Open Energy Transition benchmark across 213 real
energy models, where solver selection drove 5–30% cost differences.

| | solver=ON (SCIP) | solver=OFF (LLM) |
|---|---|---|
| Solution quality | Proven near-optimal (gap < 2%) | Merit-order heuristic — no gap |
| Ramp constraints | Enforced exactly | Checked approximately |
| Startup costs | Minimized optimally | Minimized heuristically |
| Solve time | ~20–60s for 5-gen 24h | Instant (but unverified) |

## The problem: 5-generator 24-hour unit commitment

Schedule 5 generators to meet hourly electricity demand at minimum cost:

| Generator | Min (MW) | Max (MW) | Var cost ($/MWh) | Startup ($) | Min up/dn (h) |
|---|---|---|---|---|---|
| G1 Coal | 50 | 200 | $28 | $1,200 | 4h |
| G2 Gas CC | 30 | 150 | $45 | $600 | 2h |
| G3 Gas CT | 10 | 80 | $72 | $200 | 1h |
| G4 Nuclear | 80 | 120 | $12 | $5,000 | 8h |
| G5 Peaker | 5 | 50 | $95 | $100 | 1h |

**Demand:** ranges from 145 MW (overnight) to 370 MW (evening peak at 6 pm).
**Binary variables:** 120 (on/off per generator per hour) + startup indicators.
**Why it's hard:** Nuclear (G4) must stay on 8h once committed; startup costs create
coupling across periods; ramp limits mean you can't use a generator that wasn't running
an hour ago.

## Sample Results (2026-09-07, claude-sonnet-4-6)

### solver=ON — SCIP branch-and-cut

| Metric | Value |
|---|---|
| Total operating cost | **$150,550** |
| Optimality gap | **0.0%** (proven optimal) |
| Solve time | 1.2s |
| Status | optimal |

**Generator commitment:**

| Generator | Hours ON (of 24) | Role |
|---|---|---|
| G1 Coal | 24 | Baseload — always on (cheapest variable cost) |
| G4 Nuclear | 24 | Baseload — always on (lowest MC $12/MWh, but $5K startup means never cycle) |
| G2 Gas CC | 12 | Mid-merit — covers daytime/evening peak |
| G3 Gas CT | 0 | Not needed — G1+G4+G2 meet all demand |
| G5 Peaker | 0 | Not needed |

**Peak hour snapshot (hour 18, 360 MW demand):** G1=200 MW, G2=50 MW, G4=120 MW — 370 MW total, 10 MW headroom. SCIP optimally avoided starting G3 (saves $200 startup) by holding G2 online.

### solver=OFF — LLM merit-order heuristic

Notable finding: the LLM invented its own generator parameters and demand profile instead of using the actual problem data. It assumed Nuclear at 200–400 MW (vs actual 80–120 MW), fabricated 500–900 MW load blocks (vs actual 145–370 MW), and estimated a cost of **$328,500** — for a completely different problem.

This reveals a key LLM failure mode: **hallucination of problem data** rather than reasoning on the given instance. The LLM did apply correct qualitative logic (cheapest-first, minimum up-time locking, ramp-rate lookahead) but it drifted from the actual inputs without a structured problem representation grounding it.

**Gap vs SCIP:** not directly comparable (different problems), but the LLM's cost estimate was 2.2× higher even on an easier instance — consistent with the qualitative argument that heuristic approaches cannot certify the optimality gap.

## Run

```bash
# solver=ON: SCIP branch-and-cut
graf run ~/.graflang/solvers/hard_milp_scip/hard_milp_scip.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF: LLM merit-order heuristic
graf run ~/.graflang/solvers/hard_milp_scip/hard_milp_scip.graph.yaml \
    --llm claude_cli --param use_solver=false
```

## Install

```bash
pip install pyscipopt
# SCIP binary (free academic): https://www.scipopt.org/index.php#download
# On conda: conda install -c conda-forge scip pyscipopt
```

## Background: why hard MILP needs SCIP

**Cutting planes:** SCIP generates cuts (e.g., Gomory, mixed-integer rounding) that
tighten the LP relaxation without branching, making the remaining tree smaller.

**Primal heuristics:** SCIP runs feasibility heuristics (RINS, diving) that find good
solutions early, improving the upper bound and enabling more pruning.

**Why HiGHS may leave gap:** HiGHS uses a strong simplex LP solver but fewer custom
MIP heuristics. On unit commitment with minimum up/down times — which create
time-coupled constraints that LP relaxations handle poorly — SCIP's specialized
cuts close the gap faster.

**Economic impact:** A 5% optimality gap on a grid with $2B/year fuel cost = $100M/year
in suboptimal dispatch. The Open Energy Transition benchmark found SCIP consistently
outperformed open-source alternatives on real 213-model test sets.

## Key ASSERT

```
ASSERT commitment_feasible(@result_json);
```

Passes when total generation ≥ demand in every hour (within 0.5 MW tolerance).
The ASSERT does not check optimality — that is reported via `gap_pct`.

## Connection to FPGA hardening

Branch-and-cut has a fixed tree-traversal structure:
1. LP relaxation solve at each node (parallelizable across nodes)
2. Cut generation (sparse constraint detection — fixed compute graph)
3. Branching decision (score comparison — simple hardware logic)

FPGA acceleration of LP node solves (step 1) is the most tractable near-term target.
Estimated 10–20× speedup for the LP kernel, translating to 3–8× end-to-end on hard MIP.
