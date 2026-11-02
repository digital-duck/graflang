# Recipe 87 — Route Optimization

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/087_route_optimization` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 669 tokens in / 512 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install ortools`

## What this demonstrates

This recipe is a second, harder optimization class beyond recipe 78's linear program: vehicle-routing / TSP-style logistics is **NP-hard combinatorial optimization**, yet still exactly checkable — OR-Tools' constraint-programming routing solver either returns a route with a verifiable total distance or reports no solution. Same deterministic-probabilistic boundary as 78, applied to a fundamentally harder search space (5 stops already means 5! = 120 possible orderings).

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language routing problem | **Probabilistic** | LLM (`formulate_routing_code`) | LLMs read prose; routing solvers don't |
| Generate OR-Tools code | **Probabilistic** | LLM | Build the distance matrix, routing model, and search parameters |
| Run combinatorial search | **Deterministic** | `ortools` (routing / CP-SAT) | Guided local search finds a low-cost route with a verifiable total distance |
| Gate on feasibility | **Deterministic** | `ASSERT is_optimal()` | Formal boundary: only continue if a feasible route was found |
| Repair failed code | **Probabilistic** | LLM (`repair_routing_code`) | LLM sees the actual exception |
| Interpret result | **Probabilistic** | LLM (`interpret_routing_result`) | Plain-English explanation of the verified route |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated total distance matches the solver's ground truth |

**Key property:** the LLM never proposes a route itself in the solver arm — it only writes the OR-Tools model. LLMs routinely propose plausible-looking but non-optimal (or even infeasible, revisiting a stop) routes when asked to plan logistics directly; a combinatorial solver does not have that failure mode.

## Setup

```bash
conda activate spl123
pip install ortools
```

OR-Tools ships prebuilt wheels with the CP-SAT/routing solver bundled — no separate solver installation or license needed (unlike commercial VRP solvers).

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM plans the route itself in prose — greedy nearest-neighbor reasoning by hand, with no combinatorial search. This is exactly where routing problems expose LLMs proposing a locally-plausible but globally suboptimal route.
- **`enable_solver=true`** (ARM A, default): the LLM writes runnable OR-Tools routing code from the distance matrix and problem text; `run_ortools()` executes it; `ASSERT is_optimal(@solution)` gates on the solver finding a feasible route (repair loop up to `max_tries`, fed the real exception); the LLM narrates the verified route and total distance, restating a `Final answer:` line, cross-checked by `classify_roundtrip()`.

## Run

```bash
# Default problem (1 depot + 5 customer locations)
graf run cookbook_solvers/route_optimization/route_optimization.graph.yaml \
    --llm claude_cli

# Unaided baseline arm
graf run cookbook_solvers/route_optimization/route_optimization.graph.yaml \
    --llm claude_cli \
    --param enable_solver=false


# Custom problem
graf run cookbook_solvers/route_optimization/route_optimization.graph.yaml \
    --llm claude_cli \
    --param problem="A driver starts at the depot (0) and must visit 4 stops. Distance matrix: [[0,10,15,20,25],[10,0,35,25,30],[15,35,0,30,20],[20,25,30,0,15],[25,30,20,15,0]]. Find the shortest round trip."


# Final answer: 85
# LLM calls: 2  Latency: 17023ms
# Log:     /home/gongai/.spl/logs/route_optimization-claude_cli-claude-sonnet-4-6-20260816-163024.md

```

## Default problem

> A delivery driver starts and ends at the depot (location 0) and must visit 5 customer locations (1-5). [distance matrix given]. Find the shortest round-trip route visiting every location exactly once.

**Known optimum** (verifiable by summing matrix entries along the route): **0 → 4 → 3 → 5 → 2 → 1 → 0**, total distance = **101 miles**.

Verified end-to-end (2026-07-17) with `--llm claude_cli`: correct OR-Tools routing code (RoutingIndexManager + RoutingModel + PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH) on the first attempt, `ASSERT is_optimal` passed, computed route and distance (101) exactly matching the independently-verified optimum, round-trip check returned `match`.

```bash
graf run cookbook_solvers/route_optimization/route_optimization.graph.yaml \
    --llm claude_cli --param enable_solver=true

# Final answer: 101
# LLM calls: 3  Latency: 23495ms
# Log:     /home/gongai/.spl/logs/route_optimization-claude_cli-claude-sonnet-4-6-20260816-162040.md

```

### Solved by LLM = Claude-Sonnet-4-6


```bash
graf run cookbook_solvers/route_optimization/route_optimization.graph.yaml \
    --llm claude_cli --param enable_solver=false

# Final answer: 101
# LLM calls: 1  Latency: 41733ms
# Log:     /home/gongai/.spl/logs/route_optimization-claude_cli-claude-sonnet-4-6-20260816-162223.md


```


## Execution flow

```
GENERATE formulate_routing_code(@problem)   -- LLM writes OR-Tools routing model
    │
CALL run_ortools(@code)                     -- routing solver searches the combinatorial space
    │
WHILE @tries < @max_tries                   -- repair loop on Error
    │
ASSERT is_optimal(@solution)                -- hard gate: AssertionError if no feasible route
    │
GENERATE interpret_routing_result(...)        -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution)  -- LLM's stated distance vs ground truth
    │
CALL format_report(...)                     -- Markdown report
```

## Exception handling

If OR-Tools cannot find a feasible route within `max_tries`, `ASSERT is_optimal` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning a hand-guessed route.
