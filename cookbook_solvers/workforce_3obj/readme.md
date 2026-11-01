# Recipe 107 — Workforce 3-Objective Scheduling (cost, quality, risk)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/107_workforce_3obj` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs once `pulp` is installed. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**First 3D Pareto surface benchmark in the suite.** Optimizes shift staffing
across three competing objectives simultaneously using pymoo NSGA-II.

---

## What it demonstrates

| Mode | Solver | What happens |
|------|--------|--------------|
| `use_solver=true` | NSGA-II (pymoo) | LLM extracts structure → NSGA-II produces 3D Pareto front → LLM interprets tradeoffs |
| `use_solver=false` | LLM only | LLM proposes (xD, xE, xN) integers → back-substitution verifier checks arithmetic |

Unlike single-objective recipes (r78), this recipe returns a **surface** of non-dominated
solutions rather than one optimal point. The ASSERT gate ensures at least 3 Pareto points
before interpretation proceeds.

---

## Problem (Benchmark B4)

3 shift types, minimum 10 staff per shift, cap 20, total >= 30:

| Shift | Cost/employee | Quality | Fatigue risk | Range |
|-------|---------------|---------|--------------|-------|
| Day (D)     | $100 | 0.90 | 0.10 | [10, 20] |
| Evening (E) | $130 | 1.00 | 0.25 | [10, 20] |
| Night (N)   | $160 | 0.70 | 0.40 | [10, 20] |

**Three objectives (all simultaneously):**

1. Minimize total cost: `100·xD + 130·xE + 160·xN`
2. Maximize blended quality: `(0.90·xD + 1.00·xE + 0.70·xN) / (xD+xE+xN)`
3. Minimize blended risk: `(0.10·xD + 0.25·xE + 0.40·xN) / (xD+xE+xN)`

---

## Utopia anchors (per-objective best)

| Anchor | xD | xE | xN | Cost ($) | Quality | Risk |
|--------|----|----|-----|----------|---------|------|
| Min-cost   | 10 | 10 | 10 | 3,900 | 0.867 | 0.250 |
| Max-quality| 20 | 20 | 20 | 7,800 | 0.867 | 0.250 |
| Min-risk   | 10 | 10 | 10 | 3,900 | 0.867 | 0.250 |

Note: `compute_utopia_anchors` uses a linearized PuLP formulation (minimizes/maximizes the weighted sum, not the ratio) — so min-cost and min-risk both collapse to minimum headcount (10/10/10), and max-quality pushes all variables to their cap (20/20/20). The normalized quality and risk shown by NSGA-II differ: the Pareto front achieves quality up to 0.900 and risk as low as 0.213 at feasible solutions. The anchors are reference bounds, not operating targets.

---

## Run commands

```bash
# solver=ON — NSGA-II produces 3D Pareto surface
graf run ~/.graflang/solvers/workforce_3obj/workforce_3obj.graph.yaml \
    --adapter claude_cli \
    --param use_solver=true

# solver=OFF — LLM proposes a single schedule, verifier checks it
graf run ~/.graflang/solvers/workforce_3obj/workforce_3obj.graph.yaml \
    --adapter claude_cli \
    --param use_solver=false

# Custom NSGA-II settings
graf run ~/.graflang/solvers/workforce_3obj/workforce_3obj.graph.yaml \
    --adapter claude_cli \
    --param use_solver=true \
    --param n_gen=100 --param pop_size=200

# Custom problem
graf run ~/.graflang/solvers/workforce_3obj/workforce_3obj.graph.yaml \
    --adapter claude_cli \
    --param use_solver=true \
    --param problem="A hospital runs Day ($120/nurse, quality 0.95, risk 0.08, min 15 max 25), Evening ($150, quality 1.00, risk 0.20, min 10 max 20), Night ($180, quality 0.75, risk 0.45, min 10 max 20). Total minimum: 40 nurses."
```

---

## Install

```bash
pip install pymoo pulp
```

---

## Example output (2026-09-06, claude-sonnet-4-6)

### solver=ON (NSGA-II, 50 gen, pop=100)

**82 Pareto-optimal points** spanning the full non-dominated surface. Selected rows:

| xD | xE | xN | Cost ($) | Quality | Risk | Label |
|----|----|----|----------|---------|------|-------|
| 10 | 10 | 10 | 3,900 | 0.8667 | 0.2500 | Min cost |
| 16 | 12 | 10 | 4,760 | 0.8789 | 0.2263 | Balanced (LLM recommendation) |
| 20 | 10 | 10 | 4,900 | 0.8750 | 0.2125 | Min risk |
| 11 | 20 | 10 | 5,300 | 0.9000 | 0.2463 | Max quality (min cost path) |
| 20 | 20 | 10 | 6,200 | 0.9000 | 0.2200 | Max quality + min risk |

**Cost range:** \$3,900 – \$6,200 | **Quality:** 0.867 – 0.900 | **Risk:** 0.213 – 0.250

**Structural discovery:** xN=10 (minimum) in **all 82 Pareto-optimal solutions**. Night shift is dominated on every objective simultaneously — highest cost ($160), worst quality (0.70), highest risk (0.40). NSGA-II detected this automatically and pins Night at the legal floor. The real decision space reduces to a 2D front over (xD, xE) with xN fixed.

**LLM interpretation highlights:**
- Night shift is "dominated" on all three objectives — the optimizer correctly discards it beyond its minimum
- Switching (10/10/10) → (16/12/10): +22% cost, −10% risk, +14% of quality range covered — strong efficiency point
- Carbon-equivalent insight: $667/tonne avoided cost (same structure as r101)
- Recommended default: **16 Day / 12 Evening / 10 Night** at \$4,760

### solver=OFF (LLM direct)

```
Schedule: xD=20, xE=10, xN=10
Cost: $4,900 | Quality: 0.875 | Risk: 0.2125
Verification: PASS (arithmetic correct, all constraints satisfied)
Reasoning: "Maximize Day (cheapest, lowest risk), hold Night at floor"
```

The LLM applied greedy reasoning: Day dominates on cost and risk, so fill Day to 20; put Night and Evening at minimum. Arithmetic verified correct.

### Comparison

| | solver=ON | solver=OFF |
|---|---|---|
| Solutions returned | **82-point Pareto surface** | **1 point** |
| LLM's chosen point found? | Yes — row 35 of 82: (20/10/10) | Yes — same point |
| Quality achievable at +\$400 more? | Yes — (20/12/10) → 0.879, risk 0.222 | Unknown — no surface |
| Best quality for ≤\$5,000? | Yes — (11/20/10) → 0.900, \$4,900+\$400 | Unknown |
| Night staff insight | Automatically pinned at 10 (dominated) | Same correct intuition |
| Tokens in / out | 1,557 / 457 | 896 / 192 |
| Latency | 36s | 29s |
| LLM calls | 2 | 3 |

**Why solver matters more at 3 objectives:**

- **r101 (2-objective, 2 products)**: LLM heuristic and solver agreed on the same recommendation — the 2-product LP collapses to 3 corner points, easy for a capable LLM to enumerate
- **r107 (3-objective, integer variables)**: 82 Pareto-optimal integer solutions exist; the LLM can only pick one by implicitly collapsing the 3 objectives into a single priority order. It correctly found the min-risk corner but had no way to answer "what's the quality-cost frontier?" or "how much quality do I buy per \$100 spent on Evening staff?"
- **The manager's real question** — "show me my options" — is unanswerable without the surface. Solver=ON delivers the full trade-off map; solver=OFF delivers one defensible point.

---

## Optimization formulation

**Variables:** xD, xE, xN ∈ ℤ

**Objectives:**
- f1 = 100·xD + 130·xE + 160·xN  (minimize)
- f2 = -(0.90·xD + 1.00·xE + 0.70·xN) / (xD+xE+xN)  (minimize negated quality)
- f3 = (0.10·xD + 0.25·xE + 0.40·xN) / (xD+xE+xN)  (minimize)

**Constraints:** xD+xE+xN >= 30, xD ∈ [10,20], xE ∈ [10,20], xN ∈ [10,20]

**Solver:** NSGA-II with IntegerRandomSampling, SBX crossover, PM mutation, 50 generations, population 100.

---

## TOOL_API reference

| Function | Description |
|----------|-------------|
| `solve_workforce_pareto(problem_json, n_gen, pop_size)` | Run NSGA-II; returns Pareto front JSON |
| `is_pareto_feasible(front_json)` | ASSERT gate: status==OK and n_points >= 3 |
| `format_pareto_surface(front_json)` | Markdown table sorted by cost; min/max footer |
| `compute_utopia_anchors(problem_json)` | Per-objective PuLP anchors for reference |
| `verify_workforce_off(problem_json, solution_json)` | Back-substitution check for solver=OFF |
| `json_get_field(data_json, field)` | Extract field from JSON as string |

---

## Related recipes

- **r78** — constraint optimization (single-objective, PuLP), solver=ON/OFF ablation
- **r99** — portfolio optimization (Markowitz, cvxpy)
- **r100** — supply sourcing (2-objective Pareto, cost vs. fill rate)
- **r101** — production sustainability (multi-objective)
